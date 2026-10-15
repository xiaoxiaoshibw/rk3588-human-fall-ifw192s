"""T1 会话清点：本地 captures/remote + 板端 :8766 只读 API。

用法：
    python -B -W error inventory.py --out <evidence_dir>
不写任何会话数据；板端只做 GET（超时/不可达 → 显式 BLOCKED，不重试）。
分类字段（空场/小飞机/人）只来自既有证据与本地扫描，未核实写 UNKNOWN。
"""
import argparse
import json
import socket
import urllib.request
from pathlib import Path

from common import REMOTE

# 已核实角色（来源见 docs/；只在字符串里引用证据路径，不在本脚本里改证据）
KNOWN_ROLES = {
    "cap_20261010_175227": {"scene": "empty_with_furniture", "source": "docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1/ACTION_CATALOG.md S1-empty-with-furniture (304帧)"},
    "cap_20261010_175429": {"scene": "person_S3_walk_x_near", "source": "ACTION_CATALOG.md S3-walk-x-near (258帧)"},
    "cap_20261010_175553": {"scene": "person_S3_walk_y_far", "source": "ACTION_CATALOG.md S3-walk-y-far (464帧)"},
    "cap_20261010_175804": {"scene": "person_S4_walk_stop_walk", "source": "ACTION_CATALOG.md S4-walk-stop-walk (239帧)"},
    "cap_20261010_175943": {"scene": "person_S5_turn_in_place", "source": "ACTION_CATALOG.md S5-turn-in-place (202帧)"},
    "cap_20261010_180235": {"scene": "person_S6_occlusion", "source": "ACTION_CATALOG.md S6-occlusion (238帧)"},
    "cap_20261010_180337": {"scene": "person_S7_far_5m", "source": "ACTION_CATALOG.md S7-far-5m (251帧)"},
    "cap_20261010_180557": {"scene": "person_S8_still_retention_long", "source": "ACTION_CATALOG.md S8-still-retention-long (523帧)"},
    "cap_20261010_180751": {"scene": "person_S9_two_person_cross", "source": "ACTION_CATALOG.md S9-two-person-cross INVALID_BINDING (126帧)"},
    "cap_20261013_131958": {"scene": "empty", "source": "docs/human_fall/evidence/2026-10-13_hf_real_02_r1 (空场配平注册)"},
    "cap_20261013_094333": {"scene": "person_ko", "source": "docs/human_fall/evidence/2026-10-13_hf_real_01_r1 (真人场景)"},
    "cap_20261013_093958": {"scene": "person_ko", "source": "docs/human_fall/evidence/2026-10-13_hf_real_01_r1 (DATA_BAD per HF-REAL-03)"},
    "cap_20261013_094302": {"scene": "unknown_person_candidate", "source": "docs/human_capture/returns/CAM-HOT.md:42 无相机历史；本轮新下载"},
    "cap_20261014_164522": {"scene": "small_compact_target_R6.5m", "source": "本工单已核实：唯一紧凑目标 R≈6.5m、离地≈3.0m、细长静止结构（吊灯/挂钩/小飞机 UNKNOWN，见 05_TARGET_IDENTITY.json）"},
    "cap_20261011_151639": {"scene": "unknown", "source": None},
}


def local_catalog():
    rows = []
    for path in sorted(REMOTE.iterdir()):
        if not path.is_dir():
            continue
        sid = path.name
        try:
            meta = json.loads((path / "meta.json").read_text(encoding="utf8"))
        except Exception as exc:  # noqa: BLE001 - report and continue
            rows.append({"sid": sid, "error": str(exc)})
            continue
        frames = meta.get("frames", [])
        bag = (meta.get("extraction") or {}).get("source_bag")
        role = KNOWN_ROLES.get(sid, {"scene": "unknown", "source": None})
        rows.append({
            "sid": sid,
            "frames": len(frames),
            "duration_sec": meta.get("duration_sec"),
            "total_points": int(meta.get("total_points", 0)),
            "point_stride_bytes": meta.get("point_stride_bytes"),
            "bin_bytes": (path / "points.bin").stat().st_size if (path / "points.bin").exists() else None,
            "source_bag": bag,
            "created_iso": meta.get("created_iso"),
            "has_human_annotations": bool(meta.get("human_annotations")),
            "scene": role["scene"],
            "scene_source": role["source"],
            "joint": "_joint_" in sid,
        })
    return rows


def board_catalog(timeout=6.0):
    """Read-only GET on the board REST API; explicit BLOCKED on any failure."""
    url = "http://192.168.31.58:8766/api/v1/sessions"
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf8"))
        return {"status": "PASS", "url": url, "payload": payload}
    except (OSError, socket.timeout, ValueError) as exc:
        return {"status": "BLOCKED", "url": url, "error": "%s: %s" % (type(exc).__name__, exc)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--no-board", action="store_true")
    parser.add_argument("--timeout", type=float, default=6.0)
    parser.add_argument("--name", default="01_INVENTORY.json")
    parser.add_argument("--markdown", default=None)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    payload = {"local": local_catalog()}
    payload["board"] = {"status": "NOT_RUN", "reason": "--no-board"} if args.no_board \
        else board_catalog(args.timeout)
    text = json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)
    with (out / args.name).open("x", encoding="utf8") as stream:
        stream.write(text)
    if args.markdown:
        board = {s["session_id"]: s for s in payload["board"].get("payload", {}).get("sessions", [])}
        lines = ["| sid | 帧 | 时长s | 点数 | 来源 | 场景 | 板端状态 | 配平产物 |", "|---|---:|---:|---:|---|---|---|---|"]
        for row in payload["local"]:
            board_row = board.get(row["sid"], {})
            lines.append("| %s | %s | %s | %s | %s | %s | %s | |" % (
                row["sid"], row.get("frames"), None if row.get("duration_sec") is None else round(row["duration_sec"], 1),
                row.get("total_points"), "joint-local" if row.get("joint") else "bag", row["scene"],
                board_row.get("state", "board-local-only")))
        with (out / args.markdown).open("x", encoding="utf8") as stream:
            stream.write("\n".join(lines) + "\n")
    print(json.dumps({"local_sessions": len(payload["local"]), "board": payload["board"]["status"],
                      "board_error": payload["board"].get("error")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
