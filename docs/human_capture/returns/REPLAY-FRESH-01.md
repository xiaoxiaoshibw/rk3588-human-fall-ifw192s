# REPLAY-FRESH-01 回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：REPLAY-FRESH-01 / R1（实现，前一会话）+ R2（整段核对与收口，本轮）/ OpenCode CLI（`opencode-go/mimo-v2.6-pro`）/ 2026-10-16 Asia/Shanghai。R1 为该范围唯一生产代码写入者；R2 **未改任何生产代码**（只跑核对/回归 + 写证据与回传），沿用 R1 工作树。
- 用户授权（直派）：「设计一个开关，放在回放工具条，叫"人物高亮"。开启后从头播放，显示背景渐黑、人物高亮和低姿续接；关闭后恢复原始着色。这样能保证高亮使用完整的前序帧，不会因中途开启而漏掉人物身份」，随后「继续开发」授权继续收口（整段站立/倒地/起身 + 关闭恢复）。
- [唯一验收 v1](../evidence/2026-10-16_replay_fresh_switch_r1/ACCEPTANCE_V1.md)（RF01–RF08），SHA256 `fa638140053adf589ccc0adab1cd30f52c86468552533c3d524569845d69d815`；R1 证据 [2026-10-16_replay_fresh_switch_r1](../evidence/2026-10-16_replay_fresh_switch_r1/)；R2 证据 [2026-10-16_replay_fresh_switch_r2](../evidence/2026-10-16_replay_fresh_switch_r2/README.md)。
- 执行方式 / 实际会话与模型：本机 PC 回放 UI 集成，本机浏览器 + 本地只读回放服务（`serve_review.py`，只读取 `captures/remote`，不写数据）；会话 `cap_20261013_082623`（295 帧主线）+ 空场参考 `cap_20261014_221808`（272 帧）。
- 状态：SUBMITTED（软件自验逐条结果见下表）；设备/物理/真实跌倒语义/EXE 重打包与部署 NOT_RUN（未授权）；独立复审 NOT_RUN；不宣布 ACCEPTED、不宣布总体软件 PASS。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树本就脏（含他人并行差异与未跟踪生产源），本轮未 commit/push/reset/clean，未写 `data/`。源码 SHA 见 R2 证据 README。
- ponytail 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（skill 工具加载，full）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| RF01（中途开会漏身份） | 高亮身份靠前序帧时序建立；在任意帧中途打开必然缺前序，人物认领残缺 | 回放页 `index.html` 的着色路径（`HUMAN_DETECT_OVERLAY.on_frame`） | `fresh_view.js`：开关切换 → 保留 `sid` → `location.assign` 重载 → 从 f0 逐帧重建时序 | 原始着色为默认；开关 URL 参数 `highlight=1/0` 可复现 |
| RF02（两套颜色叠加） | 原人检（`detect_overlay.js`）与新高亮都会写同一个颜色缓冲，同时开会互相覆盖 | `replay.js` 的 `HUMAN_DETECT_OVERLAY` 单钩子 + `#detectBtn`/`#lutSel` | `fresh_view.js`：高亮开 → 隐藏并禁用 `#detectBtn`、禁用 `#lutSel` | 关闭后两者原样恢复；未改 detect_overlay 本体 |
| RF02（参考未就绪时冒充成功） | 参考没到就跑 on_frame，会把本会话 warmup 当空场，把人学成背景 | `fresh_overlay.on_frame` | `fresh_view.js` 的 hook：`ready` 前不喂帧；参考失败走 HUD 明确报「人物高亮未启用」 | 失败态可关闭开关看原始点云，不静默 |
| RF04（换会话带旧身份） | 高亮状态（体素/锚点/低姿集）跨会话存活 | `replay.js` `notify_session` → `gen++` + `reset()` | `fresh_overlay.js` `notify_session/reset` + `fresh_view.js` `notify_session` 复位变换 | 会话切换只清高亮时序，不碰会话数据/回放/剪辑 |

