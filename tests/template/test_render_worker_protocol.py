# -*- coding: utf-8 -*-
"""Exercise the worker's isolation and wire contract without changing host limits."""
import ctypes
import os
import pickle
import signal
from types import SimpleNamespace

import pytest

from bamboo_engine.template import render_backend as rb


class WorkerConnection:
    def __init__(self, requests=()):
        self.requests = iter(requests)
        self.sent = []
        self.reads = 0
        self.closed = False

    def send_bytes(self, data, **kwargs):
        self.sent.append(data)

    def recv_bytes(self, **kwargs):
        self.reads += 1
        try:
            return next(self.requests)
        except StopIteration:
            raise EOFError()

    def close(self):
        self.closed = True


def test_worker_sanitizes_failure_and_handles_next_request(monkeypatch):
    monkeypatch.setattr(rb.sys, "platform", "darwin")
    monkeypatch.setenv("RENDER_TEST_SECRET", "must-not-reach-rendering")
    bad_id, good_id = "a" * 32, "b" * 32
    requests = [
        bad_id.encode("ascii")
        + pickle.dumps(("${x}", {"x": "private-context"}, rb.SandboxSpec("private-flavor", [], {}))),
        good_id.encode("ascii") + pickle.dumps(("${x + 1}", {"x": 2}, rb.SandboxSpec("engine", [], {}))),
    ]
    conn = WorkerConnection(requests)

    rb._worker_main(conn, ["render_test_secret"], {})

    assert conn.closed
    assert "RENDER_TEST_SECRET" not in os.environ
    assert conn.sent[0] == b"READY"
    assert rb.decode_reply(conn.sent[1], bad_id) == [1, "isolated render failed"]
    assert rb.decode_reply(conn.sent[2], good_id) == [0, "3"]
    assert len(conn.sent) == 3


def test_worker_never_accepts_requests_when_isolation_fails(monkeypatch):
    monkeypatch.setattr(rb.sys, "platform", "darwin")

    def denied(opts):
        raise RuntimeError("synthetic isolation denial")

    monkeypatch.setattr(rb, "_apply_os_hardening", denied)
    conn = WorkerConnection()
    rb._worker_main(conn, [], {"no_network": True})
    assert conn.closed
    assert conn.reads == 0
    assert conn.sent == []


@pytest.mark.parametrize("payload", [b"short", b"z" * 32 + b"payload", b"\xff" * 32])
def test_invalid_request_id_is_rejected_before_deserialization(monkeypatch, payload):
    monkeypatch.setattr(rb.sys, "platform", "darwin")

    def unexpected_deserialization(data):
        pytest.fail("invalid request identifier reached deserialization")

    monkeypatch.setattr(rb.pickle, "loads", unexpected_deserialization)
    conn = WorkerConnection([payload])
    rb._worker_main(conn, [], {})
    assert conn.closed
    assert conn.sent == [b"READY"]


@pytest.mark.parametrize("prctl_result,parent_alive", [(0, True), (1, True), (0, False)])
def test_linux_worker_requires_parent_death_guard(monkeypatch, prctl_result, parent_alive):
    monkeypatch.setattr(rb.sys, "platform", "linux")
    calls = []

    def prctl(*args):
        calls.append(args)
        return prctl_result

    monkeypatch.setattr(ctypes, "CDLL", lambda *args, **kwargs: SimpleNamespace(prctl=prctl))
    parent_pid = os.getppid()
    conn = WorkerConnection()
    rb._worker_main(conn, [], {"parent_pid": parent_pid if parent_alive else -1})
    assert calls == [(1, signal.SIGKILL, 0, 0, 0)]
    assert conn.closed
    assert conn.sent == ([b"READY"] if prctl_result == 0 and parent_alive else [])
    assert conn.reads == (1 if prctl_result == 0 and parent_alive else 0)


@pytest.mark.parametrize("hard_limit", [-1, 2])
def test_resource_limits_never_exceed_existing_hard_limits(monkeypatch, hard_limit):
    monkeypatch.setattr(rb.sys, "platform", "linux")
    limits = []
    resource = SimpleNamespace(
        RLIMIT_CORE=0,
        RLIMIT_CPU=1,
        RLIMIT_AS=2,
        RLIM_INFINITY=-1,
        getrlimit=lambda kind: (hard_limit, hard_limit),
        setrlimit=lambda kind, value: limits.append((kind, value)),
    )
    monkeypatch.setitem(rb.sys.modules, "resource", resource)

    rb._apply_os_hardening({"enabled": True, "rlimit_cpu": 5, "rlimit_as_mb": 8})

    cpu, memory = (5, 8 * 1024 * 1024) if hard_limit == -1 else (2, 2)
    assert limits == [(0, (0, 0)), (1, (cpu, cpu)), (2, (memory, memory))]
