"""生成 3D 展示页：目标点云 + 有向体形框(OBB) + 走过的航线。

用法：
    python -B -W error make_3d_demo.py --out <evidence_dir>
读取 15_PLANE_FG_TRACK.json；输出 19_3D_TRACK.html 并把 pc_apps/human_replay/vendor 的
three.min.js / OrbitControls.js 复制到同一目录（页内相对引用，离线可用，图元零外网）。
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from common import ROOT

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 3D：体形框 + 航线</title>
<style>
 body{margin:0;background:#0a0e13;color:#e6edf3;font-family:Consolas,monospace;overflow:hidden}
 #view{position:absolute;inset:0}
 #panel{position:absolute;left:12px;top:12px;background:rgba(13,19,26,.86);border:1px solid #26343f;
        padding:10px 12px;font-size:13px;line-height:1.5;max-width:460px}
 #panel h3{margin:0 0 6px 0;font-size:15px}
 #hud{white-space:pre}
 button{background:#1d2a36;color:#e6edf3;border:1px solid #2a3541;padding:4px 10px;font:inherit;cursor:pointer}
 button:hover{background:#26404f}
 label{margin-right:10px;font-size:12.5px}
 input[type=range]{width:320px}
 .dim{color:#8ba1b7;font-size:12px}
</style></head><body>
<div id="view"></div>
<div id="panel">
  <h3>PLANE-01 · 3D 目标 / 体形框 / 航线</h3>
  <div>
    <button id="play">暂停</button>
    <input id="slider" type="range" min="0" max="__NMAX__" value="0">
  </div>
  <div style="margin-top:6px">
    <label><input type="checkbox" id="cbBox" checked> 体形框</label>
    <label><input type="checkbox" id="cbPath" checked> 航线</label>
    <label><input type="checkbox" id="cbGhost" checked> 历史点</label>
    <label><input type="checkbox" id="cbRoom"> 房间(灰)</label>
  </div>
  <div id="hud" style="margin-top:8px"></div>
  <div class="dim" style="margin-top:6px">鼠标左键旋转 / 滚轮缩放 / 右键平移；网格=地面 z=0。
  体形框=当帧检出点云的有向包围盒(PCA)，含 0.103 s 帧内滚动拖影；航线=逐帧中心连线。</div>
</div>
<script src="three.min.js"></script>
<script src="OrbitControls.js"></script>
<script>
"use strict";
const DATA = __DATA__;
const Z_UP = new THREE.Vector3(0,0,1);
const container = document.getElementById('view');
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x0a0e13);
const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 0.05, 200);
camera.up.copy(Z_UP);
camera.position.set(1.2, -2.6, 2.2);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight);
container.appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(1.9, 1.2, 0.9);
controls.update();

// 地面网格（z=0）+ 坐标轴
const grid = new THREE.GridHelper(8, 32, 0x2b3947, 0x1b2530);
grid.rotation.x = Math.PI/2;
scene.add(grid);
const axes = new THREE.AxesHelper(0.6);
scene.add(axes);

function makeCloud(flat, color, size, opacity){
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
  const material = new THREE.PointsMaterial({color, size, sizeAttenuation:true,
                                             transparent:true, opacity});
  return new THREE.Points(geometry, material);
}
const frameClouds = DATA.frames.map(f => makeCloud(f.points.length ? f.points : [0,0,0], 0xff2d2d, 0.022, 1.0));
const ghostClouds = DATA.frames.map(f => makeCloud(f.points.length ? f.points : [0,0,0], 0xff6b6b, 0.016, 0.35));
frameClouds.forEach(c => scene.add(c));
ghostClouds.forEach(c => scene.add(c));

// 房间（单帧抽稀，默认隐藏）
const roomCloud = makeCloud(DATA.room.length ? DATA.room : [0,0,0], 0x33414f, 0.01, 0.85);
roomCloud.visible = false;
scene.add(roomCloud);

// 航线（逐帧中心）+ 中心小球 + 到地面的垂线
const centers = DATA.frames.filter(f => f.center).map(f => new THREE.Vector3(f.center[0], f.center[1], f.center[2]));
const pathGeometry = new THREE.BufferGeometry().setFromPoints(centers);
const pathLine = new THREE.Line(pathGeometry, new THREE.LineBasicMaterial({color:0xf2c14e}));
scene.add(pathLine);
const dotGeometry = new THREE.SphereGeometry(0.022, 10, 8);
const dotMaterial = new THREE.MeshBasicMaterial({color:0xf2c14e});
centers.forEach(c => { const dot = new THREE.Mesh(dotGeometry, dotMaterial); dot.position.copy(c); scene.add(dot); });
const dropMaterial = new THREE.LineDashedMaterial({color:0x6f8496, dashSize:0.06, gapSize:0.04});
const dropLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(0,0,0), new THREE.Vector3(0,0,1)]), dropMaterial);
scene.add(dropLine);

// 体形框（当前帧实线 / 历史虚线盒）
const boxGeometry = new THREE.BoxGeometry(1,1,1);
const edges = new THREE.EdgesGeometry(boxGeometry);
function makeBox(color, opacity, linewidthIgnored){
  const material = new THREE.LineBasicMaterial({color, transparent:true, opacity});
  return new THREE.LineSegments(edges, material);
}
const currentBox = makeBox(0xffa500, 1.0);
scene.add(currentBox);
const ghostBoxes = DATA.frames.map(() => { const box = makeBox(0xffa500, 0.22); scene.add(box); return box; });

const matrix = new THREE.Matrix4();
const quaternion = new THREE.Quaternion();
const scale = new THREE.Vector3();
function applyBox(target, box, opacity){
  if(!box){ target.visible = false; return false; }
  const basis = new THREE.Matrix4().makeBasis(
    new THREE.Vector3(...box.axes[0]), new THREE.Vector3(...box.axes[1]), new THREE.Vector3(...box.axes[2]));
  quaternion.setFromRotationMatrix(basis);
  scale.set(box.half[0]*2, box.half[1]*2, box.half[2]*2);
  target.position.set(box.center[0], box.center[1], box.center[2]);
  target.quaternion.copy(quaternion);
  target.scale.copy(scale);
  if(opacity !== undefined) target.material.opacity = opacity;
  target.visible = true;
  return true;
}

let index = 0, playing = true, timer = null;
const hud = document.getElementById('hud');
function render(){
  frameClouds.forEach((cloud, i) => {
    const active = i === index;
    cloud.visible = active;
    ghostClouds[i].visible = document.getElementById('cbGhost').checked && i < index;
  });
  const frame = DATA.frames[index];
  const showBox = document.getElementById('cbBox').checked;
  if(showBox && frame.box){ applyBox(currentBox, frame.box, 1.0); } else { currentBox.visible = false; }
  ghostBoxes.forEach((box, i) => {
    if(showBox && i < index && DATA.frames[i].box){ applyBox(box, DATA.frames[i].box, 0.18); }
    else { box.visible = false; }
  });
  pathLine.visible = document.getElementById('cbPath').checked;
  roomCloud.visible = document.getElementById('cbRoom').checked;
  if(frame.center){
    const c = new THREE.Vector3(frame.center[0], frame.center[1], frame.center[2]);
    dropLine.geometry.setFromPoints([c, new THREE.Vector3(c.x, c.y, 0)]);
    dropLine.computeLineDistances();
    dropLine.visible = true;
  } else { dropLine.visible = false; }
  document.getElementById('slider').value = index;
  const s = frame.stats;
  hud.textContent = [
    `帧 ${index+1}/${DATA.frames.length}   t=${(frame.t - DATA.frames[0].t).toFixed(2)} s`,
    s.detected ? `目标#1  点数 ${s.point_count}   速度 ${Number(s.speed||0).toFixed(2)} m/s   强度中位 ${Number(s.intensity).toFixed(0)}` : '目标未检出（自由空间无目标）',
    s.detected ? `中心 (${frame.center.map(v=>v.toFixed(2)).join(', ')})   离最近静态结构 ${Number(s.distance_to_empty).toFixed(2)} m` : '',
    frame.box ? `体形框 长×宽×厚 = ${(frame.box.half[0]*2).toFixed(2)} × ${(frame.box.half[1]*2).toFixed(2)} × ${(frame.box.half[2]*2).toFixed(2)} m` : '',
  ].filter(Boolean).join('\\n');
}
document.getElementById('play').onclick = e => { playing = !playing; e.target.textContent = playing ? '暂停' : '播放'; if(playing) tick(); };
document.getElementById('slider').oninput = e => { index = +e.target.value; render(); };
['cbBox','cbPath','cbGhost','cbRoom'].forEach(id => document.getElementById(id).onchange = render);
function tick(){ if(timer) clearTimeout(timer); if(!playing) return; timer = setTimeout(() => { index = (index+1) % DATA.frames.length; render(); tick(); }, 500); }
addEventListener('resize', () => { camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
function animate(){ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); }
render(); tick(); animate();
</script></body></html>
"""


