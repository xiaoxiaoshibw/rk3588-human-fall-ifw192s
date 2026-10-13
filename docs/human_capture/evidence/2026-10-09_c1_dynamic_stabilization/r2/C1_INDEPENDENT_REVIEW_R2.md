# C1 动态稳定化 — R2 独立复审（OpenCode opencode-go/deepseek-v4.1-flash 原文存档）

执行：opencode run 真推理（非提示词占位）。复审人只读核对磁盘证据：重算 SHA256、逐位 cmp、重跑 JS 单测、静态读源码（非采信报告自述）。

---

# C1 独立复审报告 R2（OpenCode `opencode-go/deepseek-v4.1-flash`）
- 审计员：OpenCode（独立、只读、未改任何文件）；已加载 `ponytail` skill (full)，按“读全再断”执行。
- 证据根：`docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/`
- 独立动作：对磁盘上文件重算 SHA256、逐位 `cmp`、重跑 JS 单测、静态读源码（非采信报告自述）。
---
## A. R2 复核轮是否可信 — 5 主张逐条独立核验
| # | 主张 | 独立核验 | 裁定 |
|---|---|---|---|
| 1 | 探针重跑 24/24 cmp IDENTICAL | 我在磁盘上对 `ab/v2_raw/*`(12) 与 `r2/ab/v2_raw/*`(12)、`workspace/shadow_raw/*`(12) 与 `r2/workspace/shadow_raw/*`(12) 逐位 `cmp` → **24/24 IDENTICAL** | **PASS** |
| 2 | 5 枚锚点 SHA 未变 | 重算：`b2a_shadow_probe.js`=`74b4a272…`、`detect_overlay.js`=`585d2964…`、`human_pipe_lib.js`=`8b50a221…`（≡`2026-10-09_b2a_fix_r1/protected_snapshot/HRV2.sha256`）、`rf_person_v1.json`=`4c83db11…`、`bg_envelope.json`=`28afdaa4…`，逐位一致 | **PASS** |
| 3 | label_audit 13/13 全 PASS（数值指纹一致） | `label_audit/report.md:14` 的 “z_band …一致” 在 `c1_label_audit.py:107-108` 为 **`checks.append({... , "pass": True})` 硬编码恒真**（`z_bands` 计算后从未使用）；其余 12 项为真比对（`numsig` 仅比数字字面量序列，`c1_label_audit.py:85-96`，属弱指纹） | **FAIL**（12 真 + 1 恒真，非 13/13） |
| 4 | JS 单测 detect_overlay 36/36、human_pipe_lib 38/38、panel 全 PASS | 重跑：`detect_overlay.test.js` → ALL PASS；`human_pipe_lib.test.js` → `38 passed, 0 failed`；`panel.test.js` → PASS | **PASS** |
| 5 | 旧 manifest 68/69 一致，唯一 FAILED = 自身 | 独立 `sha256sum -c SHA_MANIFEST.sha256`：**4 个 FAILED，非 1 个**——`./ab/summary.md`、`./rf_v2/slice_metrics.json`、`./rf_v2/wilson_perfeature.md` 三个**内容文件**哈希不符（mtime 2026-10-10T12:13–12:19，即 **R2 期间被就地改写**），加 manifest 自身 | **FAIL**（报告 §7 与 r2 prompt 主张 #5 被直接证伪） |
**小结**：1/2/4 可信；3 含 1 项恒真锚点（“数值指纹”并非全为真比对）；5 严重失实。R2 同时**违反了“旧 r1 产物已冻结/不得覆盖”**（就地改了 3 个旧证据文件）。
---
## B. R1 FAIL → R2 逐条闭环裁定
| R1 裁定 | R2 处置证据锚 | 裁定 |
|---|---|---|
| #1 Wilson 帧级伪重复 | `rf_v2/gate_by_session.md:8,11`（段级 n=6，person 下界 0.610，显式作废旧 `gate_confidence.md`） | **CLOSED** |
| #2 泄漏审计方向反/域混合 | `rf_v2/leakage_slice.md:5-9` + `wilson_perfeature.md:6-15`；主张降级为“域内不可证” | **CLOSED（降级式）**：诚实撤回“泄漏已排除”，但 `full_51≡noleak_48` 逐位相同仍**无正分离证据**，只达成“不作主张”，非解决 |
| #3 v_airoi=100% 循环论证 | `REVIEW_AND_RERUN_R2.md:55` 降为不作独立证据，仅采 `v_p`(98.1–99.1%) | **CLOSED** |
| #4 furniture_tracks 命名/悬空引用 | `ab/per_session.json:7,12,23…` 更名 `furniture_reentry_episodes`；`flicker_analysis.json` 已在证据根 | **CLOSED**，但**引入新悬空引用**：`REVIEW_AND_RERUN_R2.md:155,176` 指向不存在的 `r2/C1_INDEPENDENT_REVIEW_R2.md` |
| #5 推理耗时定性 | `ab/summary.md:22-27` 结构性估算 + JS/Py prob 差上限 0.0500 | **CLOSED** |
| A1 mf_v2 空目录 | 已删 | **CLOSED**，但**新增空目录** `r2/label_audit/`、`r2/workspace/outs/`（同类卫生问题回归） |
| A2 零动态真值 | `REVIEW_AND_RERUN_R2.md:124,170` 动态召回标 UNKNOWN，不造 GT | **CLOSED（诚实声明）**，但见 §C3 |
---
## C. 审查重点
### C1. 复核轮有效性 — 一致性只证明“探针确定”，不能证明“探针贴合生产”
- 24/24 cmp 只证明**重跑的确定性**（同代码同输入同输出），**逻辑上不排除**“R1 探针本就偏离生产并被原样重跑”。
- “探针≡生产”实际由两条独立证据支撑：(a) 生产文件本体 SHA 未变（`detect_overlay.js`/`human_pipe_lib.js`，见 A#2）；(b) label_audit 的 blueprint 比对。但 (b) 的 13 项中 **1 项恒真**（`c1_label_audit.py:107-108`），且真比对的 3 项 `numsig` **只比数字字面量序列**（`c1_label_audit.py:85-96`），不校验标识符/控制流——逻辑可不同而数字相同仍 PASS。**裁定：PASS（有限）**，但“13/13 数值指纹全绿”的表述**不可采信**。
### C2. 53 维特征 bug — 属实，影响 C2 透明度
- `workspace/c1_rf_v2.py:193-196`：`X_t2`(51 维) 与 `Xf2`(column_stack 成 53 维) `vstack`；且 `194-195` 构造的 `Xcomb2/ycomb2/scomb2` **从未传入** `train_eval_exp`（`:199-202` 用回 `X_t,Xf,Xp_dup`），`Xp2=…[0]` 又塌成单行。故 `results.json` 的 `v2e_feat_ablate`（`results.json:1237`，person 0.9997）**并非真正的特征消融**，标签不可靠。
- R2 已在 `REVIEW_AND_RERUN_R2.md:147` 披露该 bug 并列入 C2 修复项；但 `REVIEW_AND_RERUN_R2.md:86` §4 表格仍把 v2e 列为“特征消融”，**与自身披露矛盾**。C1 未授权新特征，故 **不影响 C1 判定**，但削弱 C2 透明度。**裁定：PASS（已披露）+ 表内标注瑕疵**。
### C3. 动态=UNKNOWN — 诚实，但等于核心目标未验证
- 6 段全静态（`label_audit/report.md:25-30` xy 跨度 0.03–0.06m），`ab/per_session.json` 无动态 GT。标 UNKNOWN 而非凑数**是诚实**。
- 但 C1 名义即“**动态**稳定化”，“动态召回”既不可测，则 C1 核心交付**无真值审计通过**。因此第 (b) 项必为 NO。**裁定：PASS（诚实）≠ C1 目标达成**。
### C4. 硬门 n_pts≥500 域限 — “域内预过滤”可辩护，“安全”需限定
- 段级 Wilson 下界 0.61（`gate_by_session.md:8`）、person 仅 ≤2.5m、家具仅同批柜面；硬门已丢弃 1 个真实 person 簇（n=33，`gate_by_session.md:12`）。
- `gate_by_session.md:8` 作为**同域保守下界**成立；R2 措辞已限定“限本采样域”（`REVIEW_AND_RERUN_R2.md:174`）。若作泛化“安全”论断则**过度**。**裁定：PASS（限域措辞）+ 不可外推**。
### C5. 复核轮审计卫生（prompt 列 5 重点处实际仅 4 条，此为附加）
- 旧证据被就地覆盖（A#5）、新悬空引用（B#4）、新空目录（B#A1）、报告 §4 与 §7-A 自相矛盾（C2）——四项均为“返修轮引入的旧缺陷回归”，独立性受损。
---
## D. 最终结论
**(a) C1 = PASS（条件性）** — 限本采样域（同房间 ≤2.5m、6 段 915 帧、静态 stand）；硬门 `n_pts≥500` 于该域内有效（家具 12/13/18/15→0、人零回归），B2-A-FIX-R1 完好，锚点 4/5 SHA 与 24/24 重跑可复现。**但 R2 报告本身含 2 项失实主张（A#3 恒真锚点、A#5 旧 manifest 4 项 FAILED 而非 1）与 1 项自相矛盾（§4 v2e）**，C1 的“通过”是基于底稿证据、非基于报告结论。
**(b) 进入 C2 = NO** — 主理由：C1 核心目标“动态真人识别”在全部数据上**无动态真值**（`label_audit/report.md:25-30`，xy 跨度 0.03–0.06m），动态召回 UNKNOWN 即目标不可测；统计泛化主张已自我作废（段级 Wilson 下界 0.61，`gate_by_session.md:8`）；泄漏消融仅达成“域内不作主张”而非正证据（`leakage_slice.md:6-9`）；且本轮复核自身出现证据冻结违例与失实陈述。故维持 R1 的 NO；待补真实动态 GT、域外 holdout、修 53 维脚本（`c1_rf_v2.py:193-196`）后方可再评。
---
**复审人署名**：OpenCode `opencode-go/deepseek-v4.1-flash`；工具链：ponytail(full)、sha256sum/cmp、node 单测、只读源码。
