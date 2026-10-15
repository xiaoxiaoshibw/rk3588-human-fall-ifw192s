# HC-DOWNLOAD-LIMIT-01 回传

- 用户授权：口述"改限速"（问"本机从 3588 拉数据是不是也非常快"，实测只有 8.75 MB/s 之后）。
- 2026-10-14；分支 master、HEAD `c21c443b0befe559e08283edb0efc2af02dcc6b8`；工作树起时已有其他未提交改动，本单只碰 3 个文件。
- 唯一验收：[v1](../evidence/2026-10-14_hc_download_limit_r1/ACCEPTANCE_V1.md)；逐次测量 [BENCHMARK.json](../evidence/2026-10-14_hc_download_limit_r1/BENCHMARK.json)；基线 [00_baseline.json](../evidence/2026-10-14_hc_download_limit_r1/00_baseline.json)；说明 [README.md](../evidence/2026-10-14_hc_download_limit_r1/README.md)。
- 技能：ponytail 实际读取 `C:\Users\30680\.claude\skills\ponytail\SKILL.md`。
- 根因：不是链路问题（1G 直连裸 TCP 849 Mbps、ssh 86.8 MB/s），而是板端 HC 文件路由的限速器 `download_limit_kbit`；板端 yaml 是旧版**没有这个键**，落回代码默认 `70000` Kbit/s = 8.75 MB/s，与实测完全吻合。
- 改动：板端 `capture.yaml` 加 `download_limit_kbit: 800000`（备份 `capture.yaml.bak-20261014`）；仓库 `src/human_capture/config/capture.yaml` 同步 70000→800000；`pc_apps/human_replay/config.py`、`fetch.py` 仅改注释里的旧数值。
- 生效方式：容器 `slam-localization` 内按 `/home/wel/BOOTSTRAP.md` 第 6 节原命令重启（配置启动时读入）；重启前备份容器日志为 `/var/log/capture_server.log.20261014`。板端 PID 3578 → 26094。
- 结果：同一 374.2 MB 会话 42.78 s → **3.77 s（8.75 → 99.6 MB/s，11.4×）**；DL01–DL05 PASS，落地 sha256 `e1c25096…` 与本机副本一致；`src/human_capture/tests` 45 项、`fetch_lib_test.py` 13 项 OK。
- 取 800000 而非 0：不限速实测 118 MB/s（≈940 Mbps）会吃满 1G，给同时在跑的 bridge ~93 Mbit + 预览 ~17 Mbit 留余量的代价只有每 374 MB 0.6 s。
- NOT_RUN：真实 `fetch.py --sid` 端到端（会 PATCH 板端登记状态）、拉取与实时流并发的丢帧/公平性、实际回滚演练。
- 未改板端源码、未动会话数据、未 commit/push。同侧事实：板端 10 行登记里只有 2 行还有文件（其余含 6 行 `state=transferred` 的已 404），与本单无关，仅记录。
