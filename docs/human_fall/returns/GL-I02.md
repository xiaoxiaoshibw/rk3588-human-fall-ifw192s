# GL-I02 回传（工作流程v2）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-I02 / R1 PHASE TWO / OpenCode Go `opencode-go/deepseek-v4.1-flash`（default DB，无隔离库）/ 2026-10-03（Asia/Shanghai）
- 验收表路径 / 版本 / SHA（提交时记录）：`docs/human_fall/GLI02_ACCEPTANCE.md` / v1 / `b8e172829d3a84c7da2ec346d4531f986ba83e7ce54131c41b9e592dcd5726bb`（随共享工作树未 commit）
- 执行方式 / 实际会话与模型：本机 Windows，离线纯 Python（无 ROS/板端/网络/采集）；模型同上；skill `ponytail` full
- 状态：SUBMITTED（软件自验；不自行宣布整单 ACCEPTED；设备/物理/真实 fit 分层报告）
- 起始 branch/HEAD：`master` / `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；工作树故意 dirty（`src/human_fall_detection/` 整包未跟踪为本项目常态）
- 范围内用户差异：本单新增/改动仅白名单 (a)–(d) 与本单证据目录；未动任何用户既有差异
- 设计门：`evidence/2026-10-03_gl_i02_r1/04_DESIGN_REVIEW.md`（SHA `c8cabc36…`）PASS 后实施
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（SHA `40519c9eb29bcbfe225bdf1c3566ecea7916a958f4a65c9ffae2979743cd67e2`；强度 **full**）

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| J01/N01 | 既有 adapted CLI 硬编码 `status.ground="valid"`，不满足 N01 字面；直接改冻结 `calibrate_sensors.py` 越界 | candidate 标定入口 | 新 thin wrapper 直接编排：`load_adapted`→`gate_selection`→`fit_ground_plane_constrained`→`build_geometry_calibration(statuses={"ground":"candidate"})` | 冻结 ground/calibration 数学与 adapted CLI 语义不变 |
| J04/N02/N07 | 地面选择需人工预固定，缺先验易被自动 fallback 选地面 | draft/升级链 | wrapper 读 draft：缺 fit selector/frame_group/<3 validation/up_axis/height → exit 2 无 artifact；`--emit-draft` 独占落 pending draft | 无自动地面选择，draft 命名空间独立 |
| J02/J06 | 真实 capture 只读、写点须落本单命名空间 | 文件副作用 | 仅 `prepare_npz`（命名空间 adapted NPZ）、`save_exclusive_json`（artifact/draft）三处写点 | `captures/remote/` 零写；GL-I01 四文件 SHA 不变 |
| J03/N04 | synthetic 与真实易混用 | 来源标注 | `--source-kind` 显式：`input.source`/`input.synthetic` 标签 + 独立输出命名空间 | 真实/合成同走 strict adapted route |
| J05/N06 | 非 adapted 输入可能静默跌入 legacy 或复制受限路径 | wrapper 输入入口 | `classify_npz=="legacy"` 即 exit 2；不复制 ROI/bounds，不调用 `region_indices`/`select_group_region` | 既有 `calibrate_sensors.py` legacy 路由不变 |
| 审计项 | 同名 artifact 覆盖、draft 覆盖、非有限/缺字段 | 独占写与先验 | `save_exclusive_json` `os.link`；缺失前置校验 | 旧件保留 |

实现前核查同类调用者：`build_input_info`/`gate_selection`/`fit_ground_plane_constrained`/`build_geometry_calibration` 均已存在于 GL-I01 R1/core，wrapper 只编排，无新语义。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `src/human_fall_detection/scripts/evaluate_gli02_candidate.py` | 新增唯一生产文件：thin candidate 评估 wrapper（只编排既有公开 API） | 新增，非既有文件改动 | `4a4fd0c733cdd608b42c3a11ef926b8c2041a795b1dbdfde3ef826542cad9a3a` |
| `src/human_fall_detection/tests/test_gli02_candidate.py` | 新增回归 8 项（T1–T8） | 新增 | `0dad5771f1ac68a175c2075ffe8f8a49e64b50dfce104fc62adf6d499206a9b0` |
| `docs/human_fall/GLI02_CANDIDATE_PLAN.md` | 阶段二实施记录 | 文档新增 | `536b4f303a57d144d8a35564d2f4cfcad1b950aad3368e7e7d107d39447a0922` |
| `docs/human_fall/evidence/2026-10-03_gl_i02_r1/07…14_*` | 本轮自验证据（脚本/日志/SHA） | 新路径，续接 00–06 | 见 `14_new_files_sha.txt` |
| `docs/human_fall/returns/GL-I02.md` | 本回传 | 新增 | — |

未 commit/push/reset/checkout/clean；未动 driver/webui/`captures/remote/`/config/部署/模型/DB/全局。冻结 `ground.py`/`calibration.py`/`capture_input.py`/`prepare_capture_input.py`/`calibrate_sensors.py`/`test_gli01_capture_input.py` 与真实 capture 逐项 SHA 不变（见回归）。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| J01 | synthetic（真实 fit 未跑） | wrapper `--capture-dir … --emit-draft`→填 draft→candidate | **PASS（软件，synthetic，exit 0）**；真实 fit **NOT_RUN**（设计门判定人工决断前不 fit） | `07_synthetic_candidate_check.txt`（14/14）；artifact `07_synthetic/candidate.json` |
| J02 | offline + 真实 163621 只读 | wrapper prepare/reload，后重算 capture SHA | **PASS**：meta/bin SHA 前后一致、目录无新文件 | `08_real_readonly_reload.txt`（12/12）、`09_negative_and_sha_check.txt` |
| J03 | synthetic | `--source-kind` 标签与命名空间 | **PASS**：`input.source=synthetic_fixture`/`input.synthetic=true`；真实 label `capture_export` | `07…txt`、`12_gli02_new_tests.txt` T4 |
| J04 | synthetic | draft 记录 + 缺省拒绝 | **PASS**：draft 含 up_axis/height/fit_region/validation_regions 且 `pending_human_review`/`default_refusal`；缺项 exit 2 无 artifact | `07…txt`、`09…txt`、T2/T6 |
| J05 | synthetic | wrapper 只调公开 API；非 adapted/损坏拒绝 | **PASS**：全回归 407 + GL-I01 62 + Codex 24；legacy/损坏 exit 2 | `09…txt`、`13_full_regression.txt`、`10_gli01_codex_probes.txt` |
| J06 | offline | 白名单 diff + SHA 对照 | **PASS**：仅新增 1 生产文件；GL-I01 四文件 SHA 与诊断 §1 一致 | `14_new_files_sha.txt`、`09…txt` |
| B01 | source 证据 | bag2session 未持久化 width/height/original_count | **BLOCKED**（维持，不伪造原袋行索引） | 诊断 §6 |
| D01 | 设备/物理/性能/GL05/部署/采集/网络 | 未启动 | **NOT_RUN** | — |
| D02 | GL04 真实 DPR/正式页/浏览器 | 不属本单 | **NOT_RUN** | — |
| N01 | synthetic candidate；真实 reload | wrapper 全链 | **PASS**（synthetic，exit 0）；真实 candidate fit NOT_RUN | `07…txt` |
| N02 | synthetic | 缺 fit/frame_group/<3 validation/up_axis/height | **PASS**：exit 2，无 artifact，无 fallback | T2、`09…txt` |
| N03 | synthetic | 同名 artifact 已存在 | **PASS**：exit 2，旧件字节保留 | T3、`09…txt` |
| N04 | synthetic | synthetic 标签/命名空间 | **PASS** | T4、`07…txt` |
| N05 | synthetic | GL-I01 62 + Codex 24 + SHA | **PASS**：62 OK、24/24、四文件 SHA 不变 | `11…txt`、`10…txt`、`14…txt` |
| N06 | synthetic | 非 adapted 与损坏 adapted | **PASS**：均 exit 2，不 fallback | T5、`09…txt` |
| N07 | synthetic | draft 决断表字段 | **PASS**：字段齐 + `human_review_pending`（`pending_human_review`）标签 | T6、`09…txt`、`07…txt` |

回归命令 / 数量 / 退出码：

- `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli01_capture_input.py` → Ran 62 / OK / exit 0（`11_gli01_regression.txt`）
- `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli02_candidate.py` → Ran 8 / OK / exit 0（`12_gli02_new_tests.txt`）
- `python -B -W error -m unittest discover -s src/human_fall_detection/tests` → Ran 407 / OK / exit 0（`13_full_regression.txt`）
- `python -m py_compile src/human_fall_detection/scripts/evaluate_gli02_candidate.py` → exit 0
- Claude Codex 合成探针（GL-I01 复核 24 项）：`python 10_gli01_codex_probes.py` → total=24 failed=0（`10_gli01_codex_probes.txt` / `10_gli01_codex_probes_results.json`）
- 冻结资产对照：GL-I01 四文件 + `ground.py`/`calibration.py` + 真实 capture `{meta.json,points.bin}` SHA 与诊断 §1 逐项一致（`14_new_files_sha.txt`）

真实 163621 read-only reload（`08_real_readonly_reload.txt`）：points **4372400** / frames **89** / frame_groups **89** / zero_rows **673315**，与 GL-I01 R1 一致；capture 两文件 SHA 前后不变、目录无新文件。**未对真实数据拟合**。

## 未闭合与限制

- 未满足/未跑：真实 candidate ground 拟合（J01/N01 真实侧）按设计门 condition 3 与工单行为约束 **NOT_RUN**——真实 `up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions` 属人工决断，draft 已以 `pending_human_review` 落地待决；设备/物理 D01、GL04 DPR D02 NOT_RUN；B01 BLOCKED 维持。
- 契约允许的限制：真实 export 数值 ≠ 已核标定/单位/安装；`physical_verified=false`、`source_bag_hash_verified=false`、`point_index_domain=capture_export_row`、`original_bag_point_index=unknown` 均维持；`status.ground="candidate"` 是容器状态，`ground.status="valid"` 为几何记录状态（设计门 R-a）。
- 范围外新需求：无。wrapper 未新增阈值/依赖/ROI 语义；未扩展白名单。
- 设备/物理未跑项：GL05、现场协议冻结、部署、采集、网络。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`GLI02_ACCEPTANCE.md` v1 + 本回传 + `GLI02_CANDIDATE_PLAN.md`
- 根因诊断/完整入口检查证据：`evidence/2026-10-03_gl_i02_r1/00_diag.md`、`04_DESIGN_REVIEW.md`、`09_negative_and_sha_check.txt`
- 源码差异与 SHA 证据：见“实际变更”表 与 `14_new_files_sha.txt`
- 原始日志索引：`evidence/2026-10-03_gl_i02_r1/07…14_*`（synthetic / real / negative+sha / probes / regression）
- 当前工单下一步：Codex 独立复审；本回传 SUBMITTED，不自动启动设备/下一单/部署。

## 审查附记（2026-10-03 Claude Code 顶替 Codex）

独立复审在 `evidence/2026-10-03_gl_i02_r1/codex_review_01/CODEX_REVIEW.md` + `13_route3_closeout.md`：

- **J01**：synthetic fit candidate 独立 PASS；真实 fit 路线3 分层 NOT_RUN（协议-场景矛盾：单 frame_group ~1214 点 × `_balanced_sample` 剩 ~80 < `min_inliers=100`，定义层 BLOCKED 不属于代码 bug）。
- **J02–J06 / N01–N07（除 J01/N01 real 侧）** 全 PASS：白名单 SHA、冻结资产、真实 capture SHA 一致；24 探针、62 GL-I01 回归、独立 N1–N5 反例全过。
- **B01 BLOCKED、D01/D02 NOT_RUN** 分层维持。
- **不自动派 R2 / 不动协议 / 不进生产**；完整继接由下一个工单在**用户决定**（长满 capture / 协议重审 / 其它路线）后另派。
