# -*- coding: utf-8 -*-
"""
Tencent is pleased to support the open source community by making 蓝鲸智云PaaS平台社区版 (BlueKing PaaS Community
Edition) available.
Copyright (C) 2017 THL A29 Limited, a Tencent company. All rights reserved.
Licensed under the MIT License (the "License"); you may not use this file except in compliance with the License.
You may obtain a copy of the License at
http://opensource.org/licenses/MIT
Unless required by applicable law or agreed to in writing, software distributed under the License is distributed on
an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the License for the
specific language governing permissions and limitations under the License.
"""

# 可插拔的 Mako 渲染后端（render backend）。
#
# 背景：整条渲染链里真正“执行用户表达式”的只有一处——``MakoTemplate(template)`` 编译 +
# ``harden_template_builtins`` + ``render_unicode(**data)``。这一小段是全部 RCE 注入面。
# 本模块把这一段从「进程内直接调用」抽象成一个可替换的 backend，为后续「无网无凭证的
# 隔离渲染器（子进程池 / WASM）」留出唯一切点，而**默认行为保持进程内渲染、语义零变化**。
#
# 设计要点：
#   * ``render(template, context, sandbox_builder)``：backend 内部负责用 ``sandbox_builder()``
#     构造沙箱命名空间并与 ``context`` 合并。之所以传入 ``sandbox_builder`` 而不是已合并好的
#     ``data``，是为了让隔离 backend 能在**子进程本地重建沙箱**（``datetime/re/json`` 等模块
#     不可跨进程序列化），只需序列化 ``context``。
#   * 编译失败 / 渲染失败一律 inert：返回原始 ``template`` 字符串并留日志，与历史行为一致，
#     绝不因渲染异常打断整条流程。

import atexit
import inspect
import logging
import multiprocessing
import os
import pickle
import queue
import sys
import threading

from mako.template import Template as MakoTemplate
from mako.exceptions import MakoException

from bamboo_engine.config import Settings
from bamboo_engine.template.sandbox import harden_template_builtins

logger = logging.getLogger("root")


def _render_with_sandbox(template, context, sandbox_dict):
    """唯一的“执行用户表达式”实现：沙箱 dict + context 合并 → 编译 → harden → render_unicode。

    进程内后端与隔离 worker **共用同一实现**，保证两条路径语义严格一致：编译失败 / 渲染失败一律
    inert（返回原始 ``template`` 字符串并留日志），绝不抛出、绝不打断流程。
    """
    data = {}
    data.update(sandbox_dict)
    data.update(context)
    try:
        tm = MakoTemplate(template)
    except (MakoException, SyntaxError) as e:
        logger.error("pipeline resolve template[{}] error[{}]".format(template, e))
        return template
    harden_template_builtins(tm)
    try:
        resolved = tm.render_unicode(**data)
    except Exception as e:
        logger.warning("constant content({}) is invalid, data({}), error: {}".format(template, data, e))
        return template
    else:
        return resolved


class RenderBackend(object):
    """渲染后端接口。实现方需保证：编译/渲染失败时返回原始 template（inert），不得抛出。"""

    def render(self, template, context, sandbox_builder):
        raise NotImplementedError


class InProcessRenderBackend(RenderBackend):
    """默认后端：在当前进程内编译并渲染，行为与历史 ``_render_template`` 完全一致。"""

    def render(self, template, context, sandbox_builder):
        return _render_with_sandbox(template, context, sandbox_builder())


