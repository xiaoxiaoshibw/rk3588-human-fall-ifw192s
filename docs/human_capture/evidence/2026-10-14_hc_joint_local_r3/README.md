# HC-JOINT-LOCAL-01 R3 文案对齐证据

2026-10-14，主控本轮唯一 writer，SUBMITTED 未 ACCEPTED，独审 NOT_RUN。
技能实际读取：C:/Users/30680/.claude/skills/ponytail/SKILL.md。

## 背景

现行 joint_capture.py（提交 6ecc3a2 内）为错峰设计：相机仅预览，雷达经板端 HC 服务先录到板端，停止后由 fetch.py 一次性拉回。但 console.html 卡片 desc、README.txt 联合段、joint_capture.html 部分状态文案仍是更早"两路直写本机"口径，且 joint_capture.html 保留 completed_with_gaps 死状态（现行代码不会产生）。

## 逐处对照（旧 → 新）

| 位置 | 旧 | 新 |
|---|---|---|
| console.html:119 desc | 同时录制 · 数据直接保存到本机 | 板端先存 · 录制结束后拉回本机 |
| README.txt 入口行 | USB＋雷达联合录制  数据直接保存到本机 | USB＋雷达联合录制  板端先存 · 结束后拉回本机 |
| README.txt 联合段 | 两路直写本机/cap_*_joint_*/radar.ros1/3600 秒/8 GiB/断流自动停止 | 板端先存→停止后拉回 joint_<板端会话号>\、每次独立会话；1–300 秒、256 MiB 检查、拉回未完成可重试 |
| joint_capture.html names | 含 completed_with_gaps:'已保存到本机（相机预览曾中断）' | 已删除（现行代码不产生该状态） |
| joint_capture.html #quality 行/div | completed_with_gaps 提示 | 已删除 |
| joint_capture.html 页脚 | radar = ... camera = ... | 每次录制独立会话目录；停止后从板端拉回，未完成可在会话回放重试 |
| joint_capture.py 模块 docstring | 停止后逐段拉回…按 frames 行上切片 | 停止后用官方 fetch.py 一次性回拉，无逐段切片 |
| joint_capture_test.py docstring | 最终 completed_with_gaps | 最终 completed（与其断言一致） |

## 验证（本机软件自验）

| 项 | 命令 | 结果 |
|---|---|---|
| 控制台页回归 | node console_html.test.js | 12 passed, 0 failed（TESTS_CONSOLE_JS.log） |
| 联合录制单测 | python -B joint_capture_test.py -v | 4 tests OK（TESTS_JOINT_PY.log） |
| 控制台启动单测 | python -B console_test.py | 7 tests OK（TESTS_CONSOLE_PY.log） |
| 页面探针 | python console_gui.py --check-joint-capture … | exit 0，page_ok=true（JOINT_PAGE_CHECK.json） |

## 基线

HEAD c21c443b0befe559e08283edb0efc2af02dcc6b8；工作树起时已有用户未提交差异（console.html/console_gui.py 等），本轮只在其上追加本表所列改动。逐文件改前/改后 SHA 见 SOURCE_SHA.json。

## 未闭合

- 行为未改：停止后拉回仍由记录线程自动开始（fetch.py），无手动触发按钮；若用户要"停在板上、手动拉"需另行改行为。
- EXE/ZIP 未重打：文案要生效需重打 Console.exe/Console_Pointset.exe（当前有控制台实例在运行占用 dist）。浏览器/设备验证 NOT_RUN。
- docs/human_capture/README.md 2026-10-13 HC-JOINT-LOCAL 两条历史条目仍描述更早直写本机设计，属历史记录未改动。
