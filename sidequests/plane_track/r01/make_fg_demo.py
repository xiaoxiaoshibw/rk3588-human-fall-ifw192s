"""去背景演示页：只留移动目标（房间已减掉），10 Hz 循环播放。

用法：
    python -B -W error make_fg_demo.py --out <evidence_dir>
读取 15_PLANE_FG_TRACK.json（plane_fg.py 产物），生成自包含 HTML（三视图放大到目标附近 + 轨迹 + 播放控制）。
"""
import argparse
import json
from pathlib import Path

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 去背景：只留移动目标</title>
<style>
 body{font-family:Consolas,monospace;background:#0b0f14;color:#e6edf3;margin:0;padding:14px}
 canvas{background:#05070a;border:1px solid #26343f;margin:2px}
 button{background:#1d2a36;color:#e6edf3;border:1px solid #2a3541;padding:6px 12px;font:inherit;cursor:pointer;margin-right:6px}
 button.on{background:#2d5468}
 #hud{white-space:pre;font-size:14px;line-height:1.5;margin-top:10px}
 .note{color:#8ba1b7;font-size:12px;margin-top:8px;max-width:1250px}
 label{font-size:13px;color:#b9c7d4;margin-right:12px}
</style></head><body>
<h3>PLANE-01 去背景效果：房间已减掉，只保留移动目标（cap_20261014_164522）</h3>
<div>
  <canvas id="cTop" width="430" height="400"></canvas>
  <canvas id="cSide" width="430" height="400"></canvas>
  <canvas id="cFront" width="430" height="400"></canvas>
</div>
<div style="margin-top:8px">
  <button id="play">暂停</button>
  <button id="toggleGhost" class="on">累计轨迹：开</button>
  <input id="slider" type="range" min="0" max="__NMAX__" value="0" style="width:420px">
  <span id="frameLabel"></span>
</div>
<div id="hud"></div>
<div class="note">背景=10-13 空场 cap_20261013_131958（既有 registration.js PASS 变换），判据 0.08 m 网格 ±1 格；
目标=自由空间（离最近静态点 ≥0.2 m）的高亮点簇，逐帧点数 11→64→60→41→34→18，速度 1.4→3.8 m/s。
视图自动放大到目标活动范围；数值以 15_PLANE_FG_TRACK.json 为准。目标语义 UNKNOWN（未见可判定的外形），
不做"确认是飞机/鸟"的宣称。</div>
<script>
"use strict";
const DATA = __DATA__;
const VIEWS = [
  {id:'cTop', i:0, j:1, lo:[0.9, 0.2], hi:[2.9, 2.2], label:'俯视 x-y'},
  {id:'cSide', i:0, j:2, lo:[0.9, -0.1], hi:[2.9, 1.9], label:'侧视 x-z'},
  {id:'cFront', i:1, j:2, lo:[0.2, -0.1], hi:[2.2, 1.9], label:'前视 y-z'}
];
const ctxs = VIEWS.map(v => { const c = document.getElementById(v.id); return { c, ctx: c.getContext('2d'), v }; });
let index = 0, playing = true, timer = null, showGhost = true, showRoom = false;

function project(v, x, y, z){
  const a = [x,y,z][v.i], b = [x,y,z][v.j];
  const px = (a - v.lo[0]) / (v.hi[0] - v.lo[0]);
  const py = 1 - (b - v.lo[1]) / (v.hi[1] - v.lo[1]);
  return [px * 430, py * 400];
}
function dot(entry, x, y, z, color, size){
  const [px, py] = project(entry.v, x, y, z);
  if(px < 0 || px > 430 || py < 0 || py > 400) return;
  entry.ctx.fillStyle = color;
  entry.ctx.fillRect(px - size/2, py - size/2, size, size);
}
function render(){
  const frame = DATA.frames[index];
  for(const e of ctxs){ e.ctx.clearRect(0,0,430,400); e.ctx.strokeStyle='#1b2530'; e.ctx.strokeRect(0.5,0.5,429,399);
    e.ctx.fillStyle='#5b6b7a'; e.ctx.font='12px Consolas'; e.ctx.fillText(e.v.label, 8, 16); }
  if(showRoom && frame.room && frame.room.length){
    for(const e of ctxs){ e.ctx.fillStyle = '#1f2933'; }
    for(let k=0;k<frame.room.length;k+=3){ for(const e of ctxs) dot(e, frame.room[k], frame.room[k+1], frame.room[k+2], '#1f2933', 2); }
  }
  const upto = index;
  for(let f=0; f<=index; f++){
    const past = DATA.frames[f];
    if(!past.points || !past.points.length) continue;
    const fade = showGhost ? (0.25 + 0.75 * (f / Math.max(1, index))) : (f === index ? 1 : 0);
    for(const e of ctxs){
      e.ctx.fillStyle = 'rgba(255,80,80,' + fade.toFixed(3) + ')';
      for(let k=0;k<past.points.length;k+=3) dot(e, past.points[k], past.points[k+1], past.points[k+2], 'rgba(255,80,80,'+fade.toFixed(3)+')', f===index?5:3);
    }
  }
  for(const e of ctxs){
    e.ctx.strokeStyle = '#f2c14e'; e.ctx.lineWidth = 1;
    const pts = DATA.frames.slice(0, index+1).filter(f => f.center).map(f => project(e.v, f.center[0], f.center[1], f.center[2]));
    if(pts.length > 1){ e.ctx.beginPath(); e.ctx.moveTo(pts[0][0], pts[0][1]); for(const p of pts.slice(1)) e.ctx.lineTo(p[0], p[1]); e.ctx.stroke(); }
  }
  document.getElementById('slider').value = index;
  const s = frame.stats;
  document.getElementById('frameLabel').textContent = `帧 ${index+1}/${DATA.frames.length}  t=${(frame.t - DATA.frames[0].t).toFixed(2)} s`;
  document.getElementById('hud').textContent =
    (s.detected
      ? `目标: 命中   点数 ${s.point_count}   中心 (${s.center.map(v=>v.toFixed(2)).join(', ')})   离最近静态点 ${s.distance_to_empty.toFixed(2)} m   强度中位 ${s.intensity.toFixed(0)}   速度 ${s.speed ? s.speed.toFixed(2) + ' m/s' : '(首帧)'}`
      : `目标: 未检出（本帧自由空间无 ≥8 点高亮簇）`);
}
document.getElementById('play').onclick = e => { playing = !playing; e.target.textContent = playing ? '暂停' : '播放'; if(playing) tick(); };
document.getElementById('toggleGhost').onclick = e => { showGhost = !showGhost; e.target.className = showGhost ? 'on' : ''; render(); };
document.getElementById('slider').oninput = e => { index = +e.target.value; render(); };
function tick(){ if(timer) clearTimeout(timer); if(!playing) return; timer = setTimeout(() => { index = (index + 1) % DATA.frames.length; render(); tick(); }, 100); }
render(); tick();
</script></body></html>
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="15_PLANE_FG_TRACK.json")
    parser.add_argument("--name", default="15_DEMO_FG.html")
    args = parser.parse_args()
    out = Path(args.out)
    source = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in source["track"]}
    object_points = {}
    for row in source.get("object_points", []):
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate["point_count"] >= 8:
                object_points[row["frame"]] = candidate
                break
    frames = []
    for row in source["frames"]:
        picked = object_points.get(row["frame"])
        track_row = track.get(row["frame"], {})
        frames.append({
            "t": row["stamp_s"],
            "room": [],
            "points": [] if picked is None else [v for point in picked["points"] for v in point],
            "center": track_row.get("center"),
            "stats": {"detected": bool(track_row.get("detected")),
                      "point_count": track_row.get("point_count"),
                      "center": track_row.get("center"),
                      "distance_to_empty": picked["distance_to_empty_m"] if picked else None,
                      "intensity": picked["intensity_median"] if picked else None,
                      "speed": track_row.get("speed_m_s")},
        })
    payload = {"summary": source["summary"], "frames": frames}
    html = TEMPLATE.replace("__NMAX__", str(len(frames) - 1)).replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    target = out / args.name
    with target.open("x", encoding="utf8") as stream:
        stream.write(html)
    print(json.dumps({"html": str(target), "bytes": target.stat().st_size,
                      "object_frames": [i for i, f in enumerate(frames) if f["points"]]}))


if __name__ == "__main__":
    main()
