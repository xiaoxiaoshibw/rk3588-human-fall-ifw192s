# GL-01 Codex独立复审 / 2026-10-01

软件（显式合成约束拟合/数值CLI/加载器）PASS；真实来源/地面/物理BLOCKED。允许GL-02软件数学/候选配平预览，不允许实际标定启用或部署。

Codex独立244项回归和两套6方法（共12方法）通过、各exit0，50～52日志。R4板端244项通过，Python3.8.10/NumPy1.17.4；ground.py 228931ce9e3dfe8bbaeae88d8a419617fcc78cf91b3cf5a6c9a1ecb506097067/test bee55d7d…06dc对应本地。沿源索引/候选计数/精修/逐区验证/产物加载/CLI失败产物路径复审，原9/10独立失败已闭合。

改动范围ground.py、calibrate_sensors.py、新独立geometry_constrained.yaml及相关测试/证据。冻结geometry/default、candidate/tracking/runtime/UI/driver未改，旧路径244回归保持。与R1全基线对比另发现hardware_inventory.md新增人工截图俯角估计约26度（25～27度），GL01写入事件未涉及该文件，保留来源未归因的文档差异，不擅自还原；其为截图粗估，不作为已验证安装角。

实现采用最多3个输出候选，同时最多8个内部竞争候选以防输出K=1隐藏歧义；超内部预算明确orientation_unverified。此为获审允许的有界竞争证据设计，不作为无竞争面证明。低地面支持/非法参数/退化/缺分组/不足区域明确失败，未通过记录保留原因。

CLI新constrained --bag明确拒绝：旧加载器过滤/汇总后索引不能回溯原帧点，尚不满足真实帧组验证。软件PASS仅覆盖合成数值输入；真实来源适配和现场参数仍BLOCKED。无新采集/部署/driver或网络操作。

R1/R2两次HTTP400及原日志保留；指定模型最小probe通过，OpenCode官方summarize接口同session/同model压缩成功，R3/R4续接可用。失败首次板端缺sibling/打包路径错误保留在事件日志，不把外层CLI0当验收。

GL02需复用已审严格constrained validator，不能仅调用旧validate_ground_plane后加载新字段；derived变换不进入measured extrinsics；未知物理flags false。视图/数学可用与离地物理已核验分开。
