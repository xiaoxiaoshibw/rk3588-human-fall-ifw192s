# HF-02 时间对齐、IMU 语义与数据失效
执行：OpenCode DeepSeek v4.1 Flash。依赖：HF-00 已知/未知清单、HF-01 契约。状态：**BLOCKED（设备核验）；软件 PASS（R1–R5 全闭合），整单未 ACCEPTED**，2026-10-01 Codex 第3轮复审。详见 [审查记录](../REVIEW_LOG.md)；[第3轮返工要求](../HF-02_REWORK_R3_PROMPT.md) 已完成，作为历史保留。当前需补IMU实际单位/轴向/偏置及物理偏移证据，融合禁用，HF-03未放行。原始单位/同步是本单要查的问题，不要求HF-00预先查清。先读 [CONTRACT.md](../CONTRACT.md) 的冻结范围，保留历史采样兼容边界；若改变已冻结输出字段或语义，先明确版本与兼容策略再实现。

先读 ../DISPATCH.md 并读取 ponytail SKILL.md。

## 工作与代码
- core/timebase.py：点云/IMU 的源域、证据支持的转换、session/time_epoch 与有限缓存匹配；无需图像同步器。相近 stamp/frame_id 不足以证明同钟。同步采集原始 stamp 与接收 monotonic，区分传输抖动/拟合残差和物理时间偏移；只有相关事件或厂商时间约定能支持的偏移才作校正。UTC 锚定不是首版强制条件。
- 重复/回退/大跳变重建 epoch、清历史、标 unknown；有界缓存和超时不无限等所有传感器。离线回放由消息时间推进，在线 freshness 用 monotonic。
- core/sensor_quality.py：IMU 与数据健康检查。设备 IMU 只用于静止重力参考/设备运动标记；缺方向时不伪造有效四元数。原始加速度单位必须证实后才转 SI。
- 确实需要驱动修复时，仅改 publish_manager.cpp 的对应转换：经过证实的 timestamp 单位、sec/nsec 进位、finite 检查、合法且有效的 orientation 复制或 orientation_covariance[0]=-1。SDK 默认单位四元数不构成有效估计，查 state 的实际语义。保留双 ROS 分支。
- 不仅靠 IMU 声称设备平移不存在；静态背景还检查地面/背景残差及现场重新初始化。

## 验收
注入纳秒进位、非法/重复/回退时间、单位错配、时钟偏移与漂移、IMU 晚到/停流及姿态无效；检查不乱配、不输出 NaN，记录传输与物理偏移证据的区别。实际单位用厂商协议或受控已知姿态/旋转核验，不能仅用静止近零角速度判尺度。若改 C++，验证适用 ROS 构建；未具备另一环境明确 NOT_RUN。

## 回传
修改前后的 SDK/厂商证据、映射参数来源、脚本日志、returns/HF-02.md。单位无法查清不得启用该路融合，可交离线测试但整单 BLOCKED。