class SandboxSpec(object):
    """可序列化的渲染沙箱配置，供隔离 backend 在子进程本地重建沙箱。

    只携带字符串型配置（flavor + shield_words + import_modules），因此可安全跨进程 pickle；真正
    带副作用、不可序列化的模块对象由 :meth:`build` 在目标进程本地重建。

    * ``engine`` flavor → ``bamboo_engine.template.sandbox.build_sandbox``（无 mock builtins）
    * ``legacy`` flavor → ``pipeline.core.data.sandbox_builder.build_sandbox``（含 mock builtins，
      且 Django-free，可在精简 worker 里 import）
    """

    __slots__ = ("flavor", "shield_words", "import_modules")

    def __init__(self, flavor, shield_words, import_modules):
        self.flavor = flavor
        self.shield_words = list(shield_words or [])
        self.import_modules = dict(import_modules or {})

    def build(self):
        if self.flavor == "engine":
            from bamboo_engine.template.sandbox import build_sandbox

            return build_sandbox(self.shield_words, self.import_modules)
        if self.flavor == "legacy":
            # 延迟 import：仅隔离 worker / legacy 渲染路径需要；且该模块 Django-free。
            from pipeline.core.data.sandbox_builder import build_sandbox

            return build_sandbox(self.shield_words, self.import_modules)
        raise ValueError("unknown sandbox flavor: {}".format(self.flavor))

    def __getstate__(self):
        return {"flavor": self.flavor, "shield_words": self.shield_words, "import_modules": self.import_modules}

    def __setstate__(self, state):
        self.flavor = state["flavor"]
        self.shield_words = state["shield_words"]
        self.import_modules = state["import_modules"]


class SandboxProvider(object):
    """把「进程内构造沙箱」与「可序列化沙箱 spec」打包在一起交给 render backend。

    * ``__call__`` / :meth:`build`：进程内构造命名空间（可读可变全局，保持历史语义）——供
      ``InProcessRenderBackend`` 使用，且与「直接传一个 builder 可调用」向后兼容。
    * :meth:`spec`：返回 :class:`SandboxSpec`——供隔离 backend 序列化后在 worker 本地重建。
    """

    __slots__ = ("_build_fn", "_spec")

    def __init__(self, build_fn, spec):
        self._build_fn = build_fn
        self._spec = spec

    def __call__(self):
        return self._build_fn()

    def build(self):
        return self._build_fn()

    def spec(self):
        return self._spec


# --------------------------------------------------------------------------------------------------
# 隔离渲染后端：无网无凭证的 spawn worker 进程池
#
# 设计依据：docs/specs/2026-09-04-mako-render-isolation-design.md。核心不变量——
#   * 渲染面（唯一执行用户表达式处）搬进独立子进程；子进程 **无凭证**（启动即清洗 env）、
#     后续可叠加 **无网络**（OS 加固钩子，Linux 生效）。即便渲染被 RCE 打穿，也拿不到全局
#     密钥、连不出网络，无法把标准运维当跳板打生态。
#   * worker 用 ``spawn`` 全新解释器，不 import Django / 业务 app / 凭证；沙箱由父进程序列化过来的
#     ``SandboxSpec`` 在 worker 本地重建（engine / legacy 两种 flavor 都已 Django-free）。
#   * warm 池复用（避免每次渲染新开进程），``max_uses`` 用后回收，每次渲染都以全新沙箱重建
#     （pristine），杜绝跨执行状态泄漏。
#   * 失败兜底 fail-safe：不可序列化 context / worker 异常 → 回退进程内渲染；渲染超时 → inert
#     回显原始模板（**不**回退进程内，避免把 DoS 带回主进程）。
# --------------------------------------------------------------------------------------------------

# --------------------------------------------------------------------------------------------------
# 可移植 context 归一化
#
# 无 Django 的最小 worker 只能 unpickle「builtin/stdlib 类型 + 本模块自带的类」。而 bk-sops 的 rich 内置
# 变量（DataTableValue / SetGroupInfo / SetInfo / SetModuleInfo / SetDetailData）返回的对象虽只含 plain
# data、父进程可 pickle，但其**类定义模块 import 即依赖 Django**，worker 侧 unpickle 会失败。
#
# 这些 rich 对象都是「属性包」：__init__ 里 eager ``setattr`` 把数据落进 ``__dict__``，只实现 ``__repr__``，
# 模板用法就是属性访问 + 列表下标 + bare ``${var}``（取字符串）。因此在 pickle 前把它们忠实搬运成
# Django-free 的 :class:`PortableRenderObject`（属性 + str/repr），即可让含 rich 变量的模板也进隔离渲染，
# 而不是被迫回退进程内。只在隔离 backend 的发送路径做，进程内渲染仍见原对象、行为零变化。
# --------------------------------------------------------------------------------------------------

