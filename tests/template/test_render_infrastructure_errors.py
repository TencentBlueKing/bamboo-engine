# -*- coding: utf-8 -*-
"""Infrastructure failures must be distinguishable from legitimate template text."""
import pytest

from bamboo_engine.exceptions import RenderInfrastructureError
from bamboo_engine.template import render_backend as rb
from tests.template.test_render_backend_failures import pool, provider


@pytest.mark.parametrize("failure", ["start", "protocol", "rejected", "request_size"])
def test_infrastructure_failure_raises_without_inprocess_retry(monkeypatch, failure):
    backend = pool(fallback_inprocess=True)
    inprocess_calls = []

    def no_host_render(*args):
        inprocess_calls.append(args)
        return "incorrect host retry"

    def fail_start():
        raise OSError("synthetic process quota")

    def fail_protocol(*args):
        raise rb.ProtocolError("synthetic invalid worker reply")

    monkeypatch.setattr(backend._inprocess, "render", no_host_render)
    if failure == "start":
        monkeypatch.setattr(backend, "_spawn_worker", fail_start)
    elif failure == "protocol":
        monkeypatch.setattr(rb._RenderWorker, "request", fail_protocol)
    elif failure == "rejected":
        monkeypatch.setattr(rb._RenderWorker, "request", lambda *args: (rb._STATUS_ERR, "untrusted details"))
    else:
        # Portable values fit, but the framed request plus its spec does not.
        monkeypatch.setattr(rb, "MAX_REQUEST_BYTES", 1)
    try:
        with pytest.raises(RenderInfrastructureError) as raised:
            backend.render("${x + 1}", {"x": 2}, provider())
        assert raised.value.reason == "worker_failure"
        assert "untrusted details" not in str(raised.value)
        assert inprocess_calls == []
    finally:
        backend.close()


def test_closed_backend_is_an_explicit_failure():
    backend = pool()
    backend.close()
    with pytest.raises(RenderInfrastructureError) as raised:
        backend.render("${x + 1}", {"x": 2}, provider())
    assert raised.value.reason == "backend_closed"


def test_supervisor_start_failure_is_explicit_and_slot_can_recover(monkeypatch):
    backend = pool()
    start = rb.threading.Thread.start

    def fail_start(thread):
        raise RuntimeError("synthetic thread quota")

    monkeypatch.setattr(rb.threading.Thread, "start", fail_start)
    try:
        with pytest.raises(RenderInfrastructureError) as raised:
            backend.render("${x + 1}", {"x": 2}, provider())
        assert raised.value.reason == "supervisor_start_failed"
        monkeypatch.setattr(rb.threading.Thread, "start", start)
        assert backend.render("${x + 1}", {"x": 2}, provider()) == "3"
    finally:
        backend.close()
