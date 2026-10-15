# PLANE-01 小飞行目标：配平 → 去背景 → 实时跟踪小飞机

> 本文件按 `docs/human_fall/RETURN_TEMPLATE.md`（工作流程v2）追加；本单为 sidequests 支线，证据在
> `docs/sidequests/evidence/2026-10-14_plane_track_r1/`，验收表 `00_ACCEPTANCE_A01_A08.md`。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：PLANE-01 / r1 / OpenCode CLI（本单唯一写作者）/ 2026-10-14（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA：`docs/sidequests/evidence/2026-10-14_plane_track_r1/00_ACCEPTANCE_A01_A08.md`（v1，
  SHA256 `549B0017799403FC4E0EC15ADFB11E5A2892E8D86A35018AABBD00A608581F95`；其中 A08 行在回归跑完后才填入，
  该行之前的值 `CD08221A…` 是被替换前的中间态，SHA 以本行为准）。
- 执行方式 / 实际会话与模型：OpenCode 会话内直接执行（provider `opencode-go`，model `deepseek-v4.1-flash`），
  本机 Windows + Python 3.12.10 + NumPy 1.26.4 + Node 24.14.0；无板端登录/部署。
- 状态：**SUBMITTED / 未 ACCEPTED**；软件自验见逐条表；设备/物理/部署/独立复审 NOT_RUN。
- 起始 branch/HEAD：`master` / `c21c443b0befe559e08283edb0efc2af02dcc6b8`（工作树本就脏：`git status --porcelain`
  2067 条，含未跟踪生产源码；本单未 commit/push/reset/checkout/clean）。
- 范围内用户差异：仅新增 `sidequests/plane_track/`、`docs/sidequests/evidence/2026-10-14_plane_track_r1/`、
  本回传文件；新增产物 `captures/leveled/{363473a9…,6d5809d5…,53bfb3ca…}/`；经用户确认删除
  `captures/remote/cap_20261014_164522`、`captures/remote/cap_20261013_094302` 两段未配平副本（见 A07）。
- 源码 SHA 证据：全量 SHA256 见 `docs/sidequests/evidence/2026-10-14_plane_track_r1/13_SOURCE_SHAS.json`（14 个源文件 + 本回传/验收表）；
  前 16 位：
  common.py `5D344077980C5828`、inventory.py `ECB74EFD51D2AC5A`、level_sessions.py `11F46458518BC558`、
  inspect_target.py `C66B281A12E66D69`、background.py `220FDB3ECCDCD9D4`、background_probe.py `95EFE6919DA14A8B`、
  plane_track.py `C01DBDF9A3FDF70C`、replay_server.py `22FA5F5849A9A11C`、replay.html `972253BC0CEFAD67`、
  replay_client.py `8AD1A03698FF9784`、deletion_list.py `BF93690E1DA9DA06`、apply_deletion.py `4EDA41B0F7EA1DA0`、
  test_plane_track.py `9945F7679A068D92`、README.md `54F9B7391295DDBA`。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（经 OpenCode skill 工具加载，
  本会话逐轮生效）。使用路径：先复用既有 `leveling.run_job`/`registration.js`/`core/lidar_candidates.py`/
  `human_replay` 现场代码，再标准库（http.server/urllib），最后才写本目录最小脚本；未新增依赖、未改既有文件。
- 命名核对：已读 `docs/sidequests/REVIEW.md`（v2 支线总表，最新条目 HFUS-RD-02）；现有 returns 为 `DET-xx`/`CL2-xx`/`HFUS-RD-xx`
  风格，`PLANE-01` 与证据目录 `2026-10-14_plane_track_r1` 无冲突，沿用工单给定 ID，未改 REVIEW.md（非本单授权范围）。
- 数据契约不一致（如实登记，工单已提示）：`docs/human_capture/README.md` §2 的示例仍是 16 B（`point_step_bytes: 16`），
  实际全部 41 段本机会话与板端 35 段均为 28 B（`x,y,z,intensity,ring,u2,timestamp`，stride 28）；本单代码按 28 B 断言，
  未改该 README。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| A03 背景不可用（工单已核实"10-10 空场整屋泄漏簇"） | 10-10 空场 `cap_20261010_175227` 的 auto 配平跨方法 offset 差 0.033 m > 0.03 m 一致性门 → `recommended=None`，既有 `registration.js` 在 `levelingBinding`（第 104 行 `report.recommended!=='tls'`）直接拒绝；且它与今天非同一次安装姿态（leveled pitch 25.98° vs 28.73°，ICP 相对 pitch 1.44°） | T3 空场差分入口、registration.js 的 source/reference 绑定、`04_BACKGROUND` 全部分支 | 选用 10-13 空场 `cap_20261013_131958`（既有 job 61cb6976，recommended=tls）重跑既有 `registration.js`；泄漏改距离判据（网格相位假象修复见下） | 不降 registration 门、不改 10-10 的记录，`03_REGISTRATION_175227_REFUSED` 保留 exit 1 原始日志 |
