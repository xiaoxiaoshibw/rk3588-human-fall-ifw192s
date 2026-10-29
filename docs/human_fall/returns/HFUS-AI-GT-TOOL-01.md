# HFUS-AI-GT-TOOL-01 回传（AI-GT 工具四模式 + 合成自检包络）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-AI-GT-TOOL-01 / r1 / 本会话（OpenCode 客户端；声明模型 opencode-go/deepseek-v4.1-flash，未独立审计）/ 2026-10-18。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-18_hfus_ai_gt_tool_01_r1/ACCEPTANCE_V1.md` v1（T01–T12）/ SHA256 `0f4ea09255831a84a04b42243f8af59a76abafccf42360ff4529aacb716081dc`。
- 执行方式 / 实际会话与模型：本机离线单会话；Python 3.12.10 + NumPy 1.26.4 + Pillow 12.2.0；标注者=本会话模型（目视 PNG，盲标）。
- 状态：SUBMITTED，非 ACCEPTED；T01–T12 作者自验 PASS（T09/T10 真实运行 NOT_RUN 明示）；独立复审 NOT_RUN。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；未做 Git 写；未重算全树基线。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（skill 工具加载，full）；策略：ENGINEERING（工具实现）+ 合成自检运行。
- 协议依据：`AI_GT_PROTOCOL_V1.md`（SHA `cc7f959b…5be7f`）§7 工具规格。

## 集中诊断与根因覆盖

| 缺口 | 事实来源 | 处置 |
|---|---|---|
| 协议 §7 工具全部 NOT_RUN | HFUS-GT-PROTOCOL-01 协议 v1 | 四模式实现（`tools/ai_gt/ai_gt.py`）+ 11 单测 |
| 标注器无误差包络，"不能引用包络" | 协议 §3.3 | 合成自检 12 例盲标 → `ENVELOPE.json`（px P50 8.20 / lateral P50 5.6cm / max 27.4cm） |
| 盲标保护只在纸面 | 协议 §3.1/§7 | `label` meta 白名单（拒绝管线字段）+ 单测 |
| `acos` 近零角数值放大 | 本会话自查 | 改数值稳定 `atan2(|cross|,dot)`（单测 <1e-9°） |
| 近场标注偏差未知 | 本轮自检发现 | 记录"视觉中点≠投影质心"系统偏差与协议 v2 修正方向 |

## 实际变更

| 文件 | 本轮用途与修改 | SHA |
|---|---|---|
| `tools/ai_gt/ai_gt.py` | 工具本体（label/selfcheck/crosscheck/audit） | `aef3536a…b29ca` |
| `tools/ai_gt/test_ai_gt.py` | 单元测试 11 项 | `9bb263f3…548116` |
| `docs/human_fall/evidence/2026-10-18_hfus_ai_gt_tool_01_r1/**` | 验收/协议/渲染 12/真值/标注/评分/包络/日志/报告/环境/基线/MANIFEST | 见 `MANIFEST.json`（31 件） |
| `docs/human_fall/returns/HFUS-AI-GT-TOOL-01.md` | 本回传 | 新建 |
| `docs/human_fall/WORKFLOW.md` | 顶部条目前置 | 只前置，旧字节保留 |
| `docs/human_fall/REVIEW_LOG.md` | 末尾记录追加 | 只追加，旧字节保留 |

未改 data/、既有源码、配置、模型、GT、旧证据、协议正文；无 Git 写/部署/采集/训练/网络。

## 逐条验收

| 验收ID | 状态 | 证据 |
|---|---|---|
| T01–T12 | 全部 PASS（作者自验；T09/T10 真实运行 NOT_RUN 明示） | `ACCEPTANCE_V1.md` 运行结果段 |

关键数值：TP 10 / FN 0 / FP 0 / TN 2；px P50 8.20 / P95 59.38 / max 72.11；lateral P50 5.6cm / P95 24.3cm / max 27.4cm；按距离分档见 `ENVELOPE.json`（近场 4.0–5.5m 明显更差，主因 v 方向"视觉中点"偏差，case_000/007）。

## 未闭合与限制

- `label` 未接真实会话（无 blind 渲染包）；`crosscheck`/`audit` 真实运行与跨模型一致性 NOT_RUN。
- 包络为单标注者实例、12 例小样本、合成几何；P95 接近最大值，非置信区间；不外推到真实标注精度。
- 近场偏差修正（指令措辞/细网格/分档使用）为协议 v2 候选，未实施。
- 独立复审 NOT_RUN；设备/物理/部署/采集/训练 NOT_RUN。

## 交给 Codex 独立复审

- 现行验收表与运行结果：`ACCEPTANCE_V1.md`；报告：`REPORT.md`。
- 工具与测试：`tools/ai_gt/ai_gt.py`、`tools/ai_gt/test_ai_gt.py`（`python -B -W error` exit 0）。
- 证据与 SHA：`MANIFEST.json`（31 件，含 12 渲染、truth、picks、SELFCHECK、ENVELOPE、RUN/日志）。
- 复审重点：四模式是否满足协议 §7；盲标保护是否真实（meta 白名单、先标后评顺序、truth 未在标注期读取）；评分器正确性（oracle/noise 单测）；包络结论与限制是否如实；近场偏差分析是否成立。
- 当前工单下一步：等复审与用户派发（如 label 接真实会话 / 交叉模型验证 / 首批应用）；不自动启动下一单。

## 2026-10-18 工具交付与自检包络

- 用户派发 A（协议工具 + 首次合成自检）；本会话唯一 writer，SUBMITTED，非 ACCEPTED。
- 交付：四模式工具 + 11 单测（exit 0）+ 12 例盲标自检 + 包络 + 全量 SHA 记录。
- 逐 ID：T01–T12 全 PASS；真实会话 label、交叉模型、audit 真实运行、独立复审 NOT_RUN。
- 结论：工具可用；包络已产出且暴露近场系统性偏差（已如实记录并给出修正方向）。
