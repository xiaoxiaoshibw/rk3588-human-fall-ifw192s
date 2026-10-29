# 人体系统连续开发

2026-10-18 用户明确改为整体项目开发。Codex 为唯一写入者，连续修复、整合、运行和验证，不再逐缺陷派工或要求用户另开工单。

当前开发入口：`sidequests/hfus_tcms_02/realdev/current/`。控制台“人体开发回放”连接这个入口；r01–r12 及旧证据保留为只读对照。

策略：算法 RESEARCH，入口整合 ENGINEERING。实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）及
`scientific-toolkit-skill/SKILL.md`。研究完整性优先；不平滑数字、不放宽旧门、不伪造人体/连接/跌倒标签。

## 当前状态（2026-10-18 第 3 轮，工程可用版）

- 绑定运行：`docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/run_03`
  （386 帧，`cap_20261018_110029`；几何与 run_02 相同，新增因果跟踪与跌倒状态机）。
- 默认 `partition` + ground，可切 RAW；配平 pitch 25.3607°、roll -0.8368°、地面 z=0。
- 已接入：单一目标因果锁定（`t0001`）+ 跌倒状态机（upright/unknown/low/suspected，`confirmed` 关闭）。
- 证据：`docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/verify_03/`（`NOTES.md` 为总表）。
- 服务：`python -B -W error sidequests/hfus_tcms_02/realdev/current/server.py --port 8934`（运行中）。

## 本轮实际进展

1. 跟踪 + 跌倒状态接入（新 `project_fall.py`，复用冻结 `core/tracking|features|fall_state`）：
   386 帧单一 `t0001`、locked 267 / occluded 15 / unselected 104；upright 258 / unknown 127 /
   low_posture 1；suspected 0、confirmed 0、事件 0；`confirmed_enabled=false`（`FALL_STATE.json`）。
   预测位置永不作为观测/跌倒证据；站姿基线绑定 track/epoch/selection/generation/地面变换。
2. 真实序列回归：`test_coordinates` 2/2、`test_regions` 3/3、`test_fall` 4/4、
   `tools/ai_gt/test_point_membership` 7/7、console 8/8、console_html 21/21，全部 exit 0（`TESTS.json`）。
3. API/源码/页面一致：386 帧 × 3 变体 ground↔raw 只差同一刚体变换（反投影 8.9e-16 m），
   bbox/节点/支撑/标定/track/fall 不随坐标切换改变；活服务与 Store 一致；Chrome headless 实页
   0 控制台错误，点数/节点/bbox/`3 / 12`/`t0001` 与 API 全等（`API_CHAIN.json`、`HTTP_CHECK.json`、
   `PAGE_CHECK.json` + 341/183 截图）。
4. “标定为 0”：仍是逐帧状态机（341 帧 3/12、242 帧 10/12、183 帧 0/12）。两条短分支边
   `UPPER_A|OUTER_A`（0.073 m）、`UPPER_B|OUTER_B`（0.138 m）从未达标；服务端按会话统计
   `ever_calibrated` 并显式标 `short_sparse`，页面说明；冻结门 15 样本/5%/2 cm 未改。
5. 前景/背景/目标/支撑边界重建 386 帧 0 失配；前景 614,822 点、地下 0.0、>2 m 1.03%；
   无点级 GT，purity/recall 仍 UNKNOWN。
6. 点级 GT 通道：新增 `tools/ai_gt/point_membership.py`（schema `hf_point_membership_v1`，
   validate/audit/score/selfcheck，7/7 测试）；预测行缺标签 => INCOMPLETE + null，不伪造 FP。
   当前无真实标签，未产出任何指标。
7. 冻结基线可复现：FG_NEW2 SHA 一致、20 绑定 match、9 关键帧误差 0.0；当前管线重跑
   orientation/partition 与 run_03 逐字节相同（`cc954013…`、`4731b814…`）。
8. 控制台：`--check-real-fall` 源码态/打包 exe 均 exit 0，命中 run_03（`t0001`/upright/
   confirmed_enabled=false）；`--check-startup` 的 pointset 段缺数据 NOT_RUN，整体 exit 1。

## 本轮修改文件

- `sidequests/hfus_tcms_02/realdev/current/project_fall.py`（新）：跟踪/跌倒适配器。
- `sidequests/hfus_tcms_02/realdev/current/run.py`：加载地面变换，逐帧写入 track/fall/candidate，RUN.json 绑定。
- `sidequests/hfus_tcms_02/realdev/current/server.py`：暴露 track/fall/state/height、会话级 `ever_calibrated`/`short_sparse`；校验 `project_fall.py`。
- `sidequests/hfus_tcms_02/realdev/current/app.js`、`index.html`：显示跟踪、跌倒状态、短边说明；更新提示。
- `sidequests/hfus_tcms_02/realdev/current/test_fall.py`（新）：4 项回归。
- `sidequests/hfus_tcms_02/realdev/current/LATEST.json`：指向 run_03 及新哈希。
- `tools/ai_gt/point_membership.py`、`test_point_membership.py`（新）：点级 GT 通道。
- `pc_apps/console/console_gui.py`：`_probe_real_fall` 改为当前管线契约（track/fall/confirmed 关闭）。
- `pc_apps/console/dist/Console.exe`：重建。
- `docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/run_03/*`、`verify_03/*`：本轮运行与证据。

未改冻结门、冻结源码、旧 GT、旧证据、原始数据；未做 Git 写、部署采集训练、模型下载或 HR-09。

## 未解决 / 阻塞（工程可用版的边界）

1. 点级 GT 缺失：前景 purity/recall、跌倒 TP/FP 均 UNKNOWN；GT 通道已就绪，等人工标注或授权 AI-GT。
2. 无带 GT 的跌倒会话：`confirmed` 永久关闭，交付上限 `suspected`。
3. 两条短分支边在冻结门下不可认证：需新注册区域/测量变体（RESEARCH）。
4. `--check-startup` 的 pointset 数据缺失（`2026-10-15_hfus_learn_dev_r2`），非管线回归。
5. 打包 exe 依赖 `dist/console_passthrough.ini`；`LiDAR_Console.zip` 未重建。

## 历史

- 已修复 PCA 横向基向量正负号造成的 A/B 换边（上一有效帧选符号、不平滑、不跨拒绝帧沿用身份）。
- 上侧/外侧改为互不重叠分区，保留方向修复版、分区版与冻结版对照。
- GroundCoordinates 坐标链：全场、前景、节点、包围框、支撑点同一地面变换。
- 配平 `leveling_02`：俯仰 25.36°、横滚 -0.84°、地面 z=0，未降低原门槛。
- 基线现象保留：轻晃段 OUTER_A 最大相邻位移约 207 mm、有效帧 13/14；保持段 145/151 帧、最大相邻位移约 85 mm。

数据、旧 GT、冻结源码/配置/模型/旧证据不写；无 Git 写、部署采集训练、模型下载或 HR-09。