| A03 泄漏定量被体素相位假象污染（本轮自查发现） | 空场与目标帧在 0.10 m 网格里整体 ~5 cm 错相时，逐格精确比较会把对齐良好的点判成泄漏（配准后反而"更差"） | `04_BACKGROUND_v1_cell_exact_SUPERSEDED.json`（已改名留档，不删） | `background.py` 改为"目标点在空场 cell_m 网格 ±1 格内无空场点=泄漏"的打包 int64 键距离判据 | 保留 v1 文件作为被推翻记录；两版数字均入证 |
| A04 现候选层对小目标全漏 | `core/lidar_candidates.py` 默认 `min_cluster_points=25`（`perception.yaml` 同源），工单目标每帧仅 5–22 点 | `build_snapshot` 候选出口、T4 检测/跟踪 | 只改设置：`min_cluster_points=5`、`preferred=8`、`cluster_cell_m=0.3`、range 1–10 m、height −0.5–4.5 m、denoise 关（消融显示与开同结果）；`plane_track.py` 复用该候选层不改 core | core/生产配置零改动；25 点门槛的漏检数字一并报告（0/27） |
| A04/A05 跟踪门限不适用 | `perception.yaml` 的 `max_speed_m_s=2.5`/`gate_m=0.8` 对静止/慢速吊装物过宽松，对 3–10 m/s 目标（帧内 0.3–1.0 m 划痕）过紧 | `track()` 关联与丢失状态 | 基础门 0.35 m（实测 ±0.15 m 漂移）+ 划痕自适应 `1.2×streak+0.15`；丢失后不重新分配给远处簇 | 不用 perception.yaml 参数；首帧无划痕的跳变限制写进测试固化 |
| A07 未配平副本占用本机空间 | 7 段有已验证配平产物；但多数被在仓代码消费或板端已 purged（本机是最后一份） | `captures/remote/<sid>`、各消费者脚本 | 仅删"无在仓代码消费者 + 板端仍有 bag"的 2 段，先出清单再等用户确认（已确认） | 其余 5 段保留并在 `10_DELETION_CANDIDATES.json` 说明原因；leveled 产物与板端 bag 未动 |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `sidequests/plane_track/r01/{common,inventory,level_sessions,inspect_target,background,background_probe,plane_track,replay_server,replay_client,deletion_list,apply_deletion}.py`、`replay.html`、`test_plane_track.py`、`README.md` | 本单单据工具与自检 | 全新目录，未覆盖任何既有文件 | 见"本轮信息" |
| `captures/leveled/363473a9e2e64649994dca11b2b26929/`（164522）、`6d5809d5a87b462cad4023520868b9e6/`（175227）、`53bfb3ca7bdc44b3b04084da998d7c65/`（094302） | 既有 `leveling.run_job` 产物（auto，名义 pitch 26.0/roll 0.0/高 1.14 m） | 只新增 job 目录，不覆盖既有 6 个 job | report SHA 见 `02_LEVELING_*.json` |
| `docs/sidequests/evidence/2026-10-14_plane_track_r1/` | 本轮证据（01–12 号文件） | 全新目录 | — |
| `docs/sidequests/returns/PLANE-01.md` | 本回传 | 新建 | — |
| 删除 `captures/remote/cap_20261014_164522/`、`captures/remote/cap_20261013_094302/` | 用户确认后的未配平副本清理 | 已授权删除；前后清单/SHA 在 `11_DELETION_EXECUTED.json` | — |

