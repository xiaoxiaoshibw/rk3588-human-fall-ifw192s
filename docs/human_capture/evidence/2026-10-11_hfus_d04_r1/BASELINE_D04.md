# HFUS-D04 实验预登记与基线冻结（单因素消融）

日期 2026-10-11。主控（Claude Code）授权后启动 D04。本文件在**任何变体跑数之前**冻结，避免「看到结果再改口径」。

## 预冻结输入（绝不改）

- `sidequests/human_fusion_lab_next/background/{run_b.js SHA=646aae91..., detector_b.js, engine_b.js, check_b.js, summarize_b.js}`
- `sidequests/human_fusion_lab_next/contracts/{index_v1.js, strict_v1.js, strict_v2.js, SCHEMA_V1.json, SCHEMA_V2.json}`
- `sidequests/human_fusion_lab_next/eval/instrument.js`
- 以上 SHA 已在 `sidequests/human_fusion_lab_next/background/TAKEOVER_RUN_B_FROZEN.json` 中重抄（**不再覆盖先前 D03 的 303acea5 老版历史痕迹**，仅记录现行版）
- GT/captures/models 只读，来源 SHA 已在 D03 `FINAL_MANIFEST_V2.json` / `INPUT_LOCK.json` 中冻结。

## 实验变体（单因素 × 5，含 BASELINE）

| 变体 | 变更点 | 预期假设 |
|---|---|---|
| `d04_base` (BASELINE) | 不改任何东西；同 run_b.js 直接跑 B 模式 | 现状：S1 legacyFP 347、near TP 213/FP 625、S6 acceptedTP 66 等 — 重算现存问题 |
| `d04_split_only` (SPLIT_ONLY) | 在 B 域加「混合簇拆分」（人-boundary / 家具-boundary 地拆分 PA/PB 候选） | near/far/S1 FP 降、S6 FN 降；拆分不依赖 GT |
| `d04_point30_only` (POINT30_ONLY) | 把 `hard_gate 点数` 从 60 → 30 下门 | S6 FN 降（f187/f188 的 GT 点 ≥ 15 留住）但 FP 可能上涨 |
| `d04_point15_only` (POINT15_ONLY) | 把 `hard_gate 点数` 从 60 → 15 下门 | 探索；**仅探、不因检出多目标自动晋级**（授权原话） |
| `d04_unknown04_only` (UNKNOWN04_ONLY) | 保留 UNKNOWN 邻域 0.4m 不变（与 BASELINE 同等口径，作 UNKNOWN 轴的对照点而非修复），但同时打全 per-点 `no_reference_XY_support_UNKNOWN` / `no_bg_match_supported_XY_UNKNOWN` / `bg_voxel_match` 分账 | 量化 UNKNOWN 判决对人体 vs 家具的差异 |

**双因素/三因素（承接：有显著单因素改善再做）**：先按单因素听话的结果决定是否成立 `d04_split+point30`、`d04_split+unknown04`、`d04_point30+unknown04`、`d04_split+point30+unknown04`。无单因素信号则**不盲从做组合**。

## 统一口径（严格一致）

- 输入：九会话同 DATA/AUDIT/GT/manifest/参考 cap_20261009_113611/sample_step=4/min_occ=0.5/voxel-r scale 不变
- 索引契约：`index_v1.js` 与 `strict_v2.js` 不动（SHA 冻结）
- 评分：分 legacy（候选阈 0.35，距离匹配 0.75m）和 strict（observed_confirmed/accepted/proposal + coverage/purity gates + unmatched_unknown）两轨，**不混口径**。near 的 legacy 256/258 vs strict 161/258 差异保留
- 九会话逐会话输出，不给总平均；所有 FAIL 样本（frame_index + 层 + 候选 id）落盘

## 不承诺的假设（诚实）

