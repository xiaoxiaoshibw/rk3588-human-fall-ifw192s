"""Read-only session export and offline detector trial. Output is model evidence, never GT."""
import argparse
import hashlib
import json
from pathlib import Path
import time

import numpy as np


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for block in iter(lambda: f.read(1024*1024), b""):
            h.update(block)
    return h.hexdigest()


def read_frame(session, index):
    session = Path(session)
    meta = json.loads((session / "meta.json").read_text(encoding="utf-8"))
    if meta.get("format") != "human_capture_session" or meta.get("format_version") != 1:
        raise ValueError("unsupported session format")
    layout = meta.get("point_layout", {})
    fields = layout.get("fields")
    stride = meta.get("point_stride_bytes", layout.get("stride_bytes", 16))
    if fields == ["x", "y", "z", "intensity"]:
        if stride != 16 or layout.get("dtype") != "<f4" or layout.get("stride_points") != 4:
            raise ValueError("unsupported 16B layout")
    elif fields == ["x", "y", "z", "intensity", "ring", "timestamp"]:
        if stride != 28 or layout.get("dtypes") != ["<f4"]*4 + ["<u2", "<f4"] or layout.get("endian") != "little":
            raise ValueError("unsupported 28B layout")
    else:
        raise ValueError("unsupported point layout")
    if meta.get("point_file") != "points.bin":
        raise ValueError("point_file must be points.bin")
    frames = meta["frames"]
    if type(index) is not int or not 0 <= index < len(frames):
        raise ValueError("frame index out of range")
    size = (session / "points.bin").stat().st_size
    cursor = 0
    for frame in frames:
        start, count = frame["offset_points"], frame["count_points"]
        if type(start) is not int or type(count) is not int or count <= 0 or start != cursor:
            raise ValueError("invalid frame offsets/counts")
        cursor += count
    if cursor * stride != size:
        raise ValueError("binary length does not match frames")
    frame = frames[index]
    with (session / "points.bin").open("rb") as f:
        f.seek(frame["offset_points"]*stride)
        data = f.read(frame["count_points"]*stride)
    pts = np.ndarray((frame["count_points"],4),dtype="<f4",buffer=data,strides=(stride,4)).copy()
    if not np.isfinite(pts).all():
        raise ValueError("non-finite points")
    return pts, frame


