# GL-P01 R1 集中诊断（实现前，M01-M12）

2026-10-03。唯一生产写入者 OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB。
实际读取 ponytail skill 路径：`docs/human_fall/evidence/2026-10-03_gl_p01_r1/ponytail_SKILL.md`（仓库内副本，Codex 复制并 SHA256 校验等于 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；外部路径读取被权限拒绝，未改动权限/全局配置）。full 强度。

## 0. 结论（最小修复位置）

`src/human_fall_detection/core/lidar_candidates.py` 的 `build_snapshot`（527-662）已通过共享入口 `_validated_ground_derived`（470-511）拿到 **严格 validated、绑定实际 frame/显式 ground** 的 canonical `ground_derived` 与 `parent`，但只发布了 `ground_derived_id`。最小修复：在已构造 `coordinate` 字典处（612-620）用白名单把 canonical `R/t` 及绑定字段投影为 `coordinate.ground`（`kind=coordinate_ground`, `schema_version=1`），无 validated derived 时为 `null`；不重拟合、不重算、不发 `ground_render` alias、不按 `normal` 补 identity。另在 `build_snapshot` 的 `ground` 摘要（653-657）附 `support_polygon/polyline=null` 与非空 `support_reason`，明确当前无可信支持轮廓。

不改数学/runtime/config/driver/网页；`node_runtime.project_snapshot_for_ros`（135-158）与 `dumps_strict`（106）已按 additive 字段透传，无需改 node（缺口检查见 §3）。

## 1. 生产链实际函数/赋值顺序

`build_snapshot`（pure producer）实际顺序：
1. `resolve_settings` → finite 过滤 → `array`/`original_indices`（538-548）。
2. 距离门 `keep`（550-551）。
3. `basis = ground_plane_basis(ground) if ground_frame_eligible(ground, frame_id) else None`（556-557）：源 frame 守卫，异 frame 不套平面。
4. 高度门 → `array`/`original_indices`（558-562）；background 扣除（564-567）。
5. `horizontal`/`clusters`（569-570）。
6. `ground_derived, _bound_ground = _validated_ground_derived(calibration, frame_id=frame_id, ground=ground)`（574-575）；`ground_derived_id`（576-577）。
7. `reference, _reference_reason = _resolve_reference_transform(...)`（583-584）。
8. 候选循环：`_point_features` → `_reference_block` → `_ground_geometry_block`（586-597）。
9. `coordinate`（612-620）当前字段：`source_frame/reference_frame/horizontal_basis/ground_relative_available/ground_frame/transform_status/ground_derived_id`。**本单在此新增 `ground`**。
10. `calibration_block`（621-626）：`calibration_id/schema_version/ground_status/ground_derived_id`。
11. `quality`（627-636）。
12. 顶层返回（637-662）；`ground` 摘要（653-657）。**本单在此附 support 字段**。

共享校验入口：`validate_geometry_calibration`（calibration.py:1075）→ `_validate_geometry_calibration`（958）→ `validate_ground_derived`（793）+ `_validate_ground_derived_consistency`（932）。`apply_ground_derived`（894）用同一 R/t。

消费者链：`FallNodeCore._process_locked`（node_runtime.py:705-720）→ `project_snapshot_for_ros`（135-158，深拷贝 snapshot/candidate、仅去 `evidence_indices`）→ `scripts/human_fall_node.py:410-413` `dumps_strict`（`allow_nan=False`）→ 板端 String 发布 → 预览 `parseGroundRender`（webui/human_fall_preview/human_fall_lib.js:401-416）读 `coordinate.ground`（authoritative）否则 `ground_render`（legacy）。

预览 `_parseGroundBlock`（336-380）接受 key 集合：`kind∈{ground_render,coordinate_ground}`、`schema_version===1`、`from_frame===source.frame_id`、`coordinate.source_frame===source.frame_id`、`to_frame==="ground_local"`、`units==="m"`、`validRotation(R)`、`isTriple(t)`、`calibration.schema_version===1`、`calibration_id===cal.calibration_id`、`ground_derived_id===coordinate.ground_derived_id` 且若 `cal.ground_derived_id!=null` 相等、`geometry_schema_version`（若存在）`===cal.schema_version`、`ground_status==="valid"`。因此投影字段与 canonical 值原样即可 ready。

