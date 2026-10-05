#!/usr/bin/env python3
"""Read an adapted capture, apply nominal installation parameters, compare."""
import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.capture_input import load_adapted, sha256_file
from core.nominal_leveling import build_nominal_model


def comparison_html(model, frames):
    payload = json.dumps({"model": model, "frames": frames}, ensure_ascii=True,
                         allow_nan=False).replace("<", "\\u003c")
    return """<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<title>安装参数配平：同帧前后对照</title><style>
body{font:16px system-ui;margin:24px;background:#f5f7fb;color:#172139}h1{font-size:24px}
label{margin-right:24px}input{width:90px}canvas{width:100%;background:white;border:1px solid #ccd4df}
.muted{color:#526279}.controls{padding:14px;background:white;border-radius:8px}
</style><h1>安装参数配平：同帧前后对照</h1>
<p>左列：原始雷达坐标；右列：先旋正、再沿竖直 Z 平移后的坐标。红线是名义地面 z=0。</p>
<div class="controls"><label>帧 <select id="frame"></select></label>
<label>下俯角（度） <input id="pitch" type="number" min="-90" max="90" step="0.1"></label>
<label>高度（米） <input id="height" type="number" min="0" max="50" step="0.01"></label></div>
<p id="info"></p><canvas id="plot" width="1400" height="850"></canvas>
<p id="export" class="muted"></p>
<p class="muted">参数为用户给定的近似安装值。假设源轴 X前/Y左/Z上、roll/yaw=0。显示点按源行均匀抽样，无拟合或地面身份筛选；数值文件保存全部有效点。改变控件仅改变本页预览。</p>
<script>const DATA=__PAYLOAD__;
const fs=document.querySelector('#frame'),pitch=document.querySelector('#pitch'),height=document.querySelector('#height');
pitch.value=DATA.model.pitch_down_deg;height.value=DATA.model.height_m;
DATA.frames.forEach((f,i)=>{let o=document.createElement('option');o.value=i;o.textContent=`${f.ordinal} / seq ${f.seq}`;fs.append(o)});
fs.value=Math.min(5,DATA.frames.length-1);
document.querySelector('#export').textContent=`导出文件参数：${DATA.model.pitch_down_deg}° / ${DATA.model.height_m}m；模型 ${DATA.model.model_id}`;
function panel(ctx,pts,axis,bounds,left,top,title){
 const W=600,H=320,x0=left+60,y0=top+35;
 const [xmin,xmax,zmin,zmax]=bounds,px=x=>x0+(x-xmin)/(xmax-xmin)*W,py=z=>y0+H-(z-zmin)/(zmax-zmin)*H;
 ctx.fillStyle='#172139';ctx.font='18px system-ui';ctx.fillText(title,left+20,top+20);
 ctx.strokeStyle='#d9e0ea';ctx.font='13px system-ui';
 for(let i=0;i<=5;i++){let x=xmin+(xmax-xmin)*i/5,z=zmin+(zmax-zmin)*i/5;
 ctx.beginPath();ctx.moveTo(px(x),y0);ctx.lineTo(px(x),y0+H);ctx.stroke();ctx.fillText(x.toFixed(2),px(x)-15,y0+H+20);
 ctx.beginPath();ctx.moveTo(x0,py(z));ctx.lineTo(x0+W,py(z));ctx.stroke();ctx.fillText(z.toFixed(2),left+7,py(z)+4)}
 if(zmin<=0&&zmax>=0){ctx.strokeStyle='#c4413c';ctx.beginPath();ctx.moveTo(x0,py(0));ctx.lineTo(x0+W,py(0));ctx.stroke()}
 ctx.fillStyle='#22689d';for(const p of pts){ctx.fillRect(px(p[axis])-1,py(p[2])-1,2,2)}
 ctx.fillStyle='#172139';ctx.fillText((axis===0?'X':'Y')+' (m)',x0+W-35,y0+H+36);ctx.fillText('Z (m)',left+8,top+20);
}
function draw(){let a=Number(pitch.value),h=Number(height.value),f=DATA.frames[Number(fs.value)];
 const ctx=document.querySelector('#plot').getContext('2d');ctx.clearRect(0,0,1400,850);
 if(!f||!Number.isFinite(a)||!Number.isFinite(h)||a<-90||a>90||h<0||h>50){document.querySelector('#info').textContent='请输入合法角度、高度';return}
 let c=Math.cos(a*Math.PI/180),s=Math.sin(a*Math.PI/180),src=f.points.map(p=>p.slice(1)),dst=src.map(p=>[c*p[0]+s*p[2],p[1],-s*p[0]+c*p[2]+h]);
 document.querySelector('#info').textContent=`当前预览 ${a}° / ${h}m；frame ${f.ordinal}；有效点 ${f.valid_count}，显示 ${src.length}。雷达位置 z=${h}m。`;
 for(let axis=0;axis<2;axis++){let xs=src.concat(dst).map(p=>p[axis]),zs=src.concat(dst).map(p=>p[2]);
 let lo=Math.min(...xs,0),hi=Math.max(...xs,0),zl=Math.min(...zs,0),zh=Math.max(...zs,0);
 let dx=Math.max(hi-lo,0.1)*.05,dz=Math.max(zh-zl,0.1)*.05,b=[lo-dx,hi+dx,zl-dz,zh+dz];
 panel(ctx,src,axis,b,0,axis*420,'原始 source '+(axis?'YZ':'XZ'));panel(ctx,dst,axis,b,700,axis*420,'名义配平 '+(axis?'YZ':'XZ'))}
}
[fs,pitch,height].forEach(e=>e.addEventListener('input',draw));draw();
</script></html>""".replace("__PAYLOAD__", payload)


