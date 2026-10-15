# 2026-10-14 HC-DOWNLOAD-LIMIT-01 板端下载限速 70000 → 800000

## 怎么发现的

用户问"本机从 3588 拉数据是不是也非常快"。实测 `curl` 板端 HC 网页直下路由
（`http://192.168.31.58:8766/api/v1/sessions/<sid>/files/points.bin`）：
374.2 MB 要 **42.8 s = 8.75 MB/s（70 Mbps）**，而同一根网线裸 TCP 能到 849 Mbps、
ssh 通道实测 86.8 MB/s —— 说明不是链路问题。

根因：`capture_server.py` 的文件路由有一段主动限速器，
`limit = cfg["download_limit_kbit"]`。板端 `capture.yaml` 是 2026-10-02 的旧版，
**根本没有这个键**，于是落回代码默认值 `70000` Kbit/s = 70 Mbps = 8.75 MB/s，与实测
数字一字不差。这个值是百兆/Wi-Fi 时代为了"保护实时预览"设的（原注释：`给 100M 链路留 30%`），
现在 PC 走 1G 直连已经不适用。

## 改了什么

| 位置 | 改动 |
|---|---|
| 板端 `/home/wel/slam_localization_wuhan/src/human_capture/config/capture.yaml` | 新增 `download_limit_kbit: 800000`（备份 `capture.yaml.bak-20261014`） |
| 仓库 `src/human_capture/config/capture.yaml` | `70000` → `800000` + 注释更新 |
| `pc_apps/human_replay/config.py`、`fetch.py` | 仅注释里的旧数值/旧理由 |

容器内 `slam-localization` 按 `/home/wel/BOOTSTRAP.md` 第 6 节原命令重启
（配置在启动时读入，必须重启才生效）；重启前把 `/var/log/capture_server.log`
备份为 `.20261014`。

## 实测（374,212,300 字节，PC 192.168.31.111 ↔ 板 eth3 192.168.31.58）

| `download_limit_kbit` | 耗时 | 速度 |
|---|---|---|
| 70000（改前实际生效） | 42.78 s | 8.75 MB/s |
| 700000 | 4.28 s | 87.3 MB/s |
| **800000（采用）** | **3.77 s** | **99.6 MB/s** |
| 0（不限速，取天花板用） | 3.16 s | 118 MB/s |

完整性：改后重新拉取的 `points.bin` sha256 `e1c25096…` 与本机已有副本**完全相同**。
测试：`src/human_capture/tests` 45 项 OK、`pc_apps/human_replay/fetch_lib_test.py` 13 项 OK。

## 为什么取 800000 而不是 0

不限速实测 118 MB/s（≈940 Mbps）会把 1G 链路吃满，同时在跑的实时流
（foxglove bridge ~93 Mbit + MJPEG 预览 ~17 Mbit）就没有余量了。800000 留 ~200 Mbit
余量，代价是每 374 MB 慢约 0.6 s。要绝对最快：把值改成 `0`（一行，`0 = 不限速` 是既有语义）。

## 回退

```bash
# 板端
cd /home/wel/slam_localization_wuhan/src/human_capture/config
cp -p capture.yaml.bak-20261014 capture.yaml      # 回到"无该键"的原状
bash /tmp/restart_capture_server.sh               # 与 BOOTSTRAP §6 同命令重启
curl -s http://192.168.31.58:8766/healthz
```

## 未做（如实登记）

- 真实 `fetch.py --sid` 端到端跑一遍（会 PATCH 板端登记状态）：NOT_RUN。
- 拉取与实时流并发时的丢帧/公平性：NOT_RUN。
- 实际回滚演练：NOT_RUN。

验收表见 [ACCEPTANCE_V1.md](ACCEPTANCE_V1.md)，逐次测量原始数字见 [BENCHMARK.json](BENCHMARK.json)，
改动前基线见 [00_baseline.json](00_baseline.json)。
