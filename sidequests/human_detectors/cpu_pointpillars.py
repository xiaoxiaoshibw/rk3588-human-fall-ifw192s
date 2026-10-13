"""Inference-only CPU operators for zhulf0804/PointPillars, not a training port."""
import ast
import hashlib
import json
from pathlib import Path

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from shapely.geometry import Polygon


class Voxelization(nn.Module):
    def __init__(self, voxel_size, point_cloud_range, max_num_points, max_voxels):
        super().__init__()
        self.size = np.asarray(voxel_size, dtype=np.float32)
        self.bounds = np.asarray(point_cloud_range, dtype=np.float32)
        self.max_points, self.max_voxels = max_num_points, max_voxels

    def forward(self, points):
        pts = points.detach().cpu().numpy()
        valid = np.isfinite(pts).all(axis=1)
        valid &= ((pts[:, :3] >= self.bounds[:3]) & (pts[:, :3] < self.bounds[3:])).all(axis=1)
        pts = pts[valid]
        coords = np.floor((pts[:, :3] - self.bounds[:3]) / self.size).astype(np.int32)
        # ponytail: one frame, first-seen deterministic voxels; compiled ops for throughput.
        table, rows, counts = {}, [], []
        voxels = np.zeros((self.max_voxels[1], self.max_points, points.shape[1]), dtype=np.float32)
        for p, c in zip(pts, coords):
            key = tuple(c)
            idx = table.get(key)
            if idx is None:
                if len(rows) >= len(voxels):
                    continue
                idx = len(rows)
                table[key] = idx
                rows.append(c)
                counts.append(0)
            if counts[idx] < self.max_points:
                voxels[idx, counts[idx]] = p
                counts[idx] += 1
        if not rows:
            raise ValueError("no points in model range")
        return (torch.from_numpy(voxels[:len(rows)]), torch.tensor(np.asarray(rows)),
                torch.tensor(counts, dtype=torch.int32))


def nms_cuda(boxes, scores, thresh, pre_maxsize=None, post_max_size=None, clockwise=True):
    """CPU polygon IoU; pinned upstream uses xyxy + clockwise KITTI ry.

    clockwise=False exists only to reproduce pre-DET03 evidence, not a model setting.
    """
    polys = []
    for x1, y1, x2, y2, yaw in boxes.detach().cpu().numpy():
        center = np.array([(x1+x2)/2, (y1+y2)/2])
        corners = np.array([[x1,y1],[x2,y1],[x2,y2],[x1,y2]]) - center
        yaw = -yaw if clockwise else yaw
        c, s = np.cos(yaw), np.sin(yaw)
        polys.append(Polygon(corners @ np.array([[c,s],[-s,c]]) + center))
    order = scores.detach().cpu().sort(descending=True).indices.numpy()
    if pre_maxsize is not None:
        order = order[:pre_maxsize]
    keep = []
    for idx in order:
        if all(polys[idx].intersection(polys[j]).area /
               polys[idx].union(polys[j]).area <= thresh for j in keep):
            keep.append(int(idx))
            if post_max_size is not None and len(keep) == post_max_size:
                break
    return torch.tensor(keep, dtype=torch.long)


def limit_period(value, offset=0.5, period=np.pi):
    return value - torch.floor(value / period + offset) * period


def load_model(checkpoint, upstream):
    """Reuse upstream class bodies, omitting training/CUDA-only import statements."""
    upstream = Path(upstream)
    provenance = json.loads((upstream / "provenance.json").read_text(encoding="utf-8"))
    for record in provenance["files"]:
        if hashlib.sha256((upstream / record["file"]).read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError("upstream hash mismatch: " + record["file"])
    namespace = dict(np=np, torch=torch, nn=nn, F=F, Voxelization=Voxelization,
                     nms_cuda=nms_cuda, limit_period=limit_period)
    for filename in ("anchors.py", "pointpillars.py"):
        source = (Path(upstream) / filename).read_text(encoding="utf-8")
        source = source.replace("torch.meshgrid(x_centers, y_centers, z_centers, rotations)",
                                "torch.meshgrid(x_centers, y_centers, z_centers, rotations, indexing='ij')")
        parsed = ast.parse(source)
        parsed.body = [n for n in parsed.body if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
        exec(compile(parsed, filename, "exec"), namespace)
    model = namespace["PointPillars"]().cpu().eval()
    # Only tensors accepted; strict loading prevents missing/randomly initialized layers.
    state = torch.load(checkpoint, map_location="cpu", weights_only=True)
    model.load_state_dict(state, strict=True)
    return model