## 2. 白名单投影字段（P01）

`coordinate.ground`（仅当 `ground_derived` 为 validated dict，否则 `null`）：
`kind="coordinate_ground"`、`schema_version=1`、`from_frame`、`to_frame`、`units="m"`、`calibration_id`（= canonical calibration_id）、`geometry_schema_version`（= canonical schema_version）、`ground_derived_id`、`R`（**新建** 3x3）、`t`（**新建** 3-list）。不重算 R/t，不含 `n/d/valid_region/source/applicability` 等大块，避免把 artifact evidence 发到 UI（white-list）。

## 3. M01-M12 逐行映射

| 行 | 输入/状态 | 实际函数与赋值顺序 | 校验/检查入口 | 消费者与保留/失效 | ID | 本单动作 |
|---|---|---|---|---|---|---|
| M01 | startup/full valid artifact + matching ground；empty/unlocked | `build_snapshot` 步6 得 derived；步9 投影；no cluster 时 `candidates=[]` | `_validated_ground_derived`+`validate_geometry_calibration`；JS `_parseGroundBlock` | NodeCore→project→dumps→parseGroundRender `ready`；无 candidate 不造框（candidate 循环不走） | P01/P03 | 新投影；测试空候选仍带变换 |
| M02 | startup/tilted + nonzero t；unlocked/候选 | 步6 derived（倾斜 ground 由 `build_ground_derived` 生成非单位 R）；步8 `_ground_geometry_block` 用同 R/t | `validate_ground_derived`（R 正交、t=-R@o）；JS `validRotation` | 原值 R/t 与 actual-points AABB（`bbox_ground_from=actual_points`）；原 candidate ID 不变 | P01/P03/P06 | 新投影校验 R/t 与 ground_derived 完全一致；AABB 仍来自原点集 |
| M03 | legacy/none/ground-only 无 derived；unlocked/locked | `calibration.get("ground_derived")` 非 dict → `_validated_ground_derived` 返回 `(None,None)` | `_validated_ground_derived` 首判 | `coordinate.ground=null`；source 旧行为（reference/height 路径）不变 | P02/P06 | 新投影返回 null；测试无 identity fallback |
| M04 | full artifact only、`ground=None`；producer 独立调用 | 步2 `basis`：`ground` 为 None → None；步6 derived 仍 validated（frame 绑定通过，显式 ground 检查跳过） | 同 M01；`quality.ground_valid=False`；`calibration_block.ground_status="unknown"` | `coordinate.ground` 存在但 `cal.ground_status=unknown` → JS `unqualified`（非 ready）；`snapshot.ground=null` 原义保留 | P02/P03/P06 | 不改：投影不依赖 `ground` 入参；测试 full-only 为 unqualified |
| M05 | 同内容 reload；locked、baseline pending/ready | `FallNodeCore.apply_ground_context`（543）→ `_resolve_new_context`/`ground_context_calibration`（同内容走 `preserved` 分支，1157-1167） | `validate_geometry_calibration` 全量重校；`same_reference`/`same_binding` | `changed=False`；旧 snapshot/eligibility 保留；投影随同 canonical id/GDID 不变 | P04 | 复用既有 GL02/GL03 生命周期测试；新字段不引新清空 |
| M06 | 同ID异内容/新ID reload；locked/pending/ready | `apply_ground_context` 校验先行；同 id 不同 R → `ValueError`（588-598） | `_same_transform_record`；`ground_context_calibration` | 拒绝无副作用（旧 snapshot/binding 不变）；新 id 合法则清旧资格 | P02/P04 | 复用既有测试；投影只在成功 bind 后由新 canonical 生成 |
| M07 | caller原地修改/输出 R 或 t 修改/ROS projection；后续帧 | `_validated_ground_derived` 每次 `validate_geometry_calibration(copy.deepcopy(calibration))`（496）；本单投影再新建 R/t list | `validate_geometry_calibration` 不 mutate 输入；返回 fresh canonical | 后续输出/artifact/candidate cache 不受污染；`project_snapshot_for_ros` 再拷贝顶层 dict | P02/P03/P04 | 新投影 R/t 用新建 list；测试修改输出不污染下帧 |
| M08 | foreign source frame / 显式不同 parent ground | 步6 `frame_id`/`ground` 绑定失败 → None；步3 `ground_frame_eligible` False | `_validated_ground_derived`（505/509）；`ground_frame_eligible`（115-132） | 不发可用变换（`coordinate.ground=null`）；旧 frame 不可借新字段选择 | P02/P04 | 复用绑定；测试异 frame/different ground → null |
| M09 | malformed/unsupported schema、units、ID、R/t、flags | 步6 `validate_geometry_calibration` raise → `(None,None)` | `validate_geometry_calibration`/`validate_ground_derived`（kind/version/units/frame/n/R/t/GDID/applicability/physical flags） | 共同校验拒绝；无部分应用/identity fallback；`coordinate.ground=null` | P02/P04 | 复用；测试坏整 artifact 各字段 |
| M10 | stream silent/invalid→current recovery；locked/pending/ready、历史 | `_process_locked`：`frame_valid=False` 时仍 `build_snapshot` 但 `register_snapshot` 不执行；`ground_context_unavailable` 清 candidates（749-758） | `TimebaseSession`/`ground_monitor` | 现有 unknown/位置/基线/ACK 原义；只恢复当前 context | P04/P06 | 不改 runtime；复用 GL02/03/HF07 |
| M11 | auto AABB/trusted ROI bounds 但无 actual轮廓；producer/JS 两 mode | 步6 `valid_region_ground_local` 存在于 derived，但本单只投影 R/t 白名单 | producer 只输出 null polygon + `support_reason`；JS `_normalizedSupport`（384-400）仅当 polygon/polyline 非 null 才 parse，否则 `parseSupport(null)`→`unavailable` | `ground.support_polygon/polyline=null`；`parseGroundRender.support.status="unavailable"`；`physical_verified` 不升 | P05 | 新增 support null + reason；不把 ROI 当 polygon |
| M12 | strict JSON/ROS projection/旧 reference 路径；候选存在/空候选 | `project_snapshot_for_ros` 仅 `pop("evidence_indices")`；`dumps_strict` `allow_nan=False` | `dumps_strict`；原 `validate_snapshot` 候选断言不改 | 无 NaN；保留 source/reference/IDs/候选数值/evidence（离线快照中）；投影只去候选 `evidence_indices` | P03/P06 | 复用；测试 strict JSON 往返与字段保留 |

