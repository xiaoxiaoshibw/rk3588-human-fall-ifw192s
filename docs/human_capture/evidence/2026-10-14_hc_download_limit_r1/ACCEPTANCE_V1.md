# HC-DOWNLOAD-LIMIT-01 验收 v1（唯一当前版本）

2026-10-14。用户口述授权："改限速"。范围：板端 HC 网页直下（8766 `/files/*`）的限速值，
以及仓库侧同口径的配置与注释。

| ID | 判据 | 结果 | 证据 |
|---|---|---|---|
| DL01 | 板端生效值由 70000 提到 800000（1G 直连时代），容器内服务按 BOOTSTRAP §6 同命令重启 | **PASS** | `00_baseline.json`（板端 yaml sha / PID 3578→26094）；容器日志 `listening on 0.0.0.0:8766` |
| DL02 | 拉取吞吐相对改前提升 ≥5× | **PASS** | `BENCHMARK.json`：374.2 MB 8.75 MB/s → 99.2/99.8 MB/s（11.4×） |
| DL03 | 拉取落地字节与原副本逐字节一致（不是"快了但伤了"） | **PASS** | `BENCHMARK.json.integrity`：sha256 `e1c25096…` 双向相同 |
| DL04 | 重启后板端服务可用且状态不变（healthz / status / 10 行登记） | **PASS** | 重启前后 `sessions_total=10`、`ros=up`、`recording=false` |
| DL05 | 回退材料就位：配置备份 + 幂等重启脚本实测可重复执行 | **PASS** | `capture.yaml.bak-20261014`；`/tmp/restart_capture_server.sh` 本轮连续执行 3 次均正常 |
| DL06 | 实际回滚演练（改回 70000 并验证速率回落） | **NOT_RUN** | 未执行；回退路径见 README |
| DL07 | 真实 Console/`fetch.py --sid` 端到端拉回 | **NOT_RUN** | 该命令会 PATCH 板端登记状态（transferring/transferred），未在真实会话上跑；本轮用同一条 HTTP 路由直接压测 |
| DL08 | 与同时在跑的实时流（foxglove bridge ~93 Mbit + MJPEG 预览 ~17 Mbit）并存时的公平性与丢帧 | **NOT_RUN** | 未并发实测；选 800000（而非 0）就是为了给这两路留 ~200 Mbit |

## 本单不涉及

- 未改板端源码、未改录制/抽取/回放算法、未动任何会话数据文件、未 commit/push。
- 未跑单元测试以外的设备/物理结论；本单结论只覆盖"传输通道速率与完整性"。
- 板端登记里有 8 行（含 6 行 `state=transferred`）文件已不存在，**与本单无关**，只作为同侧观察到的事实记在 `BENCHMARK.json.board_registry_spot_check`。
