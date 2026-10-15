"""3D 展示页 v3：核心跟踪 + 完整移动形态并集（按帧着色）+ 体形框 + 航线。

用法：
    python -B -W error make_3d_demo3.py --out <evidence_dir>
读取 20_TRACK_V2.json；输出 22_3D_TRACK_V3.html。
"完整移动形态"= 运动窗口(帧 8–17)内每帧、目标中心 1.4 m 内的全部瞬态前景点（含此前被当离群的
单帧点，用于看是否有翼/尾等更大结构），按帧号着色。
"""
import argparse
import json
import shutil
from pathlib import Path

import numpy as np

from common import ROOT

TEMPLATE = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 3D v3：完整移动形态 + 体形框</title>
<style>
 body{margin:0;background:#070a0e;color:#e6edf3;font-family:Consolas,monospace;overflow:hidden}
 #view{position:absolute;inset:0}
 #panel{position:absolute;left:12px;top:12px;background:rgba(11,16,22,.88);border:1px solid #22303c;
        border-radius:6px;padding:12px 14px;font-size:13px;line-height:1.55;max-width:480px}
 #panel h3{margin:0 0 8px 0;font-size:15px;color:#9fd1ff}
 #hud{white-space:pre}
 button{background:#1b2833;color:#e6edf3;border:1px solid #2a3a48;border-radius:4px;padding:5px 11px;font:inherit;cursor:pointer}
 label{margin-right:10px;font-size:12.5px;color:#b9c7d4}
 input[type=range]{width:330px;vertical-align:middle}
 .sw{display:inline-block;width:10px;height:10px;margin-right:5px;border-radius:2px}
 .dim{color:#7d90a3;font-size:11.5px;margin-top:8px}
</style></head><body>
<div id="view"></div>
<div id="panel">
  <h3>PLANE-01 · 3D v3（完整移动形态 + 体形框 + 航线）</h3>
  <div style="margin-bottom:8px"><button id="play">暂停</button>
    <input id="slider" type="range" min="0" max="__NMAX__" value="0"></div>
  <div style="margin-bottom:6px">
    <label><span class="sw" style="background:#c58cff"></span><input type="checkbox" id="cbUnion" checked> 完整移动形态(按帧着色)</label><br>
    <label><span class="sw" style="background:#ffa500"></span><input type="checkbox" id="cbBox" checked> 点云体形框</label>
    <label><span class="sw" style="background:#37d7ff"></span><input type="checkbox" id="cbBody" checked> 去拖影体形框</label><br>
    <label><span class="sw" style="background:#f2c14e"></span><input type="checkbox" id="cbPath" checked> 航线+帧号</label>
    <label><input type="checkbox" id="cbVec" checked> 速度矢量</label><br>
    <label><input type="checkbox" id="cbGhost" checked> 历史核心点</label>
    <label><input type="checkbox" id="cbDesmear"> 点云去拖影</label>
    <label><input type="checkbox" id="cbRoom"> 房间(灰)</label>
  </div>
  <div id="hud"></div>
  <div class="dim">紫=运动期内全部瞬态点（每点只在 1–2 帧出现，含此前被判为离群的单帧点；颜色越黄=帧号越大）；<br>
  红=当帧稳健核心点；橙框=核心点云 OBB；青框=去拖影体形；黄箭头=速度。语义 UNKNOWN。</div>
</div>
<script src="three.min.js"></script>
<script src="OrbitControls.js"></script>
<script>
"use strict";
const DATA = __DATA__;
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x070a0e);
const camera = new THREE.PerspectiveCamera(45, innerWidth/innerHeight, 0.05, 200);
camera.up.set(0,0,1);
camera.position.set(0.6, -2.4, 2.2);
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setSize(innerWidth, innerHeight);
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
document.getElementById('view').appendChild(renderer.domElement);
const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(1.9, 1.2, 0.9); controls.enableDamping = true; controls.dampingFactor = 0.08; controls.update();

const grid = new THREE.GridHelper(8, 32, 0x27333f, 0x17202a); grid.rotation.x = Math.PI/2; scene.add(grid);
scene.add(new THREE.AxesHelper(0.6));

function cloud(flat, color, size, opacity, colors){
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3));
  if(colors) geometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  const material = new THREE.PointsMaterial({color: colors ? 0xffffff : color, vertexColors: !!colors,
                                             size, sizeAttenuation:true, transparent:true, opacity});
  return new THREE.Points(geometry, material);
}
const frames = DATA.frames;
const currentCloud = cloud([0,0,0], 0xff3b30, 0.03, 1.0);
const desmearCloud = cloud([0,0,0], 0x9fe8ff, 0.03, 1.0);
const ghostClouds = frames.map(f => cloud(f.points.length ? f.points : [0,0,0], 0xff6b6b, 0.02, 0.30));
const unionCloud = cloud(DATA.union.positions, 0xffffff, 0.028, 0.95, DATA.union.colors);
scene.add(currentCloud); scene.add(desmearCloud); scene.add(unionCloud);
ghostClouds.forEach(c => scene.add(c));
const roomCloud = cloud(DATA.room, 0x2e3b47, 0.012, 0.9); roomCloud.visible = false; scene.add(roomCloud);

