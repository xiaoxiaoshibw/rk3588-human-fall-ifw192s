# P03 回放自动配平

2026-10-05 用户授权：「回放页选择会话时算法自动配平，算法放 8901 服务侧」。唯一验收表 [P03_ACCEPTANCE.md](../P03_ACCEPTANCE.md) v1，单 writer Claude Code，[派发提示词](../AI_PROMPT_P03_CLAUDE_R1.md)。

## 背景与为什么

- 用户是跌倒项目，不愿继续打磨配平；R2 联合单平面（26.623°/−1.395°/d 1.3219m）可作锚点只用于比较，不复制死值进代码。
- R3 证明四块地不在同一刚体面（类型 C、6 对互预测 FAIL）——全场 RANSAC 会拐非共面块，这正是它必须**如实公开支持率、不把候选当全场地面**的原因。
- GL-W01 工作台已有完整三法/留帧/门/导出/报告：本单不复制它们，只补「算法找域」+「回放自动消费」两块。

## 范围（只这些）

`pc_apps/human_replay/` 内：新建 `leveling_lib.py`（纯函数 detect_ground_domain）、改 `leveling.py`（auto 分支，不删/改 DEFAULT regions=4 路径语义）、轻调 `leveling.js`（auto 结果页显区分，仍走确认才消费的既有 STOP）、改 `replay.js`（`__load_session_sid` 侧申请 transform 并应用）、必要时 `human_replay_lib.test.js` 纯函数增补、新建 `leveling_auto_test.py`。不改 driver/webui/annotator/captures/旧证据；console exe 不重打包（内存仍按 console-app-facts）。

## 验收

按 P03 v1 固定 ID P03-A/B/C/D/E + S01 + D01；专独审与真实 browser NOT_RUN，D01 NOT_RUN。
