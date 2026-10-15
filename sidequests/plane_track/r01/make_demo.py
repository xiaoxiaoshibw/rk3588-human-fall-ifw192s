"""生成 10 Hz 演示页（自包含 HTML，无需服务端；证据/展示用）。

用法：
    python -B -W error make_demo.py --out <evidence_dir> [--job <job_id>] [--stride 8]
读取配平后的 164522（TLS 显示系），用与 plane_track.py 相同的候选层+跟踪逻辑逐帧算目标，
把 27 帧的房间点（抽稀）+ 目标点 + 每帧统计写成可循环播放的 HTML（默认 10 Hz）。
"""
import argparse
import json
from pathlib import Path

import numpy as np

from plane_track import GATE_M, load_leveled_frames, run_frames, snapshot_settings, streak_m, track

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 10 Hz 演示（164522 小目标跟踪）</title>
<style>
 body{font-family:Consolas,monospace;background:#101418;color:#dfe6ee;margin:0;padding:14px}
 canvas{background:#0b0e12;border:1px solid #2a3541}
 .row{display:flex;gap:12px;flex-wrap:wrap}
 #hud{white-space:pre;font-size:13.5px;line-height:1.5;margin-top:10px}
 button{background:#1d2a36;color:#dfe6ee;border:1px solid #2a3541;padding:6px 12px;font:inherit;cursor:pointer}
 button:hover{background:#26404f}
 .note{color:#8ba1b7;font-size:12px;margin-top:8px;max-width:1150px}
</style></head><body>
<h3>PLANE-01 效果展示：cap_20261014_164522 目标跟踪（10 Hz，源帧真实节奏，循环播放）</h3>
<div class="row">
  <canvas id="top" width="560" height="440"></canvas>
  <canvas id="side" width="560" height="440"></canvas>
</div>
<div style="margin-top:10px">
  <button id="play">暂停</button>
  <input id="slider" type="range" min="0" max="__NMAX__" value="0" style="width:520px">
  <span id="frameLabel"></span>
</div>
<div id="hud"></div>
<div class="note">灰色=当帧房间点（每 8 点抽 1），红色方块=候选层检出的目标簇（core/lidar_candidates，
min_cluster_points=5）；左=俯视（x,y），右=侧视（x,z）。数据：captures/leveled/<job>/tls（只读）；
跟踪门 0.35 m + 划痕自适应 1.2×streak+0.15。目标几何为细长静止吊装物，语义 UNKNOWN（非飞行验证）。
证据：docs/sidequests/evidence/2026-10-14_plane_track_r1/（06_TRACK_REAL.json 等）。</div>
<script>
"use strict";
const DATA = __DATA__;
const topCtx = document.getElementById('top').getContext('2d');
const sideCtx = document.getElementById('side').getContext('2d');
const BOUNDS = [[-1,10],[-3,5],[-0.5,3.6]];   // 索引 0=x, 1=y, 2=z
let index = 0, playing = true, timer = null;

function drawCloud(ctx, frame, i, j){
  const W = ctx.canvas.width, H = ctx.canvas.height;
  ctx.clearRect(0,0,W,H);
  const [loI, hiI] = BOUNDS[i], [loJ, hiJ] = BOUNDS[j];
  const px = (v,lo,hi,W) => (v-lo)/(hi-lo)*W;
  ctx.fillStyle = '#7f8c9b';
  const room = frame.room;
  for(let k=0;k<room.length;k+=3){
    const x = room[k], y = room[k+1], z = room[k+2];
    const a = [x,y,z][i], b = [x,y,z][j];
    if(a < loI || a > hiI || b < loJ || b > hiJ) continue;
    ctx.fillRect(px(a,loI,hiI,W), H - px(b,loJ,hiJ,H), 2, 2);
  }
  if(frame.target.length){
    ctx.fillStyle = '#ff4444';
    for(let k=0;k<frame.target.length;k+=3){
      const x = frame.target[k], y = frame.target[k+1], z = frame.target[k+2];
      const a = [x,y,z][i], b = [x,y,z][j];
      ctx.fillRect(px(a,loI,hiI,W)-3, H - px(b,loJ,hiJ,H)-3, 6, 6);
    }
  }
}

function render(){
  const frame = DATA.frames[index];
  drawCloud(topCtx, frame, 0, 1);
  drawCloud(sideCtx, frame, 0, 2);
  document.getElementById('slider').value = index;
  document.getElementById('frameLabel').textContent = `帧 ${index+1}/${DATA.frames.length}  t=${(frame.t - DATA.frames[0].t).toFixed(2)} s`;
  const s = frame.stats;
  document.getElementById('hud').textContent =
    `检测: ${s.detected ? '命中' : '未命中'}   候选数 ${s.candidates}   目标点数 ${s.point_count ?? '-'}   距离 ${s.range_median_m?.toFixed(2) ?? '-'} m   ` +
    `划痕 ${s.streak_m?.toFixed(3) ?? '-'} m   跟踪门 ${s.gate_m.toFixed(2)} m   中心 (${s.center?.map(v=>v.toFixed(2)).join(', ') ?? '-'})`;
}

document.getElementById('play').onclick = (e) => {
  playing = !playing;
  e.target.textContent = playing ? '暂停' : '播放';
  if(playing) tick();
};
document.getElementById('slider').oninput = (e) => { index = +e.target.value; render(); };

function tick(){
  if(timer) clearTimeout(timer);
  if(!playing) return;
  timer = setTimeout(() => {
    index = (index + 1) % DATA.frames.length;
    render();
    tick();
  }, 100);   // 10 Hz：与源帧真实节奏一致
}
render();
tick();
</script></body></html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--job", default="363473a9e2e64649994dca11b2b26929")
    parser.add_argument("--method", default="tls")
    parser.add_argument("--sid", default="cap_20261014_164522")
    parser.add_argument("--stride", type=int, default=8)
    args = parser.parse_args()
    frames, transform, _meta = load_leveled_frames(args.job, args.method, args.sid)
    seed = np.asarray(transform["R"], dtype=np.float64) @ np.array([4.3, -0.55, 4.17]) \
        + np.asarray(transform["t"], dtype=np.float64)
    rows = run_frames(frames, snapshot_settings(), session_id=args.sid)
    track_rows, _speeds, summary, _events = track(rows, seed)

    payload_frames = []
    for index, (frame_index, stamp, xyz, _values) in enumerate(frames):
        row = track_rows[index]
        target_points = np.zeros((0, 3))
        if row["detected"]:
            for candidate in rows[index]["candidates"]:
                if candidate["point_count"] == row["point_count"] and np.allclose(
                        np.asarray(candidate["center"]), np.asarray(row["center"]), atol=0.05):
                    target_points = xyz[candidate["evidence_indices"]]
                    break
        room = xyz[::args.stride]
        payload_frames.append({
            "t": stamp,
            "room": [round(float(v), 2) for v in room.reshape(-1)],
            "target": [round(float(v), 2) for v in target_points.reshape(-1)],
            "stats": {"detected": bool(row["detected"]), "candidates": row["candidate_count"],
                      "point_count": row["point_count"], "range_median_m": row["range_median_m"],
                      "streak_m": row["streak_m"], "gate_m": row["gate_m"],
                      "center": None if row["center"] is None else [round(float(v), 3) for v in row["center"]]},
        })
    payload = {"sid": args.sid, "job_id": args.job, "method": args.method,
               "summary": summary, "frames": payload_frames}
    html = TEMPLATE.replace("__NMAX__", str(len(frames) - 1)).replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    target = Path(args.out) / "09_DEMO_10HZ.html"
    with target.open("x", encoding="utf8") as stream:
        stream.write(html)
    print(json.dumps({"html": str(target), "bytes": target.stat().st_size, "frames": len(frames),
                      "detected": summary["detected_frames"], "lost": summary["lost_frames"]}))


if __name__ == "__main__":
    main()
