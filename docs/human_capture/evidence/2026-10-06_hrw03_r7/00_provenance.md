# 00 · W03-R3.5 Step-0 Provenance / 输入冻结（round r7）

- 日期：2026-10-06（Asia/Shanghai）；writer：OpenCode（DeepSeek v4.1 Flash）。
- ponytail 使用路径：已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）；实现路径 = 阶梯 rung 2/3（复用生产纯函数 `human_pipe_lib.js` + r4/r5 既有 shadow 代码逐行复用；零新依赖、单脚本、无框架）。
- 性质：**离线只读诊断（Step 0 = Residual Attribution Tool）**。未实现任何 matcher 变体（B/C/D/E 全部未做）；未接 production；未采集/部署/commit；未联网。
- 本轮 ID：W03-R3.5（承接 r6 §0 对账建议）；证据目录 = 本目录（`2026-10-06_hrw03_r7/`），不覆盖 r6 及更早轮次。
- 依据文档（r6 四件套）：`../2026-10-06_hrw03_r6/00_audit.md`～`03_shadow_ab_plan.md`；验收口径：`docs/human_capture/W03_R3_ACCEPTANCE.md` §0（console leveled pipeline 唯一权威口径）。

## 1. 本轮执行内容（可复现）

| # | 命令（在仓库根执行） | 产物 |
|---|---|---|
| run1 | `node docs/human_capture/evidence/2026-10-06_hrw03_r7/10_r35_attribution.js` | `02_attribution_results.json`、`03_attribution_points.csv`、`04_attribution_voxels.csv`、`11_tool_run.log`、stdout `12_run1_stdout.log` |
| run2 | 同 run1 + `--outdir=<临时目录>` | 同三件产物（仅用于确定性比对，未入本目录）、stdout `13_run2_stdout.log` |

- node `v24.14.0`（Windows）；run1 用时 24.9 s、run2 同量级（纯计算离线，非板端口径）。
- 工具：`10_r35_attribution.js`（62 KB，单文件，零三方依赖；只读文件输入，只写本目录）。
- 归因账号：技术上复用 `PL.build_static_map / build_reference_map / extract_foreground / cleanup_isolated_fg / cluster_voxels / cluster_features / key_vox` + r4/r5 的 TLS/ICP/扫描实现（同源复制），**未改动任何被复用文件**。

## 2. 源码 SHA（raw = 现行字节；canonical = CRLF→LF 归一，与 R3.1～CL-01 记录口径一致）

| 文件 | raw SHA256 | canonical SHA256 |
|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `f580778c366767529d74d17af8ff2ecba4a22728dcd9fc06743e74d510a4dc83` | `5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4` |
| `pc_apps/human_replay/human_replay_lib.js`（载入层，本轮新增引用） | `bbcbc547f79da60d0e6f915eeccb403997b1c192a3a37ba00e6d3c4d367cf1cc` | `6974c59b03e96fec96bb6aa3db6099328b5060205ea8d8b37c476ea0512e5a7e` |
| `pc_apps/human_replay/human_pipe_lib.test.js` | `dfd8a4c49cd27a7192161a88e4c097f052225674a4137eaea3e6c6f399ba9449` | `0dc981540e0a51d85e634c1a95284d1e19c065e80ff9bf379a991d7edf349cc5` |

- `human_pipe_lib.js` canonical == r6/CL-01/R3.1–R3.3 记录的基线内容（逐位一致）→ 归因所测代码即既定冻结版本。
- **外部 EOL 改写事件（已登记）**：上述文件（+`human_detect.js` / `human_detect.html`）mtime = `2026-10-06T13:15:11Z`（21:15:11 +08:00），与 CL-01 登记的批量改写一致；截至本轮**无更新的改写**（mtime 未再变）。按工单规则：只记录、不回改。
- 工具运行期再次校验（`inputs_unchanged`）：run 前后 7 个关键输入 SHA 全等 → **PASS**。

## 3. 会话输入（只读；与 r6/CL-01 记录逐位一致）

| 会话 | meta.json SHA256 | points.bin SHA256 | 帧数 | 角色 |
|---|---|---|---|---|
| `cap_20261002_223757` | `71915d5181b8fc409d83a8e1650671801d2d50cf09ef4a3832d43b51ec3f4ca8` | `8afb660b7bf0631462d4cde6f82bd89884b2e83acea1da25c07316c87b5fbb37` | 165 | current（所有帧号 f0–f164 均指此会话的**0-based frame_index**） |
| `cap_20261004_203349` | `c3b55d1e11ed8a043bd3645af7ed07e920024c05f3cb48b15d523405edd38392` | `2ed3fc60d99b3a2f42e0951835ad847fae2f490859e487b167fbccb1b5f10323` | 102 | reference（R3.1 候选空场 artifact 源） |

