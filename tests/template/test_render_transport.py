# -*- coding: utf-8 -*-
import socket
import struct
import threading
import time

import pytest

from bamboo_engine.template.render_transport import (
    SocketConnection,
    RenderTimeout,
    ProtocolError,
    decode_reply,
    encode_reply,
)


@pytest.mark.parametrize(
    "data",
    [
        b'[true,"x"]',
        b'[2,"x"]',
        b"[0,{}]",
        b"[0,1]",
        b'[0,"x","extra"]',
        b"null",
        b"[0,NaN]",
        b"[0,1e9]",
        b"[0," + b"9" * 100000 + b"]",
        b"[" * 2000,
        b"\xff",
    ],
)
def test_invalid_reply_is_rejected(data):
    with pytest.raises(ProtocolError):
        decode_reply(data)


def test_text_reply_roundtrip():
    assert decode_reply(encode_reply(0, '中文\n"\\')) == [0, '中文\n"\\']


def test_reply_from_another_request_is_rejected():
    with pytest.raises(ProtocolError):
        decode_reply(encode_reply(0, "old result", "a" * 32), "b" * 32)


def test_partial_reply_does_not_escape_deadline():
    parent, child = socket.socketpair()
    conn = SocketConnection(parent)
    try:
        child.sendall(struct.pack("!I", 200) + b"[")
        start = time.monotonic()
        with pytest.raises(RenderTimeout):
            conn.recv_bytes(deadline=start + 0.05)
        assert time.monotonic() - start < 0.5
    finally:
        conn.close()
        child.close()


def test_slow_trickle_cannot_extend_deadline():
    parent, child = socket.socketpair()
    conn = SocketConnection(parent)
    child.sendall(struct.pack("!I", 200))

    def trickle():
        try:
            for _ in range(20):
                child.sendall(b"x")
                time.sleep(0.02)
        except OSError:
            pass

    thread = threading.Thread(target=trickle)
    thread.start()
    try:
        start = time.monotonic()
        with pytest.raises(RenderTimeout):
            conn.recv_bytes(deadline=start + 0.08)
        assert time.monotonic() - start < 0.5
    finally:
        conn.close()
        thread.join(1)
        child.close()


def test_nonreading_worker_cannot_block_large_request():
    parent, child = socket.socketpair()
    parent.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 4096)
    conn = SocketConnection(parent)
    try:
        start = time.monotonic()
        with pytest.raises(RenderTimeout):
            conn.send_bytes(b"x" * (2 * 1024 * 1024), deadline=start + 0.05)
        assert time.monotonic() - start < 0.5
    finally:
        conn.close()
        child.close()


def test_oversized_frame_rejected_before_body_read():
    parent, child = socket.socketpair()
    conn = SocketConnection(parent)
    try:
        child.sendall(struct.pack("!I", 0xFFFFFFFF))
        with pytest.raises(ProtocolError):
            conn.recv_bytes(deadline=time.monotonic() + 0.1)
    finally:
        conn.close()
        child.close()
