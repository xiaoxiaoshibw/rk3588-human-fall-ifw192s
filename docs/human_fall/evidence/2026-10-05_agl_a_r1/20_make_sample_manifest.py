"""GL-A 示例 manifest 生成器（证据内脚本，非生产代码）。

用合成已知平面构建同一 PointDomain，运行三个薄适配器，输出 JSON 安全的
equipment 记录样例（供解耦的展示/工作台集成阶段消费结构参考）。
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "src" / "human_fall_detection"))

from core.adaptive_ground.contracts import (display_rotation, estimator_config_id,
                                            resolve_estimator_config)
from core.adaptive_ground.estimators import ESTIMATORS
from core.adaptive_ground.selection import build_point_domain, point_domain_reference


def main():
    config = {"inlier_threshold_m": 0.05, "min_inliers": 100, "min_inlier_fraction": 0.2,
              "ransac_iterations": 861, "ransac_iteration_hard_cap": 2000,
              "seed": 20261001}
    resolved = resolve_estimator_config(config)
    pitch, roll, height = 26.623261, -1.394671, 1.3200
    rotation = np.array(display_rotation(pitch, roll))
    axis = np.arange(-1.0, 1.0001, 0.05)
    grid_x, grid_y = np.meshgrid(axis, axis)
    display = np.column_stack([grid_x.ravel(), grid_y.ravel(), np.zeros(grid_x.size)])
    display[:, 2] += np.random.RandomState(20261005).normal(0.0, 0.004, grid_x.size)
    points = (rotation.T @ (display - np.array([0.0, 0.0, height])).T).T
    domain = build_point_domain(
        points,
        {"stream_instance_id": "stream:synthetic", "session_id": "session:agl-a-sample",
         "reference_epoch": 0, "ordinal": 0, "seq": 0, "source_frame": "innolidar",
         "source_stamp": 0.0, "time_domain": "device_seconds"},
        {"selector_id": "synthetic-grid-v1", "version": 1},
        estimator_config_id(resolved), "synthetic known plane (sample manifest, offline)",
        {"up_axis": [0.0, 0.0, 1.0], "provenance": "synthetic identity reference",
         "version": 1})
    manifest = {
        "kind": "agl_a_sample_manifest", "schema": 1,
        "description": "GL-A synthetic sample: one shared PointDomain + three estimator records",
        "estimator_config": resolved,
        "point_domain": point_domain_reference(domain),
        "estimators": {name: ESTIMATORS[name](domain, config)
                       for name in ("tls", "svd", "ransac")},
        "notes": ["offline synthetic data only",
                  "physical_verified / extrinsics_verified / runtime flags are absent by design",
                  "records are JSON-safe for decoupled display consumption"]}
    raw = json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False).encode("utf8")
    target = Path(__file__).with_name("20_sample_manifest.json")
    target.write_bytes(raw)
    print("wrote", target)
    print("sha256", hashlib.sha256(raw).hexdigest())
    return 0


if __name__ == "__main__":
    sys.exit(main())