def adapt(points, transform, model_z, intensity_divisor):
    r, t = np.asarray(transform["R"]), np.asarray(transform["t"])
    if r.shape != (3,3) or t.shape != (3,) or not np.isfinite(r).all() or not np.isfinite(t).all():
        raise ValueError("invalid transform")
    if not np.allclose(r @ r.T, np.eye(3), atol=1e-5) or not np.isclose(np.linalg.det(r),1,atol=1e-5):
        raise ValueError("transform must be a proper rigid rotation")
    if not np.isfinite(model_z) or not np.isfinite(intensity_divisor) or intensity_divisor <= 0:
        raise ValueError("invalid input adaptation")
    # Invalid/no-return XYZ must be removed before translation creates a false pile.
    if points.ndim != 2 or points.shape[1] != 4 or not np.isfinite(points).all():
        raise ValueError("invalid XYZI input")
    points = points[np.any(points[:,:3] != 0,axis=1)]
    if not len(points):
        raise ValueError("no valid nonzero points")
    out = points.copy()
    out[:,:3] = points[:,:3] @ r.T + t
    out[:,2] += model_z
    out[:,3] /= intensity_divisor
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["export","run"])
    parser.add_argument("--session", type=Path)
    parser.add_argument("--transform", type=Path)
    parser.add_argument("--frames", default="0,10,30")
    parser.add_argument("--model-z", type=float)
    parser.add_argument("--intensity-divisor", type=float)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", choices=["pointpillars","centerpoint"], default="pointpillars")
    parser.add_argument("--threads", type=int, default=4)
    args = parser.parse_args()
    if args.action == "export":
        if None in (args.session,args.transform,args.model_z,args.intensity_divisor):
            parser.error("export requires --session --transform --model-z --intensity-divisor")
        transform = json.loads(args.transform.read_text(encoding="utf-8"))
        source = {"meta_sha256":sha(args.session/"meta.json"), "bin_sha256":sha(args.session/"points.bin")}
        if transform.get("source") != source:
            raise ValueError("transform source hashes do not match selected session")
        args.out.mkdir(parents=True, exist_ok=False)
        records = []
        for index in map(int,args.frames.split(",")):
            points, frame = read_frame(args.session,index)
            cloud = adapt(points,transform,args.model_z,args.intensity_divisor)
            path = args.out / ("frame_%06d.bin" % index)
            cloud.astype("<f4").tofile(path)
            # nuScenes fifth feature is relative sweep time, not ring or device timestamp.
            np.column_stack((cloud,np.zeros(len(cloud),dtype=np.float32))).astype("<f4").tofile(path.with_suffix(".nus.bin"))
            records.append({"index":index,"seq":frame["seq"],"source_points":len(points),"points":len(cloud),
                            "dropped_zero_xyz":len(points)-len(cloud),"file":path.name,
                            "sha256":sha(path),"intensity_percentiles":np.percentile(points[:,3],[0,50,99,100]).tolist()})
        manifest = dict(source=source,session=str(args.session.resolve()),transform=str(args.transform.resolve()),
                        transform_sha256=sha(args.transform),model_z=args.model_z,intensity_divisor=args.intensity_divisor,
                        physical_verified=False,single_sweep=True,frames=records)
        (args.out/"manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
        print(json.dumps(manifest,indent=2))
        return
    if args.input is None:
        parser.error("run requires --input")
    args.out.mkdir(parents=True,exist_ok=False)
    try:
        import torch
        torch.set_num_threads(args.threads)
        if args.model == "pointpillars":
            from cpu_pointpillars import load_model
            upstream = Path(__file__).resolve().parent/"artifacts/upstream"
            model = load_model(upstream/"epoch_160.pth",upstream)
            names = ["Pedestrian","Cyclist","Car"]
        else:
            from mmdet3d.apis import LidarDet3DInferencer
            model = LidarDet3DInferencer(model="centerpoint_pillar02_second_secfpn_head-circlenms_8xb4-cyclic-20e_nus-3d",device="cpu")
        paths = sorted(args.input.glob("frame_*.bin")) if args.input.is_dir() else [args.input]
        paths = [p for p in paths if (".nus." in p.name) == (args.model == "centerpoint")]
        if not paths:
            raise ValueError("no input frames")
        records = []
        for path in paths:
            pts = np.fromfile(path,dtype="<f4").reshape(-1,4 if args.model=="pointpillars" else 5)
            start = time.perf_counter()
            with torch.inference_mode():
                if args.model == "pointpillars":
                    result = model([torch.from_numpy(pts)],mode="test")[0]
                    detections = [] if not isinstance(result,dict) else [dict(source="model",label=names[int(l)],
                        score=float(s),box_xyz_bottom_wlh_yaw=b.tolist()) for b,l,s in zip(result["lidar_bboxes"],result["labels"],result["scores"])]
                else:
                    result = model(dict(points=pts),no_save_vis=True,no_save_pred=True)["predictions"][0]
                    detections = dict(source="model",raw=result)
            seconds = time.perf_counter()-start
            row = dict(file=path.name,input_sha256=sha(path),seconds=seconds,detections=detections)
            records.append(row)
            print(json.dumps(row),flush=True)
        (args.out/"predictions.json").write_text(json.dumps(dict(model=args.model,device="cpu",source="model",
            physical_verified=False,accuracy_status="NOT_RUN: no human GT",frames=records),indent=2),encoding="utf-8")
    except Exception as error:
        import traceback
        (args.out/"BLOCKED.txt").write_text(traceback.format_exc(),encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