输入输出/单位：全部长度为 m、显示系为配平产物 `ground_offline_display`（地面 z=0）；时间用源 `bag_time_sec`（秒）。
兼容性：分析脚本本机 Python 3.12 运行；未新增依赖（stdlib+NumPy；matplotlib 仅证据绘图，本机已装）。
未授权动作：无 commit/push/reset/checkout/clean；无板端写入/部署/采集/驱动/网络改动。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| A01 清点 | offline（本机文件 + 板端只读 API） | `python -B -W error inventory.py --out <ev> --name 01_INVENTORY_v2.json --markdown 01_INVENTORY.md` | PASS（exit 0；本地 41 段、板端 35 段、板端-only 0、本机-only 6 段 joint） | `01_INVENTORY*.json`、`01_INVENTORY.md` |
| A02 配平（3 段新 + 4 段复验） | offline（既有管线 `leveling.run_job`） | `python -B -W error level_sessions.py --out <ev> cap_20261014_164522 cap_20261010_175227 cap_20261013_094302`；`--verify-only` 4 段 | PASS（exit 0；3 段全部三法 valid、产物 5 项验证全 True；175227 `recommended=None` 是显式 FAIL 项=跨方法 offset 差 0.033 m>0.03 m） | `02_LEVELING_*.json`、`02_LEVELING_STDOUT.log` |
| A03 配准 + 泄漏 | offline（既有 `registration.js`） | `node pc_apps/human_replay/registration.js --source=cap_20261013_131958 --reference=cap_20261014_164522 --source-job=61cb6976… --reference-job=363473a9… --outdir=…`；`python -B -W error background.py|background_probe.py` | PASS（node exit 0，gate PASS，fit p50 9.1 mm/p90 31.6 mm，holdout p50 8.7 mm）；泄漏：配准后 343 点/帧=0.70%、最大簇 224 点（位移家具，距目标 4.75 m），未配准 131958=3004（6.1%）、未配准 175227=15146（30.8%），目标区 0 泄漏 | `03_REGISTRATION_131958_to_164522/{registration,diagnostics,provenance}.json`、`03_REGISTRATION_175227_REFUSED`（exit 1）、`04_BACKGROUND*.json/png` |
| A04 检测表 | offline（实拍 164522 + 合成） | `python -B -W error inspect_target.py …`；`python -B -W error plane_track.py --job 363473a9… --method tls` | PASS（27/27 命中；3/5/8 点门槛均 27/27，25 点门槛 0/27；每帧 8–23 点、R 6.38–6.62 m；可达距离 13.0/10.1/8.0/4.5 m@实测面积、7.5/5.8/4.6/2.6 m@玩具机面积）；目标语义 UNKNOWN（细长静止结构、离地 3.0 m、±0.15 m 抖动、无一致平移） | `05_TARGET_IDENTITY.json/png`、`06_TRACK_REAL.json/png` |
| A05 跟踪连续性 | offline（实拍/合成/回放分开） | 同上 + `--synthetic --name 07_TRACK_SYNTHETIC_v2.json`；`replay_server.py`/`replay_client.py` | PASS（实拍 27/27、丢 0、ID 跳变 0、表观最大步速 2.18 m/s 注明为簇心抖动；合成 0/3/5/10 m/s 各 30/30、丢 0、测速误差 ≤0.2%、划痕=v×0.103 s；回放 27/27、丢 0） | `06_TRACK_REAL.json`、`07_TRACK_SYNTHETIC_v2.json`、`08_REPLAY_10HZ.json` |
| A06 本机 10 Hz 回放 | offline（本机服务 + 真实 Chromium 页面） | `replay_server.py --port 8941 --start-delay 12` + `replay_client.py` + OpenCode 浏览器工具打开页面截图 | PASS（本机）：compute 中位 46.4/p95 61.2/max 63.2 ms，发布延迟中位 46.5/p95 61.9/max 63.5 ms，晚启动 0/27；客户端与页面各 24/27 见帧（3 次 10 Hz 采样跳格）；板端 NOT_RUN | `08_REPLAY_10HZ.json`、`08_REPLAY_BROWSER.json`、`08_REPLAY_PAGE.png` |
| （复用说明） | — | 未直接改 `real_fall/r04/server.py`：它硬绑定 r04 自己的 manifest/tracking 产物（如 `OUT/(sid+'_foreground.json')`），复用须改该文件=超范围；故按同构写了一个 stdlib 最小服务（只读 captures），页面用 2D canvas（不引 three.js 依赖） | — | `replay_server.py`、`replay.html` |
| A07 删除清单与执行 | offline（本机文件系统） | `deletion_list.py --write`；用户确认后 `apply_deletion.py` | PASS（exit 0；7 段候选清单 + 逐段消费者分析；确认后删 2 段：41→39；leveled job 与板端 bag 保留并复核） | `10_DELETION_CANDIDATES.json`、`11_DELETION_EXECUTED.json` |
| A08 回归 | offline | python 各套 + node 各套（命令与逐套结论见 `12_REGRESSION_SUMMARY.json`，原始日志 `12_reg_*.log`，附注 `12_REGRESSION_SUMMARY_NOTE.md`） | PASS（python：`human_fall_detection` Ran 504 OK、`human_capture` Ran 45 OK、`human_follow_calibration` Ran 2 OK、`console_test` Ran 7 OK、本单 `test_plane_track` Ran 10 OK；node：`human_fall` 18、`human_fall_preview` 55、`human_capture` 33、`human_replay_lib` 45（"all 45 tests passed"）、`panel` PASS O1/O5、`human_detect_lib` 11、`human_pipe_lib` 38、`console_html` 12，0 failed；无新依赖） | `12_reg_*.log`、`12_REGRESSION_SUMMARY.json`、`12_REGRESSION_SUMMARY_NOTE.md` |
| 本单自检 | offline | `python -B -W error -m unittest test_plane_track -v`（在 `sidequests/plane_track/r01`） | PASS（10 tests OK，含首帧跳变限制的固化用例） | `12_reg_py_plane_track.log` |