_PORTABLE_SCALAR_TYPES = (str, bytes, bytearray, bool, int, float, complex, type(None))
_PORTABLE_MAX_DEPTH = 8


class PortableRenderObject(object):
    """Django-free 的属性包载体：镜像原 rich 对象的实例属性与字符串形态，供无 Django worker 本地重建。

    * 保留 ``obj.__dict__`` 的属性 → 模板 ``${var.attr}`` / ``${var.attr[i]}`` 照常可用；
    * ``__str__`` / ``__repr__`` 返回归一化时捕获的 ``str(obj)`` / ``repr(obj)`` → bare ``${var}`` 一致。

    ``_portable_*`` 放 slots、不进 ``__dict__``：既不污染模板可见属性，也避免与原对象同名属性冲突。
    自身定义在 bamboo_engine（worker 必可 import），故跨进程 unpickle 稳定成功。
    """

    __slots__ = ("__dict__", "_portable_str", "_portable_repr")

    def __init__(self, attrs, str_value, repr_value):
        self.__dict__.update(attrs)
        self._portable_str = str_value
        self._portable_repr = repr_value

    def __str__(self):
        return self._portable_str

    def __repr__(self):
        return self._portable_repr


def _safe_text(value, fn):
    try:
        return fn(value)
    except Exception:  # pragma: no cover - repr/str 抛错兜底
        return "<unrepresentable>"


def _portable_value(value, depth, seen):
    # 标量：原样保留。
    if isinstance(value, _PORTABLE_SCALAR_TYPES):
        return value
    # 可调用 / 类型 / 模块：pickle 按引用处理（stdlib/可 import 者 worker 侧可重建）；不能归一化，
    # 否则会把函数变成不可调用的载体，破坏 ``${f()}``。
    if callable(value) or isinstance(value, type) or inspect.ismodule(value):
        return value
    if depth >= _PORTABLE_MAX_DEPTH:
        return value
    # 容器：递归归一化元素。
    if isinstance(value, dict):
        return {k: _portable_value(v, depth + 1, seen) for k, v in value.items()}
    if isinstance(value, list):
        return [_portable_value(v, depth + 1, seen) for v in value]
    if isinstance(value, tuple):
        return tuple(_portable_value(v, depth + 1, seen) for v in value)
    if isinstance(value, (set, frozenset)):
        return type(value)(_portable_value(v, depth + 1, seen) for v in value)
    # 属性包对象（有 ``__dict__``）：转成 PortableRenderObject；防环。
    obj_dict = getattr(value, "__dict__", None)
    if isinstance(obj_dict, dict):
        vid = id(value)
        if vid in seen:  # 环：只保留字符串形态、断链。
            return PortableRenderObject({}, _safe_text(value, str), _safe_text(value, repr))
        seen = seen | {vid}
        attrs = {k: _portable_value(v, depth + 1, seen) for k, v in obj_dict.items()}
        return PortableRenderObject(attrs, _safe_text(value, str), _safe_text(value, repr))
    # 其它（无 ``__dict__``、非标量/容器/可调用，如 datetime/Decimal/lock）：原样保留，交给
    # pickle / worker 决定——stdlib 可移植者正常重建，真不可序列化者由发送路径统一兜底。
    return value


def _portable_context(context):
    """把渲染 context 归一化为「仅含 builtin/stdlib 类型 + PortableRenderObject」的可移植结构。

    仅供隔离 backend 在 pickle 前调用；进程内渲染不经过它、行为完全不变。
    """
    seen = frozenset()
    return {k: _portable_value(v, 0, seen) for k, v in context.items()}


_STATUS_OK = 0
_STATUS_ERR = 1

