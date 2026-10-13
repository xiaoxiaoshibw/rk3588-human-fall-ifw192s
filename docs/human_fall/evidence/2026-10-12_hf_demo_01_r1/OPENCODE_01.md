# HF-DEMO-01 / R1 只读独立复审意见（2026-10-12）

## 0. 复审依据与范围
已读：`ponytail` SKILL.md（使用路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，仅用于审查取向，未写任何代码）、`AGENTS.md`、`docs/human_fall/WORKFLOW.md` 顶层当前条目、本 `REVIEW_BRIEF.md` 全文；被测文件 `build_demo.py`/`index.html`/`app.js`/`start_demo.bat`/`manifest.json` + `data.json`；证据 `ACCEPTANCE_V1.md`/`BUILD_V3.log`/`REGRESSION.log` 及 `BUILD_DEFECT*.md`/`BUILD*_EXIT.json`/`BROWSER.jsonl`/`SERVER_LAUNCH_NOTE.md`/`OPENCODE_01.jsonl`；只读参照 `core/features.py`/`core/fall_state.py`/`core/timebase.py`。

本轮为**只读**：未执行任何 shell、未重算 SHA、未起浏览器、未写文件。凡标“已记录”的证据仅代表存在，不代表我独立复现。

## 1. Brief 指定检查点逐项核对
| 检查点 | 结论 | 依据 |
|---|---|---|
| 数据来源真实性 | 合成、已标注 | `build_demo.py` 用 `default_rng(42)`（`build_demo.py:18`）由随机模板按姿态缩放生成点云；`provenance=SYNTHETIC_KNOWN_TARGET`（`:59`）；`data.json` 首字段一致；`app.js:37` 强制校验 provenance |
| 规则复用 | 成立、未改原算法 | 仅 `import` `FeatureExtractor`/`FallStateMachine`（`build_demo.py:12-13`），未重写；`manifest.json` 记录 features/fall_state/timebase 三文件 SHA，与 `BUILD_V3.log` 一致 |
| 仅合成启用 confirmed | 成立 | 仅 `build_demo.py:26` 传 `mode_verified/allow_confirmed=True`；`fall_state.py` 默认两者 False（`:63-64`），生产路径不会 confirmed |
| 无硬编码状态动画 | 成立 | 状态/标签/事件/步骤高亮全部由预计算 `rows[frame].state` 派生（`app.js:8-18`）；无脚本化定时“演”告警 |
| 误报反例 | 存在但有保留 | `lie_fast`（“快速主动躺下·误报反例”）触发 1 次 confirmed，`app.js:15` 追加说明；但 `lie_fast` 与 `fall` 用**同一生成分支**（`build_demo.py:31`），是同一运动换名，属“已声明的几何不可分”演示，而非独立对抗样本 |
| 回放/事件/重置/seek 契约 | 成立 | `play/pause/prev/next/reset/timeline/jump/ack` 齐备；事件均由 `rows.slice(0,frame+1).filter(new_event)` 派生，seek 不重算、不累积重复（`app.js:8,43-44`）；`jump` 在无事件场景被禁用（`:41,44`） |
| SHA 失败行为 | 代码成立、未跑负例 | `app.js:35-37` 任一 fetch 失败或 SHA 不符即 `throw`，`catch` 置“无法加载”并停止渲染（`:46`）；但无“篡改数据”负例被执行 |
| V1/V2 失败保留 | 成立 | `build_demo_failed_v1/v2.py`+`BUILD/BUILD_V2.log`+`BUILD*_EXIT.json`(exit_code 1)+`BUILD_DEFECT*.md` 均在；差异仅合成输入常数（基线 .95/1.15m、姿态缩放），核心规则未动，与“V3 未改原规则”一致 |