回归范围/冻结资产对照：未修改 `src/`、`webui/`、`pc_apps/`、`config/`、既有证据与 GT；只读消费 `captures/`（除用户确认的 2 段删除）；
新产物只落在 `sidequests/plane_track/`、`docs/sidequests/evidence/2026-10-14_plane_track_r1/`、`captures/leveled/<新 job>/`。

## 未闭合与限制

- T1"用哪段/缺哪段"：**用** `cap_20261013_131958`（10-13 空场，配准 PASS）+ `cap_20261014_164522`（本单小目标段）；
  **缺**（见下方最小录制清单）同安装位置同时段空场、以及小飞机长段；其余 29 段本机会话本轮未配平、未删。
- 未满足/未跑的验收：板端部署与板端回放 NOT_RUN（本单明确不做）；设备/物理/独审 NOT_RUN；"小飞机"语义身份 UNKNOWN
  （无相机证据；几何为细长静止吊装物，未见飞行运动）。
- 复现条件与解除条件：目标语义需用户/相机确认；3–10 m/s 实拍未验证（合成已验证），需新录小飞机长段；
  10-10 空场如需复用，需先按 `captures/leveled/README_REGENERATION.md` 重生成器用 `--config` 复核或重录同位置空场。
- 合成 v1 被取代：`07_TRACK_SYNTHETIC.json`（v1）用直线运动，目标在 3 s 内飞出 10 m range 门导致后段"漏检"是几何
  假象；`07_TRACK_SYNTHETIC_v2.json` 改为 6 m 等距圆弧并保留 v1 作为被推翻记录。
- 契约允许的算法/证据限制：跟踪门在首帧无划痕时不能跟上 >0.35 m 的跳变（已测试固化）；"划痕"长度对细长静止物与
  自身长度混淆（实拍已注明）；表观速度对细长静止物的簇心抖动敏感；泄漏判据为 0.05 m 网格 ±1 格的近似距离。
- 范围外新需求及后续建议（缺的段与最小录制清单，等授权才录）：
  1) 同安装位置同场空场 ≥30 s（同一安装姿态、无人、家具不动），用于替代 10-13 空场（10-13 与今天相比有家具位移，
     泄漏 0.70% 主要来自它）；
  2) 小飞机长段 ≥60 s（同一空场之后录；目标在 1–10 m 半径内做静止/慢速/3–10 m/s 运动，每段标注大致速度），
     用于验证划痕-速度特征与检出率随距离的下降；
  3) 可选：已知尺寸标定物段（标定折合面积，替代 0.0117 m² 假设）。
- 设备/物理未跑项：板端服务/驱动/网络全未触碰；10-10 空场被既有配准门拒绝是既有门行为，不是本单新结论。
- 运维副作用（如实登记）：T5 期间我在 8941–8944 起过临时回放服务用于测量。其中 8944 与工作区里他人的
  pointset/r01 服务端口冲突（同一端口可被 SO_REUSEADDR 双绑，导致我 8944 上的请求曾命中对方页面）；
  我已在收尾时停止了自己起的全部临时服务（8941/8942/8943 关闭、8944 上的我的进程 PID 已杀），
  对方服务复核仍可访问（`http://[::1]:8944/` 200、`8954` 200），未对其做任何写入。
- 记录冲突（如实登记）：`captures/leveled/README_REGENERATION.md` 把 `captures/remote/` 声明为 single source of truth；
  本单按用户确认删除了其中 2 段的未配平副本（该 2 段板端仍有 bag，可重新拉取），其余 29 段未配平未删。
  该 README 的"仅保留 6 个 job"清单也已过时：本轮新增 3 个 job（共 9 个），未改该 README（非本单授权范围）。

## 交给Codex独立复审

- 现行验收表与本轮变更记录：`docs/sidequests/evidence/2026-10-14_plane_track_r1/00_ACCEPTANCE_A01_A08.md`（v1，SHA 见上）。
- 根因诊断/完整入口检查证据：`04_BACKGROUND_v1_cell_exact_SUPERSEDED.json`（被推翻的判据）、`03_REGISTRATION_175227_REFUSED`
  （既有门拒绝原始日志）、`12_reg_py_plane_track.log`（跟踪门/首帧限制用例）。
- 源码差异与 SHA 证据：`sidequests/plane_track/r01/`（全量 SHA 见"本轮信息"）；未改任何既有源码/配置。
- 原始日志索引：`02_LEVELING_STDOUT.log`、`12_reg_*.log`、`12_REGRESSION_SUMMARY.json`；板端只读 API 响应在 `01_INVENTORY_v2.json`。
- 当前工单下一步：若用户授权，按"未闭合"里的最小录制清单补录空场/小飞机长段；A07 已按用户确认执行完毕，无待批动作。
