# pc_apps/console（仅剩联合录制后端）

2026-10-25：旧网页版总控制台（console.html / console_gui.py / Console.exe 打包及 plane01_pages）
已被 Qt 版 [console_v2](../../console_v2/README.md) 替代并整体删除。

本目录仅保留 `console_v2/joint_server.py` 仍在使用的 USB＋雷达联合录制后端：

- `joint_capture.py` — 录制服务（板端先存、录后拉回 + 相机同步录像），标准库实现；
  另含空闲预览泵：`/api/preview` 被持续请求时才连板端相机流刷最新帧，5 秒无请求自动
  断开；与录制相机线程共用一条流锁（任何时刻最多一条相机连接，录制中泵让路）；
- `joint_capture.html` — 联合录制页（joint_server 以 `http://127.0.0.1:<port>/` 提供）;
- `joint_capture_test.py` — 回归测试：`python -B -W error joint_capture_test.py`
  （含空闲预览泵合同：请求驱动、窗口期外零设备访问、录制期间客户端并发流 ≤1）。

入口：`python -B -W error console_v2/joint_server.py --output-root <绝对路径>`（fetch 依赖
`pc_apps/human_replay`）。历史记录见 `docs/PROGRESS.md` 与 `docs/evidence/`，此处不重复。
