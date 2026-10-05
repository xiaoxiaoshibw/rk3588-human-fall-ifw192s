# GL-V01 R2 Luka 收口附记 / 2026-10-05 晚

本文件只追加本轮（R2 closeout 术语沿用 15_SUBMISSION.md）事实，不修改已由 Codex 提交的 00–17 证据与内容。

## 场景位置问题（用户 17:18 提问 → 20 号摘要）

- semantic：region = `[x_min, x_max, y_min, y_max]`；x 雷达正前、y 左(+)/右(-)。名义 z（offset/pitch）是算法从点云体素发现的候选平面高度带，只作一致性指示，不等同物理标定高。
- 20_target_plane_summary.json：三会话的 extent/pitch/roll/offset/z-range 从 04_auto_results.json 直接读取，无二次推算。

## 控制台可达旧版修复（本轮补的唯一代码外动作）

发现（19_console_launch_check.json）：
- 桌面「总控制台」.lnk 已指向 `dist/gl_v01_floor_r2/Console.exe`（新），但 `dist/Console.exe` 与 `dist/hr02_offline/Console.exe` 仍停留在 R1 版本 559383E7…。
- 两个 559383E7… 的 hr02_offline 实例（PID 25216/11968）在运行中，锁住该文件；父进程被外部 `taskkill /T` 部分工作后残留，需对父强杀后子进程才退。

处置（18_console_sync.json）：
- `dist/Console.exe`、`dist/hr02_offline/Console.exe` 同步为 R2 的 C8F34A5E…。
- `pc_apps/console/dist/LiDAR_Console.zip` 重打包，内嵌 `LiDAR_Console/Console.exe` 替换为 C8F34A5E…；除 exe 外别的文件（README 等）沿用 zip 原内容未改。
- 桌面另外存在一个 `LiDAR_Console_20261005.zip`（exe SHA16 b9709290…），仓库内没找到构建该包的记录或脚本引用，来源不明；不动它。
- `dist/gl_v01/`、`dist/gl_w01/` 历史发布目录按 GL-W01 附记「保持旧包不覆盖」约定保持原样。

## 状态

- 桌面快捷方式 → R2 exe；两个被外部工具可能启动的镜像（`dist/Console.exe`、`hr02_offline`）→ R2 exe；zip 发布包 → R2 exe。改动与 SHA 见 18。
- 验收表中 V01 在 R2 提交里已 PASS；本附记只补「本轮发现分发的旧镜像存在并已同步」这一事实，不回填验收结论、不动 Codex 判断。
