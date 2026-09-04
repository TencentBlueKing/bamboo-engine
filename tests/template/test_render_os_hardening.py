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

import sys

import pytest

from bamboo_engine.template import render_backend as rb


def test_apply_os_hardening_noop_when_opts_none():
    # 无配置 → 直接 no-op，不得抛出。
    assert rb._apply_os_hardening(None) is None


def test_apply_os_hardening_noop_when_disabled():
    assert rb._apply_os_hardening({"enabled": False, "no_network": True, "rlimit_cpu": 1}) is None


@pytest.mark.skipif(sys.platform.startswith("linux"), reason="non-Linux no-op path")
def test_apply_os_hardening_noop_on_non_linux():
    # macOS/其它平台：即便 enabled，也应 no-op 且不抛出（加固仅 Linux 生效）。
    assert rb._apply_os_hardening({"enabled": True, "no_network": True, "rlimit_cpu": 1, "rlimit_as_mb": 512}) is None


def test_os_hardening_test_hook_takes_precedence():
    # 注入测试 hook 时优先执行，用于本地/单测覆盖真实加固逻辑。
    called = []
    rb._OS_HARDENING_HOOK = lambda: called.append(True)
    try:
        rb._apply_os_hardening({"enabled": False})  # 即便 disabled，hook 覆盖仍执行
        assert called == [True]
    finally:
        rb._OS_HARDENING_HOOK = None


@pytest.mark.skipif(not sys.platform.startswith("linux"), reason="Linux-only rlimit assertion")
def test_apply_os_hardening_sets_core_rlimit_zero_on_linux():
    import resource

    orig = resource.getrlimit(resource.RLIMIT_CORE)
    try:
        rb._apply_os_hardening({"enabled": True, "no_network": False, "rlimit_cpu": None, "rlimit_as_mb": None})
        soft, _ = resource.getrlimit(resource.RLIMIT_CORE)
        assert soft == 0  # 禁 core dump，避免凭证随 core 落盘
    finally:
        try:
            resource.setrlimit(resource.RLIMIT_CORE, orig)
        except Exception:
            pass


def test_backend_with_os_harden_enabled_still_renders():
    # 打开 os_harden 的池在本机（macOS no-op / Linux 加固）都应正常渲染，验证 harden_opts 透传不破渲染。
    from bamboo_engine.template.render_backend import SandboxProvider, SandboxSpec
    from bamboo_engine.template import sandbox as engine_sandbox

    provider = SandboxProvider(engine_sandbox.get, SandboxSpec("engine", [], {}))
    backend = rb.SubprocessPoolRenderBackend(pool_size=1, max_uses=1000, timeout=10.0, os_harden=True)
    try:
        assert backend.render("${a + b}", {"a": 20, "b": 22}, provider) == "42"
    finally:
        backend.close()
