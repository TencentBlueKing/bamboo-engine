# -*- coding: utf-8 -*-
"""Regression tests for the isolation boundary and bounded pool lifecycle."""
import multiprocessing
import os
import pickle
import subprocess
import threading
import time
from collections import Counter, namedtuple

import pytest

from bamboo_engine.template import render_backend as rb
from bamboo_engine.template import sandbox
from bamboo_engine.exceptions import RenderInfrastructureError


def provider():
    return rb.SandboxProvider(sandbox.get, rb.SandboxSpec("engine", [], {}))


def pool(**kwargs):
    opts = dict(pool_size=1, timeout=3, os_harden=False, no_network=False)
    opts.update(kwargs)
    return rb.SubprocessPoolRenderBackend(**opts)


_REPLY_EXECUTED = []


def mark_reply_execution():
    _REPLY_EXECUTED.append(True)
    return "executed"


class ExecutableReply:
    def __reduce__(self):
        return mark_reply_execution, ()


class ReplyConnection:
    def send_bytes(self, *args, **kwargs):
        pass

    def poll(self, *args):
        return True

    def recv_bytes(self, *args, **kwargs):
        return pickle.dumps((0, ExecutableReply()))


def test_worker_reply_cannot_execute_in_parent():
    worker = object.__new__(rb._RenderWorker)
    worker._conn = ReplyConnection()
    worker.uses = 0
    _REPLY_EXECUTED[:] = []
    try:
        worker.request(b"request", 1)
    except (ValueError, UnicodeError):
        pass
    assert _REPLY_EXECUTED == []


def _daemon_render(out):
    backend = pool()
    try:
        out.put(backend.render("${x+1}", {"x": 2}, provider()))
    except Exception as exc:
        out.put(type(exc).__name__)
    finally:
        backend.close()


def test_real_daemon_host_can_render():
    ctx = multiprocessing.get_context("spawn")
    out = ctx.Queue()
    process = ctx.Process(target=_daemon_render, args=(out,), daemon=True)
    process.start()
    try:
        assert out.get(timeout=8) == "3"
    finally:
        process.join(3)
        if process.is_alive():
            process.terminate()
            process.join(2)
        out.close()


Record = namedtuple("Record", "name")


class WithProperty:
    def __init__(self):
        self.value = 7

    @property
    def double(self):
        return self.value * 2


@pytest.mark.parametrize(
    "template,value,expected",
    [
        ("${v.tm_year}", time.gmtime(0), "1970"),
        ("${v.most_common(1)}", Counter("aab"), "[('a', 2)]"),
        ("${v.name}", Record("prod"), "prod"),
        ("${v.double}", WithProperty(), "14"),
    ],
)
def test_rich_context_never_silently_loses_behavior(template, value, expected):
    backend = pool(fallback_inprocess=True)
    try:
        assert backend.render(template, {"v": value}, provider()) == expected
    finally:
        backend.close()


def test_recycle_does_not_mask_success_and_spawn_failure_can_recover(monkeypatch):
    backend = pool(max_uses=1)
    spawn = backend._spawn_worker
    calls = []

    def fail_second_spawn():
        calls.append(1)
        if len(calls) == 2:
            raise OSError(11, "synthetic process quota")
        return spawn()

    monkeypatch.setattr(backend, "_spawn_worker", fail_second_spawn)
    try:
        assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
        with pytest.raises(RenderInfrastructureError, match="worker_failure"):
            backend.render("${x+1}", {"x": 2}, provider())
        assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
    finally:
        backend.close()


