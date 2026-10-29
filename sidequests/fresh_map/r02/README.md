# FRESH-MOTS-01 — 离线算法融合试验 r02

用户 2026-10-15「你可以尝试一下嘛」授权的独立 sidequest。唯一生产代码 writer：Codex。
当前唯一验收表：[ACCEPTANCE_V1.md](../../../docs/sidequests/evidence/2026-10-15_fresh_mots_r1/ACCEPTANCE_V1.md)。
保留 r01 与主线；本轮仅 A0/A1/A2，不接控制台、不部署、不采集、不激活 ML。

## 对照与固定参数

- A0：原 r01 的体素候选投影，无目标锚点。
- A1：A0 + 27 邻域的二值占用序列（8 帧，至少 6 帧）；至少 2 个邻居在相邻帧改变占用，平均时间方差 ≥0.015，连续 2 帧才触发。27 邻居包括中心。无高度特征、无自监督网络；不称原论文复现。
- A2：A1 + 动态事件置信度门。log-odds 初值 -1.4，事件 +1.2、稳定观测 -0.12，范围 [-4,4]；每个体素至少间隔 0.5 秒更新一次，一窗口内重复事件合并，未观测不更新；≥0 才保留候选。该分数是启发式事件置信度，没有概率校准，不能解释为人体概率。

所有组相同配平、denoise、参考会话、点集、时间戳；均不启用目标锚点/人体分类器，防止其反馈掩盖体素模块差异。A2 的稳定占用反证可能使静止者失去候选；这是本实验必须揭示的风险，不能先假定有净收益。候选筛选仅输出索引对应的原 XYZI，原始点云仍保留。未观测一律 UNKNOWN，未实现自由空间清除。

```powershell
node --throw-deprecation sidequests/fresh_map/r02/mots_lib.test.js
node --throw-deprecation sidequests/fresh_map/r02/run_ablation.js --outdir docs/sidequests/evidence/2026-10-15_fresh_mots_r1/runs
```

runner 要求全新输出目录；开跑前冻结源码与参数，逐会话校验输入 SHA，结束复核参考及源码，输出每帧 CSV、每会话 JSON、汇总及哈希清单。输入是 captures/remote 下现有 15 段完整 meta+bin；历史参考 cap_20261014_221808 单列 reference_control，其空场身份本轮未重审。原 r01 已用的两段 cap_20261013_082717 / 083218 是 diagnostic，另外 12 段为 held_out_unlabelled。本轮不看真实结果调参。

统一几何 cohort 为 A0 第 20–170 帧候选体素并集；后续仅统计当帧实际观测到的 cohort 留存，短会话没有后窗时填 null。不是人工人体真值。候选比例、事件数、同格连续观测时状态切换数均为工程诊断，不能命名为检人精度/误检率。耗时为本机单进程非独占测量。

## 文献依据

- [Kreutz et al., WACV 2023](https://openaccess.thecvf.com/content/WACV2023/html/Kreutz_Unsupervised_4D_LiDAR_Moving_Object_Segmentation_in_Stationary_Settings_With_WACV_2023_paper.html)：邻域占用时序表示；原工作包含自监督编码与聚类，本轮仅借鉴表示机制。
- [Mersch et al., RA-L 2023](https://www.ipb.uni-bonn.de/pdfs/mersch2023ral.pdf)：扫描/地图运动分割及贝叶斯信念融合；本轮没有其稀疏卷积或学习似然，仅探索受限更新的事件记忆。

ponytail 技能实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
