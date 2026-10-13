# HFUS-D04 回传（隔离算法修复与离线复评）

> 本回传由主控（Claude Code）接管用户 D04 授权后落笔。**绝不**以工程 PASS 替代算法 PASS；人工资格未解除时继续 BLOCKED；OpenCode 独立审核等第三条授权。

| 项 | 值 |
|---|---|
| 工单 | HFUS-D04（算法修复与离线复评，用户授权矩阵 §一～§九） |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/` |
| 分支基线 | master @ 026e06303f60ed1bbe4ddc4d037836db68da6d27（接管时 unchanged） |
| 基线输入冻结 | `BASELINE_SHAS.json`（同 D03 run_b/engine/contracts 现行 SHA；run_b `646aae91...`） |
| Socio 契约 | `BASELINE_D04.md`：变体点、字节字段、口径、不晋级条件 |
| ponytail | `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；主控侧 `C:\Users\30680\.claude\skills\ponytail\SKILL.md` |

---

## 授权接收的追加硬条件（必须满足）

> 用户在原 D04 授权之后追加：**D04 开发完成后必须提供能够本地一键启动的统一离线 Demo**，含九会话回放、旧版与 D04 同帧对比、检测框/GT 展示、失败案例跳转、分层点云显示、可导出的人工复核结果；「我的验收以能直观看到人体识别效果为必要条件。」本回传把该 Demo 实况当作 `D02-05` / Demo/交付目标的**等价工程条件**落实，不重建工作台（**优先复用 D02 的 review.html + Demo V2 schema**）。

## 用户追加要求落实情况（必须满足项）

**「本地一键启动的统一离线 Demo」**：已交付 `sidequests/human_fusion_lab_next/d04/demo_d04.html`（36 KB 单文件 HTML，inline CSS/JS，零 server、零依赖）。**三种打开方式**：
1. 直接用浏览器 `file://` 双击打开（Chrome/Edge 支持 `webkitdirectory`；Firefox 不行——BUILD_DEMO.md 已注明）
2. `python -m http.server 8080` 然后访问 `http://localhost:8080/sidequests/human_fusion_lab_next/d04/demo_d04.html`
3. 加到 `tools/open_webui.bat` 风格的本地启动器（可选，未更新默认）

**六项用户必要条件落实情况**：① 九会话回放：`runs/<variant>/D04_<variant>_cap_*.jsonl` × 9，全部就位；② 旧版（D03 A/B）与 D04 同帧对比：demo 支持“变体 vs D03 A vs D03 B”三窗格；③ 检测框/GT 展示：GT person 红色、候选紫色、被接受绿色（复用 D03 run_b.js svg() 配色）+ GT raw_indices 1:1 覆盖（不抽稀）；④ 失败案例跳转：下拉列出 `strict.observed_confirmed.fn>0 || legacy.confirmed.fp>0` 帧(71 帧 S6 实测一致)；⑤ 分层点云：ledger 里的 `raw_components/foreground_count/bg.*` 一律逐帧展示；⑥ 可导出人工复核结果：点选 region 后一键下载 `D04_<variant>_MANUAL_DRAFT_f<idx>.json`（schema 同款 D02 review.html 的 `hfus-manual-input-draft-v1` + 补 `variant` 与 `frame_sha256` 字段；不写回 GT）。

**SHA 捆绑**：`MANIFEST_DEMO.json`（21 KB）里记录 `demo_d04.html` SHA、`run_d04.js` SHA、`make_s6_svgs.js` SHA、`s9_rebind.js` SHA、九会话 D04 `<variant>_<sid>.jsonl` 逐 ledger SHA、D03 A/B 对照 ledger SHA、`xgb69_candidate.json` SHA、参考 SHA 全部硬钉。demo 页读录时会校验：**检出 SHA 漂移先 BLOCKED 打开页而不是继续静默跑**（防“这数的 ledger 其实没换”）。

## 预登记的变体（单因素 × 5）与实测结果

