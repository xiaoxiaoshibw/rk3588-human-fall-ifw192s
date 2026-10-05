# GL-I01 回传（工作流程v2）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-I01 / R1 PHASE TWO / OpenCode Go `opencode-go/deepseek-v4.1-flash` / 2026-10-03
- 验收表路径 / 版本 / SHA（提交时记录）：`docs/human_fall/GLI01_ACCEPTANCE.md` / v1 / 随共享工作树（未 commit）
- 执行方式 / 实际会话与模型：本机 Windows，离线纯 Python；模型同上；skill `ponytail` full
- 状态：SUBMITTED（软件自验；设备/物理未跑 → NOT_RUN/BLOCKED，不宣布总体 PASS）
- 起始 branch/HEAD：`master` / `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；工作树故意 dirty（见下）
- 范围内用户差异：`docs/human_fall/evidence/`, `returns/` 及 `10/13/14/15/16/17_*` 为本轮/上轮记录；生产源码白名单见“实际变更”
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（full；与 `evidence/2026-10-03_gl_i01_r1/ponytail_SKILL.md` 同源）

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| I01/I04 | 真实 export 无 manifest 身份，直接喂 legacy 会丢帧成员/单位/时钟 | `calibrate_sensors.py --points` → loader | `capture_input.read_source_meta`/`canonical_source_xyz` | legacy `--points` NPY/NPZ 语义不变 |
| I02 | 零点会被预滤、行号会重编号 | 任意 pooled index → frame mapping | `canonical_source_xyz`（零点保留）+ `frame_of_row` | 原行索引域 `capture_export_row` |
| I03 | `<f4` 点 timestamp 反推 ns、隐式 mm | manifest/provenance | `validate_frames`/`read_source_meta` | 整数 header stamp；`m` 显式 |
| I05 | bounds 未先受 group 约束、可据残差预滤 | constrained fitter 入口 | `select_group_region` group-first + `gate_selection` | ground 数学/阈值不变 |
| I06 | 含 marker 的损坏 NPZ 静默回退 legacy | `classify_npz`/loader | 内容检测 + 单快照 canonical 重算 | 无 marker 的旧 points 保持旧行为 |
| I08 | 目标可被覆盖/半截正式产物 | CLI 输出 | `prepare_npz`/`save_exclusive_json` `os.link` 独占 | 无 `O_EXCL`/copy 回落 |
| 审计项 | 扩展名判定、多键、非标量 manifest、bool/int 蒙混、非有限源、负索引环绕 | loader/selector/frame map | 见 `17_implementation_checks.md` | — |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `src/human_fall_detection/core/capture_input.py` | 新增纯适配/加载/group-first 选择模块 | 新增，非既有文件改动 | `56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16` |
| `src/human_fall_detection/scripts/prepare_capture_input.py` | 新增 prepare CLI（仅 4 显式参数） | 新增 | `648a8da63a6656b02d169957cede2df4aca3a48e94dcc787c3c48c7f10c5d000` |
| `src/human_fall_detection/scripts/calibrate_sensors.py` | 加 manifest 内容识别 + adapted constrained route | 仅新增分支，legacy 路径字节语义保留 | `3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785` |
| `src/human_fall_detection/tests/test_gli01_capture_input.py` | 新增集中回归 62 项 | 新增 | `50f615d7a5ffdc490f1011b316df30da1e65c958cce93f18ad4cf0c88547030e` |
| `docs/human_fall/GLI01_INPUT_CONTRACT.md` | 输入/输出契约 | 文档新增 | — |
| `docs/human_fall/evidence/2026-10-03_gl_i01_r1/17_*` | 本轮自验证据 | 新路径 | — |

未 commit/push/reset/checkout/clean；冻结 ground/math/runtime/calibration/config/driver/webui/collector/captures 未改。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| I01 | offline + 真实 163621 | `prepare_capture_input.py`/`read_source_meta` | PASS（exit 0；反例 exit 2） | `17_implementation_checks.md` |
| I02 | synthetic | `canonical_source_xyz`/`frame_of_row` 测试 | PASS | `test_gli01_capture_input.py` |
| I03 | synthetic | `validate_frames`/`read_source_meta` | PASS | 同上 |
| I04 | synthetic+真实 | `load_adapted` 单快照 canon | PASS | `cap_20261002_163621_reload.json` |
| I05 | synthetic | `select_group_region`/`gate_selection` | PASS | 62 测试全绿 |
| I06 | synthetic | CLI 拒绝/副作用测试 | PASS（exit 2，无产物） | `17_implementation_checks.md` |
| I07 | 真实 163621 | `build_input_info`/manifest provenance | PASS（physical_verified=false；未拟合） | reload json |
| I08 | synthetic | `prepare_npz` link 独占 + legacy 回归 | PASS | 399 全绿 |
| B01 | source 证据 | capture schema 未持久化原 bag row index | BLOCKED（不变） | — |
| D01 | 设备/物理 | 未操作设备 | NOT_RUN | — |
| M01–M13 | offline/synthetic | 见 `17_implementation_checks.md` 命令 | PASS（真实 M13 仅 prepare/reload/count/hash） | 同上 |

回归：
- `python -B -W error -m unittest discover -s src/human_fall_detection/tests` → Ran 399, OK
- `... test_gli01_capture_input` → Ran 62, OK；`... test_gl01_constrained_ground` → Ran 33, OK
- 冻结资产对照：ground/calibration/config/driver/webui/captures 无改动

## 未闭合与限制

- 未满足：B01（原 bag 点索引证据缺失），D01（现场/设备）。
- 契约限制：真实 export 数值 ≠ 已核标定/单位/安装；`original_bag_point_index=unknown`，`source_bag_hash_verified=false`。
- 范围外：无；未新增阈值或范围。
- 设备/物理未跑：GL05、现场 up_axis/ROI/高度判据、部署。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`GLI01_ACCEPTANCE.md` v1 + 本回传
- 根因诊断/入口检查证据：`evidence/2026-10-03_gl_i01_r1/17_implementation_checks.md`、`GLI01_INPUT_CONTRACT.md`
- 源码差异与 SHA 证据：见“实际变更”表
- 原始日志索引：`evidence/2026-10-03_gl_i01_r1/prepared/`、`synthetic/`
- 当前工单下一步：Codex 独审；不自动启动下一单或设备

## 审查附记（2026-10-03 Claude Code 顶替 Codex）

独立复审在 `evidence/2026-10-03_gl_i01_r1/codex_review_01/CODEX_REVIEW.md`，顶行结果：

- **I01–I08 / M01–M13 软件 PASS**；B01 BLOCKED / D01 NOT_RUN 分层维持。
- SHA 与回传逐项一致；冻结 ground/calibration/capture/webui/driver/captures 零修改；scope_ok=true。
- CLI 反例 6 条 + Codex 合成探针 24/24 全过；真实 163621 独立 reload 4372400 行 / 89 帧 / 89 组 / zero_rows 673315 与回传统计一致。
- 唯一候选缺陷（np.bool_ 绕 strict）由独立探针拆穿实际正确拒绝，不形成 FAIL。
- 整单按本子阶段规则不升 ACCEPTED；GL04 真实 DPR NOT_RUN / 正式不合并；GL05 / 设备 / 采集 / 部署 / 网络未授权。
