# -*- coding: utf-8 -*-
"""HR-06 demo — python-pcl SAC_RANSAC 平面拟合

合成一块「平面 + 噪点 + 一个凸起」的 1000 点云，跑 PCL RANSAC 拟合。
输出 3 行（最后一行必须与真值夹角 < 1 度才 PASS）。

设计：
  - 真值平面：z = 0.3x + 0.4y + 0.5  → 法向量 n = (0.3, 0.4, -1) 归一化
  - 900 点平面采样（高斯抖动 σ=0.02m）
  - 80 点空气噪点（均匀）
  - 20 点「凸起」聚集 (x∈[2,2.5], y∈[3,3.5], z=2.0) —— 模拟人形
  - PCL RANSAC 应该锁住 900 内点，噪点 / 凸起被丢出。
"""
import sys
import numpy as np
import pcl

# ---- 合成点云 -------------------------------------------------------------
rng = np.random.RandomState(42)
N_PLANE, N_NOISE, N_PERSON = 900, 80, 20

# 平面：z = 0.3x + 0.4y + 0.5
xs = rng.uniform(0, 10, N_PLANE)
ys = rng.uniform(0, 10, N_PLANE)
plane_z = 0.3 * xs + 0.4 * ys + 0.5
plane_z += rng.normal(0, 0.02, N_PLANE)  # 20mm 抖动
plane_pts = np.stack([xs, ys, plane_z], axis=1).astype(np.float32)

# 噪点：均匀在 [-2,12]^2 × [-1,3]
noise = rng.uniform([-2, -2, -1], [12, 12, 3], (N_NOISE, 3)).astype(np.float32)

# 凸起：人形聚集 z≈2.0
person = np.stack([
    rng.uniform(2.0, 2.5, N_PERSON),
    rng.uniform(3.0, 3.5, N_PERSON),
    rng.uniform(0.5, 2.0, N_PERSON),
], axis=1).astype(np.float32)

cloud_np = np.vstack([plane_pts, noise, person])

# ---- PCL: SAC_RANSAC + SACMODEL_PLANE -------------------------------------
cloud = pcl.PointCloud(cloud_np)
seg = cloud.make_segmenter()
seg.set_model_type(pcl.SACMODEL_PLANE)
seg.set_method_type(pcl.SAC_RANSAC)
seg.set_distance_threshold(0.05)       # 5cm 内算内点
seg.set_max_iterations(200)
indices, coefficients = seg.segment()

if len(indices) == 0:
    print("FAILED: 无内点", file=sys.stderr)
    sys.exit(1)

# coefficients = [a, b, c, d]，平面 ax+by+cz+d=0，法向量 (a,b,c)
n_fit = np.array(coefficients[:3], dtype=np.float64)
n_fit = n_fit / np.linalg.norm(n_fit)
# 真值：z = 0.3x+0.4y+0.5 → 0.3x+0.4y -z + 0.5 = 0 → n_true = (0.3, 0.4, -1)
n_true = np.array([0.3, 0.4, -1.0]); n_true /= np.linalg.norm(n_true)

# 法向量方向可能反 → 取绝对值
cos_angle = abs(float(np.dot(n_fit, n_true)))
angle_deg = float(np.degrees(np.arccos(np.clip(cos_angle, -1, 1))))

print("法向量:  n_fit=(%.4f, %.4f, %.4f)  n_true=(%.4f, %.4f, %.4f)"
      % (n_fit[0], n_fit[1], n_fit[2], n_true[0], n_true[1], n_true[2]))
print("内点数:  %d / %d  (期望≈%d，含平面真点)" % (len(indices), len(cloud_np), N_PLANE))
print("夹角:  %.3f deg  (PASS 若 < 1.0)" % angle_deg)

sys.exit(0 if angle_deg < 1.0 else 2)
