# S-A 离线原型：人体结构语义测试（人/非人/不确定）

- **授权**：用户「用现有正负样本做 S-A 离线原型」（承接 [HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md](../../HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md) §9(a)）。
- **范围**：离线诊断原型；**不接管线、不改生产、不启用 ML**；仅直立/举臂样本。
- **工具**：`semantic_sa.js` —— 结构特征 F1–F5 的 node 实现 + 占位阈值 + 三值组合（HEAD/TORSO/LEGS/ARM/SLAB/FLAT_TOP → HUMAN_EVIDENCE / OBJECT_EVIDENCE / UNKNOWN）；复用 `registration.js` 的 `levelingBinding`/`loadFrames`（只读）。
- **样本**：正 = 四段人（215540/215643 站；215607/215623 举臂；多帧合并）；负 = WD01（223757）、箱子堆、低横条（215540）；另对空场 233658 的 P 链逐簇（66 簇）跑三值。

## 结果（校准后 r1，`semantic_sa_results.json`）

| 样本 | 期望 | 输出 | 关键特征 |
|---|---|---|---|
| pos-540 站 | HUMAN | **HUMAN_EVIDENCE** | head=true legs=true torso=true cv=0.084 w=0.157 |
| pos-607 举臂 | HUMAN | **HUMAN_EVIDENCE** | arm=true legs=true torso=true（HEAD 未检出，见限制） |
| pos-623 举臂 | HUMAN | **HUMAN_EVIDENCE** | arm=true legs=true torso=true |
| pos-643 站 | HUMAN | **HUMAN_EVIDENCE** | head=true legs=true torso=true |
| neg-WD01 | 非人 | **OBJECT_EVIDENCE** | slab=true（cv=0.033，w=0.301） |
| neg-箱子堆 | 非人 | **OBJECT_EVIDENCE** | flat=true（顶 0.277） |
| neg-低横条 | 非人 | UNKNOWN | POINTS_LOW（<400 点，该样本未有效检验规则） |
| 空场 233658 逐簇 | 无 HUMAN | **0 HUMAN** | 54 OBJECT / 12 POINTS_LOW |

**7/7 样本 PASS；空场 0 HUMAN_EVIDENCE。**

## 校准记录

- r0（c_slab=0.03）：WD01 的 cv=0.033 恰好卡线 → UNKNOWN；按探针分离（板 0.02–0.033 vs 人 0.084–0.144）取中值 **0.05** → r1 WD01=OBJECT。r0 产物保留为 `calibration_r0_results.json`。

## 已知限制

1. 举臂时 HEAD 未检出（走 LEGS∧TORSO 路径通过；"去臂找头"启发式待改进）；
2. 低横条样本点数不足，未有效检验低矮负样本；
3. 阈值为占位、仅 7+66 样本校准，需更多负样本（格栅/远场/空场多簇）后冻结；
4. 仅直立/举臂；遮挡、人与家具粘连、多姿态（弯腰/坐蹲/卧）未测；
5. 样本为"区域点集"级（非逐帧簇窗口），管线接入前的形态差异待 S-A+ 处理。

## 记录

- ponytail：实读（opencode skill，base `C:\Users\30680\.config\opencode\skills\ponytail`，full）；复用既有 loader 与探针逻辑，单脚本 + 一档校准，无新依赖。
- 文件：`semantic_sa.js` / `semantic_sa_results.json` / `calibration_r0_results.json` / `semantic_sa.run.log`。
- 未 commit / 未 push；生产文件与既有证据未改动。
