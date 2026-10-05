# Claude Code GL-I01 R1 独立复审 / 2026-10-03

顶替登记见 [CLI_RECOVERY.md](../../CLI_RECOVERY.md)；本轮复审由 **Claude Code** 按 [CLAUDE_STANDBY.md](../../CLAUDE_STANDBY.md) 顶替 Codex 完成，生产代码单写入者仍是 OpenCode `opencode-go/deepseek-v4.1-flash`（default DB，无隔离库）。本轮**未发现代码级 FAIL**；I01—I08 / M01—M13 软件 PASS，B01 BLOCKED / D01 NOT_RUN 分层维持。整单未升 ACCEPTED（本子阶段默认）。

## 0. 范围与 SHA（复审结尾再核，与00_review_baseline一致）

| 文件 | 本轮 SHA（重构后） | 与回传对应 |
|---|---|---|
| `src/human_fall_detection/core/capture_input.py` | `56355e9594433d91…` | 与回传逐项一致 |
| `src/human_fall_detection/scripts/prepare_capture_input.py` | `648a8da63a6656b0…` | 与回传逐项一致 |
| `src/human_fall_detection/scripts/calibrate_sensors.py` | `3f30cf945d70b06f…` | 与回传逐项一致 |
| `src/human_fall_detection/tests/test_gli01_capture_input.py` | `50f615d7a5ffdc49…` | 与回传逐项一致 |

冻结资产：`src/human_fall_detection/core/ground.py`、`core/calibration.py`、`src/human_capture/scripts/capture_server.py`、`src/human_capture/core/bag2session.py` 全部与 00_before_manifest 一致；真实 capture `captures/remote/cap_20261002_163621/{meta.json,points.bin}` SHA 与 04_capture_before_sha 一致，未被修改。

范围审计见 `01_scope_audit.json`（`scope_ok=true`）：2068 条基线中除上面 ALLOWED_NEW/ALLOWED_MODIFIED/历史垃圾（用户删除的 build_ros1/2.sh、open_webui.bat、rk.txt、.mirasim/schedules.json）外，其余 0 modified、0 unexpected_new。`src/CMakeLists.txt` 为 /opt/ros 的符号链接，Windows 上不可读，属预期。

## 1. 复审手段与命令（全部原始日志在 codex_review_01/）

| 阶段 | 命令 | 结果 |
|---|---|---|
| 白名单回归 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli01_capture_input.py` | Ran 62 / OK（02_gli01_suite.txt） |
| 全回归 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests` | Ran 399 / OK（01_full_regression.txt） |
| GL01 constrained 回归 | `python -B -W error -m unittest discover … -p test_gl01_constrained_ground.py` | Ran 33 / OK（03_gl01_suite.txt） |
| HF03 几何回归 | `python -B -W error -m unittest discover … -p test_hf03_geometry.py` | OK（04_hf03_suite.txt） |
| Positive adapted CLI fit（合成 7 帧 2000 点 + 3 独立 validation 区） | `calibrate_sensors.py --points cap_synthetic_01.npz --constrained --fit-… --validation-… --up-axis 0 0 1 --sensor-height-interval 0.5 2.5 --output codex_geometry.json` | exit 0；`status=valid`，`sensor_height_m ≈ 1.20004`，artifact 含 `input.input_manifest` 全字段（06_cli_positive.txt / 09c_artifact_provenance.txt） |
| A1 非 constrained 提前接 manifest | `calibrate_sensors.py --points cap_synthetic_01.npz --output n1.json` | exit 2，无 artifact（07_cli_negatives.txt） |
| A2 adapted 拒 `--diagnostics` | 同上 + `--diagnostics n2d.json` | exit 2，无主 artifact、无 diagnostics artifact（07） |
| A3 CLI frame 冲突 | 同上 + `--frame other_lidar` | exit 2，cli_frame_mismatch（07） |
| A4 覆盖已存在 target | 同 5 用 codex_geometry.json | exit 2，旧文件保留（07） |
| A5 缺 fit selector | 无 `--fit-region/--fit-indices` | exit 2，无 artifact（07） |
| A6 legacy NPZ 不跌进 adapted | 普通 savez to legacy_cloud.npz | exit 0 legacy fit valid，未触发 adapted 拒绝（07；M07 PASS） |
| Codex 合成探针（24 项） | `10_codex_probes.py` | 24 / 24 全过；含 bin/meta 变化反例、frames 表 gap/overlap、bool dropped_frames、字符串/缺失 bag_time、units 空白/大小写、sensor.frame_id 缺失、frames=[]、alias 组、seq 交换、点计数缩水、np.bool_/np.float32索引拒绝、boundary 空帧映射、路径重命名可重载、fit indices 泄漏拒（10_codex_probes.txt / 10_codex_probes_results.json） |
| M13 真实 capture 独立 reload | `load_adapted cap_20261002_163621.npz`（terr） | points 4372400 / 89 frames / 89 groups / bin/meta sha 与基线一致 / sample boundary 映射正确 / independent zero_rows 673315 == 实现者声明 673315（09_real_reload_check.txt） |
| M10 adapted invalid fit no-artifact | fit-region bounds 无点 | exit 2，无 artifact（09b_invalid_fit.txt） |
| M12 artifact input provenance | 检查 codex_geometry.json | input_manifest 7 字段齐全、所有 physical 假、frame_groups=7（09c_artifact_provenance.txt） |
| Scope 审计 | `01_scope_audit.py` | scope_ok=true；白名单完全、冻结资产零修改 |
| 01_review_baseline（核 SHA + capture） | `00_review_baseline.py` | all_match=true |

