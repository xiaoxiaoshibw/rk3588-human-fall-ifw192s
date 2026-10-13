# 第二轮：算法架构与依赖检查

在第一轮事实基础上，采用一个隔离执行入口、现有模块复用、分层可替换实验；不新增生产框架。

重要设计修正：

1. 背景命名 BG-A/B/C，候选命名 PA/PB，避免两个“A/B”混淆。BG-B 在 PA/PB 共同上游接入，PB 不得再次偷偷执行 BG-A envelope，否则人体点仍会被共同硬门删除。
2. 冻结 V2 A链 XGB+Unique 作为对照；BG-B+旧XGB是域变化实验，不是假定可直接推广的组合。必须报告 B-S1 家具误检压力。
3. reference absence 明确 UNKNOWN；只有有效射线/覆盖证据才叫 FREE。当前 BG-B no-match 不能直接证明 free。未知支持候选由算法从 RAW 产生，GT只做事后归因。
4. 点集评分顺序/Float32/预处理都是契约；merge后 classifier、bbox、count 来自相同有序 union。association_anchor 与 scoring_centroid 在版本字段中分开记录，初轮不偷偷改旧 anchor。
5. 发现现有 engine 有 PIPE tracker 管 retention、Unique管最终输出。BG/Candidate 初轮保留这个事实；最终单一轨迹状态与 retention 对齐只在 HFUS-D05b 单独实施，不能混入背景实验。
6. 候选在分类前导出，包含被硬门拒绝的 component 和 PB 非人候选；不能沿用旧 d._candidates 当完整 proposal 集。
7. 旧 final TP 是 human_confirmed && lost==0 的距离匹配。新 observed_confirmed 还需当帧 accepted 成员支持；两者并列重算，禁止拿旧491直接当新定义基线。
8. D03 工程接通可以完成而算法 FAIL；D04/D05a 允许基于冻结失败实验继续研究。只有集成晋级门要全部满足，避免“旧XGB在B失效→永远不能训练”的循环依赖。
9. D02 导出工具可先完成；人工资格、heldout负例和身份审核独立 BLOCKED，不能由软件伪造。
10. KF/Hungarian 为条件 shadow；先核现有实现。至多两人、少量候选时可复用既有精确一对一 matcher，不为算法名称强加 SciPy/板端依赖。

结果写入统一计划的架构/契约/任务序列。开发指标为目标，全部未执行。
