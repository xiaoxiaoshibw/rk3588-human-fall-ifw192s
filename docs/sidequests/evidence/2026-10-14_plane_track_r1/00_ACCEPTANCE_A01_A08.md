# PLANE-01 唯一验收表 v1（2026-10-14）

工单：小飞行目标：配平 → 去背景 → 实时跟踪小飞机（本单）。
证据目录：`docs/sidequests/evidence/2026-10-14_plane_track_r1/`；回传：`docs/sidequests/returns/PLANE-01.md`。
作者：OpenCode CLI（opencode-go/deepseek-v4.1-flash），本单唯一写作者；ponytail 实际读取路径
`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（本机 OpenCode skill 目录）。

| ID | 要求 | 结果 | 证据 / 数值 |
|---|---|---|---|
| A01 | 数据清点完整（本地+板端，含来源与是否空场） | PASS | `01_INVENTORY_v2.json` + `01_INVENTORY.md`（本地 41 段、板端 API 35 段全部命中、6 段 joint 为本机专属）；9 段场景角色来自 `ACTION_CATALOG.md` 等既有证据，其余 UNKNOWN |
| A02 | 每段会话配平结果齐全、可复算；失败项显式 FAIL | PASS | `02_LEVELING_*.json`（3 段新配平 auto：全部三法 valid；164522/094302 recommended=tls，175227 recommended=None，根因=跨方法 offset 差 0.033 m>0.03 m 一致性门）；4 段既有 job 复验 deletable_candidate=True |
| A03 | 背景配准通过（或"需重录空场"结论），泄漏带定量 | PASS | `03_REGISTRATION_131958_to_164522/`（既有 registration.js：PASS，fit p50 9.1 mm / p90 31.6 mm，holdout p50 8.7 mm，20 项 gate 无 reason）；`04_BACKGROUND*.json`：配准后泄漏 343 点/帧（0.70%）、最大簇 224 点=位移家具（中心 (3.9,2.9,0.2)，距目标 4.75 m）；未配准 131958=3004 点（6.1%）、未配准 175227=15146 点（30.8%）；10-10 空场被既有配准门拒绝（`03_REGISTRATION_175227_REFUSED`，exit 1，registration.js:104）；目标区 0 泄漏点=目标物在 10-13 空场里（背景减除会把它删掉，检测不得依赖背景） |
| A04 | 小飞机逐帧检测表：距离-点数-命中帧率，明确可达距离与漏检 | PASS（阈值口径）/ 语义身份 UNKNOWN | `06_TRACK_REAL.json`：27/27 帧命中（min_cluster_points=3/5/8 全部 27/27；=25 时 0/27，即现配置 25 点门槛落空，与工单预期一致）；每帧 8–23 点（中位 12）、R=6.38–6.62 m；折合面积中位 0.0354 m²（工单玩具机 0.0117 m²）；可达距离（3/5/8/25 点）：13.0/10.1/8.0/4.5 m（实测面积）与 7.5/5.8/4.6/2.6 m（玩具机面积）；`05_TARGET_IDENTITY.json/png`：细长水平结构 0.4–1.2 m×0.2–0.5 m、离地≈3.0 m、中心抖动 ±0.15 m、无一致平移 → 更像固定吊装物（吊灯/挂钩/轨道），非飞行目标，语义判定需用户/相机确认 |
| A05 | 跟踪连续性：丢失帧数、ID 跳变次数、最大速度；实拍/合成/回放分开标 | PASS | 实拍 `06_TRACK_REAL.json`：27/27、丢 0、ID 跳变 0、重初始化 1、表观中心最大步速 2.18 m/s（细长静止物的簇心抖动，非真实位移）；合成 `07_TRACK_SYNTHETIC_v2.json`：0/3/5/10 m/s 各 30/30 命中丢 0，划痕=0.309/0.515/1.028 m≈v×0.103 s，测速 3.00/5.00/9.98 m/s（最大误差 0.2%），cluster_cell 0.3/0.5 同结果；回放 `08_REPLAY_10HZ.json`：27 帧全发布全命中丢 0；已知限制（测试固化）：首帧无划痕时 >0.35 m 的跳变会丢失 |
| A06 | 本机 10 Hz 回放延迟/掉帧数；板端 NOT_RUN | PASS（本机）/ 板端 NOT_RUN | `08_REPLAY_10HZ.json` + `08_REPLAY_BROWSER.json` + `08_REPLAY_PAGE.png`：按源帧 real bag 间隔（≈10 Hz）喂帧；服务端 compute 中位 46.4 ms / p95 61.2 / max 63.2，发布延迟中位 46.5 / p95 61.9 / max 63.5 ms，晚启动（掉帧）0/27；Python 客户端 24/27 见帧 3 次采样跳格；真实 Chromium 页面渲染 24 帧 3 次采样跳格，页面 fetch→渲染 30–44 ms；无板端部署 |
| A07 | 删除执行与清单（未获批 = NOT_RUN） | PASS（已获用户确认） | `10_DELETION_CANDIDATES.json`（7 段已验证产物，逐段给消费者/板端状态/建议）+ `11_DELETION_EXECUTED.json`（用户确认后删 `cap_20261014_164522`、`cap_20261013_094302` 的本机未配平副本；captures/remote 41→39；leveled job 363473a9…/53bfb3ca… 保留并复核；删除前 SHA/字节/清单留存）；其余 5 段保留并给出原因（在仓代码消费者/板端已 purged 只剩本机一份） |
| A08 | 回归：python -B -W error -m unittest 各套 + node 各套全绿，无新依赖 | PASS | `12_REGRESSION_SUMMARY.json` + `12_reg_*.log`（python 504/45/2/7/10 全 OK；node 18/55/33/45/panel/11/38/12 全过 0 failed；无新增依赖） |

状态：**SUBMITTED / 未 ACCEPTED**（作者自验）。设备/物理/部署一律 NOT_RUN；本表只覆盖本工单 A01–A08。