# worker 启动即从 ``os.environ`` 摘除的凭证类 env（大小写不敏感子串匹配）。渲染是纯计算，几乎不
# 需要任何 env，over-scrub 是安全的；这里覆盖蓝鲸生态常见密钥/连接串命名。可经
# ``Settings.MAKO_RENDER_ENV_SCRUB_EXTRA`` 追加。
DEFAULT_ENV_SCRUB_PATTERNS = (
    "SECRET",
    "PASSWORD",
    "PASSWD",
    "TOKEN",
    "CREDENTIAL",
    "PRIVATE_KEY",
    "APP_SECRET",
    "APP_TOKEN",
    "ACCESS_KEY",
    "SECRET_KEY",
    "DSN",
    "DATABASE_URL",
    "MYSQL",
    "REDIS",
    "MONGO",
    "BROKER",
    "RABBITMQ",
    "AMQP",
    "BKREPO",
    "BK_APP_SECRET",
)

# OS 级加固的默认参数（可经 backend 构造参数 / Settings 覆盖）。
DEFAULT_OS_HARDEN_RLIMIT_CPU = 30  # 秒；CPU 时间硬上限，作为 wall-clock timeout 的兜底，杀死 ${9**9**9} 这类狂算
DEFAULT_OS_HARDEN_RLIMIT_AS_MB = 1024  # MB；地址空间上限，抑制渲染面内存炸弹

# 测试注入用的 OS 加固覆盖钩子。默认 None；置为可调用对象时，:func:`_apply_os_hardening` 优先执行它。
# 注意：``spawn`` worker 会以全新解释器重新 import 本模块，故该覆盖只在**同进程**内生效（单测用），
# 真实 worker 的加固由 :func:`_apply_os_hardening` 依据传入的 ``opts`` 在子进程本地施加。
_OS_HARDENING_HOOK = None


def _try_unshare_network():
    """尽力把 worker 放进独立的空网络 namespace（Linux）。

    需要 CAP_SYS_ADMIN / user namespace，普通部署常无权限而失败（EPERM）——此时仅 debug 记录并继续：
    **凭证已被 env-scrub 清除**，即便有网也无法冒充平台身份，这是纵深防御而非唯一屏障。
    """
    try:
        import ctypes

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        clone_newnet = 0x40000000  # CLONE_NEWNET
        if libc.unshare(clone_newnet) != 0:
            err = ctypes.get_errno()
            logger.debug(
                "mako render worker unshare(CLONE_NEWNET) failed errno=%s (need userns/root); env already scrubbed",
                err,
            )
    except Exception as e:  # pragma: no cover - 平台/权限差异
        logger.debug("mako render worker network unshare unavailable: %s", e)


def _scrub_environ(patterns):
    """从当前进程 ``os.environ`` 摘除命中 ``patterns`` 的键（子串、大小写不敏感）。"""
    if not patterns:
        return
    lowered = [p.lower() for p in patterns]
    for key in list(os.environ.keys()):
        low = key.lower()
        if any(p in low for p in lowered):
            os.environ.pop(key, None)


def _apply_os_hardening(opts):
    """在 worker 本地施加 OS 级加固（rlimits + 尽力无网）。Linux 生效，其它平台 no-op。

    ``opts`` 为可跨进程序列化的 dict：``{"enabled", "no_network", "rlimit_cpu", "rlimit_as_mb"}``。
    任何异常都不得打断渲染——加固失败时以 fail-open 记录日志继续（env-scrub 仍已生效）。
    单测可通过设置模块级 ``_OS_HARDENING_HOOK`` 覆盖真实逻辑。
    """
    # 测试覆盖优先（仅同进程生效）。
    if _OS_HARDENING_HOOK is not None:
        try:
            _OS_HARDENING_HOOK()
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("mako render worker os-hardening hook failed: %s", e)
        return
    if not opts or not opts.get("enabled"):
        return
    if not sys.platform.startswith("linux"):
        return  # macOS / 其它平台：加固不可用，no-op（隔离仍靠 spawn + env-scrub）

    try:
        import resource

        def _set_rlimit(res, soft):
            try:
                cur_soft, hard = resource.getrlimit(res)
                new_soft = soft if hard == resource.RLIM_INFINITY else min(soft, hard)
                resource.setrlimit(res, (new_soft, hard))
            except Exception as e:  # pragma: no cover - 平台差异
                logger.debug("mako render worker setrlimit(%s) failed: %s", res, e)

        # 禁 core dump：避免带凭证/context 的内存随 core 落盘。
        _set_rlimit(resource.RLIMIT_CORE, 0)
        cpu = opts.get("rlimit_cpu")
        if cpu:
            _set_rlimit(resource.RLIMIT_CPU, int(cpu))
        as_mb = opts.get("rlimit_as_mb")
        if as_mb:
            _set_rlimit(resource.RLIMIT_AS, int(as_mb) * 1024 * 1024)
    except Exception as e:  # pragma: no cover - defensive, never break rendering
        logger.warning("mako render worker rlimit hardening failed: %s", e)

    if opts.get("no_network"):
        _try_unshare_network()


