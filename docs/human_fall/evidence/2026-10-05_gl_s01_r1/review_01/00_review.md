# GL-S01 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5，通过 Mirasim 会话）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，同一条 AI 批量授权（2026-10-05 ONESHOT）下的独立复审会话。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`；复审期间工作树含用户既有在办改动，复审本身只读。
- ponytail 使用路径与 frozen 资产 SHA 在复审命令日志中记录。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-S01_floor_sheet_v2.md`（作者 SUBMITTED）
- 验收表：`docs/human_fall/GLS01_ACCEPTANCE.md` v1
- 回传：`docs/human_fall/returns/GL-S01.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_gl_s01_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_gl_s01_r1/review_01/`

## 范围核对（开工必做）

| 文件 | 回传声明 SHA256（前 8） | 实际 SHA256（前 8） | 一致？ | 备注 |
|---|---|---|---|---|
| `floor_sheet.py` | `92d2ed105…` | `92d2ed105…` | ✅ | |
| `floor_sheet_test.py` | `0c6e311e6…` | `0c6e311e6…` | ✅ | |
| `leveling.py` | `e01d52666…` | `3c3a88196…` | ❌ | 因 GL-S02 追加 v3 接入 |
| `validation.py` | `ff7a51478…` | `469fff14d…` | ❌ | 因 GL-S02 把 `lowest_floor_sheet_v3_fine_roi` 加入 `floor_identified` |
| `LEVELING_README.md` | （回传未列） | `653caabdcb…` | — | 工单范围内，GL-S02 同样有改动 |
| `floor_detector.py` | `72ce790f…`（回传 B1 引用） | `72ce790f…` | ✅ | B1 冻结一致 |

`leveling.py` / `validation.py` 的 SHA 不一致**不是范围越界**：GL-S02 工单在其 v1 验收表内明确授权在同一文件上叠加 v3 层。复审以"v1 → v2 → v3 委托链完整"为目标，逐文件 diff 见 GL-S02 复审。

## 逐条验收（独立复跑结果）

复跑命令与日志全部落盘 `review_01/`：

| 文件 | 内容 |
|---|---|
| `01_rerun_tests.log` | `floor_sheet_test.py` 12 项 + `*_test.py` 39 项 |
| `02_golden_rerun.log` | `01_golden_v2_check.py` 223757 + 三会话 |
| `03_b1_hardcode_check.py` + `.log` | B 层门是否硬编码字面量探针 |
| `04_independent_probes.py` | 自写边界探针 4 项（seed 与作者不同） |

| 验收 ID | 判据（字面） | 复跑证据 | 复审结论 |
|---|---|---|---|
| A1 合成回归 | 12 项 + 2 bug 回归 + `-W error` | `01_rerun_tests.log`：`python -B -W error -m unittest discover -s pc_apps/human_replay -p floor_sheet_test.py -v` → **12/12 OK，exit 0**（3.961s） | PASS |
| A2 223757 golden | A=PASS / B=FAIL / `INSUFFICIENT_CLEAN_ROI_SUPPORT`，稳定输出，不产物 | `02_golden_rerun.log`：`INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 independent=0 min_sep_m=0.354 condition=0.162`，exit 0；与作者 `02_golden_v2.log` 逐字一致 | PASS |
| A3 三会话不回归 | 203349/203135/202456 v2 逐字返回 v1 regions/candidate，`kind=lowest_connected_floor_v1` | `02_golden_rerun.log`：三会话均输出 `lowest_connected_floor_v1`，exit 0；另 `leveling_auto_test.py::test_real_sessions_detect_four_regions` 跑 cap_20261004_202456 / 203349 通过 | PASS |
| B1 B 层门不降 | 逐帧≥30 / 厚度≤0.18 / \|n_z\|≥0.94 / RMS≤0.025 / 全高度源行 / 四区互不重叠 / 最小间距≥0.5m / 独立=4 / 条件数≥0.10；`floor_detector.py` SHA 不变 | ① `floor_detector.py` 实际 SHA `72ce790f…` = 回传声明；② 实测 `floor_detector.PROFILE`：`min_points_per_fit_frame=30 / cell_height_span_max_m=0.18 / normal_alignment_min=0.94 / cell_local_rms_max_m=0.025 / cell_floor_gap_max_m=0.08`——与判据逐项一致；③ `03_b1_hardcode_check.py`：`hardcoded_B_gates = []`、`SHEET_PROFILE_B_keys = []`（v2 完全经 `PROFILE[...]` 引用 20 处）；④ `SHEET_PROFILE`：`roi_min_separation_m=0.50`、`condition_min=0.10` 与判据一致 | PASS |
| B2 桥接边界证明 | 仅显著碎片(≥0.25m²)、缺口≤4格、触面证据(接触格比≥0.5 且≥1 个触面格)、仅当最大片<0.5m²才需要桥 | `01_rerun_tests.log` 中作者的 `test_contact_bridge_merges_fragmented_sheet`（触面 → 合并 ≥0.5m²）、`test_bridge_requires_contact_and_bounded_gap`（空缺口 / 宽缺口不合并）、`test_small_satellite_fragment_ignored`（小碎片不触发 gap 门）、`test_undulating_floor_stays_connected`（2–4cm 起伏不断开）全过 | PASS |
| C1 失败/成功语义 | A 失败→`floor_regions_invalid: floor identity failed`；A过B不足→`INSUFFICIENT_CLEAN_ROI_SUPPORT`；双过→`kind=lowest_floor_sheet_v2`+`full_height_preserved=True`+`uses_manual_reference=False` | ① 作者 `test_low_platforms_with_empty_gaps_identity_rejected`（A 失败），`test_adjacent_clean_cells_insufficient_support`（B 失败），`test_scattered_clean_cells_on_one_sheet_succeed`（双过）通过；② `04_independent_probes.py::test_p3_v2_candidate_fields_literal` 复核双过时 `kind/full_height_preserved/uses_manual_reference` 字面 True；③ `test_p4_…does_not_take_over`：v1 抛**非** `floor_regions_invalid`（如 `floor_auto_candidate_invalid`）时，v2 原样抛错不接管——委托边界忠实 | PASS |
| C2 消费者与全回归 | `floor_identified` 接受 v2 kind；`leveling_test`/`validation_test`/`floor_detector_test` 全回归过 | `01_rerun_tests.log`：`python -B -W error -m unittest discover -s pc_apps/human_replay -p "*_test.py" -v` → **39/39 OK，exit 0**（作者记录 33 项是 GL-S02 加入前；GL-S02 加了 `floor_roi_test.py` 6 项；39 = 12 floor_sheet + 6 floor_roi + 3 floor_detector + 4 leveling + 5 leveling_auto + 6 fetch_lib + 2 sessions + 1 validation，全部 OK） | PASS |
| C3 审计 code_files | `run_job` 的 `code_files`/`code_hashes` 纳入 `floor_sheet.py`；v2 candidate 携带 evidence 字段 | 复审源码 `leveling.py` `run_job` 行 264–268：`code_files` 含 `leveling.py / leveling_quality.py / floor_detector.py / floor_sheet.py / floor_roi.py / leveling_estimators/*.py`；行 294：运行结束时再次 `sha(p) != code_hashes[p.name]` 校验——任何运行期改动直接拒绝结果。`floor_sheet.py` 行 300–319 candidate 含 `profile / support_ratio / fit_frame_count / component_cells / component_area_m2 / sheet / roi / selected_cells / full_height_preserved / uses_manual_reference / basis`——契约字段齐全 | PASS |
| S01 流程 | ponytail 加载、SHA 记录、不越界、不 commit/push/reset | 复审会话记录见上；复审未对生产源码 / 测试 / 验收表做任何写操作；新增文件仅 `review_01/` | PASS |
| D01 设备/物理 | 离线单，NOT_RUN | 未运行 | NOT_RUN |

## 复审期间发现的非问题项（已澄清，不影响结论）

1. **`leveling.py` 调的是 v3，不是 v2**：回传行级描述只说 auto 改调 v2。实际行 243 `from floor_roi import detect_floor_regions_v3`、行 244 调 v3。这是 GL-S02 在 v2 之上的合法 additive 层；v3 在 v1/v2 成功时逐字返回，在 v2 `INSUFFICIENT_CLEAN_ROI_SUPPORT` 才进入 15cm 细 ROI——委托语义没破坏 v2 的失败语义。GL-S02 复审会单独核 v3 入口与 v2 路径。
2. **作者回传 `leveling.py` SHA 与实测不一致**：同 1，属于 GL-S02 范围内叠加。
3. **作者记录 33 项 OK**：当前 39 项是叠加 floor_roi_test 6 项的结果，均通过。

## 观察

- v2 委托实现忠实：v1 成功逐字返回，v1 `floor_regions_invalid` 接管，v1 其他错误原样抛——`test_p4` 独立探针验证。
- 失败语义三分在 `floor_sheet.py` 行 248（v1 委托）/ 行 276（A 失败）/ 行 283（B 失败）/ 行 300–319（双过），与判据逐字一致。
- `_roi_metrics` 对 24 格以内穷举 C(n,4)、>24 改贪心——作者为我们>4 格的真实数据留了 fallback；223757（6 格）走穷举。
- `_clean_cells` 行 87–88：`local_normal = vectors[:, 0]`——`np.linalg.eigh` 特征值升序，`vectors[:, 0]` 是最小特征值对应特征向量，即恰为局部法向。修法正确；bug 回归 `test_clean_cell_normal_direction_regression` 锁定。
- `_sheet_metrics` 行 173：`sig = [c for c in comps if len(c) * cell_area >= p["significant_fragment_m2"]]`（≥0.25m²）后才参与缺口评估——把作者探针发现的"无关小碎
片误触发 gap 门"问题在共享函数内一次修到位。bug 回归 `test_small_satellite_fragment_ignored` 锁定。

## 复审命令实际记录

```
python -B -W error -m unittest discover -s pc_apps/human_replay -p floor_sheet_test.py -v   -> exit 0, 12/12 OK, 3.961s
python -B -W error -m unittest discover -s pc_apps/human_replay -p "*_test.py" -v           -> exit 0, 39/39 OK, 90.873s
python -B docs/human_fall/evidence/2026-10-05_gl_s01_r1/01_golden_v2_check.py               -> exit 0
python -B docs/human_fall/evidence/2026-10-05_gl_s01_r1/review_01/03_b1_hardcode_check.py   -> exit 0 (hardcoded_B_gates=[])
python -B -W error docs/human_fall/evidence/2026-10-05_gl_s01_r1/review_01/04_independent_probes.py -> exit 0 (4/4 PASS)
sha256sum pc_apps/human_replay/floor_detector.py                                            -> 72ce790f...
```

## 复审结论

**软件 PASS**（A1–A3, B1–B2, C1–C3, S01 全过；D01 NOT_RUN 属本单边界）。范围越界无、冻结资产零改、v1 语义零改、B 层门零降。

整单 **不报 ACCEPTED**：D01 NOT_RUN / 设备物理未跑；按 WORKFLOW 由用户决定是否收口。移交 GL-S02 复审。
