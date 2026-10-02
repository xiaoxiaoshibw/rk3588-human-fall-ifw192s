# HF-03已实现几何接口 v1

2026-10-01：Codex第2轮软件复审PASS，基于core/calibration.py、ground.py和calibrate_sensors.py的实际实现。此文档冻结后续软件消费的数值/坐标/质量语义；不表示真实设备安装、IMU旋转或地面物理已验收。HF-01的CONTRACT.md保持不变。

## 坐标与数值

长度m、角度rad。变换记录的from_frame/to_frame和`p_to = R @ p_from + t`为权威方向；反变换R.T与-R.T t。旋转为3×3有限正交det+1矩阵，平移为3项有限米值；mm只能经显式转换。unknown记录rotation/translation为空，不按frame_id补身份矩阵。synthetic证据不会成为verified。

地面为单位法向n与偏移d表示的`n.p+d=0`；向上法向、地面在传感器下方时d>0，原点离地高度=d。点的地面相对高度=n.p+d；其地面投影=p-(n.p+d)n。原始雷达XY不一定是水平面，后续可从n构造切平面基底，必须标明派生自雷达而非已测得世界坐标。

## 独立标定产物

kind=geometry_calibration、schema_version=1。calibration_id、created_at_utc、units、frames、transforms、rotations、ground、sensor_height_m、status、verification、input、note各按当前构造器输出。frames.lidar明确来源，frames.reference可null；未测T_reference_lidar和R_lidar_imu保持unknown。input记录bag/数值文件名、sha256、帧数与点数，不改原始采样。

ground.status为valid/orientation_unverified/invalid，normal、offset_m、frame、sensor_height_m、tilt_rad、fit_inlier_count/inlier_fraction、fit_residual、holdout_residual、holdout_support、valid_region和settings记录拟合与验证。valid表示几何拟合/支持通过，**不等于ground_physical_verified**。未通过地面不能用于有效跌倒高度；可保留候选平面参数作诊断。读取产物须调用validate_geometry_calibration，不用字段缺失的伪valid记录。

holdout_residual保留全部留出场景点的count/RMS/max，包括合法非地面点；holdout_support记录阈值内地面点count/fraction/RMS/max。判据使用足够支持点、独立支持率及地面支持残差；全部场景点RMS高不能单独证明地面平面错误。默认support门槛0.5为未做现场调参的工程参数，真实bag当前0.242未通过，物理证据仍未知。

valid_region为采样地面支持区域，包含XYZ/range bounds与点数；它是地面覆盖范围，不是人体可占据的三维空间。后续人体范围检查应对地面投影做覆盖判断，不能用地面窄z范围筛掉站立或低卧目标。

## 模式与验证边界

verification.ground_physical_verified/extrinsics_verified/imu_alignment_verified默认false；status/数值/evidence不能与其矛盾。当前真实外参、IMU与地面物理未验证，融合禁用；后续位置可在innolidar显示，不能标成已标定世界坐标。当前几何软件可继续实现候选/锁定/状态机，confirmed需独立模式验收门控，不能凭合成回归或平面拟合自动开启。

软件证据见REVIEW_LOG.md及evidence/2026-10-01_autonomous_hf03_r2/10–14。本地/板上92项回归与6项独立边界通过。地面标定工具失败返回明确invalid产物和exit2；验证成功产物仍按physical flags报告未知。
