只读最终定向复核完成（仅读 V3 三文件 + FOLD_SAMPLE_COUNTS + EXPERIMENT_STREAMS；未写文件、未 bash/训练/下载）。

# 最终结论：**PLAN_PASS**

## 三项低危（对照 V2）——全部落实
1. **提示词必读 OUTPUT_BUDGET**：Prompt V3 §1 已列 `OUTPUT_BUDGET_V2.json`（并含 FOLD_SAMPLE_COUNTS、EXPERIMENT_STREAMS）。✓
2. **未标帧按 fold、不固定 720**：Plan V3 §73 改述为"对应训练 sid 未标帧"，§160 明文"按具体 fold 元数据计算，不采用约 720 固定数"。FOLD_SAMPLE_COUNTS 逐 fold=593/705/637/657、final=864；我复算 665=183+251+231、777=295+251+231、709=295+183+231、729=295+183+251，各 −72 核心即未标数，960−96=864。✓
3. **12/4/3 流映射 + 不伪消融**：EXPERIMENT_STREAMS 给出 12 学习流（3 族×3seed + 3 MAIN 训练消融）、4 几何流（R1_legacy / A / G0_B / G1_HDBSCAN）、3 推理压力流、1 主权重复现，与 OUTPUT_BUDGET 的 12/4/3/120B 一一对应；§160 与 applicability 明禁复制主结果冒充消融。✓（一处补强见下）

**state_dict**：Plan V3 §160 已加"核对包括 buffer 的整个 state_dict 前后 SHA，随机状态不得包装为已训练"。**未改 36 作业/30h/评分/授权门**——§73–§77、§8、§2 与 V2 逐字一致。✓

**权威指针与边界**：Plan §162 声明当前权威为 V3（V1 PLAN_REVISE、V2 PLAN_PASS 保留）；ACCEPTANCE_V3 头、Prompt §1/§66 同指 V3，§66 明确"PLAN_PASS 只证明计划可执行，非 E1 授权/开发验收"。L 表全 NOT_RUN，无 ACCEPTED；实例/关节 GT 门仍在（§49、§144、L07/L09）。✓

## 两处**非阻断**就地收紧（不改门限/预算/授权；writer 派发前可并入，不影响 PASS）
1. **state_dict 未贯穿**：Plan §126 与 Prompt §71 仍写"参数前后 SHA 相等"，L08 未提 buffer，与 §160 不完全一致。最小改：三处统一为"整个 state_dict（含 buffer）前后 SHA 相等"。
2. **伪消融适用性缺口**：applicability 只写"if MAIN=L3D: NOT_APPLICABLE"；若 MAIN=L2D，遮断 2D 分支即遮断唯一分支，应同样记 NOT_APPLICABLE。最小改："MAIN_2D_branch_masked 仅当 MAIN=LFUSION 适用；MAIN∈{L3D,L2D} → NOT_APPLICABLE"。

## 结论
**PLAN_PASS（最终）**：D1–D7 及三项低危已闭合，权威三文件指针一致，未把计划 PASS 当 E1 授权/ACCEPTED，实例/关节 GT 门在，36/30h/评分门未变。上述两点为文字收紧、非阻断。PLAN_REVIEW 最终 SHA 指针由 writer 在你的真实结论后追加，即可按 V3 派发；本轮未写文件、未训练/下载/采集/部署，仍为**仅计划审查，非 ACCEPTED**。