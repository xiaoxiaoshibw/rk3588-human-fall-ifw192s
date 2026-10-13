#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""HFUS-RD-02 工作二：负例人工审核工作台（默认 :8932）。

只做三件事：
  GET /                    → 单页审核台（读 review_ui/review.html）
  GET /api/queue           → work/review_queue.json（冻结队列）
  POST /api/label          → append-only 写 work/review_labels.jsonl
                             body: {qid, label, note?, reviewer?}
                             label ∈ PERSON|FURNITURE|WALL_OR_FLOOR|OTHER_OBJECT|UNKNOWN
  GET /api/labels          → 已审标签汇总（续标用）

不写 GT、不写 captures、不改队列文件。未审核条目一律 UNKNOWN（不落盘）。
ponytail: 单文件 + 标准库 http.server；标签 append-only 天然防覆盖。
"""
import json
import os
import sys
from http import server as http_server
from pathlib import Path
from socketserver import ThreadingTCPServer

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent.parent
WORK = ROOT / "sidequests" / "HFUS-RD-02" / "work"
QUEUE = WORK / "review_queue.json"
LABELS = WORK / "review_labels.jsonl"
PORT = 8932

VALID = {"PERSON", "FURNITURE", "WALL_OR_FLOOR", "OTHER_OBJECT", "UNKNOWN"}


class H(http_server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, obj, code=200):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        p = self.path.split("?", 1)[0]
        if p == "/":
            html = (HERE / "review.html").read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(html)))
            self.end_headers()
            self.wfile.write(html)
        elif p == "/api/queue":
            if not QUEUE.exists():
                self._json({"error": "queue not built"}, 404)
                return
            self._json(json.loads(QUEUE.read_text(encoding="utf-8")))
        elif p == "/api/labels":
            rows = []
            if LABELS.exists():
                for line in LABELS.read_text(encoding="utf-8").splitlines():
                    if line.strip():
                        rows.append(json.loads(line))
            self._json({"labels": rows, "n": len(rows)})
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/api/label":
            self._json({"error": "not found"}, 404)
            return
        try:
            n = int(self.headers.get("Content-Length", "0"))
            body = json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            self._json({"error": "bad json"}, 400)
            return
        label = body.get("label")
        qid = body.get("qid")
        if label not in VALID or not qid:
            self._json({"error": "label/qid invalid"}, 400)
            return
        rec = {"qid": qid, "label": label,
               "note": (body.get("note") or "")[:500],
               "reviewer": (body.get("reviewer") or "anonymous")[:80],
               "ts": body.get("ts")}
        with open(LABELS, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        self._json({"ok": True, "qid": qid, "label": label})

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()


if __name__ == "__main__":
    print("HFUS-RD-02 review workbench: http://127.0.0.1:%d" % PORT)
    print("queue:", QUEUE, "| labels append →", LABELS)
    ThreadingTCPServer(("127.0.0.1", PORT), H).serve_forever()