def oriented_box(points):
    if len(points) < 3:
        return None
    centred = points - points.mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / len(centred))
    order = np.argsort(values)[::-1]
    basis = vectors[:, order]
    local = centred @ basis
    low, high = local.min(axis=0), local.max(axis=0)
    center = points.mean(axis=0) + basis @ ((low + high) / 2.0)
    return {"center": [round(float(v), 4) for v in center],
            "axes": [[round(float(v), 6) for v in basis[:, k]] for k in range(3)],
            "half": [round(float(v), 4) for v in (high - low) / 2.0]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="15_PLANE_FG_TRACK.json")
    parser.add_argument("--name", default="19_3D_TRACK.html")
    parser.add_argument("--room-stride", type=int, default=12)
    args = parser.parse_args()
    out = Path(args.out)
    payload_source = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in payload_source["track"]}
    points_by_frame = {}
    for row in payload_source.get("object_points", []):
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate["point_count"] >= 8:
                points_by_frame[row["frame"]] = np.asarray(candidate["points"], dtype=np.float64)
                break

    # 房间点：取目标出现那一帧（f12）的原始配平点云，抽稀一次作为空间参照
    room_flat = []
    try:
        from background import load_points
        frames, _meta = load_points("363473a9e2e64649994dca11b2b26929", "tls")
        xyz = frames[12][2]
        finite = np.isfinite(xyz).all(axis=1)
        inside = finite & (np.abs(xyz) < 12).all(axis=1)
        sampled = xyz[inside][::args.room_stride]
        room_flat = [round(float(v), 3) for v in sampled.reshape(-1)]
    except Exception as exc:  # noqa: BLE001 - 房间只是可选参照
        print("room sample skipped:", exc)

    frames_payload = []
    for row in payload_source["frames"]:
        frame_index = row["frame"]
        points = points_by_frame.get(frame_index)
        track_row = track.get(frame_index, {})
        frames_payload.append({
            "t": row["stamp_s"],
            "points": [] if points is None else [round(float(v), 4) for v in points.reshape(-1)],
            "center": track_row.get("center"),
            "box": None if points is None else oriented_box(points),
            "stats": {"detected": bool(track_row.get("detected")),
                      "point_count": track_row.get("point_count"),
                      "speed": track_row.get("speed_m_s"),
                      "intensity": track_row.get("intensity_median"),
                      "distance_to_empty": track_row.get("distance_to_empty_m")},
        })
    payload = {"sid": payload_source["target_sid"], "frames": frames_payload, "room": room_flat}
    html = TEMPLATE.replace("__NMAX__", str(len(frames_payload) - 1)).replace(
        "__DATA__", json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False))
    target = out / args.name
    with target.open("x", encoding="utf8") as stream:
        stream.write(html)
    for vendor in ("three.min.js", "OrbitControls.js"):
        destination = out / vendor
        if not destination.exists():
            shutil.copy2(ROOT / "pc_apps/human_replay/vendor" / vendor, destination)
    print(json.dumps({"html": str(target), "bytes": target.stat().st_size,
                      "room_points": len(room_flat) // 3,
                      "boxes": sum(1 for f in frames_payload if f["box"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
