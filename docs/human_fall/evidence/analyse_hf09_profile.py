"""Read-only summary of recorded finite telemetry, without inventing missing baselines."""
import hashlib
import json
import statistics
import sys
from pathlib import Path

path = Path(sys.argv[1])
rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
if not rows:
    raise SystemExit("no rows")
total_s = sum(row["window_s"] for row in rows)
result = {"source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
          "row_count": len(rows), "recorded_window_s": round(total_s, 3),
          "first_t_rel_s": rows[0]["t_rel_s"], "last_t_rel_s": rows[-1]["t_rel_s"],
          "queue_count_at_first_row": rows[0]["queue_dropped_total"],
          "queue_count_at_last_row": rows[-1]["queue_dropped_total"],
          "queue_increment_between_first_and_last_rows":
              rows[-1]["queue_dropped_total"] - rows[0]["queue_dropped_total"],
          "full_capture_queue_increment": None,
          "note": "Queue baseline at capture start was not recorded; between-row increment excludes the first window. No frozen performance threshold or thermal throttling measurement."}
for name in ("cpu_pct", "rss_mb", "temp_c", "input_hz", "processed_hz"):
    values = [row[name] for row in rows if isinstance(row.get(name), (int, float))]
    result[name] = {"min": min(values), "median": statistics.median(values), "max": max(values)} if values else None
    if values and name in ("cpu_pct", "input_hz", "processed_hz"):
        weighted = [(row[name], row["window_s"]) for row in rows if isinstance(row.get(name), (int, float))]
        result[name]["time_weighted_mean"] = round(sum(v * dt for v, dt in weighted) / sum(dt for _, dt in weighted), 4)
result["rss_first_mb"] = rows[0]["rss_mb"]
result["rss_last_mb"] = rows[-1]["rss_mb"]
result["rss_endpoint_change_mb"] = round(result["rss_last_mb"] - result["rss_first_mb"], 4)
print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
