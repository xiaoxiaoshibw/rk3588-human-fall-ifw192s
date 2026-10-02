# GL-01 约束地面拟合与验证原型

执行：OpenCode DeepSeek v4.1 Flash；审核：Codex。状态：WAIT_DEPENDENCY。前置：GL-00方法/参数方案获审；若仅允许合成原型，回传必须保留真实数据BLOCKED。

## 方法与任务

2026-10-01前置已满足（仅合成原型）：GL-00 R4软件PASS/物理BLOCKED。按 ../evidence/2026-10-01_gl00_r4/24_synthetic_protocol.json 与 CODEX_REVIEW.md实施；默认路径与冻结配置保留，真实参数/数据结论仍BLOCKED。

借鉴 [PCL约束模型](https://github.com/PointCloudLibrary/pcl/blob/master/sample_consensus/include/pcl/sample_consensus/impl/sac_model_perpendicular_plane.hpp)，改造现有NumPy ground.py，不新建库或全新算法体系。

1. 候选支持计数前应用明确的法向先验和高度合理性检查；取向/符号必须一致。三点样本互异，退化样本跳过；预算和点数有上限，记录随机种子。
2. 对密集墙与稀疏地面使用GL-00获审的ROI与均衡采样。空间采样仅改变拟合样本，保留源索引/数据以重查支持；不能改实时原始点云。
3. 若需多个候选，在固定上限内保留或逐一检查，避免同一平面重复占满；桌面与地面歧义需方向/高度/区域/现场证据。不能自动把最低平面或最大平面叫地面。
4. 对通过候选的内点SVD精修，再对原验证点重算支持、方向和残差；点呈细线/法向退化时明确失败，不能给任意法向。
5. 支持率、支持点残差、独立已知地面区完整残差分列；按帧组/区域独立验证。修正现有“0.05m截断集合用0.12m RMS验收”的弱检查，先按审查批准的质量语义实施，保留历史字段兼容。
6. 完善CLI的ROI、分组、先验与诊断产物参数；错误产物明确invalid/待确认，不设置物理verified。

## 允许修改

`core/ground.py`、`scripts/calibrate_sensors.py`、独立geometry配置、相关几何测试、必要契约扩展与本单文档。不改候选/跟踪/UI/driver，不部署到活动节点。

## 验收

- 倾斜地面、墙占多数、桌面竞争、缺地面、少点/重复/共线、NaN/Inf、法向歧义与高度冲突有能失败的回归。
- 与旧基线同样本对照，报告选中平面身份、区域误差、耗时、采样/迭代量；真数据未跑则NOT_RUN。
- 显示拟合/验证支持点，不用仅测试数代替地面身份验证。
- 确认帧组/空间留出不泄漏；GL-00门槛变更需先解释并复审，不能为通过改断言。
- 全量相关Python回归；Noetic依赖的检查在Linux，Windows不伪称ROS构建。
- 输出 `returns/GL-01.md` 与独立轮次证据，Codex审查实际候选路径和失败案例后放行GL-02。

## GL-01 R4独立软件复审PASS / 2026-10-01

显式约束RANSAC、数值CLI与加载器经Codex244回归/12独立方法exit0及同SHA板端244验证，软件PASS；真实bag源索引/帧组适配、ROI与物理BLOCKED，未部署。原9/10独立失败已闭合，两次API400在同DeepSeek session压缩后恢复，日志保留。hardware_inventory.md外来人工截图约26度粗估保留，不据此标实测。详evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md。允许串行GL02数学软件/未核验候选预览，不升级真实外参/IMU/confirmed。
