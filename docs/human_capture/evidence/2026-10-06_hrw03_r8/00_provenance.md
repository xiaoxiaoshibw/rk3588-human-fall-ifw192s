# 00 · W03-R3.6 Provenance / 输入冻结（round r8）

- 日期：2026-10-06（Asia/Shanghai）；writer：OpenCode（DeepSeek v4.1 Flash）。
- ponytail 使用路径：已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）；实现路径 = 阶梯 rung 2/3（逐行复用 r7 归因工具 + 生产纯函数 `human_pipe_lib.js`；零新依赖、单脚本、无框架）。
- 性质：**离线只读诊断 / 因果实验（Registration Causality）**。不修改任何 production 文件；不接 production；不采集/部署/commit/联网。
- 本轮 ID：W03-R3.6（承 R3.5/`06_summary.md` §6 建议 #1；用户 2026-10-06 工单）。证据目录 = 本目录（`2026-10-06_hrw03_r8/`），不覆盖 r6/r7 及更早轮次。
- 前置文档：`../2026-10-06_hrw03_r7/`（R3.5 归因全量）、`../2026-10-06_hrw03_r6/`（审计/设计四件套）、`../../W03_R3_ACCEPTANCE.md` §0（console leveled pipeline 唯一权威口径）。

## 1. 输入冻结（本轮开测前实测 SHA256；raw = 现行字节；canonical = CRLF→LF 归一，与 R3.1～r7 记录口径一致）

| 文件 | raw SHA256 | canonical SHA256 | mtime (UTC) |
|---|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `f580778c366767529d74d17af8ff2ecba4a22728dcd9fc06743e74d510a4dc83` | `5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4` | 2026-10-06T13:15:11.329Z |
| `pc_apps/human_replay/human_replay_lib.js` | `bbcbc547f79da60d0e6f915eeccb403997b1c192a3a37ba00e6d3c4d367cf1cc` | `6974c59b03e96fec96bb6aa3db6099328b5060205ea8d8b37c476ea0512e5a7e` | 2026-10-04T11:38:09.328Z |
| `pc_apps/human_replay/human_pipe_lib.test.js` | `dfd8a4c49cd27a7192161a88e4c097f052225674a4137eaea3e6c6f399ba9449` | `0dc981540e0a51d85e634c1a95284d1e19c065e80ff9bf379a991d7edf349cc5` | 2026-10-06T13:15:11.347Z |
| `pc_apps/human_replay/human_detect.js` | `45d1305577e53dee79887b454e291c3904ae753c07f69984269310e2b6ad6307` | `555685b5899e196779f403a8a2a26b24670e3eaa8bb42347041f9857d7e250c0` | 2026-10-06T13:15:11.307Z |
| `pc_apps/human_replay/human_detect.html` | `9d89589d2a6e5e3f3fa7e0972fe7775cf6b9df40641cf9fbb7dab73d19cb5a6f` | `62bf91268460353fabaf5d936949f830a54e680fc4e7f586c1e65961181cad37` | 2026-10-06T13:15:11.293Z |
| `pc_apps/human_replay/leveling.py` | `3c3a88196cfd9851e2cadac76690a8343d6c949c4c7f467950495c32e6b54a6e` | — | 2026-10-05T12:57:41.110Z |
| `pc_apps/human_replay/leveling_quality.py` | `4cbafd0c1ab64f7efabf1a3740b26983154105c847a151bdbb6a09be2f33c04e` | — | 2026-10-05T04:05:00.320Z |

- 5 个 JS 文件 raw/canonical 与 r6/r7/CL-01 记录**逐位一致**；mtime 全部停留在 `2026-10-06T13:15:11Z`（CL-01 登记的外部 EOL 批量改写事件时刻）→ 无更新的改写，production 内容未变。
- `leveling.py` / `leveling_quality.py` 为首次入册（R3.6 registration 链审计需要）；此前轮次只引用未记录 SHA。

## 2. 会话输入（只读；与 r6/r7/R3.1 记录逐位一致）

| 会话 | meta.json SHA256 | points.bin SHA256 | 帧数 | 角色 |
|---|---|---|---|---|
| `cap_20261002_223757` | `71915d5181b8fc409d83a8e1650671801d2d50cf09ef4a3832d43b51ec3f4ca8` | `8afb660b7bf0631462d4cde6f82bd89884b2e83acea1da25c07316c87b5fbb37` | 165 | current（所有 `f<n>` = 本会话 0-based frame_index） |
| `cap_20261004_203349` | `c3b55d1e11ed8a043bd3645af7ed07e920024c05f3cb48b15d523405edd38392` | `2ed3fc60d99b3a2f42e0951835ad847fae2f490859e487b167fbccb1b5f10323` | 102 | reference（R3.1 空场候选 artifact 源） |

## 3. Transforms（只读；job 选择规则 = `report.recommended=="tls"` 最新）