def level_capture(npz, output, pitch_down_deg, height_m, declared_frame, repo_root):
    root = Path(repo_root).resolve()
    target = Path(output).absolute()
    allowed = root / "docs/human_fall/evidence/2026-10-04_gl_n01_r1"
    if target.resolve() != target or allowed not in target.parents or target.exists() \
            or not target.parent.is_dir():
        raise ValueError("output must be a new child directory inside this work item")
    for parent in [target] + list(target.parents):
        if parent.is_symlink():
            raise ValueError("output path alias forbidden")
    before = sha256_file(npz)
    manifest, points = load_adapted(npz)
    if declared_frame != manifest["declared"]["frame"] or manifest["declared"]["units"] != "m":
        raise ValueError("source frame/units mismatch")
    for path in [Path(npz)] + [Path(manifest["source"][n + "_path"]) for n in ("meta", "bin")]:
        if target == path.resolve() or target in path.resolve().parents:
            raise ValueError("output contains an input")
    model = build_nominal_model(pitch_down_deg, height_m, declared_frame)
    valid = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1)
    source_rows = np.flatnonzero(valid)
    # Public frozen arithmetic; dtype/shape checked once, avoid Python loops
    # over millions of already-validated decoder floats.
    from core.calibration import apply_transform
    mapped = apply_transform(points[valid], model)
    stats, samples = [], []
    for gid, group in sorted(manifest["frame_groups"].items(), key=lambda pair: pair[1]["ordinal"]):
        low, high = group["rows"]
        first, last = np.searchsorted(source_rows, [low, high])
        rows = source_rows[first:last]
        selected = mapped[first:last]
        finite_count = int(np.isfinite(points[low:high]).all(axis=1).sum())
        entry = {"frame_group": gid, "ordinal": group["ordinal"], "seq": group["seq"],
                 "stamp_sec": group["stamp_sec"], "stamp_nanosec": group["stamp_nanosec"],
                 "source_rows": [low, high], "output_rows": [int(first), int(last)],
                 "source_count": high-low, "valid_count": len(rows),
                 "nonfinite_count": high-low-finite_count,
                 "zero_count": finite_count-len(rows),
                 "nominal_z_quantiles_all_scene_m": np.quantile(selected[:, 2], [0, .05, .5, .95, 1]).tolist() if len(rows) else None,
                 "statistics_domain": "all_valid_scene_points_not_ground_error"}
        stats.append(entry)
        chosen = np.linspace(0, len(rows)-1, min(2000, len(rows)), dtype=int) if len(rows) else []
        samples.append({"ordinal": group["ordinal"], "seq": group["seq"], "valid_count": len(rows),
                        "points": [[int(rows[i])] + points[rows[i]].astype(float).tolist() for i in chosen]})
    inputs = {"npz_path": str(Path(npz).resolve()), "npz_sha256": before,
              "source": manifest["source"], "source_xyz_sha256": manifest["points"]["sha256"],
              "window_bag_time_sec": [manifest["frames"][0]["bag_time_sec"], manifest["frames"][-1]["bag_time_sec"]],
              "declared": manifest["declared"], "model_id": model["model_id"],
              "valid_point_count": len(source_rows), "input_point_count": len(points),
              "display_sampling": "uniform pooled rows per frame; maximum 2000; no residual or ground labeling"}
    if sha256_file(npz) != before:
        raise ValueError("NPZ changed during processing")
    for name in ("meta", "bin"):
        if sha256_file(manifest["source"][name + "_path"]) != manifest["source"][name + "_sha256"]:
            raise ValueError("actual source changed during processing")
    target.mkdir(exist_ok=False)
    with (target / "nominal_leveled.npz").open("xb") as f:
        np.savez(f, points=mapped, source_rows=source_rows, model_json=np.array(json.dumps(model)),
                 input_json=np.array(json.dumps(inputs)))
    for name, content in (("nominal_model.json", model), ("input_manifest.json", inputs),
                          ("frame_stats.json", stats)):
        with (target / name).open("x", encoding="utf8") as f:
            json.dump(content, f, ensure_ascii=False, indent=2, allow_nan=False)
    with (target / "view.html").open("x", encoding="utf8") as f:
        f.write(comparison_html(model, samples))
    return inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--pitch-down-deg", type=float, required=True)
    parser.add_argument("--height-m", type=float, required=True)
    parser.add_argument("--source-frame", required=True)
    args = parser.parse_args()
    try:
        info = level_capture(args.input, args.output, args.pitch_down_deg, args.height_m,
                             args.source_frame, Path(__file__).resolve().parents[3])
        print(json.dumps(info, ensure_ascii=False))
        return 0
    except (ValueError, OSError, KeyError, TypeError, OverflowError) as exc:
        print("nominal leveling refused: " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