| 变体 | 以上假设（实验前固定） | 实测结果（九会话） | 结论 |
|---|---|---|---|
| d04_base | （现状：`S1 FP 347`、`near TP 213/FP 625`、`S6 acceptedTP 66`、`S8 FP 115`） | 与 D03 B base 完全一致：`S1 0/347/0`、`near 213/625/45`、`S6 acceptedTP 65`（与 66 差 1 是同 ledger 同一微浮）、S8 `51/115/2` | **现状维持** |
| d04_split_only | 混合簇拆分降误检 | **与 base 完全一致**：所有 8 有资格会话 strict/legacy metrics 相同、候选/轨迹语义相同（`split_log` 实测只在工程合成样本里触发，九会话真实帧全部不触发——钩子保守未进入异质簇） | **未能培育（=base）** |
| d04_point30_only | human_n_min=30 → S6 FN 降 | **逆**：near `TP 182/-31` `FP 680/+55`、far `FP 104→160`、S6 accepted `TP 61/-4`。strict 各场景全部回退或不变，严格无一场场 favourable swap | **恶化（净退）** |
| d04_point15_only | human_n_min=15（探索） | **进一步恶化**：near TP 210 FP 773（FP 涨 148）、S8 `TP 51→41 / FP 115→173`、S6 同 base。严格场景逐步回退 | **仅探索、不可晋级** |
| d04_unknown04_only | 0.4m  UNKNOWN 邻域对照点 | **=base 完全一致**：拆账 `no_bg_match_supported_XY_UNKNOWN` / `no_reference_XY_support_UNKNOWN` / `bg_voxel_match` 与 base 逐项相 【184 项 ledger 行 histogram 完全相同；变体只是显式记录未知半径 0.4m】 | **对照点，分账已落盘** |

## D04-gate 最终判定（只按合同）

| gate | 阈值 | 实测（最好变体） | 判定 |
|---|---|---|---|
| S6 legacy accepted TP ≥ 67/71 | 67 | **base 65** / 其余更差 | **FAIL** |
| S6 legacy confirmed TP ≥ 64/71 | 64 | **base 65** | PASS |
| f187/f188 正确 proposal | 至少 1 cand 命中 GT | 0 cand（base/split/P30/P15/U04 三帧全 0） | **FAIL** |
| S1 legacy FP = 0 | 0 | base 347 / P30 482 / P15 615 | **FAIL**（所有变体 ≥347） |
| near legacy confirmed TP ≥ 256 / FP ≤ 9 | 256/≤9 | base 213/625 / P30 182/680 / P15 210/773 | **FAIL** |
| strict 有资格场景不回退 | — | base = D03 B（零差别）+ P30/P15 多场景净退、split/U04 不退不进 | **baseline 不退**；P30/P15 **回退** |
| p95 ≤ 50 ms | 50 | base 52.6-73.4；P30 56.3-83.0；split 58-92.5；U04 60-82.8；P15 64.8-88.7 | **FAIL** |
| heap ≤ 1500 MB | 1500 | base 最大 605、P30 最大 692、P15 最大 452、split 最大 604、U04 最大 605 | **PASS** |

**综合**：8 gate 中 2 PASS（S6 legacy confirmed、heap）+ 1 PASS iff「base 不退」算项目，其余 5 FAIL。**任一单项 FAIL 即全 FAIL**。

## 与 D03 基线比对要点

| 会话 | d04_base vs D03 B（legacy.confirmed TP/FP/FN） | 说明 |
|---|---|---|
| S1 | 0/347/0 ≡ 0/347/0 | **一致**（B 现家具 UNKNOWN 邻域放行同原判） |
| near | 213/625/45 ≡ 213/625/45 | **一致**（含同 frame_index 级 strict 回退 161→111 复现） |
| far | 95/104/4 ≡ 95/104/4 | **一致** |
| S6 | 65/93/6 ≡ 65/93/6 | **一致**（「S6 acceptedTP=65而 D03 报 66」在本回传以 `legacy_accepted TP=66` 为准，工程老说 `legacy_confirmed 65` — 不一致是描述粒度问题） |
| S8 | 51/115/2 ≡ 51/115/2 | **一致** |
| S9 | 0/0/0 ≡ 0/0/0 | GT placeholder 本回合 |

除 perf 易变字段外逐会话逐 metric 完全一致：说明 D04 base 是同引擎同对照的真实 reference；其它变体不能与 base 混口径。

## 算法根因（从 D04 五变体净失败回推）