def test_startup_and_admission_share_deadline(monkeypatch):
    backend = pool(timeout=0.1)
    entered = threading.Event()
    release = threading.Event()
    spawn = backend._spawn_worker

    def stalled_spawn():
        entered.set()
        release.wait(1)
        return spawn()

    monkeypatch.setattr(backend, "_spawn_worker", stalled_spawn)
    try:
        start = time.monotonic()
        with pytest.raises(RenderInfrastructureError, match="deadline_exceeded"):
            backend.render("${x+1}", {"x": 2}, provider())
        assert time.monotonic() - start < 0.5
        assert entered.is_set()
        start = time.monotonic()
        with pytest.raises(RenderInfrastructureError, match="admission_timeout"):
            backend.render("${x+1}", {"x": 2}, provider())
        assert time.monotonic() - start < 0.5
    finally:
        release.set()
        backend.close()


def test_missing_spec_honors_strict_policy():
    backend = pool()
    try:
        assert backend.render("${x+1}", {"x": 2}, sandbox.get) == "${x+1}"
    finally:
        backend.close()


def test_worker_error_cannot_force_opted_in_fallback(monkeypatch):
    backend = pool(fallback_inprocess=True)

    def broken_reply(*args, **kwargs):
        raise rb.ProtocolError("synthetic invalid worker reply")

    monkeypatch.setattr(rb._RenderWorker, "request", broken_reply)
    try:
        with pytest.raises(RenderInfrastructureError, match="worker_failure"):
            backend.render("${x+1}", {"x": 2}, provider())
    finally:
        backend.close()


def test_no_network_requirement_fails_closed(monkeypatch):
    monkeypatch.setattr(rb.sys, "platform", "darwin")
    with pytest.raises(RuntimeError):
        rb._apply_os_hardening({"enabled": True, "no_network": True})


def test_late_cancel_does_not_kill_worker_reused_by_next_job(monkeypatch):
    backend = pool()
    jobs = []
    run = backend._run

    def capture(job, *args):
        jobs.append(job)
        return run(job, *args)

    monkeypatch.setattr(backend, "_run", capture)
    try:
        assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
        request = rb._RenderWorker.request

        def cancel_previous(worker, *args):
            jobs[0].cancel()
            return request(worker, *args)

        monkeypatch.setattr(rb._RenderWorker, "request", cancel_previous)
        assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
    finally:
        backend.close()


def test_close_wakes_callers_waiting_for_a_slot(monkeypatch):
    backend = pool(timeout=5)
    entered = threading.Event()
    release = threading.Event()
    results = []

    def stalled_spawn():
        entered.set()
        release.wait(2)
        raise OSError("cancelled synthetic launch")

    monkeypatch.setattr(backend, "_spawn_worker", stalled_spawn)

    def render_until_closed():
        try:
            results.append(backend.render("${x+1}", {"x": 2}, provider()))
        except RenderInfrastructureError as exc:
            results.append(exc.reason)

    callers = [threading.Thread(target=render_until_closed) for _ in range(2)]
    try:
        callers[0].start()
        assert entered.wait(1)
        callers[1].start()
        backend.close()
        for caller in callers:
            caller.join(0.5)
            assert not caller.is_alive()
        assert results == ["backend_closed", "backend_closed"]
    finally:
        release.set()
        backend.close()


def test_unsupported_property_is_rejected_before_lossy_conversion():
    with pytest.raises(rb.UnsupportedContext):
        rb._portable_context({"v": WithProperty()})


def test_cycles_and_excessive_object_counts_are_rejected(monkeypatch):
    cyclic = []
    cyclic.append(cyclic)
    with pytest.raises(rb.UnsupportedContext):
        rb._portable_context({"v": cyclic})
    monkeypatch.setattr(rb, "_PORTABLE_MAX_ITEMS", 10)
    with pytest.raises(rb.UnsupportedContext):
        rb._portable_context({"v": list(range(100))})


def test_pool_concurrent_requests_return_their_own_results():
    from concurrent.futures import ThreadPoolExecutor

    backend = pool(pool_size=2, max_uses=3, timeout=5)
    try:
        with ThreadPoolExecutor(max_workers=8) as executor:
            results = list(executor.map(lambda n: backend.render("${x+1}", {"x": n}, provider()), range(24)))
        assert results == [str(n) for n in range(1, 25)]
    finally:
        backend.close()