## 4. 保留/失效与检查计划

- 保留：`snapshot` schema1、`source/reference/IDs/候选数值/evidence_indices`、`ground_status` 原文、无 derived 时的 null/unknown 与 source-only 路径。
- 失效：仅无 canonical derived（坏记录/异 frame/不同 ground/无 derived）时不发变换；不新增任何 global 清空。
- 新增集中检查：`tests/test_glp01_ground_projection.py`（pure producer 正负例 + NodeCore→project→dumps 链）与 `tests/glp01_consumer.js`（实调 `webui/human_fall_preview/human_fall_lib.js` 的 `parseGroundRender`）。
- 回归：受影响 `test_gl03_candidates_geometry.py`、`test_gl02_ground_frame.py`、`test_hf04_candidates.py`；不重跑无关全量。
- 不改：`docs/human_fall/WORKFLOW.md`/`DISPATCH.md`/`REVIEW_LOG.md`/验收表、preview/formal 页面、runtime、config、driver、历史 evidence/returns。

## 5. R1 resume 验收澄清（本轮唯一新增阅读，来自 resume 提示）

1. **producer R/t 与 artifact 解耦**：投影只读 validated canonical 的 `R/t`，并用**新建** list 输出；不持有/不改写 artifact 内嵌 `ground_derived`（`_validated_ground_derived` 已每次 `deepcopy` 校验，本单再新建输出 list）。
2. **投影执行保留 cache，维持既有嵌套浅拷贝语义**：`project_snapshot_for_ros`（node_runtime.py:135-158）继续按既有方式浅拷贝顶层 snapshot 并仅去候选 `evidence_indices`，不改其为深拷贝；只新增 `coordinate.ground`（小块，R/t 新建）与 `ground` 摘要 support 字段。缓存 `_latest_valid_snapshot`/`_last_state` 不受投影影响。
3. **support 字段只挂在既有 ground 摘要上**：仅在 `snapshot.ground` 为非 null 时追加 `support_polygon/polyline=null` 与非空 `support_reason`；不新增顶层 support 结构，不改 JS 标签语义。
4. **artifact-only（`ground=None`）仍为 null**：`ground` 入参为 None 时 `snapshot.ground` 保持 null（不加 support 字段），与 `calibration.ground_status="unknown"` 一致；`coordinate.ground` 因 validated derived 仍存在而可读，但 JS 因 `ground_status!="valid"` 判 unqualified，非假 ready。
5. **不改 monitor 与 lost/prediction 既有生命周期**（见 §6）。

