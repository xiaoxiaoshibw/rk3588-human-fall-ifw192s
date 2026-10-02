# HF-03 雷达安装、地面与 IMU 旋转标定
执行：OpenCode DeepSeek v4.1 Flash。依赖：HF-01契约、HF-02软件PASS。状态：软件PASS（2026-10-01第2轮，独立两端92回归/6边界通过）；真实安装/IMU/地面物理验证BLOCKED/NOT_VERIFIED，整单未ACCEPTED。依用户新授权继续独立几何软件路线HF04–06，融合禁用。接口见 [GEOMETRY_CONTRACT.md](../GEOMETRY_CONTRACT.md)，恢复信息见 [AUTONOMOUS_RUN.md](../AUTONOMOUS_RUN.md)。

先读 ../DISPATCH.md 并读取 ponytail SKILL.md。

## 工作与代码
- scripts/calibrate_sensors.py、core/calibration.py：确定固定安装下 LiDAR 到场地/底盘参考系的变换，明确方向、轴和 m/rad 单位；优先采安装测量和多位置几何证据，不引入相机、PnP 或 OpenCV。
- 记录 T_reference_lidar 将 LiDAR 点转到参考系，R_lidar_imu 将 IMU 向量转到 LiDAR 系；检查刚体/旋转矩阵。没有 IMU 安装证据就标 unknown，不因 frame_id 相同直接设 identity。
- IMU 在已证实单位后用多个已知静止姿态核验重力方向；重力只能约束部分旋转，不能单靠一个静止方向解完整 yaw/外参。无法识别的参数保持未验证，几何基线可独立完成。
- core/ground.py：静止点云拟合/验证地面平面，记录法向、传感器高度、残差与有效范围；IMU 已验证安装旋转后才用于重力一致性检查。阈值有单位，不通过把地面点全部删掉来掩盖低姿态目标。
- 新标定 schema 独立于旧人体标定 JSON。记录版本/哈希、设备安装、地面有效区域、可用/未知旋转与采集条件；装置移动/异常残差要求重新初始化。雷达内部 CSV 与单站位表面距离残差都不能代替外部安装标定。
- 按 [WEBUI_SCOPE.md](../WEBUI_SCOPE.md) 明确网页显示位置的坐标系和定义（稳健点云中心/地面投影），给后续框/位置输出提供标定版本。网页选人与站姿基线请求留给 HF-05/11，不能用屏幕像素或点击结果代替地面/安装标定。

## 验收
合成几何检查变换反向、轴符号/米毫米错配、非刚体矩阵、地面倾斜与缺地面；真机留出位置/高度验证地面残差与目标高度误差。地面点不足、水平/垂直面混淆和 IMU 旋转未知应明确失效，不报假标定。门槛提交 Codex 冻结，不仅报拟合样本误差。

## 回传
标定流程、地面/目标三维示意、留出样本、参数/误差表、returns/HF-03.md；几何标定与 IMU 辅助旋转验收分列，不因 IMU 未知而伪造旋转或把几何模式标成融合通过。
