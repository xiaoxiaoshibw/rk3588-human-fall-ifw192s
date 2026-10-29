# HFUS-TCMS-01 本机 RAW 支撑时序实验

用户2026-10-16“开始开发”实施附件的新路线。隔离侧链，不替换旧BG/RF/跟踪，不训练，不修改生产/数据/GT。当前唯一验收：[TC01–TC10 v1](../../docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/ACCEPTANCE_V1.md)。

从仓库根执行（输出必须是该证据目录的**全新直接子目录**）：

```powershell
python -B -W error -m unittest discover -s sidequests/hfus_tcms -p test_tcms.py
python -B -W error sidequests/hfus_tcms/run_experiment.py --output docs/human_fall/evidence/2026-10-16_hfus_tcms_01_r1/run_new
```

只依赖stdlib和现有NumPy；复用pointset/r01/next_contract.py的严格meta契约与SHA。不沿用已缺失的E0 manifest，不把配平代理当原字节。读取28B记录中offset0/4/8的XYZ小端float32，其他16B不解释；用device帧时间而非假设10Hz。坐标用固定RAW米制，不判断地面、人体姿态或跌倒。

RAW → 合法XYZ/0.3–12m有效点 → 0.12/0.15m体素 → 约1.2m固定空间块 → 两个各5/10/20帧的相邻窗口 → 同一观测支撑集的静态/平移解释。

- B1：当前帧与上一帧观测命中集合的Dice差异，弱基线。
- B2：早窗/晚窗观测命中并集的Dice差异，减少重复采样位置变化。
- B3：同一早/晚命中集合，26种±1体素平移中Dice拟合提升最大值，扣除0.03×位移L1格数。shift_to_past是对齐向量，不能当真实物理速度。尚未要求跨三窗同方向持续，属于最小双假设原型。

未命中=UNKNOWN；不声称自由空间。早/晚窗任一少于8个命中体素不评分；空窗>0.5秒清历史；非单调时间拒绝；每会话/空场每分段新状态。无证据静态人体不能被本侧链否决。

空场272帧连续三段，各自重置双窗；FIT用于噪声诊断、CAL按距离段(块中心约0–4/4–8/8–12m)的p99定阈值、REPORT只报告不调参。小于30个CAL样本为UNKNOWN。所有会话已有开发暴露，同空场尾段绝非独立测试。阈值不是人体置信度，CAL元样本相关，不能给虚假统计置信区间。

输出每帧metrics.jsonl.gz、B3候选members.jsonl.gz、MANIFEST/THRESHOLDS/NOISE/SUMMARY/INTEGRITY。候选源行是**当前帧该块全部合法点**，并非声称每个点真的运动；全局源行=frame_offset_points+source_rows。两个索引与成员SHA可回查原28B，不合成点、不导出human=true。网格边界、可见性变化、强非刚性、慢移不足1格、跨块迁移均会失败；新物体刚进入时早窗不足支撑保持UNKNOWN。

停止条件：REPORT空场仍明显激活、未知率过高或动作/空场分数无法区分，先审查固定块/扫描采样混叠，禁止B4融合晋级。继续门：人工核对空场、行走、慢动、运动后静止、冷启动静止、移动家具和贴家具遮挡的同源ROI/ID，至少两个独立采集组分别tune与test；先冻结阈值再测试。只有点级/ROI级恢复增益及家具污染净收益成立才实现B0+B3源行级融合；冲突保留UNKNOWN，不否决原静态支路。身份记忆需TTL/几何支持/撤销规则，学习需独立标签和算力门。当前这些语义/生产门BLOCKED，不额外启动训练、采集、部署。

技能路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。报告图使用该工具包matplotlib参考技能。
