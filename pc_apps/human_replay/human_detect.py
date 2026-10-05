# -*- coding: utf-8 -*-
"""HR-W02 人体识别工作台 — 本地只读 API 插件。

与 leveling.py / validation.py 同构：Handler.handle(handler, method, root) 被
human_replay_lib.Handler._human_detect 调，只 locally 扫 root（=captures/remote），
不联系板、不做会话写。当前只有 sessions 一个 route；判别人/家具、姿态、平滑
完全由浏览器层（human_detect_lib.js）跑，板端无回路。

未来如需 POST（如保存 ROI / 导出报告），在 handle 内加 elif 分支，必须：
  - 校验 Origin == http://<Host>（参照 leveling.handle 的同源 gate）
  - 用 _SID 同款的 sid 白名单正则（防路径穿越）
  - 一律读 root/<sid>/... 且要求 os.path.realpath == 期望目录（防链接注入）
"""
import json
import os
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

_SID = re.compile(r"^cap_[0-9_]+$")


def _session_row(root, name):
    """最小描述（对齐 human_replay_lib._local_sessions 的字段名）。"""
    d = os.path.join(root, name)
    meta_p = os.path.join(d, "meta.json")
    bin_p = os.path.join(d, "points.bin")
    if not (os.path.isdir(d) and name.startswith("cap_")
            and os.path.isfile(meta_p) and os.path.isfile(bin_p)):
        return None
    row = {"sid": name}
    try:
        with open(meta_p, "r", encoding="utf-8") as fh:
            m = json.load(fh)
        row.update(
            duration_sec=m.get("duration_sec"),
            total_points=m.get("total_points"),
            frames=len(m.get("frames") or []),
            frame_rate_hz_measured=m.get("frame_rate_hz_measured"),
            created_iso=m.get("created_iso"),
            session_has_leveling=bool(m.get("leveling")),   # 仓内 meta 带 embedded leveling 表示已 leveled
            bytes=os.path.getsize(bin_p),
        )
    except Exception as exc:
        row["error"] = "meta 不可读: %s" % exc
    return row


def handle(handler, method, root):
    """Dispatches only /api/human_detect/*; callers (`human_replay_lib.Handler`) keep
    every existing replay/leveling/validation route."""
    parsed = urlparse(handler.path)
    query = parse_qs(parsed.query)
    try:
        if method != "GET":
            return handler.send_error(405)
        if parsed.path == "/api/human_detect/sessions":
            out = []
            if os.path.isdir(root):
                for name in sorted(os.listdir(root), reverse=True):
                    row = _session_row(root, name)
                    if row is not None:
                        out.append(row)
            return handler._json({"sessions": out})
        if parsed.path == "/api/human_detect/source":
            sid = (query.get("sid") or [""])[0]
            if not _SID.fullmatch(sid):
                raise ValueError("会话ID非法")
            d = Path(root).resolve() / sid
            if d.resolve() != d or not d.is_dir():
                raise ValueError("会话不存在或目录为链接")
            meta_p = d / "meta.json"
            bin_p = d / "points.bin"
            if not meta_p.is_file() or not bin_p.is_file():
                raise ValueError("会话缺 meta.json / points.bin")
            meta = json.loads(meta_p.read_text(encoding="utf-8"))
            return handler._json({"sid": sid, "meta": meta,
                                  "leveling_embedded": bool(meta.get("leveling"))})
        return handler.send_error(404)
    except (ValueError, TypeError, KeyError, OSError) as exc:
        return handler._json({"error": str(exc)}, 400)
