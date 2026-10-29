# REPLAY-MEASURE-01 回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：REPLAY-MEASURE-01 / R1 / OpenCode CLI（`opencode-go/deepseek-v4.1-flash`，本轮该范围唯一生产代码写入者）/ 2026-10-15 Asia/Shanghai。
- 用户授权（直派）：「给总控会话回放加一个测点距离的工具」。
- [唯一验收 v1](../evidence/2026-10-15_replay_measure_r1/ACCEPTANCE_V1.md)（M01–M07）、[改动/验证/限制](../evidence/2026-10-15_replay_measure_r1/README.md)。提交时验收表 SHA 未冻结。
- 状态：SUBMITTED（软件自验部分 PASS/FAIL 见下表）；浏览器实录 M03/M05 NOT_RUN，冻结 EXE M07 NOT_RUN，独立复审 NOT_RUN；不宣布 ACCEPTED、不宣布总体软件 PASS。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树本就脏（含他人并行差异），本轮只动下表 5 文件，未 commit/push/reset/clean。源码 SHA 见证据 README。
- ponytail 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail/SKILL.md`（skill 工具加载，full）。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| M02（工具能力不足） | HR-04 的 `M` 标尺把光标投到地面 `z=0` 两点，只能量平面距离，量不了身高/任意两点；且无可见入口 | 会话回放页（`index.html`）与人检锁定页（`human_track.html`）都加载同一 `replay.js`，标尺是 `S.measure` 三态 | `human_replay_lib.js` 新增 `measure_point_from`；`replay.js` `measure_pick/measure_step/measure_render` | 三态语义（起点→出尺→清除）、红色线+端球+距离 Sprite、`M` 键都保留；点到地面空处仍退化成原地面距离 |
| M01（入口缺失） | 只有键位提示，无按钮；`replay.js` 的 els 契约要求 id 在两个 HTML 里都存在 | 两页启动即取 `els.measureBtn`，缺则 `_els_missing` 报错 | `index.html`/`human_track.html` 加 `#measureBtn`（该缺失由既有 `human_track_static.test.js` R2 抓出） | 既有 id/键位/面板不动 |

实现前核查同类调用者：`pick_point_on_ray`（`human_detect.js` 准星 ROI）与 `find_nearest_xy`（`P` 键快照）都是既有取点路径，本轮**复用** `pick_point_on_ray` 而不再写一份取点；拾取半径沿用 0.5m 约定。语义变化（M 从「地面两点」变「点云真点优先 + 地面回退」）已记录在证据 README；不改既有验收断言。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `pc_apps/human_replay/human_replay_lib.js` | 新增导出 `measure_point_from(pick, ground)`（点云点→地面→null） | 本轮新增 | `a7683b5a…` |
| `pc_apps/human_replay/replay.js` | 3D 取点 + 点击测量模式 + 按钮绑定 + 拖动阈值 4px + 换会话清尺 + 标签挂 3D 中点 | 本轮新增 | `e7340640…` |
| `pc_apps/human_replay/index.html` | 工具栏 `#measureBtn` + 底部提示 `<kbd>M</kbd> 测距` | 本轮新增 | `5abc2e16…` |
| `pc_apps/human_replay/human_track.html` | 同页加载 `replay.js`，补 `#measureBtn` 满足 els 静态契约 | 本轮新增 | `12696d1e…` |
| `pc_apps/human_replay/human_replay_lib.test.js` | 新用例 `measure_point_from`（3 断言） | 本轮新增 | `139be33e…` |

单位/坐标：沿用板端 IFW192S 坐标（x-forward/y-left/z-up），无变换、无单位换算；距离为欧氏米制。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline | 实际命令或源码审查位置 | 结果及退出码 | 日志/样本 |
|---|---|---|---|---|
| M01 入口可见 + 两页 els 契约 | offline | `cd pc_apps/human_replay; node human_track_static.test.js` | **PASS**（R1/R2/R3 全过，exit 0；修前 FAIL `missing: measureBtn`） | 见证据 README「验证」表 |
| M02 取点优先级 | offline（lib 单测） | `node human_replay_lib.test.js` → `measure_point_from` 用例 | **PASS**（46 passed，exit 0） | 同上 |
| M03 两击出尺显示 | — | 源码审查 `replay.js` `measure_step`/`measure_render`（状态栏 3D/水平/高差/两端坐标） | **NOT_RUN**（浏览器实录未跑） | 同上 |
| M04 清除路径 | offline（源码审查） | `measure_clear` 调用点：第三击 / 关按钮 / `load()` 换会话 | **PASS**（审查） | 同上 |
| M05 不误触 | offline（源码审查） | `bind_measure_click` 位移 >4px 返回；`bind_person_drag` 测距开启时返回 | **PASS**（审查）；实录 NOT_RUN | 同上 |
| M06 回归 | offline | human_replay 10 个 JS 套件 + `sessions_test.py` 7；console `console_html.test.js` 21 + `console_test.py` 7 | **PASS**（全 exit 0） | 同上 |
| M07 冻结 EXE 吃到本改动 | — | 读 `dist/console_passthrough.ini` + `console_gui._replay_dir()`/`_read_passthrough_ini()`（源码审查）；桌面 lnk 目标核实为 `dist\Console.exe` | **PASS（INI/SOURCE_BYPASS，重启生效）**；exe 内嵌副本重打 NOT_RUN | — |

既有失败保留：`node gt_roundtrip.test.js` exit 1 —— 缺真实会话 `cap_20261010_180751` 时该测试自行 `process.exit(1)`，与本轮改动无关，未掩盖。

## 未闭合与限制

- M03/M05 浏览器实录：解除条件是「真浏览器点两下出距离并截图」。**M07 已澄清**：本机桌面控制台目标是
  `dist\Console.exe`，同目录 `console_passthrough.ini` 的 `[human_replay] replay_dir` 指向本仓源码目录且校验通过 →
  冻结 exe 走 INI/SOURCE_BYPASS，**重启控制台即吃到本改动，无需重打**。exe 内嵌副本未由本轮重打（NOT_RUN）：
  检查时发现并行写入者的 `PyInstaller Console.spec`（PID 37556）仍在跑，共用 `build/`+`dist/`，本轮不叠加第二次构建。
- 契约允许的限制：取点半径写死 `MEASURE_PICK_R = 0.5`；点得离点云太远落到地面而非报错（刻意回退）；标尺仍是浏览器瞬态，不落 meta（与 HR-04/HR-05 约定一致）。
- 范围外新需求/后续建议：如需「多点折线/封闭面积/保存测量记录」，另开一轮（本轮不做，避免把瞬态标尺复杂化）。
- 设备/物理：无（纯 PC 侧 UI）；未连板、未采集、未部署、未改板端/驱动/算法/模型/GT/数据。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：[ACCEPTANCE_V1.md](../evidence/2026-10-15_replay_measure_r1/ACCEPTANCE_V1.md) / [README.md](../evidence/2026-10-15_replay_measure_r1/README.md)。
- 根因诊断/完整入口检查证据：本文「集中诊断」表；els 契约缺失由既有 `human_track_static.test.js` 实证。
- 源码差异与 SHA 证据：证据 README 的两张表（逐文件 bytes + sha256）。
- 原始日志索引：本轮命令输出见证据 README「验证」表（`.log` 未单独落盘，无隐藏失败）。
- 当前工单下一步：复审源码差异与 lib 单测；如需我重打 `Console.exe` 并在真浏览器实录，请显式派发（会写 `dist/` 冻结产物）。