## 2. 可执行缺陷（按优先级；未发现 P0/P1 功能性缺陷）
- **[P2-1] 来源链 SHA 不完整。** `manifest.json.sources` 只含 `features.py/fall_state.py/timebase.py`，遗漏被 `timebase.py:32` 导入的 `core/sensor_health.py`；同时 `app.js`/`index.html` 未纳入校验，页面只校验 `data.json` 一个文件。影响 FD01“来源与 SHA 可查”只做到部分。修法：`sources` 补 `sensor_health.py`（可选加 UI 文件哈希）。
- **[P2-2] FD06 独立复审产物不完整。** `OPENCODE_01.jsonl` 仅 48 行，止于一次 `read`，**无结论、无 `REVIEW_COMPLETE`**，是中断的会话记录；按现证据 FD06 尚不可判定为完成，需补一份终版独审意见。
- **[P3-1] UI 门限文本硬编码且与契约不完整。** `index.html` 步骤文案 “≥1.5 秒 / ≥3 秒” 与页脚 “下降≥0.35m、速度≥0.35m/s、低姿态≤0.70m” 是 `fall_state.DEFAULT_SETTINGS` 的复制，未由设置驱动；且页脚漏写 confirmed 还需“有效站姿基线 + 低姿态持续≥3.0s”。设置一变即文案漂移。
- **[P3-2] 播放/时间轴长度写死。** `app.js:9` 时钟分母 `18.0`、`index.html` timeline `max=180` 均为常量，仅适配当前 181 帧场景，换成其它长度会错位。建议由 `rows.length` 派生。
- **[P3-3] 重建流程未文档化。** `build_demo.py:71,75` 用 `'xb'` 独占创建，首次成功后再次运行会失败（不可变性是好事），但未说明需先删除 `data.json`+`manifest.json` 才能重建，重建者易踩坑。
- **[P3-4] 标注与运行前置。** `app.js:13` 对合成点云显示“DEMO-01 · 实测样例”，易被误读为真实测量（画布另注“合成/非真实雷达”，尚可）；且 SHA 校验依赖 `crypto.subtle` 需安全上下文，直接 `file://` 打开会落“无法加载”，应明确只经 `start_demo.bat`（127.0.0.1:8920）访问。

## 3. 验收结论与注意事项（对照 ACCEPTANCE_V1）
| ID | 结论 | 说明 |
|---|---|---|
| FD01 | 基本满足（有 P2-1 缺口） | 隔离启动成立、无生产/原数据改动；SHA 可查但不完整，且我未独立重算 SHA |
| FD02 | 满足（代码追溯） | 逻辑链可复现 descending→suspected→confirmed→recovering、每事件一次；依据 V3 build 输出 |
| FD03 | 满足 | walk/sit/low/occlusion 零 confirmed，遮挡帧 unknown，lie_fast 明确标注不可分 |
| FD04 | 满足 | 控制项与事件/重置/seek 契约经代码核对成立 |
| FD05 | 已记录、未独立复现 | `BROWSER.jsonl`/`DEMO_ALARM.png`/`SERVER_LAUNCH_NOTE.md` 存在；浏览器行为与 SHA 负例我未亲验，**不宣称 PASS** |
| FD06 | 未闭合（P2-2） | 已有独审记录中断，无终版结论 |
| FD07 | **NOT_RUN** | `manifest.real_fall_accuracy=NOT_RUN`，真实准确率/真实跟踪/设备/部署均未验，不得以合成分代替 |

其他注意：`BASELINE_EXIT.json` 自述 `atomic:false`（非原子扫描，不宣称全树冻结）；`REGRESSION.log` 仅 “Ran 20 tests … OK” 而无命令行/套件归属，可归因性偏弱；6 段合成序列不是检测器、也不是真实跌倒准确率评估。

综合：Demo 本体（合成来源、规则复用、仅合成 confirmed、无硬编码动画、回放/事件/seek 契约、SHA 失败即停）在**只读代码审查**层面成立，未发现阻断性缺陷；行动项集中在来源链补全（P2-1）与独审收口（P2-2），以及若干文案/健壮性 P3。设备与真实准确率维持 NOT_RUN。

REVIEW_COMPLETE