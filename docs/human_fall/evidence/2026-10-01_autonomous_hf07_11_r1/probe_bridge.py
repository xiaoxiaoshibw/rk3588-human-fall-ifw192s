#!/usr/bin/env python3
"""Read-only Foxglove WebSocket serverInfo/capabilities probe (stdlib only)."""

import base64
import hashlib
import json
import os
import socket
import struct
import time

HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("BRIDGE_PORT", "8765"))


def handshake(sock):
    key = base64.b64encode(os.urandom(16)).decode()
    request = (
        "GET / HTTP/1.1\r\n"
        "Host: {0}:{1}\r\n"
        "Upgrade: websocket\r\n"
        "Connection: Upgrade\r\n"
        "Sec-WebSocket-Key: {2}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n"
    ).format(HOST, PORT, key)
    sock.sendall(request.encode())
    headers = b""
    while b"\r\n\r\n" not in headers:
        chunk = sock.recv(4096)
        if not chunk:
            break
        headers += chunk
    return headers.decode("latin-1")


def recv_exact(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError("socket closed")
        data += chunk
    return data


def read_frame(sock):
    header = recv_exact(sock, 2)
    fin = header[0] & 0x80
    opcode = header[0] & 0x0F
    masked = header[1] & 0x80
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", recv_exact(sock, 8))[0]
    mask = recv_exact(sock, 4) if masked else b""
    payload = recv_exact(sock, length) if length else b""
    if masked:
        payload = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    return fin, opcode, payload


def main():
    sock = socket.create_connection((HOST, PORT), timeout=5)
    headers = handshake(sock)
    status = headers.split("\r\n")[0]
    print("HTTP_STATUS", status)
    sock.settimeout(3.0)
    ops = {}
    deadline = time.monotonic() + 3.0
    while time.monotonic() < deadline:
        try:
            fin, opcode, payload = read_frame(sock)
        except (socket.timeout, EOFError):
            break
        if opcode == 1:
            try:
                message = json.loads(payload.decode("utf-8"))
            except ValueError:
                continue
            op = message.get("op")
            ops[op] = ops.get(op, 0) + 1
            if op == "serverInfo":
                print("serverInfo", json.dumps(message, ensure_ascii=False))
            if op == "advertise":
                channels = message.get("channels", [])
                topics = [c.get("topic") for c in channels]
                print("advertise_topics", json.dumps(sorted(t for t in topics if t), ensure_ascii=False))
        if ops.get("serverInfo") and ops.get("advertise"):
            # keep reading briefly to catch any further ops
            pass
    print("op_counts", json.dumps(ops, sort_keys=True))
    print("PROBE_DONE")


if __name__ == "__main__":
    main()
