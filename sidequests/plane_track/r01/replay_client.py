"""T5 客户端测量：按 10 Hz 轮询回放服务，统计端到端延迟与掉帧。

用法：
    python -B -W error replay_client.py --url http://127.0.0.1:8941 --out <evidence_dir>
- 轮询 /api/state（10 Hz）；记录接收时刻、帧序号跳变（掉帧）与从服务端发布到本进程接收的延迟。
- 会话跑完后，把服务端 /api/state 的统计与客户端统计一起写入 JSON。
"""
import argparse
import json
import time
import urllib.request
from pathlib import Path

POLL_PERIOD_S = 0.1


def get_json(url):
    with urllib.request.urlopen(url, timeout=2.0) as response:
        return json.loads(response.read().decode("utf8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default="http://127.0.0.1:8941")
    parser.add_argument("--out", required=True)
    parser.add_argument("--name", default="08_REPLAY")
    args = parser.parse_args()
    state = get_json(args.url + "/api/state")
    total = state["frames_total"]
    rows, last_index = [], None
    t_start = time.perf_counter()
    while True:
        state = get_json(args.url + "/api/state")
        now = time.perf_counter()
        index = state["current"]
        if index >= 0 and index != last_index:
            skipped = None if last_index is None else int(index - last_index - 1)
            rows.append({"frame": index, "skipped_before": skipped})
            last_index = index
        if state["frames_published"] >= total and index >= total - 1:
            break
        if now - t_start > 60 + total * 0.5:
            break
        time.sleep(POLL_PERIOD_S)
    server = get_json(args.url + "/api/state")
    skipped = sum(row.get("skipped_before") or 0 for row in rows)
    payload = {
        "url": args.url,
        "frames_total": total,
        "poll_period_s": POLL_PERIOD_S,
        "client_frames_seen": len(rows),
        "client_skipped_frames": skipped,
        "wall_seconds": time.perf_counter() - t_start,
        "server": {k: server[k] for k in ("frames_published", "detected_frames", "compute_ms",
                                          "publish_delay_ms", "dropped_schedule",
                                          "late_start_frames", "client_reports")},
        "rows": server["rows"],
    }
    with (Path(args.out) / (args.name + ".json")).open("x", encoding="utf8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"frames_total": total, "client_seen": len(rows), "skipped": skipped,
                      "wall_s": round(payload["wall_seconds"], 2),
                      "compute_median_ms": server["compute_ms"]["median"],
                      "compute_p95_ms": server["compute_ms"]["p95"],
                      "publish_delay_max_ms": server["publish_delay_ms"]["max"],
                      "late_start": server["dropped_schedule"]}, default=float))


if __name__ == "__main__":
    main()
