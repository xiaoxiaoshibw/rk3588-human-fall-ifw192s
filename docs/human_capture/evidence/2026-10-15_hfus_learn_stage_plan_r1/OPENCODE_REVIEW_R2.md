只读复审完成（仅读 V2 计划包与 V1 原审；未写文件、未 bash/训练/下载/读原始点云；V1 及原审保留）。

# HFUS-LEARN-PLAN-03 V2 复审结论：**PLAN_PASS**（仅计划审查，非 ACCEPTED，非 E1 授权）

V1 的 D1–D7 全部实质修复且经我独立核对（含预算实数复算）；无残留阻断项。下一轮可直接派发，但派发前须完成 D4 的可判定前置（见下）。

## 一、逐项核对（对照 V1 缺陷）

**D1 分组泄漏｜已修｜§95/§122/§155、L13、提示词 §70/§74、EXPERIMENT_SPLIT_V2**
OOF_960_LABEL96（每 fold 只训 3 sid 的 72 核心、验证该 sid 24）与 FINAL_DEV4（96 核心训练）严格分表；主语义只由 OOF 评分，最终全 dev 权重只在 COMPARE_974_LABEL96（96）+EMPTY90 评分；明文禁止把全 dev 拟合预测混入语义/2pp/非退化门，全量预测标 `TRAIN_FIT_VISUAL_ONLY`。4fold 全齐门（§153–155）堵住"截停/缺 fold 从宏平均删除"。✓ 无误用训练帧。

**D2 预算闭合｜已修且实数可核｜§73/§75/§126/§130/§134、EXPERIMENT_BUDGET_V2、OUTPUT_BUDGET_V2**
- 样本：screen 72 训/24 验（3 训练 sid×24），final 96；`semantic_roles` 与之一致（72/24/96/96/96/90）。✓
- 探针：3 族×2 宽×2 分辨率=12 个纯软件 profile，≤5min，`profile_optimizer_step=FORBIDDEN`、合成 loss 只求梯度、参数 SHA 不变、不出语义成绩。✓ 明确不构成训练。
- 冻结时点：统一最高可行分辨率与共同 E_screen(10–40)/E_final(15–40) 先于任何验证成绩冻结；不满足 128×512/预算即 RESOURCE_BLOCKED；触发硬上限的 fit 标 `TRUNCATED_NONCOMPARABLE`、耗作业预算、不参与主排序。✓
- 输出预算：以原行上界 **99,329,595** 估。我按 DATA_PREFLIGHT_V2 复算——动作 2,657,407,004B/28=**94,907,393** 行，空场 90/272×13,364,725≈**4,422,150** 行，合计≈99,329,543，与上界一致（Δ≈52）。逐项 52/40/28×12/8×4/28×3/120B/行 + 36×2×64MB + 8GiB 合计 79,152,785,672B = **73.72GiB** < 80 硬顶，`required_free` 90GiB。✓ 算术与量级一致。

**D3 版本化 surface｜已修｜§136–140、L14、提示词 §72**
原页=同应用/同源路由/原 console 入口，非改写旧 r01 已绑字节；新增 `learn/<run_id>/` 版本闸门模块，旧 server/app/index 原字节保留；需重构共享入口时须先交调用链+旧文件全字节归档+旧 run 冻结资源/新路由方案与 pre/post SHA、回滚点。✓

**D4 提示词需最终 PLAN_PASS+SHA｜已修｜提示词 §64–66、§146**
执行前必须确认 PLAN_REVIEW 最后结论为 PLAN_PASS 且指向 V2 计划/验收/提示词及配套 JSON 的 SHA；PENDING/PLAN_REVISE/指针不一致即拒开算法工。✓（唯一运营前置见下。）

**D5 队列人工量分离｜已修｜§9/§47、ANNOTATION_QUEUE_V2**
474=282 人工核心+192 非金标建议（`queue_not_gold`）；第二人工复核我逐 sid 核对 **8×6+18=66 帧**（=23.4%≥20%），名单冻结；082623 核心改覆盖 f119/f124/f140/f195/f232 并入 `hard_case_note` 声明为预先已消费难例、非总体随机抽样。✓

**D6 实例/关节条件放行｜已修｜§144、L07/L09、提示词 §73**
E0 必交 instance query/归属互斥/损失开关与结构/关节适配接口+坏数据/无权重的明确状态；实例监督取决于未来真实人工实例门，缺门则 semantic-only、L07 BLOCKED；关节 GT 缺失→真实评分 BLOCKED、公开模型推理 NOT_RUN；明禁 13 槽改名。✓ 非自动放行。

**D7 预检 deferred｜已修｜DATA_PREFLIGHT_V2**：`L02_deferred_implementation_NOT_RUN` 列背景/注册-RT、tracked/untracked 源前后、开发实测预检、131958 复核，`not_implementation_PASS=true`。✓

**附加项｜已落实｜§151–155、提示词 §76**：S_sem（p_H≥t+0.1/t−0.1 带）、S_event（可靠同身份当前 query 的 S_sem 子集，不充测量）、实例分歧不反向改语义 H、几何/槽必报 S_event 缺测；4fold 全齐门。✓

## 二、无残留阻断；以下为低危非阻断项（建议实施时记录）

1. **提示词 §1 必读清单**漏列 `OUTPUT_BUDGET_V2.json`（§71 才"详读"）。最小修订：把 OUTPUT_BUDGET_V2.json 列入 §1 同目录必读。｜低
2. **§73"额外建议/未标约 720 帧"**与 960−96=864 不一致（按 fold 训练 sid 未标≈593–705）。最小修订：改述为"训练 sid 未标帧"，不给固定约数，避免被当契约数字。｜低
3. **OUTPUT_BUDGET 的 twelve/four/three 流**未按方案命名（12 学习流=3 族×3seed+3 消融，4 几何流=G0/G1 等）。最小修订：补一份 stream↔方案映射使 73.72GiB 可审。｜信息级
4. **残余统计风险（非缺陷、不要求新数据）**：2pp 与非退化门仅落在 OOF96+比较96（每 sid 24 帧），功效有限；计划已声明为预登记工程门而非已证明可达，故不改计划。

## 三、派发前唯一运营前置（非计划缺陷）
D4 要求执行 AI 先核到 PLAN_REVIEW 的**最终 PLAN_PASS 与 SHA 指针**；当前 `PLAN_REVIEW.md` 仍为 PENDING。故本轮结论须由 writer 按流程写入 PLAN_REVIEW.md（引用本 PLAN_PASS、本审记录及 DEVELOPMENT_PLAN_V2/ACCEPTANCE_V2/AI_DEVELOPMENT_PROMPT_V2/各 JSON 的 SHA）后，提示词才可判定开工；否则执行 AI 应据 §66 拒绝开算法工。我本轮未写文件。

## 四、结论
**PLAN_PASS**：D1–D7 与附加 S_sem/S_event/4fold 门均已修复并经独立复算；权限边界（E0/E1 分离、单 writer、data 只读、不触设备/部署/HR09）保持。本结论仅为计划可执行性审查，**不等于 E1 训练授权，不等于实现验收，不构成 ACCEPTED/默认晋级**；物理/板端/采集/泛化仍 NOT_RUN/BLOCKED。