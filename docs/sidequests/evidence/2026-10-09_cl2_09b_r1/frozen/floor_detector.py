"""Automatic lowest connected floor patches; select whole XY cells, never trim fit rows."""
from collections import deque
import math
import numpy as np

from leveling_estimators import ESTIMATORS
from leveling_quality import rotation

PROFILE = {"id": "lowest_connected_floor_v1", "voxel_m": .1, "cell_m": .25,
           "normal_alignment_min": .94, "offset_range_m": [.8, 1.8], "discovery_band_m": .08,
           "cell_height_span_max_m": .18, "cell_floor_gap_max_m": .08,
           "cell_local_rms_max_m": .025, "min_points_per_fit_frame": 30,
           "min_component_cells": 8, "min_component_axis_m": .5, "max_discovery_planes": 6}


def components(cells):
    remaining = set(cells)
    out = []
    while remaining:
        seed = min(remaining); remaining.remove(seed)
        queue = deque([seed]); component = []
        while queue:
            key = queue.popleft(); component.append(key)
            for neighbor in ((key[0]-1,key[1]),(key[0]+1,key[1]),(key[0],key[1]-1),(key[0],key[1]+1)):
                if neighbor in remaining:
                    remaining.remove(neighbor); queue.append(neighbor)
        out.append(component)
    return out


