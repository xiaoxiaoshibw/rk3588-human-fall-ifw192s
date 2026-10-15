"""3D 展示页 v2：稳健体形框（OBB + 去拖影）+ 速度矢量 + 航线 + 帧号标签。

用法：
    python -B -W error make_3d_demo2.py --out <evidence_dir>
读取 20_TRACK_V2.json（plane_fg2.py 产物）；输出 20_3D_TRACK_V2.html（three r127 同目录引用）。
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from common import ROOT

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 3D v2：体形框 + 去拖影 + 航线</title>
<style>
 body{margin:0;background:#070a0e;color:#e6edf3;font-family:Consolas,monospace;overflow:hidden}
 #view{position:absolute;inset:0}
 #panel{position:absolute;left:12px;top:12px;background:rgba(11,16,22,.88);border:1px solid #22303c;
        border-radius:6px;padding:12px 14px;font-size:13px;line-height:1.55;max-width:470px;backdrop-filter:blur(3px)}
 #panel h3{margin:0 0 8px 0;font-size:15px;color:#9fd1ff}
 #hud{white-space:pre}
 button{background:#1b2833;color:#e6edf3;border:1px solid #2a3a48;border-radius:4px;padding:5px 11px;font:inherit;cursor:pointer}
 button:hover{background:#26３d4f}
 label{margin-right:10px;font-size:12.5px;color:#b9c7d4}
 input[type=range]{width:330px;vertical-align:middle}
 .sw{display:inline-block;width:10px;height:10px;margin-right:5px;border-radius:2px}
 .dim{color:#7d90a3;font-size:11.5px;margin-top:8px}
</style></head><body>
<div id="view"></div>
<div id="panel">
  <h3>PLANE-01 · 3D v2（单链接聚类 + 稳健核 + 去拖影）</h3>
  <div style="margin-bottom:8px">
    <button id="play">暂停</button>
    <input id="slider" type="range" min="0" max="__NMAX__" value="0">
  </div>
  <div style="margin-bottom:6px">
    <label><span class="sw" style="background:#ffa500"></span><input type="checkbox" id="cbBox" checked> 点云体形框(OBB)</label><br>
    <label><span class="sw" style="background:#37d7ff"></span><input type="checkbox" id="cbBody" checked> 去拖影体形框</label><br>
    <label><span class="sw" style="background:#f2c14e"></span><input type="checkbox" id="cbPath" checked> 航线 + 帧号</label>
    <label><input type="checkbox" id="cbVec" checked> 速度矢量</label><br>
    <label><input type="checkbox" id="cbGhost" checked> 历史点</label>
    <label><input type="checkbox" id="cbDesmear"> 点云去拖影(示意)</label>
    <label><input type="checkbox" id="cbRoom"> 房间(灰)</label>
  </div>
  <div id="hud"></div>
  <div class="dim">左键旋转 / 滚轮缩放 / 右键平移；网格=地面 z=0。<br>
  橙色框=当帧检出点云的有向包围盒；青色框=去拖影体形（长度=实测沿轨范围−帧内位移，小于可分辨下限时按 0.02 m 上限画，见 HUD 标注）；<br>
  黄箭头=速度方向（长度∝速度）。语义仍 UNKNOWN，不宣称是飞机外形。</div>
</div>
<script src="three.min.js"></script>
<script src="OrbitControls.js"></script>
<script>
"use strict";
const DATA = __DATA__;
const Z_UP = new THREE.Vector3(0,0,1);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070a0e);
const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 0.05, 200);
camera.up.copy(Z_UP);
camera.position.set(0.9, -2.3, 2.3);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
document.getElementById('view').appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(1.9, 1.2, 0.9);
controls.enableDamping = true; controls.dampingFactor = 0.08;
controls.update();

const grid = new THREE.GridHelper(8, 32, 0x27333f, 0x17202a);
grid.rotation.x = Math.PI/2;
scene.add(grid);
scene.add(new THREE.AxesHelper(0.6));

function makeCloud(flat, color, size, opacity){
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
  return new THREE.Points(geometry, new THREE.PointsMaterial({color, size, sizeAttenuation:true,
                                                              transparent:true, opacity}));
}
const frames = DATA.frames;
const currentCloud = makeCloud([0,0,0], 0xff3b30, 0.03, 1.0);
const desmearCloud = makeCloud([0,0,0], 0x9fe8ff, 0.03, 1.0);
const ghostClouds = frames.map(f => makeCloud(f.points.length ? f.points : [0,0,0], 0xff6b6b, 0.02, 0.32));
scene.add(currentCloud); scene.add(desmearCloud);
ghostClouds.forEach(c => scene.add(c));
const roomCloud = makeCloud(DATA.room.length ? DATA.room : [0,0,0], 0x2e3b47, 0.012, 0.9);
roomCloud.visible = false; scene.add(roomCloud);

// 航线 + 中心球 + 帧号标签
const centers = frames.filter(f => f.center).map(f => ({frame:f.frame, v:new THREE.Vector3(...f.center)}));
const pathLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(centers.map(c => c.v)),
                                new THREE.LineBasicMaterial({color:0xf2c14e}));
scene.add(pathLine);
const dotGeometry = new THREE.SphereGeometry(0.018, 10, 8);
const dotMaterial = new THREE.MeshBasicMaterial({color:0xf2c14e});
const labels = [];
centers.forEach(c => {
  const dot = new THREE.Mesh(dotGeometry, dotMaterial); dot.position.copy(c.v); scene.add(dot);
  const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 32;
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#f2c14e'; ctx.font = 'bold 22px Consolas';
  ctx.fillText('f' + c.frame, 2, 24);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),
                                                            transparent:true, depthTest:false}));
  sprite.position.copy(c.v).add(new THREE.Vector3(0.05, 0.05, 0.08));
  sprite.scale.set(0.22, 0.11, 1);
  scene.add(sprite); labels.push(sprite);
});
const dropLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(), new THREE.Vector3(0,0,1)]),
    new THREE.LineDashedMaterial({color:0x6f8496, dashSize:0.06, gapSize:0.04}));
scene.add(dropLine);

// 体形框：橙色=OBB，青色=去拖影框
const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1));
const obbBox = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({color:0xffa500}));
const bodyBox = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({color:0x37d7ff}));
const ghostBoxes = frames.map(() => new THREE.LineSegments(edges,
    new THREE.LineBasicMaterial({color:0xffa500, transparent:true, opacity:0.16})));
scene.add(obbBox); scene.add(bodyBox); ghostBoxes.forEach(b => scene.add(b));

// 速度矢量
const arrow = new THREE.ArrowHelper(new THREE.Vector3(1,0,0), new THREE.Vector3(), 0.4, 0xf2c14e, 0.07, 0.045);
scene.add(arrow);

const basisMatrix = new THREE.Matrix4(), quaternion = new THREE.Quaternion(), scale = new THREE.Vector3();
function placeBox(target, axes, half, center){
  basisMatrix.makeBasis(new THREE.Vector3(...axes[0]), new THREE.Vector3(...axes[1]), new THREE.Vector3(...axes[2]));
  quaternion.setFromRotationMatrix(basisMatrix);
  target.position.set(...center); target.quaternion.copy(quaternion);
  scale.set(half[0]*2, half[1]*2, half[2]*2); target.scale.copy(scale);
  target.visible = true;
}

let index = 0, playing = true, timer = null;
const hud = document.getElementById('hud');
function desmearPoints(frame){
  if(!frame.motion || !frame.points.length) return [];
  const d = frame.motion.direction;
  const out = [];
  for(let k=0;k<frame.points.length;k+=3){
    const p = [frame.points[k], frame.points[k+1], frame.points[k+2]];
    const t = (p[0]-frame.center[0])*d[0] + (p[1]-frame.center[1])*d[1] + (p[2]-frame.center[2])*d[2];
    out.push(p[0]-t*d[0], p[1]-t*d[1], p[2]-t*d[2]);
  }
  return out;
}
function render(){
  const frame = frames[index];
  const showGhost = document.getElementById('cbGhost').checked;
  ghostClouds.forEach((c, i) => c.visible = showGhost && i < index && frames[i].points.length > 0);
  const desmearOn = document.getElementById('cbDesmear').checked;
  const flat = desmearOn ? desmearPoints(frame) : frame.points;
  currentCloud.visible = !desmearOn && flat.length > 0;
  desmearCloud.visible = desmearOn && flat.length > 0;
  const cloud = desmearOn ? desmearCloud : currentCloud;
  if(flat.length){ cloud.geometry.dispose(); cloud.geometry = new THREE.BufferGeometry();
    cloud.geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3)); }
  const showBox = document.getElementById('cbBox').checked;
  if(showBox && frame.box){ placeBox(obbBox, frame.box.axes, frame.box.half, frame.box.center); } else obbBox.visible = false;
  ghostBoxes.forEach((box, i) => {
    if(showBox && i < index && frames[i].box){ placeBox(box, frames[i].box.axes, frames[i].box.half, frames[i].box.center); }
    else box.visible = false;
  });
  const showBody = document.getElementById('cbBody').checked;
  if(showBody && frame.bodybox){ placeBox(bodyBox, frame.bodybox.axes, frame.bodybox.half, frame.bodybox.center); }
  else bodyBox.visible = false;
  pathLine.visible = document.getElementById('cbPath').checked;
  labels.forEach(l => l.visible = pathLine.visible);
  roomCloud.visible = document.getElementById('cbRoom').checked;
  const showVec = document.getElementById('cbVec').checked;
  if(showVec && frame.motion){
    arrow.visible = true;
    arrow.position.set(...frame.center);
    arrow.setDirection(new THREE.Vector3(...frame.motion.direction));
    arrow.setLength(Math.min(0.8, 0.15 + frame.motion.speed*0.12), 0.07, 0.045);
  } else arrow.visible = false;
  if(frame.center){
    const c = new THREE.Vector3(...frame.center);
    dropLine.geometry.setFromPoints([c, new THREE.Vector3(c.x, c.y, 0)]);
    dropLine.computeLineDistances(); dropLine.visible = true;
  } else dropLine.visible = false;
  document.getElementById('slider').value = index;
  const s = frame.stats, de = frame.desmear;
  hud.textContent = [
    `帧 ${frame.frame+1}/${frames.length}   t=${(frame.t - frames[0].t).toFixed(2)} s`,
    s.detected ? `目标  点数 ${s.point_count}（核心 ${s.core_point_count}）  速度 ${Number(s.speed||0).toFixed(2)} m/s  强度中位 ${Number(s.intensity).toFixed(0)}` : '目标未检出（自由空间无目标）',
    s.detected ? `稳健中心 (${frame.center.map(v=>v.toFixed(2)).join(', ')})  离最近静态结构 ${Number(s.distance_to_empty).toFixed(2)} m` : '',
    de ? `沿轨范围 ${de.along.toFixed(2)} m − 帧内位移 ${de.step.toFixed(2)} m → 本体长度 ${de.body_length>=0.02 ? de.body_length.toFixed(2)+' m' : '不可分辨(≤0.02 m)'}` : '',
    de ? `横截面  宽 ${de.width.toFixed(2)} m × 厚 ${de.thickness.toFixed(2)} m` : '',
  ].filter(Boolean).join('\\n');
}
document.getElementById('play').onclick = e => { playing = !playing; e.target.textContent = playing ? '暂停' : '播放'; if(playing) tick(); };
document.getElementById('slider').oninput = e => { index = +e.target.value; render(); };
['cbBox','cbBody','cbPath','cbVec','cbGhost','cbDesmear','cbRoom'].forEach(id => document.getElementById(id).onchange = render);
function tick(){ if(timer) clearTimeout(timer); if(!playing) return; timer = setTimeout(() => { index = (index+1) % frames.length; render(); tick(); }, 500); }
addEventListener('resize', () => { camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix(); renderer.setSize(innerWidth, innerHeight); });
(function animate(){ requestAnimationFrame(animate); controls.update(); renderer.render(scene, camera); })();
render(); tick();
</script></body></html>
"""


