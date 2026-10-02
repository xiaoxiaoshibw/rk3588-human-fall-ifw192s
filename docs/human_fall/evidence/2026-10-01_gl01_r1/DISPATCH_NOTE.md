# GL-01 合成原型派工 / 2026-10-01

GL-00 R4软件/协议PASS，真实物理BLOCKED。先读 ../2026-10-01_gl00_r4/CODEX_REVIEW.md、approved_protocol.json及本工单。使用本目录ponytail_SKILL.md（真实源及哈希见GL00记录）。模型opencode-go/deepseek-v4.1-flash；GL-01新会话，禁止自行推进GL-02。

范围：ground.py、calibrate_sensors.py、新增独立geometry配置、相关几何测试、本单方案/证据/回传；geometry.yaml/default.yaml保持冻结。不得改candidate/tracking/runtime/UI/driver，不部署/采集/重启。Windows纯函数，已授权板端隔离副本可验证Python3.8.10/NumPy1.17.4；无需ROS构建不伪称已构建。

尽量复用旧实现，加显式新约束路径，旧默认API/行为兼容。遵循获审protocol和CODEX_REVIEW补充口径（逐验证区门槛，非聚合；基底来自显式up_axis；3点互异/面积定义；降序eigen退化；法向/高度约束在支持计数前；SVD后重新计算原点集支持；K<=3但不可用截断掩盖竞争歧义）。所有参数严格拒绝bool/NaN/Inf/负数/非整数，不静默截断。保存源索引和诊断采样/迭代/候选量。

CLI提供明确的fit/validation ROI与帧组/源索引分离输入，不能把随机点拆分伪称独立验证。数值文件可用显式划分索引/区域输入；bag在Linux由冻结解码器读，不用自写固定布局替代。清晰的region/group元数据，检测重叠和不足。缺up_axis/height interval/独立区域则失败，不隐含world-Z或把1.1m当真值。

软件验收：倾斜地面、墙占多数、桌面竞争、缺地面、少点/重复/共线、非法数值、方向和高度冲突、区域验证单区失败、重叠索引/帧组，旧回归无退化。对同synthetic样本旧/新路径对照身份/残差/耗时，不叫device真值。真实bag可保持NOT_RUN/BLOCKED（未确认ROI），不需要再对现场强拟合。

软件quality可用不意味着物理verified；未确认数据不能有效启用地面。所有verification flags保持false，confirmed/IMU融合禁用。回传returns/GL-01.md只SUBMITTED/BLOCKED，记实际修改列表/函数/版本/测试命令/内外退出码/失败与缺项。证据本目录，旧证据不覆写。先运行本地实质用例，之后按需隔离板端兼容检查；SSH用LF脚本，禁止chr/复杂引号串。