- SPLIT_ONLY 不能自证改善混合簇；只做「拆分后重新分类」对照，拆分规则只受益人-boundary 几何特征（z、跨度、倾斜跨度、XY extent）与家具几何特征（大概率更方形 / 平坦 / 低矮），**不用 GT 在拆分内作为输入**。若拆分误分是常见模式，SPLIT_ONLY 可能不改善甚至变差——这是记录，不是失败。
- POINT15 因下限极松易泄底，仅探。不会因「召回涨」即晋级主链。
- UNKNOWN04_ONLY 不证明 0.4m 是正确半径；只是一个对照点。后询敏感半径 0.3/0.6 交给 D05（未授权当前单）。
- 结果不做「更换 GT 口径 / 改检测阈值 / 藏差」处理；人机资格依然 BLOCKED。

## 预登记的最小落盘

| 文件 | 含义 |
|---|---|
| `SUMMARY_<variant>.json` | 同 D03 SUMMARY schema；每会话 strict/legacy/observed_confirmed/proposal + bg 分账 + heap/p50/p95/p99 + 全部累计字段 |
| `FAILURES_<variant>.json` | strict/legacy 失败帧索引与层归因 |
| `LEDGER_EVENTS_<variant>.json` | 事件化（FN, UNMATCHED_UNKNOWN）逐会话 |
| `COMPARE_<variant>_vs_BASELINE.json` | 逐会话差异表 |
| `POINTFLOW_S6_<frame>_<variant>.json` | f128/187/188 逐点 flow（复用 run_b 内部 point_flow） |
| `MANIFEST_<variant>.json` | 输入 SHA、代码 SHA、config SHA、run 目录 SHA 列表 |
| `REGRESSION_FINAL.json` | 变体 × 会话 × strict/legacy 合并视图 |

## 附带硬性约束（D04 交付附加要求 — 来自用户追加消息）

> 用户追加条件：D04 完成时**必须提供本地一键启动的统一离线 Demo**，含（a）九会话回放、（b）旧版与 D04 同帧对比、（c）检测框/GT 可视化、（d）失败案例跳转、（e）分层显示、（f）可导出的人工复核结果。「必须报告真实检出改善与退化，不得只提供代码测试通过和 SHA 报告。优先复用 Demo V2，不要重新构建新工作台。我的验收以能直观看到人体识别效果为必要条件。」

**执行方案（冻结在 D04 启动前）**：
- **不新建工作台底座**；复用两路既有成品：D02 的 `sidequests/human_fusion_lab_next/review/review.html`（纯静态 file://，MANIFEST 绑定 SHA、逐帧逐点、可导出 DRAFT json，已真实 Chrome 验证）为**点云/原始视图与人工复核导出层**；Demo V2 的 `demo_v2.html` 为**legacy 参考**（它依赖 server_v2 的独有 API，不做为本次一键底座；它已作为对照在 BROWSER_CHECK_03 证明可跑）。
- D04 Demo = 新页 `sidequests/human_fusion_lab_next/d04/demo_d04.html`（本地一键 `file://` 或 `python -m http.server`），**输入是 D04 冻结 run output** 而非重算：读 `evidence/2026-10-11_hfus_d04_r1/runs/<variant>/<sid>.jsonl` + 同帧 BASELINE（d03 A/B ledger） + GT（只读），用同一份 candidate/track id schema 叠加显示「`旧A / 旧B / d04_<variant>`」三色同帧对比；失败帧跳转由 `FAILURES_<variant>.json` 的 frame_index 生成按钮；人工复核导出复用 review.html 的 DRAFT json schema（加 `variant` 字段）在新页实现同款 save。
- 同时输出一份 **MANIFEST_DEMO.json** 列出九会话输入 SHA + ledger 双 SHA + GT SHA + variant config → 用户在 Demo 里看到的每帧都是 SHA 绑定可追。
- 「直观看到」由三个层次满足：①浏览器内同帧三色叠加；②`POINTFLOW` SVG（`svg(...)` 已在 run_b.js 里且已有 `A_S6_f128.svg` 等先例）在 D04 变体的 f128/187/188 全部 SVG；③失败截图归到 FAILURES 里。

**改善与退化**：在 REGRESSION_FINAL 每会话每变量明「strict tp delta / legacy conf tp delta / fp delta / fn delta / heap/p95 delta」五元组，同时在返回以会话为单位的真案例帧号（亲自跑 frame_index 的 SVG）。