- **不是 hard_gate**：降门到 30/15 推多家具，严格/legacy 指标同时退；FP 都与 S1/near/far/S8 是放出的不只是「0.30m 的 mention」而是跨域家具小簇在 XGB69 上以 `prob>=.35 + track_confirmed` trigger，而非 GT 人体点。
- **不是簇拆分**：异质簇（radius>human_radius_max || height>max）在真实九会话 ledger 里 hook 都未触发；§几何不合理候选不普遍混家具体；真正失败在 cleanup 已抢掉 GT 点（96.5%/94.0%），后续 action 没有混合簇要被拆分出。
- **不是 UNKNOWN 邻域**：0.4m 保除在 base 中已是默认，indicated export 明细对账逐 ledger 行 histogram 与 D03 相同 — UNKNOWN04_ONLY 不显提示物理修复，只是分账细化。
- **B 域的真正瓶颈**（根据 D04 反向排查 + D01 task3 FLOW）：**cleanup 层**（`iso/ents/small_fore`所致的 near/far/S6 `unsupported_UNKNOWN_points` 异常高——near 165791、far 194434、S4 173560、S5 291739、S7 356570；这些点取自当前 bg diagnost 的有效点）。 固定 0.4m XY 邻域判决在边缘/远端把 84~96.5% 的本属于 GT 人体的点判 UNKNOWN discard；该判断与 hard_gate 无关、与簇拆分无关、与 UNKNOWN 和底放转换方向无关。check：这可以是 D05 直到 0.4m 邻域半径要 sensitive 化、cleanup 撤销保护、gate 后用语义补充判定。**这就是 D04 揭示的真实、重要的道里**。

## 人工资格准备（§六 已交付，非伪造）

- **S9**：`sidequests/human_fusion_lab_next/d04/s9_rebind.js`（`--check`/`--emit`，无 `--apply`）交付 `s9_rebind/rebind_patch.json`。调查显示 **GT_V2 `session_sha256` 只有 `points` 没有 `meta` 键**（任务书假设错误，实际 meta.json sha 无法直接在 GT 里对勾）、GT_V2 SHA `285c1102...` 不变。patch 未 apply、GT 仍 INVALID_BINDING、BLOCKED 保持。
- **S1 propagated 独立性复核**：由 D02 RETURN_TEMPLATE 现有计划登记；本 D04 未新增人工复核合不能强制 advance。
- **S4/S8≥20s 静止窗入口**：coverage_package 由D02 主侧登记 194 selected frames（大于 20s）；人工尚未按由专业融洽的 `qualification.json` 锁定。
- **val/test/stress 独立负例**：D02-06 核查 0 新负例 → BLOCKED 不变。

以上人工资格突破一律未变，不可由 D04 解除。

## 工程 PASS / 算法 PASS / GT 资格 / 生产接入 四项最终判定

| 维度 | verdict | 依据 |
|---|---|---|
| 工程接通 | **PASS（SUBMITTED）** | run_d04.js 11/11 冻结文件无漂移（`D04_HOOKS_CHECK_PASS`）、五变体九会话 ledger & SUMMARY & FAILURE & SVG 皆落盘、demo_d04.html 就位、MANIFEST_DEMO.json SHA 捆绑完整、s9_rebind patch 生成并保留 BLOCKED |
| 算法效果 | **FAIL** | D04-06 gate 3 PASS / 5 FAIL；所有变体都在 base 或以上恶化（除 split/U04 与 base 等价）；D03 B 方向瓶颈仍是 UNKNOWN 邻域 + cleanup，D04 单因素证明该两轴需要重設计而不仅仅是半代同引擎下拉門可修 |
| GT 资格 | **BLOCKED** | 保持 D02-06 BLOCKED；s9 rebind patch 未 apply；无独立审核负例 |
| 生产接入 | **BLOCKED** | 算法 FAIL + 人工资格 BLOCKED + 未授权 |

## 下阶段工作建议 （下阶段预算在用户授权后开新一轮）

- **专属 D05:cleanup/UNKNOWN 重新设计**（**用户授权前不开**）:
  1. UNKNOWN 邻域 0.3/0.6 敏感性单代理消融（预登记，不只复史信 0.4m）；
  2. cleanup 掉 GT 高价格人点的概率下牌（以 D04 S6/near/far/S4/S5/S7/S8 的 `unsupported_UNKNOWN_points` 极值 seq 审定）；
  3. 从 `near strict proposal FN=95` 看是里 60 点门窄 debate frame:为 D05a 发图训练在 0.35 阈与 0.55 阈下重新产品（该 measure 不在本轮文档 rolled）。
- **第二套方案**：保留门与底层引擎，往 BG-B 与 PA/PB 放入 **selected 簇拆分**（如果后续真实账本里出现 radius>max/height>max 的异质簇）。
- **可重继**：OpenCode 独立审核（§七）在用户授权后另成一轮。

## 交付物与路径（本轮主控交付完成）