def _worker_main(conn, scrub_patterns, harden_opts):
    """隔离 worker 主循环（``spawn`` 目标，模块级函数）。

    启动即清洗凭证 env + 应用 OS 加固；随后循环处理请求：每条请求本地重建沙箱（pristine）后渲染，
    回送 ``(status, result)``。收到 ``None`` 或管道 EOF 时退出。
    """
    _scrub_environ(scrub_patterns)
    _apply_os_hardening(harden_opts)
    while True:
        try:
            payload = conn.recv_bytes()
        except EOFError:
            break
        try:
            request = pickle.loads(payload)
        except Exception as e:
            # worker 侧反序列化失败：父进程 pickle 成功、但 worker 无法 loads——典型如 rich 内置变量
            # （DataTableValue / SetGroupInfo 等）的类定义模块在无 Django worker 里 import 失败。
            # 必须**立即回 STATUS_ERR** 让父进程走统一兜底（回退进程内 / strict），否则父进程只能等满
            # timeout 再 inert，既慢又破坏正常渲染。回复不依赖请求内容，可无条件发送。
            try:
                conn.send_bytes(pickle.dumps((_STATUS_ERR, "unpickle request failed: {!r}".format(e))))
            except Exception:  # pragma: no cover - 管道断裂
                break
            continue
        if request is None:  # stop sentinel
            break
        template, context, spec = request
        try:
            sandbox_dict = spec.build()
            result = _render_with_sandbox(template, context, sandbox_dict)
            reply = pickle.dumps((_STATUS_OK, result))
        except Exception as e:  # 沙箱重建 / 结果序列化异常 → 让父进程回退进程内
            reply = pickle.dumps((_STATUS_ERR, repr(e)))
        try:
            conn.send_bytes(reply)
        except Exception:  # pragma: no cover - 管道断裂
            break
    try:
        conn.close()
    except Exception:  # pragma: no cover
        pass


class _RenderTimeout(Exception):
    """单次隔离渲染超时。"""


class _RenderWorker(object):
    """一个 warm 渲染子进程 + 父进程侧管道句柄 + 使用计数。"""

    def __init__(self, ctx, scrub_patterns, harden_opts):
        parent_conn, child_conn = ctx.Pipe(duplex=True)
        self._conn = parent_conn
        self._proc = ctx.Process(
            target=_worker_main,
            args=(child_conn, list(scrub_patterns), dict(harden_opts or {})),
            daemon=True,
        )
        self._proc.start()
        child_conn.close()  # 父进程侧关闭子端句柄，仅保留 parent_conn
        self.uses = 0

    @property
    def pid(self):
        return self._proc.pid

    def request(self, payload, timeout):
        """发送已序列化请求，最多等 ``timeout`` 秒。超时抛 :class:`_RenderTimeout`。"""
        self._conn.send_bytes(payload)
        if not self._conn.poll(timeout):
            raise _RenderTimeout()
        resp = self._conn.recv_bytes()
        self.uses += 1
        return pickle.loads(resp)

    def is_alive(self):
        return self._proc.is_alive()

    def stop(self):
        """优雅停止：发 sentinel + join；必要时 terminate。"""
        try:
            self._conn.send_bytes(pickle.dumps(None))
        except Exception:
            pass
        try:
            self._conn.close()
        except Exception:
            pass
        self._proc.join(timeout=1)
        if self._proc.is_alive():  # pragma: no cover - 兜底
            self._proc.terminate()
            self._proc.join(timeout=1)

    def kill(self):
        """强制回收（用于超时 / broken worker）。"""
        try:
            self._conn.close()
        except Exception:
            pass
        if self._proc.is_alive():
            self._proc.terminate()
        self._proc.join(timeout=1)


