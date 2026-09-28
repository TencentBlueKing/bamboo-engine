# -*- coding: utf-8 -*-
"""Bounded, non-executable worker replies and deadline-aware POSIX socket framing."""
import json
import socket
import struct
import time


MAX_REQUEST_BYTES = 8 * 1024 * 1024
MAX_RESPONSE_BYTES = 8 * 1024 * 1024


class RenderTimeout(Exception):
    pass


class ProtocolError(ValueError):
    pass


def remaining(deadline):
    left = deadline - time.monotonic()
    if left <= 0:
        raise RenderTimeout()
    return left


def encode_reply(status, result, request_id="0" * 32):
    if type(status) is not int or status not in (0, 1) or type(result) is not str:
        raise ProtocolError("invalid render reply")
    if len(result) > MAX_RESPONSE_BYTES:
        raise ProtocolError("render reply too large")
    data = json.dumps([1, request_id, status, result], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    if len(data) > MAX_RESPONSE_BYTES:
        raise ProtocolError("render reply too large")
    return data


def decode_reply(data, request_id="0" * 32):
    if len(data) > MAX_RESPONSE_BYTES:
        raise ProtocolError("render reply too large")
    # Require the canonical, fixed header BEFORE invoking the JSON decoder. Only a
    # string is then parsed: a hostile nested object or giant integer cannot allocate
    # an arbitrarily large object graph or monopolize the host's integer conversion.
    prefix = b'[1,"' + request_id.encode("ascii") + b'",'
    if not data.startswith(prefix) or not data.endswith(b"]"):
        raise ProtocolError("invalid render reply header")
    body = data[len(prefix) :]
    if body[:3] not in (b'0,"', b'1,"'):
        raise ProtocolError("invalid render reply body")
    try:
        result = json.loads(body[2:-1].decode("utf-8"))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ProtocolError("invalid render reply") from exc
    if type(result) is not str:
        raise ProtocolError("invalid render reply")
    return [int(body[:1]), result]


class SocketConnection:
    """One uint32 length followed by bytes; check size before allocating a body."""

    def __init__(self, sock):
        self.sock = sock

    def _timeout(self, deadline):
        self.sock.settimeout(None if deadline is None else remaining(deadline))

    def send_bytes(self, data, deadline=None, max_bytes=MAX_REQUEST_BYTES):
        if len(data) > max_bytes:
            raise ProtocolError("render request too large")
        try:
            # Keep the header and body separate: do not copy a large request again.
            for part in (struct.pack("!I", len(data)), data):
                view = memoryview(part)
                while view:
                    self._timeout(deadline)
                    sent = self.sock.send(view)
                    if not sent:
                        raise EOFError()
                    view = view[sent:]
        except socket.timeout as exc:
            raise RenderTimeout() from exc

    def _read(self, size, deadline):
        chunks = bytearray()
        while len(chunks) < size:
            self._timeout(deadline)
            chunk = self.sock.recv(min(size - len(chunks), 65536))
            if not chunk:
                raise EOFError()
            chunks.extend(chunk)
        return bytes(chunks)

    def recv_bytes(self, deadline=None, max_bytes=MAX_RESPONSE_BYTES):
        try:
            size = struct.unpack("!I", self._read(4, deadline))[0]
            if size > max_bytes:
                raise ProtocolError("render frame too large")
            return self._read(size, deadline)
        except socket.timeout as exc:
            raise RenderTimeout() from exc

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass
