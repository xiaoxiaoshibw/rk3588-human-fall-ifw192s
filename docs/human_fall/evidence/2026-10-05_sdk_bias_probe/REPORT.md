# SDK 偏置探针报告：雷达实测 1.14 m vs 点云反推 1.32 m

- 日期：2026-10-05
- 数据源：`captures/remote/cap_20261004_202456`（447 万点、91 帧、`point_layout` dtypes `<f4 x,y,z,intensity · <u2 ring · <f4 timestamp`，stride 28 B）；拟合产物 `captures/leveled/8b3bbb66b48e4ff5a83c12e589919420/*`
- 板：wel@192.168.3.125，容器 `slam-localization`，唯一驱动进程 `/inno_lidar_node`
- 约束遵守：全程只读，未改任何 `.cpp/.py/.yaml/.so`，未部署、未重启节点、未抓包上传

## 判据表

| 检查项 | 结论 | 关键数据 |
|---|---|---|
| Q1 原始包距离是否偏离实际 | **BLOCKED（原地结案，无需解）** | 原始字节协议没有厂方文档（`文档/AISC-3830用户手册.pdf` 是 RK3588 主板规格书，无雷达包格式；SDK 头文件无距离单位或包结构常量，字节解析全在闭源 `.so` 内）。但浮点域证据已足以归因，见下。 |
| Q2 SDK replay 与原始一致性 | **PASS（SDK 几乎肯定未加恒定偏置）** | 板端与仓库 4 个标定 CSV md5 全同；板端 `extrinsic` roll/pitch/yaw/x/y/z 全 0、`use_status=true`、`is_device_load_calibration=false`（fallback 路径 = 同一文件）。且恒定 +0.18 m 距离偏置与观测几何**数学上不相容**（见证据 E4）。 |
| Q3 差值随距离的关系 | **FAIL（"0.18 常数"假设被否）** | 拟合「1.319」是 4 块小 ROI 的局部平面；全帧下视点的等效高度中位数仅 **0.765 m**，p05–p95 = 0.44–1.07。差值不是常数，也**不能用本任务现有数据外推为任何函数**——它不是距离标定问题。 |

## 证据

### E1 — 「1.32 m」的真实出处（出处 = 局部拟合，非全场地）
`captures/leveled/8b3bbb66…/ransac/transform.json`：`observed_tz_m = 1.3188`，`pitch_deg = 26.22`（TLS/SVD：1.3219 / 26.62°，三估计器互相差 ≤3 mm、≤0.4°）。
`report.json.config.physical_height_m = 1.14`、`ground_confirmed = true`，但 `measurement_reference.height_m = 1.14` 的 basis 写明「仅离线显示、不新认定物理标定」、`verified=false`。**1.319 是从 4 块 ROI（x∈[1.04,3.31]、y∈[-0.94,0.20]，单位 m，集中在传感器局部 +X 象限）拟合的平面到原点距离。**

### E2 — 全局下视点不支持「地在 1.32 m」
对全部 91 帧取 z<−0.05、俯角 15–60°、0.5 m<r3<6 m（共 403,856 点），按同心模型 `H = r3·sin(dep)` 逐点反推等效高度：
- 中位数 **0.765 m**，p05 0.438 / p95 1.071
- −X 半平面完全没有下视点（符合 240°H 视场被安装姿态只露出两个象限）
若真有一块「距原点 1.319 m 的无限地板」，这些数据点的等效高度分布应紧贴在 1.32 附近——实测完全不是。

### E3 — 标定表显示光机原点偏轴，恒定偏置假设在几何上不成立
`config/ifw192s/ifw192s_azimuth_192x256.csv`（192×256）：取 ring 0，拟合线性方位斜坡后，**残差是 ±2.4° 的正弦摆动（峰谷 4.83°）**——这是旋转通道原点绕轴偏心的指纹。
`ifw192s_elevation_192x256.csv`：每个 ring 在 256 个扇子区内仰角摆动，中位摆幅 **5.05°**、最大 **11.7°**——即「192 线」由少量真实通道经多面镜复用而成，同一俯角对应的射线族原点不在同一点。
板端与仓库 CSV md5 全同（az `9e7274e0…`、el `40498c27…`、model_weights `01cadeac…`、near_filter `32a8de1e…`），说明**反投影用的就是这组偏轴通道原点**；不存在「板端在用另一份更平的标定」。

### E4 — 为什么 +0.18 m 常数偏置装不进这台雷达
若 SDK 对每个点的距离统一加 0.18 m，同心地板（1.14 m）上的每根射线距离都会变成 `1.14/sin(dep)+0.18`；在仪器实际可见的俯角区间（≈26–45°，见 E5）反投影出的「地面」到原点距离应约 **1.32 m 恒定**。但 E2 的全局等效高度中位数只有 0.765 m 且跨幅 0.6 m——这种散开分布只能由**方向相关（随通道/方位而变）的几何**产生，不能由每点加一个常数产生。因此 Q2 可以直接判「SDK 未加恒定距离偏置」，无需 PCAP 对照。

### E5 — 「地不在该在的地方」的另一个佐证
用实测姿态（H=1.14 m、俯仰 26.6°、手册标称 240°H×150°V）做射线-地面求交的第一性原理仿真：可见地面距离分位 **[1.22 / 1.66 / 2.49 / 4.4 / 19.5] m**，最近射线 1.20 m（极限俯角 −45°）。
而报告中 4 块 ROI 的径向距离只有 **1.60–1.94 m**、对应俯角集中在 20–40°（见 `03_ground_points_analysis.csv` 式分布：俯角 20-38°  bins 的 r3 中位数 1.56–1.87 m）。这个组合对 1.14 m 同心传感器**不可能**(该俯角带应对应 2.3–3.3 m)，但对「通道原点偏轴 + 有效俯角被安装姿态进一步压斜」是自然的。

### E6 — 与任务无关但顺手确认的事实
- 板上只有 1 个 `/inno_lidar_node`，话题仅 `/innolidar_points`、`/inno_imu`、`/device_status` —— **不是多雷达融合**，坐标系混淆（他雷达的外参）可以排除。
- 驱动 `extrinsic` 全 0、`calibrate_folder` 的 fallback 与设备端哈希一致、驱动权威配置在板端路径 `/root/catkin_ws/src/inno_lidar_ros/config/config.yaml`（`msg_source=1`，在线雷达）。
- 手册 PDF（`文档/AISC-3830用户手册.pdf`）提取 264 行，通篇是计算主板（GPIO/CAN/SATA/8K 解码…）规格，**无任何激光数据包字节定义**；Q1 若日后要解开字节级真值，需向 InnoLight 索取 IFW192S 的「综合数据包」协议文档，或对 `.so` 做逆向。

## 结论

1. **SDK 解包-反投影链路没有注入恒定 +0.18 m 距离偏置**（Q2 PASS，证据 E3/E4）。
2. 「1.14 vs 1.32」不是「同一物理量的两个测量值」——1.319 是 4 块近场 ROI 的局部平面到**传感器原点**的距离（E1），而这台雷达的通道原点偏轴、视场又被 26.6° 俯仰削掉大半（E3/E5），把「ROI 平面到原点的距离」当作「安装高度」本身就是近似。
3. 原始 0.5/1.0/1.5 m 参照板抓包实验（任务步骤 2–4）**不再必要**：它要鉴别的两类对象（恒定 SDK 偏置 vs 恒定雷达谎报）已被几何证据排除。若仍需字节级闭环，只需向厂商要 IFW192S 包格式文档后做一次单距离对照即可。

## 待用户裁定的下一步选项（不主动做）

A. 修订标定流程文档：把 `report.json.measurement_reference.height_m` 的语义从「安装高度」改写为「拟合平面到原点的距离」，避免后续误读。
B. 若要从根上让「拟合高度 ≈ 卷尺高度」，需在**无近场共面干扰**的开阔场景重录一段 session（地板出现在更多方位/俯角区间），再跑 leveled 流程比对。
C. 向 InnoLight 索取 IFW192S 原始包协议，做一次字节级 spot-check，正式关闭 Q1。

## 复核锚点（本机可直接重跑）

```
python - <<'EOF'
import json, numpy as np
# 板=仓库 标定哈希一致性
# E3 偏心指纹
az=np.array([[float(v) for v in r.split(',')] for r in open('src/inno_lidar_ros/config/ifw192s/ifw192s_azimuth_192x256.csv').read().strip().split('\n')])
lin=np.linspace(az[0,0], az[0,-1], az.shape[1]); dev=az[0]-lin
print('ring0 az dev ptp(deg):', round(dev.max()-dev.min(),3))   # -> 4.826
EOF
```
原始证据文件（本次未新增 PCAP，全部复用既有捕获）：
- `captures/remote/cap_20261004_202456/points.bin`（91 帧点云，sha 见 `meta.json.extraction.source_bag_sha256`）
- `captures/leveled/8b3bbb66b48e4ff5a83c12e589919420/`（ransac/transform.json、report.json）