def obb(points):
    centred = points - points.mean(axis=0)
    values, vectors = np.linalg.eigh(centred.T @ centred / len(centred))
    basis = vectors[:, np.argsort(values)[::-1]]
    local = centred @ basis
    low, high = local.min(axis=0), local.max(axis=0)
    center = points.mean(axis=0) + basis @ ((low + high) / 2.0)
    return {"center": center, "axes": [basis[:, k] for k in range(3)], "half": (high - low) / 2.0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--name", default="20_3D_TRACK_V2.html")
    parser.add_argument("--room-stride", type=int, default=12)
    args = parser.parse_args()
    out = Path(args.out)
    payload_source = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in payload_source["track"]}
    picked = {}
    for row in payload_source["frames"]:
        for candidate in row["candidates"]:
            if candidate["free_space"] and not candidate["near_known_leak"] and candidate["point_count"] >= 8:
                picked[row["frame"]] = candidate
                break

    room_flat = []
    from background import load_points
    frames_lv, _meta = load_points("363473a9e2e64649994dca11b2b26929", "tls")
    xyz = frames_lv[12][2]
    inside = np.isfinite(xyz).all(axis=1) & (np.abs(xyz) < 12).all(axis=1)
    room_flat = [round(float(v), 3) for v in xyz[inside][::args.room_stride].reshape(-1)]

    # 逐帧速度由稳健核中心差分（生成器自己算，避免依赖 v2 JSON 的字段）
    detected = [(row["frame"], np.asarray(track[row["frame"]]["center"]), row["stamp_s"])
                for row in payload_source["frames"] if track.get(row["frame"], {}).get("detected")]
    speed_by_frame = {}
    for i, (frame, center, stamp) in enumerate(detected):
        candidates = []
        if i + 1 < len(detected):
            delta, dt = detected[i + 1][1] - center, detected[i + 1][2] - stamp
            if dt > 0:
                candidates.append(float(np.linalg.norm(delta) / dt))
        if i > 0:
            delta, dt = center - detected[i - 1][1], stamp - detected[i - 1][2]
            if dt > 0:
                candidates.append(float(np.linalg.norm(delta) / dt))
        speed_by_frame[frame] = min(candidates) if candidates else 0.0

    frames_payload = []
    for row in payload_source["frames"]:
        frame = row["frame"]
        candidate = picked.get(frame)
        track_row = track.get(frame, {})
        entry = {"frame": frame, "t": row["stamp_s"], "points": [], "center": None, "box": None,
                 "bodybox": None, "desmear": None, "motion": None,
                 "stats": {"detected": bool(track_row.get("detected")),
                           "point_count": None, "core_point_count": None,
                           "speed": track_row.get("point_count"), "intensity": None,
                           "distance_to_empty": None}}
        if candidate is None:
            entry["stats"]["point_count"] = track_row.get("point_count")
            entry["stats"]["core_point_count"] = track_row.get("core_point_count")
            entry["stats"]["speed"] = None
            entry["stats"]["intensity"] = track_row.get("intensity_median")
            entry["stats"]["distance_to_empty"] = track_row.get("distance_to_empty_m")
            frames_payload.append(entry)
            continue
        points = np.asarray(candidate["points"], dtype=np.float64)
        box = obb(points)
        desmear = candidate.get("desmear")
        entry.update({
            "points": [round(float(v), 4) for v in points.reshape(-1)],
            "center": candidate["center"],
            "box": {"center": [round(float(v), 4) for v in box["center"]],
                    "axes": [[round(float(v), 6) for v in axis] for axis in box["axes"]],
                    "half": [round(float(v), 4) for v in box["half"]]},
            "desmear": (None if desmear is None else
                        {"along": desmear["along_track_span_m"], "step": desmear["step_m"],
                         "body_length": desmear["body_length_est_m"], "width": desmear["body_width_m"],
                         "thickness": desmear["body_thickness_m"]}),
            "motion": (None if desmear is None else
                       {"direction": desmear["motion_direction"],
                        "speed": float(speed_by_frame.get(frame, 0.0))}),
            "stats": {"detected": True, "point_count": candidate["point_count"],
                      "core_point_count": candidate["core_point_count"],
                      "speed": float(speed_by_frame.get(frame, 0.0)), "intensity": candidate["intensity_median"],
                      "distance_to_empty": candidate["distance_to_empty_m"]},
        })
        # 去拖影体形框：轴 = 运动方向 + 两垂直方向，长度=去拖影估计（≥0.02 显示下限），宽厚=实测
        if desmear is not None:
            direction = np.asarray(desmear["motion_direction"], dtype=np.float64)
            reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            perp1 = np.cross(direction, reference); perp1 /= np.linalg.norm(perp1)
            perp2 = np.cross(direction, perp1)
            length = max(desmear["body_length_est_m"], 0.02)
            entry["bodybox"] = {
                "center": [round(float(v), 4) for v in candidate["center"]],
                "axes": [[round(float(v), 6) for v in direction],
                         [round(float(v), 6) for v in perp1], [round(float(v), 6) for v in perp2]],
                "half": [round(length / 2, 4), round(desmear["body_width_m"] / 2, 4),
                         round(desmear["body_thickness_m"] / 2, 4)],
                "length_resolvable": bool(desmear["body_length_est_m"] >= 0.02),
            }
        frames_payload.append(entry)

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
                      "bodyboxes": sum(1 for f in frames_payload if f["bodybox"])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
