# 文件直下端点 + 网页下载链接：板端部署实录（2026-10-07 晚）

用户直派「部署板端」（免 SSH 的会话文件 HTTP 直下 + 8090 控制页下载链接）。
PC 侧代码与重建的 Console.exe 见同日 `pc_apps/human_replay/fetch.py`、`pc_apps/console/dist/LiDAR_Console.zip`。

## 部署内容（4 个文件，sha256 前后对照）

| 文件（容器内路径） | 部署前 | 部署后（= 仓库本地） |
|---|---|---|
| `/root/catkin_ws/src/human_capture/scripts/capture_server.py`（宿主 bind `/home/wel/slam_localization_wuhan/src`） | `9c1ce997…d8abf7e` | `8d0bd5ca…a9d18e54a` |
| `/root/catkin_ws/webui/human_capture/capture.js`（容器内，docker cp） | `a55ac2ec…954495aa` | `4e6a71b7…035ff5b` |
| `/root/catkin_ws/webui/human_capture/capture_lib.js` | `b9be2ddd…4e43a047` | `515e4ab0…670002cd` |
| `/root/catkin_ws/webui/human_capture/index.html` | `42750c57…10aa7a3c` | `f12894b6…f364ca4d3` |

- 旧文件备份：`/home/wel/deploy_backups/20261007_human_capture_files/`（`capture_server.py.old`、3 个 `.old`、`sessions.json.before`）；上传暂存 `/home/wel/hc_deploy_20261007/`。
- 板端 `capture.yaml` **未动**（`download_limit_kbit` 由代码默认 70000 Kbit/s 生效）。
- capture_server 重启：旧 PID 2344 → 新 PID 3578（重启前 `recording=false`，未在录制中）；8090 静态页无需重启。

## 验证（PC 侧实测，192.168.3.8 → 板）

- `HEAD /api/v1/sessions/cap_20261007_155534/files/meta.json` → 200，`Content-Length: 8437`，`Content-Disposition: attachment`，CORS `*`
- 同会话 `points.bin` 整份 GET → 200，**50,890,308 B**（与板端 `ls` 一致），5.896 s，8,631,014 B/s ≈ 69 Mbit（限速生效）
- `files/sessions.json`（白名单外）→ 400 `bad_name`
- 8090 `/human_capture/`：`capture.js` 含 `fileLinksHtml`、`index.html` 含免 SSH 提示

## 附带修复：4 个卡死会话

旧 exe 失败拉取留下的 `transferring`（155534 / 155436 / 154920 / 154341）已 PATCH 回 `ready`；
随后用修复版 `fetch.py --sid cap_20261007_154341` 真机端到端拉取成功
（digest `98d6006f03f335ec`，本地 meta 8242 B + points 49,513,912 B），板端置 `transferred`。其余 3 个待拉。

副作用（按 FIFO 既有策略，非故障）：unstick 后候选数 13 > `fifo_keep=10`，
FIFO 清掉 3 个最老**已下载**会话（20261004_202456 / 203135 / 203349 → `purged`；
删 bag/manifest/reserve，会话目录按既有设计保留）。三者在 PC `captures/remote/` 均有本地副本。

## 回滚

`cp` 备份的 `capture_server.py.old` 回宿主源 + `docker cp` 三个 `.old` 回容器 +
按 BOOTSTRAP §6 重启 capture_server（勿在录制中操作）。