- 帧号歧义处理：本目录所有 `f<n>` = `session_id=cap_20261002_223757` 的 `frame_index=n`（CSV 同时给 `frame_seq`，f55 → seq 176073）。除明确标注外，无跨会话同号帧。

## 4. Transforms / git / 工作树

- current tls：job `6bc5aabf8f0041ffa961758b4e84da94`，transform_id `de973fdbbec95379dfce52063cc8bdf473c9bbbf146a05a58452ec8f441b9a1f`；reference tls：job `c9712acad48c4fb7a78cb119c08d4cdb`，transform_id `5d8fd5c032f2b8131e5d5ef2027e0560605e9a7ba83376c55528b9c8edff6f03`（与 r6/CL-01 记录一致；选择规则 = 各 sid 最新 `recommended=="tls"` job）。
- git HEAD `d8efabaf1201847c960e5f522aaeb6e7eee049b4`（与 r6 相同；无新提交）。
- 工作树：既有未提交改动（R2.6b/R3.1 production 改动 + 与本工单无关的 console/webui 修改）**保持原样**，本轮未触碰；本轮唯一新增未跟踪目录 = `docs/human_capture/evidence/2026-10-06_hrw03_r7/`。
- 生产文件 mtime 全部停留在 `2026-10-06T13:15:11Z`（外部改写事件时刻）→ 本轮零写入生产。

## 5. 冻结参数（全部使用现行值，不改）

- `bg_match_radius=0.12`；邻域 3×3×3；voxel XY 0.15 / Z 0.12；在线 `bg_hit_min_pts=2`、`occ_strong=0.85`、`occ_supported=0.65`、`jitter=0.05`、`neighbor=2`；参考图 `hit_min=1`、`occ_min=0.5`（v1 候选）；工作空间 z∈[0.10, 2.50]；denoise 距离窗 [0.35, 25]（在 TLS 之后应用，与 console 口径一致——本会话 leveled 数据 0 个点被该窗剔除，见 `01_baseline_equivalence.md` §2）。
- registration 三档 `{none, tls, icp}`：none = 不做跨会话配准（各会话仅自家 TLS）；tls = `R_direct=R_cur·R_refᵀ` 的逆（R3.2 同款，无平移）；icp = R3.2 固定解复跑（仅作**实验条件**，不是"真实安装偏差"；roll↔yaw 非唯一已登记）。

## 6. 文件清单（本目录）

| 文件 | 内容 |
|---|---|
| `00_provenance.md` | 本文件 |
| `01_baseline_equivalence.md` | G0 等价 / 守恒 / 确定性 / 跨轮复现 |
| `02_attribution_results.json` | 全 165 帧聚合 + 分组 + checks + SHA（digest `4b89a044…`，见 01 §4） |
| `03_attribution_points.csv` | 18 个 focal/control 帧逐 residual 点归因（~82k 行，51 列） |
| `04_attribution_voxels.csv` | 全帧逐（帧，3D 体素）residual 归因（227,188 行） |
| `05_frame_analysis.md` | GQ1–GQ6 + 逐帧分析（含 f55 族 proxy 与站点混淆发现） |
| `06_summary.md` | 结论、K1–K6 判定、下一步建议（仅建议）、边界 |
| `10_r35_attribution.js` | 归因工具源码（离线只读） |
| `11_tool_run.log` | run1 运行日志（工具自写） |
| `12_run1_stdout.log` / `13_run2_stdout.log` | 两次运行 stdout（确定性比对） |

## 7. 边界（本轮明确不做）

- 不实现 B（XY/Z 解耦）、C（AABB 标定）、D（fusion/occ 扫描）、E（组装/完整管线门）；工单 §12 全部保持 DO NOT IMPLEMENT。
- 不改任何 production 文件/阈值/接口；不接 reference 进生产；不重打包 console；不部署；不 commit。
- 不重开 R3.0–R3.3 / CL-01 结论；`POST_FILTER_ERROR`（显示层）仍属独立工单，本轮不碰。
- 所有 reason 标签、proxy 分类、bucket 仅为 **shadow-only 诊断字段**，不进入 production contract。
