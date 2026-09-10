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

import os
import time
import threading

import pytest

from bamboo_engine.template.render_backend import (
    PortableRenderObject,
    SandboxProvider,
    SandboxSpec,
    SubprocessPoolRenderBackend,
    _portable_context,
)
from bamboo_engine.template import sandbox as engine_sandbox
from bamboo_engine.exceptions import RenderInfrastructureError


# ---- module-level, picklable probes injected into render context (spawn needs top-level refs) ----


def _worker_pid_probe():
    return os.getpid()


def _read_scrubbed_env():
    # 若 env 未被清洗，这里会读到父进程注入的 "topsecret"。
    return os.environ.get("MAKO_TEST_APP_SECRET", "<absent>")


def _slow_probe():
    time.sleep(5)
    return "done"


def _raise_on_unpickle():
    raise RuntimeError("boom on unpickle in worker")


class _UnpicklableOnLoad(object):
    """父进程可 pickle、worker 侧 loads 抛错，且**无 __dict__**（不会被归一化拦截）。

    用 ``__slots__=()`` + ``__reduce__`` 指向一个 load 时抛错的模块级函数，精确重现「可 pickle 但 worker
    无法重建」这一残余失败模式（归一化只处理属性包，管不到这种无 __dict__ 的按引用重建对象）。
    """

    __slots__ = ()

    def __reduce__(self):
        return (_raise_on_unpickle, ())


class _RichLikeVar(object):
    """模拟 bk-sops rich 内置变量：属性包 + ``__repr__``，且 ``__setstate__`` 抛错。

    若隔离 backend 未归一化就直接 pickle 原对象，worker unpickle 会触发 ``__setstate__`` 报错；因此
    「渲染出正确结果」本身就证明 worker 只见到了归一化后的 :class:`PortableRenderObject`，从未 unpickle 原类。
    """

    def __init__(self):
        self.col = ["a", "b"]
        self.flat__col = "a\nb"

    def __repr__(self):
        return "RichLike(2 rows)"

    def __setstate__(self, state):
        raise RuntimeError("original rich object must not be unpickled in worker")


def _engine_provider():
    """engine flavor provider：进程内构造 + 可序列化 spec（供 worker 本地重建）。"""
    return SandboxProvider(
        engine_sandbox.get,
        SandboxSpec("engine", [], {}),
    )


def _local_backend(**kwargs):
    # Portable process/IPC tests; actual no-network requirements are tested separately.
    return SubprocessPoolRenderBackend(no_network=False, **kwargs)


@pytest.fixture
def backend():
    b = _local_backend(pool_size=1, max_uses=1000, timeout=10.0)
    try:
        yield b
    finally:
        b.close()


def test_subprocess_backend_renders_in_a_different_process(backend):
    parent_pid = os.getpid()
    result = backend.render("${probe()}", {"probe": _worker_pid_probe}, _engine_provider())
    assert result.isdigit()
    assert int(result) != parent_pid  # 证明渲染发生在隔离子进程里


def test_subprocess_backend_reuses_warm_worker(backend):
    r1 = backend.render("${probe()}", {"probe": _worker_pid_probe}, _engine_provider())
    r2 = backend.render("${probe()}", {"probe": _worker_pid_probe}, _engine_provider())
    assert r1 == r2  # pool_size=1 且 max_uses 很大 → 同一 warm worker 复用


def test_subprocess_backend_recycles_after_max_uses():
    b = _local_backend(pool_size=1, max_uses=1, timeout=10.0)
    try:
        r1 = b.render("${probe()}", {"probe": _worker_pid_probe}, _engine_provider())
        r2 = b.render("${probe()}", {"probe": _worker_pid_probe}, _engine_provider())
        assert r1 != r2  # max_uses=1 → 每次渲染后回收，PID 不同
    finally:
        b.close()


def test_subprocess_backend_scrubs_credentials_from_env():
    os.environ["MAKO_TEST_APP_SECRET"] = "topsecret"
    b = _local_backend(pool_size=1, max_uses=1000, timeout=10.0)
    try:
        result = b.render("${probe()}", {"probe": _read_scrubbed_env}, _engine_provider())
        assert result == "<absent>"  # 子进程启动即清洗掉了凭证类 env
    finally:
        b.close()
        os.environ.pop("MAKO_TEST_APP_SECRET", None)