const centers = frames.filter(f => f.center).map(f => ({frame:f.frame, v:new THREE.Vector3(...f.center)}));
scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(centers.map(c => c.v)),
                         new THREE.LineBasicMaterial({color:0xf2c14e})));
const dotGeometry = new THREE.SphereGeometry(0.018, 10, 8);
const labels = [];
centers.forEach(c => {
  const dot = new THREE.Mesh(dotGeometry, new THREE.MeshBasicMaterial({color:0xf2c14e}));
  dot.position.copy(c.v); scene.add(dot);
  const canvas = document.createElement('canvas'); canvas.width = 64; canvas.height = 32;
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#f2c14e'; ctx.font = 'bold 22px Consolas';
  ctx.fillText('f' + c.frame, 2, 24);
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(canvas),
      transparent:true, depthTest:false}));
  sprite.position.copy(c.v).add(new THREE.Vector3(0.05,0.05,0.08)); sprite.scale.set(0.22,0.11,1);
  scene.add(sprite); labels.push(sprite);
});
const dropLine = new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(), new THREE.Vector3(0,0,1)]),
  new THREE.LineDashedMaterial({color:0x6f8496, dashSize:0.06, gapSize:0.04}));
scene.add(dropLine);

const edges = new THREE.EdgesGeometry(new THREE.BoxGeometry(1,1,1));
const obbBox = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({color:0xffa500}));
const bodyBox = new THREE.LineSegments(edges, new THREE.LineBasicMaterial({color:0x37d7ff}));
const ghostBoxes = frames.map(() => new THREE.LineSegments(edges,
  new THREE.LineBasicMaterial({color:0xffa500, transparent:true, opacity:0.14})));
scene.add(obbBox); scene.add(bodyBox); ghostBoxes.forEach(b => scene.add(b));
const arrow = new THREE.ArrowHelper(new THREE.Vector3(1,0,0), new THREE.Vector3(), 0.4, 0xf2c14e, 0.07, 0.045);
scene.add(arrow);