## 6. monitor 与 lost/prediction 现有生命周期保留映射（不新增、不回归）

以下为既有测试，本单只保证 additive 字段不破坏它们（新增集中测试从同一夹具同步断言 `coordinate.ground` 与 `ground.support_*`）：

- **ground monitor**：`test_gl03_candidates_geometry.NodeCoordinateTest._trusted_core`（836-840）用 `flat_ground()+calendar trusted_block()`；`test_observed_state_ground_equals_candidate`（874）断言 `core.ground_monitor_report["status"]==MONITOR_OK` 且 `state["ground_derived_id"]==snapshot.coordinate.ground_derived_id`（891-892）——新 `coordinate.ground.ground_derived_id` 必须与之同值；`test_selected_occlusion_never_mislabels_reference_as_source`（915/918）、`test_lost_status_masks_ground_geometry`（933/936）、`test_predicted_reference_box_follows_prediction_or_is_null`（956/963）同样先断言 monitor ok。`test_gl02_ground_frame.test_capture_baseline_refused_when_ground_monitor_unavailable`（334-355）断言 monitor 不可用时基线 `reason=="ground_monitor_unavailable"`——本单不触碰 monitor 判定。
- **prediction（参考系预测/无变换）**：`test_prediction_is_inverse_transformed_into_source`（895-908）参考系预测须逆变换回 source（非 identity）；`test_prediction_without_transform_stays_source_coordinates`（910-913）无 transform 时保持 source 坐标。本单不改 `_prediction_in_source`/reference 解析，`coordinate.ground` 只是把已验证 R/t 另发布，供 JS 显示，不参与预测正逆变换。
- **lost / occluded 清理**：`test_lost_status_masks_ground_geometry`（933-954）lost/ambiguous 时 `center_ground_m/bbox_ground_*=None`、`bbox_ground_from=="unavailable"`；`test_release_without_new_cloud_clears_old_target_geometry`（981-998）、`test_new_selection_without_new_cloud_keeps_binding_without_geometry`（1000-1019）、`test_invalid_frame_masks_ground_and_reference`（1021-1032）同族。这些属 state/候选层，本单只改 snapshot `coordinate`/`ground` 摘要，不涉及；集中测试仅核对无回归。
- **invalid/foreign frame**：`test_foreign_frame_invalidates_and_refuses_select`（1042-1062）、`test_no_valid_derived_yields_unavailable_and_no_id`（614-618）——异 frame/无 derived 时 `coordinate.ground=null`（P02/M03/M08），旧行为（`bbox_ground_from=="unavailable"`）不变。