实现前核查同类调用者：`detect_overlay.js` 的钩子契约（`notify_session/reset/attach_color/set_leveled_in_s/on_frame`）是既有单钩子，本项**复用**同一钩子位，不新增第二条着色管线；`attach_color` 收裸 `Float32Array`（r8 定案契约）沿用，不做形态推断式改写。语义变化（开关=整页重载从头建时序）已写入证据 README 与 `index.html` 开关 tooltip；未以降低断言代替修复。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区别 | 提交源码SHA |
|---|---|---|---|
| `pc_apps/human_replay/index.html` | 工具条 `#highlightSwitch`（人物高亮）+ `#freshHud` 状态条 + 载入 `human_pipe_lib.js`/`fresh_map_lib.js`/`fresh_overlay.js`/`fresh_view.js` + `?sid=` 载入改为等 `FRESH_VIEW_READY` | 本轮新增（相对 `evidence/r1/index.before.html` 仅此差异） | `e3821329aa0e…` |
| `pc_apps/human_replay/fresh_view.js` | 新增：开关状态机（重载保 sid、从头播放）、原人检互斥、着色菜单停用、参考载入与失败态 | 本轮新增 | `4a61fd835d2a…` |
| `pc_apps/human_replay/fresh_overlay.js` | 新增：高亮着色层（背景渐黑/认领高亮/低姿续接），复用站姿+低姿算法 | 本轮新增（源自 sidequest `sidequests/fresh_map`，未改算法口径） | `aee3380d00bb…` |
| `pc_apps/human_replay/fresh_map_lib.js` | 新增：新鲜度/记忆/参考图/低姿续接算法本体 | 本轮新增（同上来源） | `6bc0e2de35b6…` |
| `pc_apps/human_replay/replay.js` | 2 行：配平成功后把 R/T 传给 `HUMAN_DETECT_OVERLAY.set_transform`（否则逻辑坐标与渲染坐标不一致） | 相对 `evidence/r1/replay.before.js` 仅此 2 行 | `35cf5a90ea28…` |
| `pc_apps/human_replay/fresh_view.test.js` / `fresh_overlay.test.js` | 新增回归：default/off/on、保会话、从头重建、人检互斥、参考 pending/error/invalid、代次与脚本序、配平重建、低姿续接拒绝歧义 | 本轮新增 | `1f81625a195f…` / `d650d89888d2…` |

单位/坐标：沿用板端 IFW192S（x-forward/y-left/z-up）米制；高亮层在 `?sid=` 服务路径下用 `DEFAULT_LEVEL_TRANSFORM` 配平后的逻辑坐标，渲染仍原始系。未改 `human_replay_lib.py`/`sessions_test.py`（那是并行他项差异）。

**并行写入者改动了同范围 4 个文件（本轮未参与其改动，只做对账）**：工具条新增「方案 legacy/metric3d/xy」与「空场」下拉；`fresh_view.js` 重载带 `perception`/`ref`、本地目录会话拒绝重载；`fresh_overlay.js` 新增 `set_mode()`；`fresh_view.test.js` 随参数补用例。改动后当前字节 SHA：`index.html 222ca7ec…`、`replay.js fa90c2f4…`、`fresh_view.js 5cbe4c80…`、`fresh_overlay.js a675f5c5…`、`fresh_view.test.js b327c562…`（`fresh_map_lib.js`/`fresh_overlay.test.js` 未变）。对账：14 个 JS 套件 + Python 45 tests 在新字节上全 exit 0（`regression_after_parallel_edit.log`），开/关两态浏览器复核通过，`on_f61_stand_v2.png` 为新 UI 开态截图；开关「保会话 + 从头重建时序」语义未被破坏。整段 295 帧数值判读跑的是旧 `overlay_sha=aee3380d…`，**新方案切换的逐帧数值未重跑**。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED 及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| RF01 默认原始着色 + 显式开关 + 切换保会话并从头播放 | synthetic + browser | `node fresh_view.test.js`；浏览器 `?sid=cap_20261013_082623&highlight=1` 从 f0 逐帧推到 f295 | **PASS**（test exit 0；浏览器 `FRESH_VIEW_ACTIVE` 两态、切关后 URL 保留 sid） | r2 `switch_states.md`、`regression.log` |
| RF02 算法复用 / 裸数组着色 / 参考未就绪·失败不冒充成功 | synthetic | `node fresh_overlay.test.js`（含 `attach_color` 契约对账）+ `node fresh_view.test.js`（pending/error/invalid reference） | **PASS**（8 + 2 组全过，exit 0） | r2 `regression.log`；源码 `fresh_view.js` L24–L61 |
| RF03 原人检互斥 + 不破坏测距/视角/会话/回放/剪辑 | synthetic + browser | 浏览器 DOM 实测（高亮开：`#detectBtn.hidden`、`#lutSel.disabled`；关：均恢复）+ 14 个 JS 套件 + Python 45 tests | **PASS**（全部 exit 0） | r2 `switch_states.md`、`regression.log` |
| RF04 校准/换会话/循环/参考更换生命周期一致，无旧会话或旧参考污染 | synthetic + browser | `node fresh_view.test.js`（generation/script order、calibration rebuild、state reset）；浏览器同页 `__load_session_sid` 从 295 帧主线切到 272 帧空场 | **PASS**（切后锚点 `[]`、`目标 0`；空场 f31–f90 `claim_hot=0 claim_cool=0`） | r2 `switch_states.md`「换会话生命周期」 |
| RF05 主线 082623 完整 295 帧播放，站立/倒地/起身高亮可见，两态有截图 | offline + browser | r1 `audit_mainline.js` 全 295 帧离线审计 + 浏览器逐帧推到 f61/f201/f295 截图 | **PASS**（291/295 帧有认领；低姿续接 140 帧 f109–f252；身份跳变 0） | r2 `mainline_summary.log` + `mainline_f61_stand.png`/`mainline_f201_fall.png`/`mainline_f295_getup.png`；关态截图见 r1 `switch_off.png`/`switch_off_verified.png` |
| RF06 相关现有回归及开关失败/时序/低姿回归通过 | synthetic | 14 个 JS 套件逐个跑 + `python -B -W error -m unittest discover -s src/human_capture/tests` | **PASS**（全 exit 0；Python 45 tests OK） | r2 `regression.log` |
| RF07 来源/改动前副本 SHA/输入保护/回传齐全；旧有空场误认领不隐藏、不宣称人体GT | offline/记录 | r1 `BASELINE_GIT_VISIBLE.json`/`STATUS_BEFORE.txt`/`HEAD.txt` + r2 源码 SHA 登记 | **PASS**（记录齐全；本表明确保留"旧有误认领仍可能出现"，未宣称人体GT） | r2 `README.md` 源码 SHA 段；`index.html` 开关 tooltip |
| RF08 设备/物理/真实跌倒语义/EXE 重打包与部署 | device | — | **NOT_RUN**（本轮未授权设备/部署/重打包） | — |

