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
#   * 表达式编译/求值失败保留原文；隔离设施失败抛出 RenderInfrastructureError，
#     由调用方停止节点执行，不能把未渲染的输入交给业务插件。

import atexit
import datetime
import decimal
import inspect
import logging
import os
import pickle
import queue
import signal
import socket
import subprocess
import sys
import threading
import time
import uuid
from collections import Counter
from types import SimpleNamespace

from mako.exceptions import MakoException
from mako.template import Template as MakoTemplate

from bamboo_engine.config import Settings
from bamboo_engine.exceptions import RenderInfrastructureError
from bamboo_engine.template.render_transport import MAX_REQUEST_BYTES, MAX_RESPONSE_BYTES, ProtocolError
from bamboo_engine.template.render_transport import RenderTimeout as _RenderTimeout
from bamboo_engine.template.render_transport import SocketConnection, decode_reply, encode_reply, remaining
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
    """表达式编译/求值失败保留原文；基础设施故障以 RenderInfrastructureError 显式传递。"""

    def render(self, template, context, sandbox_builder):
        raise NotImplementedError


class InProcessRenderBackend(RenderBackend):
    """默认后端：在当前进程内编译并渲染，行为与历史 ``_render_template`` 完全一致。"""

    def render(self, template, context, sandbox_builder):
        return _render_with_sandbox(template, context, sandbox_builder())