const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3();
function placeBox(target, axes, half, center){
  m4.makeBasis(new THREE.Vector3(...axes[0]), new THREE.Vector3(...axes[1]), new THREE.Vector3(...axes[2]));
  q.setFromRotationMatrix(m4);
  target.position.set(...center); target.quaternion.copy(q);
  s.set(half[0]*2, half[1]*2, half[2]*2); target.scale.copy(s); target.visible = true;
}
let index = 0, playing = true, timer = null;
function desmearPoints(frame){
  if(!frame.motion || !frame.points.length) return [];
  const d = frame.motion.direction, out = [];
  for(let k=0;k<frame.points.length;k+=3){
    const p = [frame.points[k], frame.points[k+1], frame.points[k+2]];
    const t = (p[0]-frame.center[0])*d[0] + (p[1]-frame.center[1])*d[1] + (p[2]-frame.center[2])*d[2];
    out.push(p[0]-t*d[0], p[1]-t*d[1], p[2]-t*d[2]);
  }
  return out;
}
const hud = document.getElementById('hud');
function render(){
  const frame = frames[index];
  const showGhost = document.getElementById('cbGhost').checked;
  ghostClouds.forEach((c,i) => c.visible = showGhost && i < index && frames[i].points.length > 0);
  const desmearOn = document.getElementById('cbDesmear').checked;
  const flat = desmearOn ? desmearPoints(frame) : frame.points;
  currentCloud.visible = !desmearOn && flat.length > 0;
  desmearCloud.visible = desmearOn && flat.length > 0;
  const target = desmearOn ? desmearCloud : currentCloud;
  if(flat.length){ target.geometry.dispose(); target.geometry = new THREE.BufferGeometry();
    target.geometry.setAttribute('position', new THREE.Float32BufferAttribute(flat, 3)); }
  unionCloud.visible = document.getElementById('cbUnion').checked;
  const showBox = document.getElementById('cbBox').checked;
  if(showBox && frame.box) placeBox(obbBox, frame.box.axes, frame.box.half, frame.box.center); else obbBox.visible = false;
  ghostBoxes.forEach((box,i) => {
    if(showBox && i < index && frames[i].box) placeBox(box, frames[i].box.axes, frames[i].box.half, frames[i].box.center);
    else box.visible = false; });
  if(document.getElementById('cbBody').checked && frame.bodybox)
    placeBox(bodyBox, frame.bodybox.axes, frame.bodybox.half, frame.bodybox.center); else bodyBox.visible = false;
  const showPath = document.getElementById('cbPath').checked;
  labels.forEach(l => l.visible = showPath);
  scene.children.forEach(o => { if(o.isLine && o.geometry.attributes.position.count === centers.length) o.visible = showPath; });
  if(document.getElementById('cbVec').checked && frame.motion){
    arrow.visible = true; arrow.position.set(...frame.center);
    arrow.setDirection(new THREE.Vector3(...frame.motion.direction));
    arrow.setLength(Math.min(0.8, 0.15 + frame.motion.speed*0.12), 0.07, 0.045);
  } else arrow.visible = false;
  roomCloud.visible = document.getElementById('cbRoom').checked;
  if(frame.center){ const c = new THREE.Vector3(...frame.center);
    dropLine.geometry.setFromPoints([c, new THREE.Vector3(c.x,c.y,0)]);
    dropLine.computeLineDistances(); dropLine.visible = true; } else dropLine.visible = false;
  document.getElementById('slider').value = index;
  const st = frame.stats, de = frame.desmear;
  hud.textContent = [
    `帧 ${frame.frame+1}/${frames.length}   t=${(frame.t - frames[0].t).toFixed(2)} s`,
    st.detected ? `核心  点数 ${st.point_count}（核 ${st.core_point_count}）  速度 ${Number(st.speed||0).toFixed(2)} m/s  强度中位 ${Number(st.intensity).toFixed(0)}` : '本帧核心未检出',
    st.detected ? `稳健中心 (${frame.center.map(v=>v.toFixed(2)).join(', ')})  离最近静态结构 ${Number(st.distance_to_empty).toFixed(2)} m` : '',
    de ? `沿轨 ${de.along.toFixed(2)} m − 帧内位移 ${de.step.toFixed(2)} m → 本体长度 ${de.body_length>=0.02 ? de.body_length.toFixed(2)+' m' : '不可分辨'}` : '',
    de ? `横截面  宽 ${de.width.toFixed(2)} m × 厚 ${de.thickness.toFixed(2)} m` : '',
  ].filter(Boolean).join('\\n');
}
document.getElementById('play').onclick = e => { playing = !playing; e.target.textContent = playing ? '暂停' : '播放'; if(playing) tick(); };
document.getElementById('slider').oninput = e => { index = +e.target.value; render(); };
['cbUnion','cbBox','cbBody','cbPath','cbVec','cbGhost','cbDesmear','cbRoom'].forEach(id =>
  document.getElementById(id).onchange = render);
function tick(){ if(timer) clearTimeout(timer); if(!playing) return;
  timer = setTimeout(() => { index = (index+1) % frames.length; render(); tick(); }, 500); }
addEventListener('resize', () => { camera.aspect = innerWidth/innerHeight; camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight); });
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
    return {"center": points.mean(axis=0) + basis @ ((low + high) / 2.0),
            "axes": [basis[:, k] for k in range(3)], "half": (high - low) / 2.0}


