# Codex 接管提示词 / 2026-10-03（Claude Code 交回）

> 给 Codex 的冷启动包。你 18:45 额度恢复后接回全部角色：编排/派工/独立复审/状态收口。当前无活动生产 writer；唯一生产 writer 仍为 OpenCode `opencode-go/deepseek-v4.1-flash`（default DB、无隔离库）。

## 一、身份与边界（30 秒读完）

- 2026-10-03 Codex 额度故障（"18:45后重试"），用户指令 Claude Code 按 `CLAUDE_STANDBY.md` 顶替全部角色；期间 Claude 未写任何生产代码/测试，只写流程/状态/复审文档与本单证据目录脚本。
- 用户期间明确授权："随便你如何调用，开发主线，每次完成都要审核，规划，调用返工"（Claude 据此派了 GL-I02 R1 两阶段）。
- **交回后**：唯一生效编排者=Codex；Claude Code 退出编排、不再派工/复审。
- 顶替/交回登记：`CLI_RECOVERY.md` 末尾须由 Codex 确认追加一条交回记录（时间、HEAD、锚点）。

## 二、核心事实（读这几份就够，勿全量重读历史）

1. `docs/human_fall/WORKFLOW.md` + `DISPATCH.md` 顶行 —— 当前流程入口。
2. `CLI_RECOVERY.md` —— 含 2026-10-03 Claude 顶替登记（SHA、锚点、DONE 清单）。
3. `REVIEW_LOG.md` 末尾两段：**GL-I01 R1 复审 PASS**、**GL-I02 R1 路线3 收口**。
4. `GLI02_ACCEPTANCE.md` v1 结果列 —— J01 SYNTH PASS/REAL NOT_RUN，其余 PASS。
5. **GL-I02 路线3 关键证据**：`evidence/2026-10-03_gl_i02_r1/codex_review_01/13_route3_closeout.md`。
6. **当前待批工单**：`AI_PROMPT_GLI03_OPENCODE_R1.md`（用户已选路线 B，但**尚未批准开火**）。配套验收表未建——工单内含 GL-I03 v1 验收表草稿（K01–K06 + P01–P06），如需正式建表拆成独立 `GLI03_ACCEPTANCE.md`。**工单文末已标注**其中混有排版噪点与若干提议性措辞，发派前请复核/清洗（尤其回传统/晚判两节）。

## 三、当前技术锚点（一句话版）

GL-I02 R1 路线3：真实 fit NOT_RUN 的根因 = GL-00 R4 冻结采样参数（`spatial_cell_m=0.2` × `max_points_per_cell=4`）× 26° 下倾安装 → `_balanced_sample` 只剩 80 < `min_inliers=100`。GL-I03 拟用**独立 override config**（`spatial_cell_m=0.05, max_points_per_cell=8`）让真实 fit 走通，**不改** ground.py/calibration.py/冻结协议/wrapper 默认行为。

- up_axis（用户审定）= `[0.438371, 0, 0.898794]`（雷达绕 Y 下倾 26°）
- sensor_height_interval_m = `[1.2, 1.7]`；真实 fit 圈：FIT X[2.0,3.0] Y[-1.0,0.0] Z[-0.66,0.04]（filled_real_draft.json）
- 实测地板：`Z = 0.51·X + 0.05·Y - 1.53`，58 万内点 RMS=0.027 m
- `geometry_constrained.yaml` 冻结参数**一律不动**（K05）

## 四、SHA 对照（任何决策先核这组）

| 文件 | SHA256 前缀 |
|---|---|
| `src/human_fall_detection/core/capture_input.py` | `56355e95…` |
| `src/human_fall_detection/scripts/prepare_capture_input.py` | `648a8da6…` |
| `src/human_fall_detection/scripts/calibrate_sensors.py` | `3f30cf94…` |
| `src/human_fall_detection/tests/test_gli01_capture_input.py` | `50f615d7…` |
| `src/human_fall_detection/scripts/evaluate_gli02_candidate.py` | `4a4fd0c7…` |
| `src/human_fall_detection/tests/test_gli02_candidate.py` | `0dad5771…` |
| `src/human_fall_detection/core/ground.py` | `2d25ccfd…` |
| `src/human_fall_detection/core/calibration.py` | `d29519a1…` |
| `captures/remote/cap_20261002_163621/meta.json` | `675c23de…` |
| `captures/remote/cap_20261002_163621/points.bin` | `b81797f9…` |
| HEAD | `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（master，工作树故意脏） |

## 五、待你决策的事（按优先级）

1. **是否批准 GL-I03 R1 派工**（用户已选 B，但工单未获正式放行）：复核 `AI_PROMPT_GLI03_OPENCODE_R1.md`（注意清洗噪点/措辞），先建/定稿 `GLI03_ACCEPTANCE.md`（可用工单内草稿），再按 WORKFLOW 走 probe → 阶段一诊断 → 设计门 → 阶段二实施 → 独立复审。
2. **GL04 真实 DPR**：R7 后仍 NOT_RUN；只缺真实 DPR 浏览器验证（非代码工作），用户何时提供环境再补。
3. **GL05 / 设备 / 部署 / 采集 / 网络**：未授权，维持冻结。
4. **human_capture / HR 支线**：另一支线，HEAD 外部推进保留，不归因本轮。

## 六、铁律复述（违反=交接失败）

- 不 reset/checkout/clean/commit/push；不代替用户提交；保留用户差异与 `src/CMakeLists.txt` 软链接表示。
- 单生产 writer=OpenCode Go Flash/default DB；每次派工先 ≤1min 无工具 probe 并记录。
- NOT_RUN/BLOCKED 如实记录；M/S/B/D 分层；synthetic/offline/device 分清。
- GL04 正式页合并需获审 + 真实 DPR；GL05 系列未授权不启动。

## 七、Claude Code 期间产物索引（供追溯）

- GL-I01 R1：`evidence/2026-10-03_gl_i01_r1/codex_review_01/`（00–10 + CODEX_REVIEW.md）
- GL-I02 R1：`evidence/2026-10-03_gl_i02_r1/`（00–14 + 00_diag.md + 04_DESIGN_REVIEW.md + codex_review_01/00–13）
- 复审回归基线：全 407 / GL-I01 62 / GL-I02 8 / gl01 33 / hf03 / 24 探针全部 OK
- 本文件：`docs/human_fall/CODEX_HANDOVER.md`

—— Claude Code 顶替结束，交回 Codex。