class SandboxSpec(object):
    """可序列化的渲染沙箱配置，供隔离 backend 在子进程本地重建沙箱。

    仅向 worker 发送受信任的字符串配置（flavor + shield_words + import_modules）；
    模块对象由 :meth:`build` 在目标进程本地重建。不得从 worker 接收此对象的 pickle。

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


# The subprocess backend reduces exposure but is not a filesystem/credential sandbox.
# Workers start with an environment allowlist and close unrelated descriptors. When
# no_network=True they MUST establish a network namespace before reading requests.
# Context and sandbox configuration are trusted host inputs (one-way pickle); replies
# from the potentially compromised worker are bounded JSON, never executable pickle.


class UnsupportedContext(ValueError):
    """Context cannot be transported without changing its template-visible behavior."""


_PORTABLE_SCALAR_TYPES = (str, bytes, bytearray, bool, int, float, complex, type(None))
_PORTABLE_MAX_DEPTH = 8
_PORTABLE_MAX_ITEMS = 100000


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


def _portable_value(value, depth, seen, budget):
    budget[0] -= 1
    if budget[0] < 0 or budget[1] < 0:
        raise UnsupportedContext("render context exceeds transport budget")
    kind = type(value)
    if kind in (str, bytes, bytearray):
        budget[1] -= len(value)
        if budget[1] < 0:
            raise UnsupportedContext("render context exceeds transport budget")
    if kind is int and value.bit_length() > 4096:
        raise UnsupportedContext("render context integer exceeds transport budget")
    if kind in _PORTABLE_SCALAR_TYPES:
        return value
    if depth >= _PORTABLE_MAX_DEPTH or id(value) in seen:
        raise UnsupportedContext("cyclic or excessively deep render context")
    seen = seen | {id(value)}

    def convert(item):
        return _portable_value(item, depth + 1, seen, budget)

    if kind in (dict, Counter):
        return kind({convert(k): convert(v) for k, v in value.items()})
    if kind in (list, tuple, set, frozenset):
        return kind(convert(v) for v in value)
    if kind in (time.struct_time, datetime.date, datetime.timedelta, decimal.Decimal):
        return value
    if kind in (datetime.datetime, datetime.time):
        if value.tzinfo is None or type(value.tzinfo) is datetime.timezone:
            return value
        raise UnsupportedContext("unsupported timezone type")
    # Host-provided importable callables retain their identity. They are trusted
    # configuration, never supplied by the worker; imports may load application code.
    if inspect.isfunction(value) or inspect.isbuiltin(value):
        return value
    # Only structural attribute bags are converted. Properties, methods, inherited
    # behavior and container subclasses must take the explicit unsupported path.
    bag_members = {
        "__module__",
        "__doc__",
        "__dict__",
        "__weakref__",
        "__init__",
        "__repr__",
        "__str__",
        "__getstate__",
        "__setstate__",
    }
    is_bag = kind in (PortableRenderObject, SimpleNamespace) or (
        kind.__bases__ == (object,) and set(vars(kind)).issubset(bag_members)
    )
    if is_bag and type(getattr(value, "__dict__", None)) is dict:
        attrs = {k: convert(v) for k, v in vars(value).items()}
        return PortableRenderObject(attrs, str(value), repr(value))
    raise UnsupportedContext("unsupported render context type: {}.{}".format(kind.__module__, kind.__name__))


def _portable_context(context):
    """Validate supported host values before one-way transport; never coerce unknown behavior.

    Importable host functions remain trusted references. Inprocess bypasses conversion.
    """
    if type(context) is not dict or any(type(k) is not str for k in context):
        raise UnsupportedContext("render context must have plain string keys")
    return _portable_value(context, 0, frozenset(), [_PORTABLE_MAX_ITEMS, MAX_REQUEST_BYTES])


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


def _try_unshare_network():
    """Fail closed if the explicitly requested network namespace is unavailable."""
    if not sys.platform.startswith("linux"):
        raise RuntimeError("network isolation requires Linux")
    import ctypes

    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    if libc.unshare(0x40000000) != 0:  # CLONE_NEWNET
        raise RuntimeError("network isolation failed errno={}".format(ctypes.get_errno()))


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
    """Requested network isolation must succeed; resource limits apply on Linux."""
    if not opts:
        return
    if opts.get("no_network"):
        _try_unshare_network()
    if not opts.get("enabled") or not sys.platform.startswith("linux"):
        return
    import resource

    def set_limit(res, soft):
        _, hard = resource.getrlimit(res)
        limit = soft if hard == resource.RLIM_INFINITY else min(soft, hard)
        resource.setrlimit(res, (limit, limit))

    set_limit(resource.RLIMIT_CORE, 0)
    if opts.get("rlimit_cpu"):
        set_limit(resource.RLIMIT_CPU, int(opts["rlimit_cpu"]))
    if opts.get("rlimit_as_mb"):
        set_limit(resource.RLIMIT_AS, int(opts["rlimit_as_mb"]) * 1024 * 1024)


def _worker_main(conn, scrub_patterns, harden_opts):
    """Read trusted host requests only after all required isolation is established."""
    try:
        if sys.platform.startswith("linux"):
            import ctypes

            libc = ctypes.CDLL("libc.so.6", use_errno=True)
            if libc.prctl(1, signal.SIGKILL, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
                raise RuntimeError("cannot set render worker parent-death signal")
            if os.getppid() != harden_opts["parent_pid"]:
                return  # host died between exec and prctl
        _scrub_environ(scrub_patterns)
        _apply_os_hardening(harden_opts)
        conn.send_bytes(b"READY", max_bytes=128)
        while True:
            payload = conn.recv_bytes(max_bytes=MAX_REQUEST_BYTES)
            request_id = payload[:32].decode("ascii")
            if len(request_id) != 32 or any(c not in "0123456789abcdef" for c in request_id):
                raise ProtocolError("invalid request identifier")
            try:
                template, context, spec = pickle.loads(payload[32:])
                result = _render_with_sandbox(template, context, spec.build())
                reply = encode_reply(_STATUS_OK, result, request_id)
            except Exception:
                # Do not echo exception/context data or let a worker demand privileged fallback.
                reply = encode_reply(_STATUS_ERR, "isolated render failed", request_id)
            conn.send_bytes(reply, max_bytes=MAX_RESPONSE_BYTES)
    except (EOFError, OSError, ValueError, RuntimeError):
        pass
    finally:
        conn.close()


def _worker_environment(patterns):
    # An allowlist is applied BEFORE starting Python/site imports. Arbitrary env keys
    # (including names without SECRET/TOKEN) must not reach the interpreter.
    allowed = {"PATH", "LANG", "LC_ALL", "LC_CTYPE", "TZ", "SYSTEMROOT"}
    patterns = [p.lower() for p in patterns]
    return {k: v for k, v in os.environ.items() if k in allowed and not any(p in k.lower() for p in patterns)}


_CONNECTION_PID = os.getpid()
_WORKER_SOCKETS = set()


def _close_inherited_connections():
    """Include transports still inside a concurrent Popen constructor during fork."""
    global _CONNECTION_PID, _WORKER_SOCKETS
    if _CONNECTION_PID != os.getpid():
        inherited = tuple(_WORKER_SOCKETS)
        _CONNECTION_PID = os.getpid()
        _WORKER_SOCKETS = set()
        for sock in inherited:
            sock.close()  # local fd copy only; never shutdown the parent's socket


class _RenderWorker(object):
    """A fresh Python interpreter, also launchable from a daemon prefork host."""

    def __init__(self, scrub_patterns, harden_opts):
        if os.name != "posix":
            raise RuntimeError("subprocess rendering requires POSIX")
        _close_inherited_connections()
        parent_sock, child_sock = socket.socketpair()
        _WORKER_SOCKETS.update((parent_sock, child_sock))
        self._conn = SocketConnection(parent_sock)
        self._owner_pid = os.getpid()
        self.uses = 0
        self._ready = False
        self._killed = False
        # -S avoids site hooks before hardening; no re-import of the host __main__.
        # sys.path is trusted host configuration and carries the installed engine/runtime.
        code = (
            "import sys,socket; sys.path={paths!r}; "
            "from bamboo_engine.template.render_backend import _worker_main; "
            "from bamboo_engine.template.render_transport import SocketConnection; "
            "_worker_main(SocketConnection(socket.socket(fileno={fd})), {scrub!r}, {opts!r})"
        ).format(
            paths=[os.path.abspath(p) for p in sys.path],
            fd=child_sock.fileno(),
            scrub=list(scrub_patterns),
            opts=harden_opts,
        )
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-I", "-S", "-c", code],
                pass_fds=(child_sock.fileno(),),
                close_fds=True,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=_worker_environment(scrub_patterns),
                start_new_session=True,
            )
        except BaseException:
            parent_sock.close()
            _WORKER_SOCKETS.discard(parent_sock)
            raise
        finally:
            child_sock.close()
            _WORKER_SOCKETS.discard(child_sock)

    @property
    def pid(self):
        return self._proc.pid

    def request(self, payload, timeout):
        deadline = time.monotonic() + timeout
        if not getattr(self, "_ready", True):
            if self._conn.recv_bytes(deadline=deadline, max_bytes=128) != b"READY":
                raise ProtocolError("render worker isolation setup failed")
            self._ready = True
        request_id = uuid.uuid4().hex
        self._conn.send_bytes(request_id.encode("ascii") + payload, deadline=deadline)
        response = self._conn.recv_bytes(deadline=deadline, max_bytes=MAX_RESPONSE_BYTES)
        result = decode_reply(response, request_id)
        remaining(deadline)
        self.uses += 1
        return result

    def is_alive(self):
        return self._owner_pid == os.getpid() and self._proc.poll() is None

    def kill(self):
        # No blocking wait/send on the caller's deadline path.
        self._conn.close()
        _WORKER_SOCKETS.discard(self._conn.sock)
        if self._owner_pid == os.getpid() and not self._killed:
            self._killed = True
            try:
                os.killpg(self._proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

    def stop(self):
        self.kill()
        if self._owner_pid == os.getpid():
            try:
                self._proc.wait(timeout=1)
            except subprocess.TimeoutExpired:
                return False
        return True


class _RenderSlot:
    """A slot stays occupied until even a timed-out launcher has cleaned up."""

    def __init__(self):
        self.worker = None
        self.jobs = queue.Queue()
        self.thread = None
        self.lock = threading.Lock()
        self.active = None


class _RenderJob:
    def __init__(self, slot, deadline):
        self.slot = slot
        self.deadline = deadline
        self.cancelled = threading.Event()
        self.done = threading.Event()
        self.result = None
        self.error = None

    def cancel(self):
        with self.slot.lock:
            self.cancelled.set()
            worker = self.slot.worker
            if self.slot.active is self and worker is not None:
                worker.kill()


class SubprocessPoolRenderBackend(RenderBackend):
    """Bounded warm subprocess pool; disabled by default, strict failure policy.

    At most pool_size supervisor threads can exist, including launchers which outlive
    a timeout. A slot is returned only after cleanup, so process-launch stalls cannot
    create an unbounded number of background launchers. Later calls time out on admission.
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
        # 默认 strict：未知 context 不隐式进入宿主。显式兼容回退仅处理父侧类型/spec 问题，
        # worker、协议、启动、超时和网络隔离失败不会触发回退。
        if fallback_inprocess is None:
            fallback_inprocess = bool(getattr(Settings, "MAKO_RENDER_FALLBACK_INPROCESS", False))
        self.fallback_inprocess = fallback_inprocess
        if env_scrub_patterns is None:
            env_scrub_patterns = list(DEFAULT_ENV_SCRUB_PATTERNS) + list(
                getattr(Settings, "MAKO_RENDER_ENV_SCRUB_EXTRA", []) or []
            )
        self._scrub_patterns = list(env_scrub_patterns)
        # Linux 资源限制；no_network 为独立强制要求，不支持/无权限时拒绝渲染。
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
        if mp_context != "spawn":
            raise ValueError("only fresh-interpreter rendering is supported")
        if self.pool_size <= 0 or self.max_uses <= 0 or self.timeout <= 0:
            raise ValueError("pool size, max uses and timeout must be positive")
        self._owner_pid = os.getpid()
        self._idle = queue.Queue()
        self._slots = [_RenderSlot() for _ in range(self.pool_size)]
        for slot in self._slots:
            self._idle.put(slot)
        self._jobs = set()
        self._inprocess = InProcessRenderBackend()
        self._lock = threading.Lock()
        atexit.register(self.close)
        self._closed = False

    def _ensure_process(self):
        _close_inherited_connections()
        if self._owner_pid == os.getpid():
            return
        # Forked hosts must never share transports/locks or terminate the parent's workers.
        for slot in self._slots:
            if slot.worker is not None:
                slot.worker._conn.close()
        self._owner_pid = os.getpid()
        self._lock = threading.Lock()
        self._idle = queue.Queue()
        self._slots = [_RenderSlot() for _ in range(self.pool_size)]
        for slot in self._slots:
            self._idle.put(slot)
        self._jobs = set()

    def _spawn_worker(self):
        opts = dict(self._harden_opts, parent_pid=os.getpid())
        return _RenderWorker(self._scrub_patterns, opts)

    def _slot_loop(self, slot):
        # Keep the launching thread alive for the worker's lifetime: Linux
        # PR_SET_PDEATHSIG follows that thread, not just the host process PID.
        while True:
            args = slot.jobs.get()
            if args is None:
                if slot.worker is not None:
                    self._retire(slot.worker)
                    slot.worker = None
                return
            self._run(*args)
            if self._closed:
                return

    @staticmethod
    def _retire(worker):
        # Only supervisor threads wait here. Even after a timeout/cleanup exception,
        # retain the slot until the child has actually been reaped.
        reported = False
        while True:
            try:
                if worker.stop():
                    return
            except Exception:
                if not reported:
                    logger.exception("isolated render worker cleanup failed; retaining slot")
                    reported = True
            time.sleep(0.05)

    def _run(self, job, template, context, sandbox_builder):
        slot = job.slot
        try:
            remaining(job.deadline)
            spec = sandbox_builder.spec() if hasattr(sandbox_builder, "spec") else None
            if type(spec) is not SandboxSpec:
                raise UnsupportedContext("sandbox provider has no transport spec")
            if (
                type(template) is not str
                or type(spec.flavor) is not str
                or spec.flavor not in ("engine", "legacy")
                or type(spec.shield_words) is not list
                or any(type(w) is not str for w in spec.shield_words)
                or type(spec.import_modules) is not dict
                or any(type(k) is not str or type(v) is not str for k, v in spec.import_modules.items())
            ):
                raise UnsupportedContext("invalid render template or sandbox spec")
            try:
                payload = pickle.dumps((template, _portable_context(context), spec))
            except Exception as exc:
                raise UnsupportedContext("context cannot be transported: {}".format(type(exc).__name__)) from exc
            if len(payload) > MAX_REQUEST_BYTES:
                raise ProtocolError("render request too large")
            remaining(job.deadline)
            if job.cancelled.is_set():
                raise _RenderTimeout()
            if slot.worker is None or not slot.worker.is_alive():
                if slot.worker is not None:
                    self._retire(slot.worker)
                slot.worker = self._spawn_worker()
            if job.cancelled.is_set():
                raise _RenderTimeout()
            status, result = slot.worker.request(payload, remaining(job.deadline))
            remaining(job.deadline)
            if status != _STATUS_OK:
                raise ProtocolError("isolated worker rejected render")
            job.result = result
        except BaseException as exc:
            job.error = exc
        finally:
            # Publish the completed result before recycling. Cleanup/spawn failures
            # cannot overwrite success; replacement is lazy on the next admitted job.
            job.done.set()
            try:
                if slot.worker is not None and (
                    job.error is not None
                    or job.cancelled.is_set()
                    or self._closed
                    or slot.worker.uses >= self.max_uses
                    or not slot.worker.is_alive()
                ):
                    try:
                        self._retire(slot.worker)
                    finally:
                        slot.worker = None
            except Exception:
                logger.warning("isolated render worker cleanup failed")
            finally:
                retired = None
                with self._lock:
                    self._jobs.discard(job)
                    with slot.lock:
                        slot.active = None
                    # close() and returning the slot are atomic with respect to each other.
                    if self._closed:
                        retired, slot.worker = slot.worker, None
                    else:
                        self._idle.put(slot)
                if retired is not None:
                    self._retire(retired)

    def close(self):
        self._ensure_process()
        with self._lock:
            if self._closed:
                return
            self._closed = True
            jobs = list(self._jobs)
            while True:
                try:
                    self._idle.get_nowait()
                except queue.Empty:
                    break
        for job in jobs:
            job.cancel()
            job.done.set()
        # Include slots between Queue.get and registration in _jobs.
        for slot in self._slots:
            slot.jobs.put(None)
            worker = slot.worker
            if worker is not None:
                worker.kill()

    def _fallback(self, template, context, sandbox_builder):
        if self.fallback_inprocess:
            return self._inprocess.render(template, context, sandbox_builder)
        return template

    def render(self, template, context, sandbox_builder):
        self._ensure_process()
        deadline = time.monotonic() + self.timeout
        if self._closed:
            raise RenderInfrastructureError("backend_closed")
        try:
            while True:
                if self._closed:
                    raise RenderInfrastructureError("backend_closed")
                try:
                    slot = self._idle.get(timeout=min(0.05, remaining(deadline)))
                    break
                except queue.Empty:
                    continue
        except _RenderTimeout:
            logger.warning("isolated render admission timeout")
            raise RenderInfrastructureError("admission_timeout")
        job = _RenderJob(slot, deadline)
        with self._lock:
            if self._closed:
                slot.jobs.put(None)
                raise RenderInfrastructureError("backend_closed")
            self._jobs.add(job)
            with slot.lock:
                slot.active = job
        try:
            if slot.thread is None:
                slot.thread = threading.Thread(target=self._slot_loop, args=(slot,), daemon=True)
                try:
                    slot.thread.start()
                except Exception:
                    slot.thread = None
                    raise
            slot.jobs.put((job, template, context, sandbox_builder))
        except Exception:
            with self._lock:
                self._jobs.discard(job)
                if not self._closed:
                    self._idle.put(slot)
            logger.warning("isolated render supervisor could not start")
            raise RenderInfrastructureError("supervisor_start_failed")
        try:
            if not job.done.wait(remaining(deadline)):
                raise _RenderTimeout()
            remaining(deadline)
        except _RenderTimeout:
            job.cancel()
            logger.warning("isolated render deadline exceeded (%ss)", self.timeout)
            raise RenderInfrastructureError("deadline_exceeded")
        except BaseException:
            job.cancel()
            raise
        if job.cancelled.is_set() or self._closed:
            raise RenderInfrastructureError("backend_closed")
        if job.error is not None:
            logger.warning("isolated render failed: %s", type(job.error).__name__)
            # Only a trusted parent-side compatibility decision may request fallback.
            # A compromised/slow worker must never force rendering in the host.
            if isinstance(job.error, UnsupportedContext):
                return self._fallback(template, context, sandbox_builder)
            if isinstance(job.error, _RenderTimeout):
                raise RenderInfrastructureError("deadline_exceeded") from job.error
            raise RenderInfrastructureError("worker_failure") from job.error
        return job.result


_BACKEND = None
_BACKEND_LOCK = threading.Lock()
_BACKEND_PID = os.getpid()


def _backend_lock():
    global _BACKEND_LOCK, _BACKEND_PID
    if _BACKEND_PID != os.getpid():
        _BACKEND_LOCK = threading.Lock()
        _BACKEND_PID = os.getpid()
    return _BACKEND_LOCK


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
    with _backend_lock():
        if _BACKEND is None:
            _BACKEND = _build_default_backend()
        return _BACKEND


def set_render_backend(backend):
    """显式设置渲染后端（用于配置注入与测试）。"""
    global _BACKEND
    with _backend_lock():
        previous, _BACKEND = _BACKEND, backend
    if previous is not backend and hasattr(previous, "close"):
        previous.close()


def reset_render_backend():
    """清空缓存，使下次 ``get_render_backend`` 重新按配置构造。"""
    set_render_backend(None)