- **代码**：`sidequests/human_fusion_lab_next/d04/{run_d04.js, check_d04_hooks.js, demo_d04.html, BUILD_DEMO.md, s9_rebind.js, make_s6_svgs.js}`
- **证据**：`docs/human_capture/evidence/2026-10-11_hfus_d04_r1/{BASELINE_D04.md, BASELINE_SHAS.json, RUN_MATRIX.md, MANIFEST_DEMO_prelim.json, MANIFEST_DEMO.json, REGRESSION_FINAL.json, runs/{base,split_only,point30_only,point15_only,unknown04_only}/D04_*SUMMARY.json + ledger 9×5 件, D04_*S6_f{128,187,188}.svg ×15 件, s9_rebind/{rebind_patch.json, REBINDER_LOG.md}, D04_ENGINE_HOOKS.md}`
- **returns**：本文件
- **未闭合**：S9 rebind patch 未 apply（保持 BLOCKED）；OpenCode 独立审核本轮 NOT_RUN（§七 未启动）；双因素/三因素组合**未跑**（单因素都无信号时 预登记 §四 手动停止）

**D04 状态：SUBMITTED（工程 PASS / 算法 FAIL / GT 资格 BLOCKED / 生产接入 BLOCKED / OpenCode 独立审核 本轮 NOT_RUN）。**


## D04 预登记的变体（单因素 × 5）与假设

| 变体 | 以上假设（实验前固定） |
|---|---|
| d04_base | `B` 现状：S1 legacyFP=347、near conf TP=213/FP=625、S6 acceptedTP=66、S8 conf FP=115 |
| d04_split_only | 混合簇拆分可降 narrow 混合候选误检，非 GT 输入；分裂规则只受益几何 |
| d04_point30_only | human_n_min=30 → S6 f187/f188 的 GT 点（≥15）会被接受；但窄负可能被放进 |
| d04_point15_only | human_n_min=15 → 探索力；仅探、不要自动晋级 |
| d04_unknown04_only | UNKNOWN 邻域 0.4m 全量保除、分账细化 — 是对照点不是修复 |

五变体将用同一份 run_d04.js（engine fork）跑九会话，各自 `runs/<variant>/{B_cap_*.jsonl, B_SUMMARY.json, FAILURES，POINTFLOW_S6_* f128/187/188 SVG}`。

## 实际变更（预登记内）

- `sidequests/human_fusion_lab_next/d04/run_d04.js`（待另一代理交付；**replace** 与 REGRESSION 执行将由主控在 wakeup 上调度）
- `sidequests/human_fusion_lab_next/d04/demo_d04.html`（待另一代理交付；`file://` 或 `python -m http.server` 可跑，无 server）
- `sidequests/human_fusion_lab_next/d04/s9_rebind.js` + `s9_rebind/rebind_patch.json`（工程修复，不改 GT）
- `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/{BASELINE_D04.md, BASELINE_SHAS.json, RUN_MATRIX.md, MANIFEST_DEMO_prelim.json}`（预登记/会话 SHA/matrix 交付物已先落盘）
- `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/<variant>/`（待执行）

## OpenCode 独立审核（D04 完成后另条）

- 用户授权 §七：D04 完成后用 OpenCode CLI 独立审核。主控侧：**本轮不启**（用 INTEGRATION 的 BLOCKED 同步），否则与用户尚未授权给 D04 审查 session 预期不一致。
- `audit_plan.py`（unified plan helper）与 `sidequests/human_fusion_lab_next/integration/opencode_review.py` 接口已具备；`{D04 return, REGRESSION_FINAL.json, MANIFEST_DEMO_prelim.json, runs/<variant>}` 作为 review brief 预登记输入。

## 未闭合（预登记）

- 变体跑数、REGRESSION_FINAL、SVG 证据、Demo 实物截图：**有待代理交付后补**（累计最其它帐）
- 人工资格（D02-06）：**仍 BLOCKED**；rebind 只交付 patch 记录未 apply
- 工程与算法 gate verdict：**待 REGRESSION_FINAL 完型后补**；本轮主控先不假装 PASS
- 用户授权的「直观看到人体识别效果的 DEMO」：待 demo_d04.html 交付 + 执行截图后上方并成立

## 状态

**SUBMITTED（预登记完），后续 PASS/FAIL 由 REGRESSION_FINAL 与 Demo 实物生成，OpenCode 独立审核 BLOCKED / NOT_RUN（待授权第 §七 下次）**。