## 2. 逐条验收（I01—I08 / M01—M13 / B01 / D01）

| 验收 ID | 结果 | 依据 |
|---|---|---|
| I01 严格 28B little-endian、完整/连续/无 clip/drop | **PASS** | 白名单 62 通、Codex 合成 bin 变化 (28B 追加、截断、offset gap/overlap) 全部在 prepare/reload 阶段拒绝；clip 会话 `cap_20261002_165321_clip_*` 不存在 `source_bag_sha256`/非 bag2session/0.1.0 → 按诊断不会通过本单入口（与 07_diag_revision M04 一致）；真实 163621 meta/tool/layout/point_step 均合规，独立重读确认 |
| I02 帧顺序/零点/原行保留、索引不滤重编 | **PASS** | 62 回归含 zero/empty frame；Codex boundary 空帧映射 truth；真实 163621 zero_rows 673315 independent recount 与实现者 reload.json 一致；任意 position_within_group mapping 经 `frame_of_row` 返回 [0,0,1,88] 正确 |
| I03 frame/units 显式声明、整数 stamp_sec/nanosec、不从 `<f4 timestamp` 恢复 ns、frame/units 冲突拒 | **PASS** | fit/validation 不含 mm、不允许 unknown/units 不一致；CLI frame 冲突 case A3 PASS；真实 meta.time_domain 记录为 device_stamp_s_unanchored，不动用 `<f4` timestamp 推 ns |
| I04 确定性 group、manifest 与实际源绑定、label 不能伪装独立 | **PASS** | loader 从无 NPZ 重读实际 meta/bin 重建 canonical manifest 相同；alias 组注入、seq 交换、frame count 改等都在 canonical JSON 比较阶段被拒，"canonical mismatch"；真实 163621 89 个 group 每个唯一 |
| I05 fit/≥3 validation，显式选区，group-first bounds，不预滤残差 | **PASS** | gate 正/反例都过：缺 fit 选择器拒、缺 validation 区数拒、fit/val 帧overlap拒、显式 indices 越组拒、空组法律 bounds 拒 bool/NaN/边界倒置；归一化后 `_strict_indices` / `frame_of_row` 全 pool 索引一致 |
| I06 含 manifest 拒绝绝不 fallback legacy，失败无副作用，adapted 不生成半截 artifact | **PASS** | A2 A4 M10 全部 exit 2 + artifact=no；`save_exclusive_json` 与 `prepare_npz` 均用 os.link 独占；显式临时文件清理已在回传统测试内 |
| I07 provenance metadata_declared、physical=false、原 bag hash 未核、synthetic 检查标注 | **PASS** | 框架 build_input_info.write 文件均带 physical_verified=false 、 source_bag_hash_verified=false 、 point_index_domain="capture_export_row" 、 original_bag_point_index="unknown" 、 frame_provenance="metadata_declared"；01_codex_geometry.json 重新确认 |
| I08 同一 NPZ、原子写、独占、legacy NPY/NPZ 保留、Python3.8 | **PASS** | pp atomic、unique link；legacy 单一 NPZ/NPY 走老路径（A6 legacy fit valid）；白名单只新加 1 模块，全 stdlib+NumPy，未 import cv2/RKNN/ROS |
| **B01** 原 bag 点索引/独特 layout 证据不足 | **BLOCKED** | bag2session 只写 count/offset，不持久化 width/height，bag 源索引未知；本单不伪造；与 07_diag_revision §5 一致 |
| **D01** 真实物理/设备/性能/现场 | **NOT_RUN** | 按工单不启动、不部署、不采集；本单只软件 |