| 会话 | job | transform_id | tls/transform.json SHA256 | report.json SHA256 |
|---|---|---|---|---|
| current | `6bc5aabf8f0041ffa961758b4e84da94` | `de973fdbbec95379dfce52063cc8bdf473c9bbbf146a05a58452ec8f441b9a1f` | `7f1cd4f734f8d14e6da9bfc97d0e24d5a213a9fe10d1cafde1048a8df118a7b2` | `5b8854eb81295f8f69cf3625d3776279d6076ac4fc1dc102de55fcc4a2dc18e0` |
| reference | `c9712acad48c4fb7a78cb119c08d4cdb` | `5d8fd5c032f2b8131e5d5ef2027e0560605e9a7ba83376c55528b9c8edff6f03` | `c845929272d350faa35deb0c1595e93cda46a9562e23aa9927476029cb46c194` | `e7455741fc74a1fb24c9e5d5d21dab0eda4f927428088f76057799e001d55a15` |

- 与 r6/r7 登记的 job/transform_id 一致；两 job `recommended=="tls"`、manifest 内 transform.json SHA 校验一致（本轮实测）。
- 两 transform：`scope=offline_display_only`、`physical_verified=false`、`extrinsics_verified=false`、`runtime_eligible=false`（`leveling.py` L195–203）。

## 4. git / 工作树基线（本轮开测前）

- git HEAD = `cfbb80c57508be1a0435fdb92260f698dc763934`（较 r6/r7 记录的 `d8efabaf…` 前进；新增 4 个提交 = 仓库卫生/证据归档/console 旁路/ROI probe，均不触碰 human_replay 管线 —— 相关文件 SHA 已逐位核对）。
- 工作树：`git status --porcelain` 仅 1 项 = `?? docs/human_capture/evidence/2026-10-06_hrw03_r7/`（上一轮 evidence 未跟踪）。本轮未做任何 git 操作；r8 目录新增后同样保持未跟踪。
- 生产文件 mtime/SHA 见 §1；本轮零写入生产。

## 5. 既有 referenced artifacts（只读取用）

- R3.5 归因全量：`../2026-10-06_hrw03_r7/02_attribution_results.json`（digest `4b89a044…`）、`03_attribution_points.csv`（SHA `08691659…`）、`04_attribution_voxels.csv`（SHA `5662d18f…`）。
- R3.5 工具：`../2026-10-06_hrw03_r7/10_r35_attribution.js`（本工具同源复制其中加载/归因/聚合段）。
- R3.2 ICP 存值：`roll 1.7476 / pitch −0.2818 / yaw −2.3924 / t [0.0182, 0.031, 0.0012]`（r5/11_r33_ab.js 与 r7 CHECK 逐位一致）。

## 6. 本轮产物清单（完成后回填）

| 文件 | 内容 |
|---|---|
| `00_provenance.md` | 本文件 |
| `01_registration_chain_audit.md` | 真实 production registration 链只读审计（15 问逐条） |
| `02_experiment_design.md` | A/B/C 定义、变量控制、C 构造与验证方案、判定规则 |
| `_recon_c_probe.js/.log` | 预研探针 v1（C 选型，point-to-point 多初值） |
| `_recon_c2_probe.js/.log` | 预研探针 v2（point-to-plane + held-out，C 定型依据） |
| `10_r36_registration.js` | R3.6 主工具（离线只读；复用 r7 归因 + 新增 C） |
| `03_results.json` | A/B/C 全 165 帧聚合 + 逐帧 + checks + SHA（digest `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357`；run1==run2） |
| `04_point_attribution.csv` | focal/control 帧逐 residual 点 A/B/C 链路（含 registration shell；SHA `d0ac5be9…`） |
| `04b_voxel_transitions.csv` | 全帧逐体素各条件主导 bucket 与吸收/recover 计数（SHA `de6c2503…`） |
| `_r36_analyze.js` / `.log` | 结果提取分析脚本与日志（05/06 数字来源） |
| `05_frame_analysis.md` | 关键帧分析（WD01/WD02/f55/f155/f160/clean controls） |
| `06_summary.md` | 结论 + 因果判定 + 建议 + 边界 |
| `11_run1_stdout.log` / `12_run2_stdout.log` / `13_tool_run.log` | 运行与确定性日志 |

## 7. 边界（本轮明确不做）

- 不改任何 production 文件/阈值/接口；不接 reference 进生产；不重打包 console；不部署；不 commit。
- 不调 matcher（radius/XY/Z/voxel/AABB/morphology/connectivity 全冻结）；不用 matcher 扩张掩盖 registration 问题。
- 不修改输入数据（session/reference/leveling artifacts 前后 SHA 一致，工具内断言）。
- 不重开 R3.0–R3.5 / CL-01 结论；`POST_FILTER_ERROR` 不碰。
- 所有 A/B/C 之外的 pipeline 变量与 R3.5 逐字一致（见 `02_experiment_design.md` §3）。