def viridis(value):
    stops = np.array([[0.267, 0.005, 0.329], [0.283, 0.141, 0.458], [0.254, 0.265, 0.530],
                      [0.207, 0.372, 0.553], [0.164, 0.471, 0.558], [0.128, 0.567, 0.551],
                      [0.135, 0.659, 0.518], [0.267, 0.749, 0.441], [0.478, 0.821, 0.318],
                      [0.741, 0.873, 0.150], [0.993, 0.906, 0.144]])
    position = float(np.clip(value, 0.0, 1.0)) * (len(stops) - 1)
    low = int(np.floor(position)); high = min(low + 1, len(stops) - 1)
    weight = position - low
    return (stops[low] * (1 - weight) + stops[high] * weight).tolist()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", required=True)
    parser.add_argument("--track", default="20_TRACK_V2.json")
    parser.add_argument("--name", default="22_3D_TRACK_V3.html")
    parser.add_argument("--registration", default="03_REGISTRATION_131958_to_164522")
    parser.add_argument("--room-stride", type=int, default=12)
    args = parser.parse_args()
    out = Path(args.out)
    payload_source = json.loads((out / args.track).read_text(encoding="utf8"))
    track = {row["frame"]: row for row in payload_source["track"]}
    picked = {}
    for row in payload_source["frames"]:
        for candidate in row["candidates"]:
            if candidate.get("free_space") and not candidate.get("near_known_leak") \
                    and candidate["point_count"] >= 8:
                picked[row["frame"]] = candidate
                break

    from background import apply_transform, background_keys, collect_points, foreground_mask, load_points
    registration = json.loads((out / args.registration / "registration.json").read_text(encoding="utf8"))
    target_frames, _tmeta = load_points("363473a9e2e64649994dca11b2b26929", "tls")
    empty_frames, _emeta = load_points("61cb6976b0f8479394641850d9a7c6ca", "tls")
    empty_registered = apply_transform(empty_frames, registration["rotation_row_major"],
                                       registration["translation_m"])
    keys, origin, base = background_keys(collect_points(empty_registered, stride=2), 0.08)
    track_detected = {row["frame"]: row for row in payload_source["track"] if row["detected"]}
    union_positions, union_colors = [], []
    for index, _stamp, xyz, _values in target_frames:
        if index < 8 or index > 17 or index not in track_detected:
            continue
        finite = np.isfinite(xyz).all(axis=1)
        points = xyz[finite]
        mask = foreground_mask(points, keys, origin, base, 0.08)
        center = np.asarray(track_detected[index]["center"])
        near = points[mask][np.linalg.norm(points[mask] - center, axis=1) <= 1.4]
        color = viridis((index - 8) / 9.0)
        for point in near:
            union_positions.extend([round(float(v), 4) for v in point])
            union_colors.extend(color)

    room_flat = []
    xyz = target_frames[12][2]
    inside = np.isfinite(xyz).all(axis=1) & (np.abs(xyz) < 12).all(axis=1)
    room_flat = [round(float(v), 3) for v in xyz[inside][::args.room_stride].reshape(-1)]

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
                 "stats": {"detected": bool(track_row.get("detected")), "point_count": None,
                           "core_point_count": None, "speed": None, "intensity": None,
                           "distance_to_empty": None}}
        if candidate is None:
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
                      "speed": float(speed_by_frame.get(frame, 0.0)),
                      "intensity": candidate["intensity_median"],
                      "distance_to_empty": candidate["distance_to_empty_m"]},
        })
        if desmear is not None:
            direction = np.asarray(desmear["motion_direction"], dtype=np.float64)
            reference = np.array([0.0, 0.0, 1.0]) if abs(direction[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            perp1 = np.cross(direction, reference); perp1 /= np.linalg.norm(perp1)
            perp2 = np.cross(direction, perp1)
            length = max(desmear["body_length_est_m"], 0.02)
            entry["bodybox"] = {
                "center": [round(float(v), 4) for v in candidate["center"]],
                "axes": [[round(float(v), 6) for v in direction], [round(float(v), 6) for v in perp1],
                         [round(float(v), 6) for v in perp2]],
                "half": [round(length / 2, 4), round(desmear["body_width_m"] / 2, 4),
                         round(desmear["body_thickness_m"] / 2, 4)]}
        frames_payload.append(entry)

    payload = {"sid": payload_source["target_sid"], "frames": frames_payload, "room": room_flat,
               "union": {"positions": union_positions, "colors": union_colors,
                         "note": "frames 8-17, transient foreground within 1.4 m of the tracked center"}}
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
                      "union_points": len(union_positions) // 3}, ensure_ascii=False))


if __name__ == "__main__":
    main()