class SubprocessPoolRenderBackend(RenderBackend):
    """无网无凭证的 spawn worker 进程池渲染后端。

    池不变量：``_idle`` 队列中始终维持 ``pool_size`` 个可用 worker——每次渲染 ``acquire`` 恰好取出
    一个、结束后 ``release``/``discard`` 恰好放回一个（健康则复用，超 ``max_uses`` 或损坏则替换为
    新 worker）。懒启动：构造时不 spawn，首次 ``render`` 才拉起池，避免 import 期 fork。
    """

    def __init__(
        self,
        pool_size=None,
        max_uses=None,
        timeout=None,
        env_scrub_patterns=None,
        fallback_inprocess=None,
        mp_context="spawn",
        os_harden=None,
        no_network=None,
        rlimit_cpu=None,
        rlimit_as_mb=None,
    ):
        self.pool_size = int(pool_size or getattr(Settings, "MAKO_RENDER_POOL_SIZE", 4) or 4)
        self.max_uses = int(max_uses or getattr(Settings, "MAKO_RENDER_MAX_USES", 500) or 500)
        self.timeout = float(timeout or getattr(Settings, "MAKO_RENDER_TIMEOUT", 30) or 30)
        # 兜底策略：默认 **strict**（无法隔离渲染即 inert 回显，不静默回退特权进程）。归一化已让绝大多数
        # 合法 context（含 rich 内置变量）可进隔离渲染，故残余「不可序列化」多为异常/攻击者构造——此时
        # strict 更安全，避免「加个 rich 变量 / 塞个不可序列化对象」把注入拽回有网有凭证的主进程。
        # 灰度需要保可用时，可显式置 ``fallback_inprocess=True`` 或 ``MAKO_RENDER_FALLBACK_INPROCESS=True``。
        if fallback_inprocess is None:
            fallback_inprocess = bool(getattr(Settings, "MAKO_RENDER_FALLBACK_INPROCESS", False))
        self.fallback_inprocess = fallback_inprocess
        if env_scrub_patterns is None:
            env_scrub_patterns = list(DEFAULT_ENV_SCRUB_PATTERNS) + list(
                getattr(Settings, "MAKO_RENDER_ENV_SCRUB_EXTRA", []) or []
            )
        self._scrub_patterns = list(env_scrub_patterns)
        # OS 级加固参数（Linux 生效）。默认开启：core dump 关闭 + CPU/内存 rlimits + 尽力无网。
        if os_harden is None:
            os_harden = bool(getattr(Settings, "MAKO_RENDER_OS_HARDEN", True))
        if no_network is None:
            no_network = bool(getattr(Settings, "MAKO_RENDER_NO_NETWORK", True))
        self._harden_opts = {
            "enabled": bool(os_harden),
            "no_network": bool(no_network),
            "rlimit_cpu": rlimit_cpu
            if rlimit_cpu is not None
            else getattr(Settings, "MAKO_RENDER_RLIMIT_CPU", DEFAULT_OS_HARDEN_RLIMIT_CPU),
            "rlimit_as_mb": rlimit_as_mb
            if rlimit_as_mb is not None
            else getattr(Settings, "MAKO_RENDER_RLIMIT_AS_MB", DEFAULT_OS_HARDEN_RLIMIT_AS_MB),
        }
        self._ctx = multiprocessing.get_context(mp_context)
        self._idle = queue.Queue()
        self._inprocess = InProcessRenderBackend()
        self._lock = threading.Lock()
        self._started = False
        self._closed = False

    # -- 池生命周期 --

    def _spawn_worker(self):
        return _RenderWorker(self._ctx, self._scrub_patterns, self._harden_opts)

    def _ensure_started(self):
        if self._started:
            return
        with self._lock:
            if self._started:
                return
            for _ in range(self.pool_size):
                self._idle.put(self._spawn_worker())
            self._started = True
            atexit.register(self.close)

    def _acquire(self):
        return self._idle.get()

    def _release(self, worker):
        """归还一个 worker：健康且未超 ``max_uses`` 则复用，否则停掉并补一个新 worker。"""
        if self._closed:
            worker.stop()
            return
        if worker.is_alive() and worker.uses < self.max_uses:
            self._idle.put(worker)
        else:
            worker.stop()
            self._idle.put(self._spawn_worker())

    def _discard(self, worker):
        """丢弃一个损坏 / 超时 worker，并补一个新 worker 维持池容量。"""
        worker.kill()
        if not self._closed:
            self._idle.put(self._spawn_worker())

    def close(self):
        """停掉池内所有空闲 worker（幂等）。在飞的渲染完成后其 worker 也会被 stop。"""
        with self._lock:
            if self._closed:
                return
            self._closed = True
        while True:
            try:
                worker = self._idle.get_nowait()
            except queue.Empty:
                break
            worker.stop()

    # -- 渲染 --

    def _fallback(self, template, context, sandbox_builder):
        if self.fallback_inprocess:
            return self._inprocess.render(template, context, sandbox_builder)
        return template

    def render(self, template, context, sandbox_builder):
        spec = sandbox_builder.spec() if hasattr(sandbox_builder, "spec") else None
        if spec is None:
            # 拿不到可序列化 spec（历史裸 builder）→ 无法隔离 → 进程内渲染，保持向后兼容。
            return self._inprocess.render(template, context, sandbox_builder)
        try:
            # 归一化 rich context 对象为 Django-free 载体，让含 rich 变量的模板也能进隔离渲染；随后整体
            # 预序列化，在**不污染管道**的前提下探测残余不可 pickle 的 context，命中即按策略兜底。
            payload = pickle.dumps((template, _portable_context(context), spec))
        except Exception as e:
            logger.warning(
                "render context not serializable, fallback(%s): %s",
                "inprocess" if self.fallback_inprocess else "strict-inert",
                e,
            )
            return self._fallback(template, context, sandbox_builder)

        self._ensure_started()
        worker = self._acquire()
        try:
            status, result = worker.request(payload, self.timeout)
        except _RenderTimeout:
            logger.warning("isolated render timeout(%ss), inert: %s", self.timeout, template)
            self._discard(worker)
            return template  # 超时 inert；绝不回退进程内，避免把 DoS 带回主进程
        except Exception as e:
            logger.warning("isolated render worker error, fallback in-process: %s", e)
            self._discard(worker)
            return self._fallback(template, context, sandbox_builder)
        else:
            self._release(worker)
            if status == _STATUS_OK:
                return result
            logger.warning("isolated render sandbox error(%s), fallback in-process", result)
            return self._fallback(template, context, sandbox_builder)


_BACKEND = None


def _build_default_backend():
    """按 ``Settings.MAKO_RENDER_BACKEND`` 构造后端；未配置或未知值时回退进程内渲染。"""
    name = getattr(Settings, "MAKO_RENDER_BACKEND", "inprocess") or "inprocess"
    if name == "inprocess":
        return InProcessRenderBackend()
    if name == "subprocess":
        return SubprocessPoolRenderBackend()
    logger.warning("unknown MAKO_RENDER_BACKEND=%s, fallback to inprocess", name)
    return InProcessRenderBackend()


def get_render_backend():
    """返回当前进程缓存的渲染后端单例（懒构造）。"""
    global _BACKEND
    if _BACKEND is None:
        _BACKEND = _build_default_backend()
    return _BACKEND


def set_render_backend(backend):
    """显式设置渲染后端（用于配置注入与测试）。"""
    global _BACKEND
    _BACKEND = backend


def reset_render_backend():
    """清空缓存，使下次 ``get_render_backend`` 重新按配置构造。"""
    global _BACKEND
    _BACKEND = None