def test_subprocess_backend_timeout_raises_without_hanging():
    b = _local_backend(pool_size=1, max_uses=1000, timeout=0.5)
    try:
        start = time.time()
        template = "${probe()}"
        with pytest.raises(RenderInfrastructureError, match="deadline_exceeded"):
            b.render(template, {"probe": _slow_probe}, _engine_provider())
        elapsed = time.time() - start
        assert elapsed < 4  # 及时超时，未被拖挂
    finally:
        b.close()


def test_subprocess_backend_falls_back_inprocess_on_unpicklable_context():
    # 显式 fallback_inprocess=True：threading.Lock 不可 pickle → 无法进隔离子进程 → 回退进程内、渲染正确。
    b = _local_backend(pool_size=1, max_uses=1000, timeout=10.0, fallback_inprocess=True)
    try:
        context = {"x": 5, "_lock": threading.Lock()}
        result = b.render("${x + 1}", context, _engine_provider())
        assert result == "6"
    finally:
        b.close()


def test_subprocess_backend_strict_default_is_inert_on_unserializable():
    # 默认 strict：不可序列化 context → inert 回显模板（绝不静默回退特权进程），保安全边界。
    b = _local_backend(pool_size=1, max_uses=1000, timeout=10.0)
    try:
        template = "${x + 1}"
        result = b.render(template, {"x": 5, "_lock": threading.Lock()}, _engine_provider())
        assert result == template
    finally:
        b.close()


def test_subprocess_backend_normalizes_rich_object_to_render_in_worker(backend):
    # rich 属性包（__setstate__ 抛错）：归一化后 worker 只见 PortableRenderObject，仍能渲染属性 + bare ${var}。
    # 默认 strict 后端：若归一化失效则会 inert；因此渲染出正确值即证明归一化生效。
    v = _RichLikeVar()
    assert backend.render("${v.flat__col}", {"v": v}, _engine_provider()) == "a\nb"
    assert backend.render("${v.col[0]}", {"v": v}, _engine_provider()) == "a"
    assert backend.render("${v}", {"v": v}, _engine_provider()) == "RichLike(2 rows)"


def test_subprocess_backend_without_spec_requires_explicit_fallback(backend):
    backend.fallback_inprocess = True
    # 仅显式 fallback 配置允许没有 spec 的 builder 回退进程内。
    parent_pid = os.getpid()
    result = backend.render("${probe()}", {"probe": _worker_pid_probe}, engine_sandbox.get)
    assert int(result) == parent_pid


def test_subprocess_backend_compile_error_is_inert(backend):
    bad = "${1 + }"
    result = backend.render(bad, {}, _engine_provider())
    assert result == bad  # 编译失败 → inert 回显，与进程内后端一致


def test_subprocess_worker_side_unpickle_failure_falls_back_fast():
    # 父进程可 pickle、worker 侧 unpickle 失败（无 __dict__ 故绕过归一化，模拟按引用重建失败的残余场景）：
    # 显式 fallback_inprocess=True 时必须快速、干净地回退进程内，而不是等满 timeout 再 inert。
    b = _local_backend(pool_size=1, max_uses=1000, timeout=2.0, fallback_inprocess=True)
    try:
        context = {"x": 5, "_evil": _UnpicklableOnLoad()}
        start = time.time()
        result = b.render("${x + 1}", context, _engine_provider())
        elapsed = time.time() - start
        assert result == "6"  # 干净回退进程内 → 渲染正确（而非 inert "${x + 1}"）
        assert elapsed < 1.5  # worker 立即回 STATUS_ERR → 快速回退，而非等满 2s timeout
    finally:
        b.close()


def test_portable_render_object_roundtrips_via_pickle():
    o = PortableRenderObject({"a": 1, "flat__x": "y\nz"}, "STRV", "REPRV")
    import pickle

    o2 = pickle.loads(pickle.dumps(o))
    assert o2.a == 1 and o2.flat__x == "y\nz"
    assert str(o2) == "STRV" and repr(o2) == "REPRV"


def test_portable_context_preserves_plain_and_callables_normalizes_rich():
    def f():
        return 1

    out = _portable_context({"x": 5, "s": "hi", "l": [1, {"k": "v"}], "f": f, "rich": _RichLikeVar()})
    assert out["x"] == 5 and out["s"] == "hi"
    assert out["l"] == [1, {"k": "v"}]  # 容器递归、plain 元素不变
    assert out["f"] is f  # 可调用不被归一化（否则 ${f()} 会坏）
    assert isinstance(out["rich"], PortableRenderObject)  # rich 属性包被归一化
    assert out["rich"].flat__col == "a\nb" and str(out["rich"]) == "RichLike(2 rows)"
