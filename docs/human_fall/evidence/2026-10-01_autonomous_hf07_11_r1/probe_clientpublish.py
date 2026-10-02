#!/usr/bin/env python3
"""Validate Foxglove bridge clientPublish for /human_fall/selection_request.

Publishes a synthetic std_msgs/String over the existing bridge with the exact
ros1 client-message wire format the preview page will use. Read-only elsewhere.
"""

import base64
import json
import os
import socket
import struct
import time

HOST = os.environ.get("BRIDGE_HOST", "127.0.0.1")
PORT = int(os.environ.get("BRIDGE_PORT", "8765"))
TOPIC = os.environ.get("TEST_TOPIC", "/hf11_clientpub_test")
PAYLOAD_TEXT = os.environ.get("TEST_TEXT", '{"hello":"clientPublish"}')


def handshake(sock):
    key = base64.b64encode(os.urandom(16)).decode()
    sock.sendall((
        "GET / HTTP/1.1\r\nHost: {0}:{1}\r\nUpgrade: websocket\r\n"
        "Connection: Upgrade\r\nSec-WebSocket-Key: {2}\r\n"
        "Sec-WebSocket-Version: 13\r\n"
        "Sec-WebSocket-Protocol: foxglove.websocket.v1\r\n\r\n"
    ).format(HOST, PORT, key).encode())
    data = b""
    while b"\r\n\r\n" not in data:
        data += sock.recv(4096)
    return data.decode("latin-1")


def send_text(sock, text):
    payload = text.encode("utf-8")
    _send(sock, 0x1, payload)


def send_binary(sock, payload):
    _send(sock, 0x2, payload)


def _send(sock, opcode, payload):
    mask = os.urandom(4)
    masked = bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    header = bytes([0x80 | opcode])
    length = len(payload)
    if length < 126:
        header += bytes([0x80 | length])
    elif length < 65536:
        header += bytes([0x80 | 126]) + struct.pack(">H", length)
    else:
        header += bytes([0x80 | 127]) + struct.pack(">Q", length)
    sock.sendall(header + mask + masked)


def recv_exact(sock, count):
    data = b""
    while len(data) < count:
        chunk = sock.recv(count - len(data))
        if not chunk:
            raise EOFError
        data += chunk
    return data


def read_frame(sock):
    header = recv_exact(sock, 2)
    opcode = header[0] & 0x0F
    length = header[1] & 0x7F
    if length == 126:
        length = struct.unpack(">H", recv_exact(sock, 2))[0]
    elif length == 127:
        length = struct.unpack(">Q", recv_exact(sock, 8))[0]
    return opcode, recv_exact(sock, length)


def main():
    sock = socket.create_connection((HOST, PORT), timeout=5)
    print("HTTP_STATUS", handshake(sock).split("\r\n")[0])
    sock.settimeout(2.0)
    opcode, payload = read_frame(sock)
    info = json.loads(payload.decode())
    print("serverInfo", json.dumps(info))
    print("clientPublish_supported", "clientPublish" in info.get("capabilities", []))
    print("supportedEncodings", info.get("supportedEncodings"))

    advertise = {"op": "advertise", "channels": [{
        "id": 1, "topic": TOPIC, "encoding": "ros1",
        "schemaName": "std_msgs/String", "schema": "string data\n",
        "schemaEncoding": "ros1msg"}]}
    send_text(sock, json.dumps(advertise))
    time.sleep(0.5)

    text = PAYLOAD_TEXT.encode("utf-8")
    ros1_payload = struct.pack("<I", len(text)) + text
    client_message = bytes([0x01]) + struct.pack("<I", 1) + ros1_payload
    for _ in range(3):
        send_binary(sock, client_message)
        time.sleep(0.3)
    print("published_bytes", len(client_message))

    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        try:
            op, data = read_frame(sock)
        except (socket.timeout, EOFError):
            break
        if op == 0x1:
            try:
                msg = json.loads(data.decode())
            except ValueError:
                continue
            if msg.get("op") in ("status", "statusMessage"):
                print("server_status", json.dumps(msg))
    send_text(sock, json.dumps({"op": "unadvertise", "channelIds": [1]}))
    sock.close()
    print("PROBE_DONE")


if __name__ == "__main__":
    main()