回归明细（本轮实跑，全 exit 0）：`fresh_overlay` 8、`fresh_view` 2 组、`human_replay_lib` 46、`human_track_static` 全、`detect_overlay` 全、`panel`、`human_detect_lib` 11、`human_pipe_lib` 38、`session_selection` 12、`gt_lib` 29、`gt_live` 15、`gt_workbench_ops`、`rf_person` 全、`registration`；Python `src/human_capture/tests` 45 tests OK。

## 未闭合与限制

- RF08 未跑：设备/物理/真实跌倒语义、EXE 重打包与部署均未授权，不以本机浏览器结果替代。
- 关态截图未新增：R2 的 `browser.screenshot` 因桌面窗口不可见连续失败，关态视觉沿用 R1 的 `switch_off.png`/`switch_off_verified.png`（同一开关/同一入口页），关态 DOM 与状态为 R2 实测。
- 「低姿续接 140 帧」是离线逐帧审计的判读口径（有认领着色但 0 站姿人形簇），非人工标注 GT；旧有空场误认领不隐藏（开关 tooltip 已明示），空场会话实测不产生认领高亮，但不等于所有空场场景都不会误认领。
- 高亮身份是单目标邻域无歧义续接（`_continuations`），分裂/并人场景会拒接；需要身份 GT 时须换关联器，届时另行立项。
- 独立复审 NOT_RUN；工单 SUBMITTED 非 ACCEPTED。

## 交给Codex独立复审

- 现行验收表：[r1/ACCEPTANCE_V1.md](../evidence/2026-10-16_replay_fresh_switch_r1/ACCEPTANCE_V1.md)（RF01–RF08），本轮变更记录见上表与 r2 `README.md`/`switch_states.md`。
- 根因诊断/完整入口检查证据：r2 `switch_states.md`（开关两态 + 换会话生命周期实测）、`mainline_summary.log`（整段身份连续性）。
- 源码差异与 SHA 证据：r2 `README.md`「本轮源码 SHA」；改动前副本在 r1 `index.before.html`/`replay.before.js`。
- 原始日志索引：r2 `regression.log`、`mainline_summary.log`；r1 `mainline_082623.json`/`mainline_082623.log`/`*_tests.log`/`server_*.log`。
- 当前工单下一步：等 Codex 独立复审；复审通过后如需 RF08（设备/部署/EXE），须用户另行明确授权。