M01—M13 行映射（见 `10_codex_probes.txt` 与 07_diag_revision §4）：

| 行 | 结果 | 侧重 |
|---|---|---|
| M01 multi-frame export → NPZ → constrained loader | PASS | 合成 7 帧带两空帧、真实 89 帧均 0 退出 |
| M02 零点/空帧/首/尾 | PASS | zero_rows 673315、空帧 zero-width range 归属正确 |
| M03 截断/尾数据/overlap/gap/total 矛盾 | PASS | bin 追加、截断、offset gap、offset overlap 均拒绝（create 阶段） |
| M04 unknown format/version/layout/endian/clip/drop != 0 | PASS | tool / stride / version 强制校验；clip drop!=0 走 dropped_frames==0 reject |
| M05 bool/float/string 数/章/ns/frame/units | PASS | dropped_frames、count seq stamp strict int、units 大小写、m vs mm、frame 冲突 |
| M06 修改 source/meta/bin/points/manifest/group 后 reload | PASS | 调 alias、seq 交换、points 减一、bin/meta 实际改都在 reload canonical 阶段拒 |
| M07 legacy NPY/NPZ 无 manifest → 旧入口 | PASS | legacy_cloud.npz 走 legacy fit valid |
| M08 fit/validation 点交叉或同源帧不同 group | PASS | 显式 pooled indices 越组拒、validation 共享 fit group 拒、validation 之间 共享帧拒 |
| M09 bounds 经 pooled frames + group 限制 | PASS | bounds 只作用在组成员内、返 pooled 原行、不预筛残差 |
| M10 缺 ROI/group/<3 validation | PASS | 没有 selector → exit 2 无 artifact（09b) |
| M11 output exists / 失败 / 重复写 / 竞争 | PASS | A4 cover 拒、prepare_npz exclusive link、临时文件清理 |
| M12 adapted CLI 成功/失败 → artifact input provenance | PASS | artifact 含 input_manifest 全字段所有 physical false |
| M13 真实 163621 全 89 帧 4372400 行 → 适配/加载 | PASS | reload.json 与独立 reload 一致；bin/meta SHA 同基线；zero 数 673315 |

## 3. 唯一复审期识别出的候选缺陷（复审自证闭合）

**候选**：`frame_of_row`（与 `_strict_indices`）若调用方传入 `np.array([True, 0], dtype=np.bool_)`，`_strict_indices`/`frame_of_row` 各自 `dtype.kind == "b"` 分支先拒，但底层 Python `isinstance(item, bool)` 不 catch 裸 `np.bool_`。

- 独立复核：np.bool_ 是符合 integer 接口（`dtype.kind in "iu"` 与 `isinstance(item, np.integer)` 都为 True）的另一种 case。
- 但这条 pathway **上游有门前**：`_strict_indices` 已在进入 `frame_of_row` 元素循环之前用 `dtype.kind == "b"` 拒绝 ndarray；`frame_of_row` 自身在 ndarray 输入头一段也同法卡。要让 np.bool_ 实际走到元素循环外层、得不直接传 ndarray、`tolist()`、而它 `tolist()` 出来的是 Python `bool`，`_strict_indices`/`frame_of_row` 的元素循环会 `isinstance(item, bool)` → 拒。
- 结论：当前实现实际是对 np.bool_ strict 正确拒绝；该“候选”由我的 10 号独立探针拆穿—— `np.bool_ element (pure) strictly rejected` 通过；不是 production FAIL。

## 4. 冻结/边界确认

- ground/math/runtime/calibration/Python 配置/driver/webui/capture/captures 未改
- GL04 真实 DPR 浏览器验证、GL05 设备/板端网络/部署，本轮未启动也未授权
- 真实 163621 capture 只 read/hash/count；未在 R1 拟合、未写生产 config、不改历史 capture
- 不 commit/push/reset/checkout/clean；工作树保留用户差异

## 5. 收口

GL-I01 R1 软件范畴 review 结论：**所有 I01—I08 / M01—M13 PASS**。B01 BLOCKED / D01 NOT_RUN 维持，均与工单契约一致。本复审整单**不**升 ACCEPTED（本子阶段默认），仅软件条项 review 合格。

下一步按用户明确指令：同一编排者 Claude Code 顶替代派 OpenCode CLI `opencode-go/deepseek-v4.1-flash` 沿主线推进——推进对象、工单号与验收表另起，工作流不变。