def test_unreaped_worker_keeps_its_slot(monkeypatch):
    backend = pool(max_uses=1)
    entered = threading.Event()
    release = threading.Event()
    stop = rb._RenderWorker.stop

    def delayed_reap(worker):
        if not release.is_set():
            entered.set()
            worker.kill()
            return False
        return stop(worker)

    monkeypatch.setattr(rb._RenderWorker, "stop", delayed_reap)
    try:
        assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
        assert entered.wait(1)
        # The short deadline tests admission while reaping, not worker startup.
        backend.timeout = 0.2
        with pytest.raises(RenderInfrastructureError, match="admission_timeout"):
            backend.render("${x+1}", {"x": 2}, provider())
    finally:
        release.set()
        backend.close()


def test_close_handles_dequeued_but_not_registered_slot(monkeypatch):
    backend = pool()
    assert backend.render("${x+1}", {"x": 2}, provider()) == "3"
    entered = threading.Event()
    release = threading.Event()
    get = backend._idle.get

    def delayed_get(*args, **kwargs):
        slot = get(*args, **kwargs)
        if kwargs.get("block") is not False:
            entered.set()
            release.wait(1)
        return slot

    monkeypatch.setattr(backend._idle, "get", delayed_get)
    errors = []

    def render_until_closed():
        try:
            backend.render("${x+1}", {"x": 2}, provider())
        except RenderInfrastructureError as exc:
            errors.append(exc.reason)

    caller = threading.Thread(target=render_until_closed)
    try:
        caller.start()
        assert entered.wait(1)
        backend.close()
        release.set()
        caller.join(1)
        assert errors == ["backend_closed"]
        for slot in backend._slots:
            if slot.thread is not None:
                slot.thread.join(1)
                assert not slot.thread.is_alive()
    finally:
        release.set()
        backend.close()


def test_caller_interruption_cancels_its_job(monkeypatch):
    backend = pool()
    jobs = []
    init = rb._RenderJob.__init__

    def interrupt_init(job, *args):
        init(job, *args)
        jobs.append(job)

        def interrupted(*args):
            raise KeyboardInterrupt()

        job.done.wait = interrupted

    monkeypatch.setattr(rb._RenderJob, "__init__", interrupt_init)
    try:
        with pytest.raises(KeyboardInterrupt):
            backend.render("${x+1}", {"x": 2}, provider())
        assert jobs[0].cancelled.is_set()
    finally:
        backend.close()


@pytest.mark.skipif(not hasattr(os, "fork"), reason="POSIX fork lifecycle")
def test_fork_closes_transports_of_worker_still_starting(monkeypatch):
    backend = pool(timeout=2)
    entered = threading.Event()
    release = threading.Event()
    popen = subprocess.Popen

    def stalled_popen(*args, **kwargs):
        entered.set()
        release.wait(2)
        return popen(*args, **kwargs)

    monkeypatch.setattr(subprocess, "Popen", stalled_popen)
    results = []
    caller = threading.Thread(target=lambda: results.append(backend.render("${x+1}", {"x": 2}, provider())))
    try:
        caller.start()
        assert entered.wait(1)
        fds = [sock.fileno() for sock in rb._WORKER_SOCKETS]
        assert len(fds) >= 2
        child = os.fork()
        if child == 0:
            try:
                backend._ensure_process()
                for fd in fds:
                    try:
                        os.fstat(fd)
                    except OSError:
                        continue
                    os._exit(2)
                os._exit(0)
            except BaseException:
                os._exit(3)
        _, status = os.waitpid(child, 0)
        assert status == 0
        release.set()
        caller.join(3)
        assert results == ["3"]  # closing child copies did not damage parent transport
    finally:
        release.set()
        backend.close()