def detect_floor_regions(points, frame_ids, pitch_deg, roll_deg):
    points = np.asarray(points, dtype="f8")
    frame_ids = np.asarray(frame_ids)
    if points.ndim != 2 or points.shape[1] != 3 or len(points) != len(frame_ids):
        raise ValueError("floor_input_invalid: points/frame_ids")
    # Candidate workspace bound only; final ROI freezing still consumes every source row.
    valid = np.isfinite(points).all(axis=1) & np.any(points != 0, axis=1) & (np.abs(points) <= 100).all(axis=1)
    points, frame_ids = points[valid], frame_ids[valid]
    if len(points) < 120:
        raise ValueError("floor_not_found: insufficient points")
    initial = rotation(pitch_deg, roll_deg); anchor = initial[2]
    frames = np.unique(frame_ids)
    frame_index = np.searchsorted(frames, frame_ids)
    # Spatial centroids remove sensor-density bias for plane discovery, not final estimation.
    voxel = np.floor(points / PROFILE["voxel_m"]).astype("i4")
    _, inverse = np.unique(voxel, axis=0, return_inverse=True)
    count = np.bincount(inverse)
    representatives = np.column_stack([np.bincount(inverse, weights=points[:,i])/count for i in range(3)])
    remaining = representatives
    planes = []
    for _ in range(PROFILE["max_discovery_planes"]):
        if len(remaining) < 80:
            break
        normal, offset = ESTIMATORS["ransac"](remaining)
        if normal @ anchor < 0:
            normal, offset = -normal, -offset
        distances = np.abs(remaining @ normal + offset)
        inliers = distances <= PROFILE["discovery_band_m"]
        if (normal @ anchor >= PROFILE["normal_alignment_min"]
                and PROFILE["offset_range_m"][0] <= offset <= PROFILE["offset_range_m"][1]):
            planes.append((normal.copy(), float(offset), int(inliers.sum())))
        if not inliers.any():
            break
        remaining = remaining[~inliers]
    if not planes:
        raise ValueError("floor_not_found: no horizontal plane in floor-height hypothesis")
    display = points @ initial.T
    keys = np.floor(display[:,:2] / PROFILE["cell_m"]).astype("i4")
    unique, inverse = np.unique(keys, axis=0, return_inverse=True)
    order = np.argsort(inverse, kind="stable")
    splits = np.r_[0, np.cumsum(np.bincount(inverse))]
    # Check entire cell height and local surface before calling it a clean floor patch.
    clean = {}
    for i, key_array in enumerate(unique):
        indices = order[splits[i]:splits[i+1]]
        counts = np.bincount(frame_index[indices], minlength=len(frames))
        if counts.min() < PROFILE["min_points_per_fit_frame"]:
            continue
        cell = display[indices]
        height_span = float(np.ptp(cell[:,2]))
        if height_span > PROFILE["cell_height_span_max_m"]:
            continue  # one high object point excludes the whole cell, not only that point
        values, vectors = np.linalg.eigh(np.cov(cell.T))
        local_normal = vectors[:,0]
        local_rms = math.sqrt(max(0., float(values[0])))
        if abs(local_normal[2]) < PROFILE["normal_alignment_min"] or local_rms > PROFILE["cell_local_rms_max_m"]:
            continue
        key = tuple(int(v) for v in key_array)
        clean[key] = {"count":len(indices), "min_frame_count":int(counts.min()),
                      "center":cell.mean(axis=0), "z_min":float(cell[:,2].min()),
                      "z_max":float(cell[:,2].max()), "height_span_m":height_span,
                      "local_rms_m":local_rms, "local_normal_z":float(abs(local_normal[2]))}
    failures = []
    # Of horizontal hypotheses, a floor is the lower connected sheet, not the densest patch.
    for normal, offset, discovery_count in sorted(planes, key=lambda p: -p[1]):
        nd = initial @ normal
        floor_cells = {}
        for key, cell in clean.items():
            center = cell["center"]
            predicted = -(nd[0]*center[0] + nd[1]*center[1] + offset)/nd[2]
            if abs(center[2]-predicted) <= PROFILE["cell_floor_gap_max_m"] and abs(cell["z_min"]-predicted) <= PROFILE["cell_height_span_max_m"]:
                floor_cells[key] = cell
        groups = sorted(components(floor_cells), key=lambda g: (-len(g), min(g)))
        for group in groups:
            xy = np.array(group)
            span = (np.ptp(xy,axis=0)+1)*PROFILE["cell_m"]
            if len(group) < PROFILE["min_component_cells"] or span.min() < PROFILE["min_component_axis_m"]:
                continue
            centers = (xy+.5)*PROFILE["cell_m"]
            lo, hi = centers.min(axis=0), centers.max(axis=0)
            selected = []
            for fx, fy in ((.25,.25),(.75,.25),(.25,.75),(.75,.75)):
                target = lo+(hi-lo)*[fx,fy]
                choices = [k for k in group if k not in selected]
                key = min(choices, key=lambda k: (float(np.linalg.norm((np.array(k)+.5)*PROFILE["cell_m"]-target)), -floor_cells[k]["min_frame_count"], k))
                selected.append(key)
            regions = [[k[0]*.25,(k[0]+1)*.25,k[1]*.25,(k[1]+1)*.25] for k in selected]
            details = [{"bounds":r, **{key:value for key,value in floor_cells[k].items() if key != "center"}} for k,r in zip(selected,regions)]
            return {"regions":regions, "candidate":{"kind":PROFILE["id"],"profile":dict(PROFILE),
                    "normal_source":normal.tolist(),"offset_source_m":offset,
                    "pitch_deg":math.degrees(math.atan2(-normal[0],normal[2])),
                    "roll_deg":math.degrees(math.asin(float(np.clip(normal[1],-1,1)))),
                    "support_ratio":float(np.mean(np.abs(points @ normal+offset)<=.08)),
                    "discovery_voxels":len(representatives),"plane_voxels":discovery_count,
                    "fit_frame_count":len(frames),"component_cells":len(group),"component_area_m2":len(group)*.25**2,
                    "component_span_m":span.tolist(),"selected_cells":details,
                    "full_height_preserved":True,"uses_manual_reference":False,
                    "basis":"lowest horizontal connected sheet; full-height obstacle rejection; four interior patches; FIT frames only"}}
        failures.append({"offset_m":offset,"clean_floor_cells":len(floor_cells)})
    raise ValueError("floor_regions_invalid: no connected unobstructed floor component; " + str(failures))
