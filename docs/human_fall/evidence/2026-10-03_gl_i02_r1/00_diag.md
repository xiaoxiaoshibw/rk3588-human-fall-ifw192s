# GL-I02 R1 阶段一诊断（只诊断；唯一写入本文件）

- 日期：2026-10-03（Asia/Shanghai）。派工：Claude Code（CLAUDE_STANDBY 顶替）；唯一生产 writer：OpenCode `opencode-go/deepseek-v4.1-flash`（default DB）。
- 工单：本单派工文本；唯一验收表 `docs/human_fall/GLI02_ACCEPTANCE.md` v1（SHA `b8e172829d3a84c7da2ec346d4531f986ba83e7ce54131c41b9e592dcd5726bb`）。
- 目标：把 J01–J06 + N01–N07 逐行映射到**实际现有函数/调用点/赋值顺序/副作用点**，给出最小新增文件白名单、候选 vs synthetic 标记路径、关键不变量、draft 格式与最小测试集。**本阶段只写本文件；不写生产/tests/config/contract/state/returns；不 commit/push/reset/checkout/clean；不 board/网络/采集/部署/GL05/driver/webui/ground/calibration 改动；不对真实数据 fit。**
- 工作树：`master`，HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（GL-I01 R1 复审时基线；本轮不动工作树既有差异）。
- ponytail：实际读取本地 `C:\Users\30680\.claude\skills\ponytail\SKILL.md`（SHA256 `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`），强度 **full**；与 GL-I01 R1 记录一致。本单以“复用 GL-I01 R1 prepared NPZ + adapted 函数”为最高 rung，不新增 service、不新增抽象层、不热更新。

## 0. 必要先读（已读，只读）

| 文件 | 关键事实 |
|---|---|
| `GLI02_ACCEPTANCE.md` v1 | J01–J06/B01/D01/D02 + N01–N07；范围冻结；两阶段派工 |
| `evidence/2026-10-03_gl_i01_r1/07_diag_revision.md` §2/§4/§5 | GL-I01 R1 实际函数：`prepare_npz`/`load_adapted`/`gate_selection`/`frame_of_row`/`resolve_group`/`select_group_region`；manifest 三方 digest；link-only 原子 |
| `GLI01_INPUT_CONTRACT.md` | 6 节契约：源格式 / NPZ / 加载 / group-first / constrained / provenance 诚实 |
| `evidence/2026-10-03_next_stage_plan_r1/PLAN_REVIEW.md` §C | “适配器必须先于真实标定生成”；fit + ≥3 独立验证区人工预固定；物理门槛未成立 |
| `evidence/2026-10-03_gl_i01_r1/codex_review_01/CODEX_REVIEW.md` | GL-I01 R1 软件 PASS；四文件 SHA；真实 163621 reload 一致 |
| `scripts/calibrate_sensors.py`（全文） | `load_points:99`、`save_exclusive_json:46`、`run_constrained:238`、`main:447` |
| `core/capture_input.py`（全文） | `classify_npz:107`、`prepare_npz:357`、`load_adapted:466`、`resolve_group:548`、`gate_selection:620`、`build_input_info:682` |

## 1. 只读基线 SHA（本单锚点，未修改）

| 对象 | SHA256 |
|---|---|
| ponytail SKILL（本地） | `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2` |
| `core/capture_input.py` | `56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16` |
| `scripts/prepare_capture_input.py` | `648a8da63a6656b02d169957cede2df4aca3a48e94dcc787c3c48c7f10c5d000` |
| `scripts/calibrate_sensors.py` | `3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785` |
| `tests/test_gli01_capture_input.py` | `50f615d7a5ffdc490f1011b316df30da1e65c958cce93f18ad4cf0c88547030e` |
| `core/ground.py`（冻结） | `2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3` |
| `core/calibration.py`（冻结） | `d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3` |
| 真实 capture `cap_20261002_163621/meta.json` | `675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692` |
| 真实 capture `cap_20261002_163621/points.bin` | `b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff` |

四文件 SHA 与 `codex_review_01/CODEX_REVIEW.md §0` 逐项一致 → **GL-I01 R1 未被改动**。`ground.py`/`calibration.py` 与 GL-I01 记录一致。

## 2. 最小新增文件白名单（严格）

| 类别 | 路径 | 说明 |
|---|---|---|
| (a) thin evaluation script | `src/human_fall_detection/scripts/evaluate_gli02_candidate.py`（新，唯一生产新增） | 仅编排既有 API；不复制 ROI 语义、不做 fit 数学 |
| (b) tests | `src/human_fall_detection/tests/test_gli02_candidate.py` | 覆盖 J01–J06/N01–N07 主要反例（§7 最小集） |
| (c) docs | `docs/human_fall/GLI02_*`（如 `GLI02_CANDIDATE_PLAN.md` / draft 说明） | 本单文档 additions |
| (d) returns | `docs/human_fall/returns/GL-I02.md`（阶段二追加） | 回传统 |

**不做**：不新增 `core/` 模块、不改 `capture_input.py`/`prepare_capture_input.py`/`calibrate_sensors.py`、不新增 config、不改 driver/webui/`captures/remote/`/`ground.py`/`calibration.py`/release YAML/deploy。阶段一**零生产文件**。

## 3. 实际调用链与赋值顺序（entry → 函数 → 顺序 → 副作用点）

拟新增 entry：`evaluate_gli02_candidate.py`。逐点复用 GL-I01 R1 公开 API，**不重写任何已存在逻辑**。

| # | 步骤 | 实际函数/位置 | 赋值/行为 | 副作用点 |
|---|---|---|---|---|
| P0 | 解析参数 | 新 `parse_args` | `--capture-dir` / `--prepared-npz`(可选，复用 GL-I01 prepared NPZ) / `--frame` / `--units` / `--draft`(人工填写) / `--emit-draft`(输出空白草案) / `--source-kind {capture_export,synthetic_fixture}` / `--output` / `--calibration-id` / `--note` | 无 |
| P1 | 适配真实源 | `capture_input.prepare_npz(source_dir, frame, units, output)` `capture_input.py:357` | `read_snapshot`→`read_source_meta`→`validate_frames`→`canonical_source_xyz`→`build_manifest`→`_publish_npz`（temp+fsync+`os.link` exclusive） | **写 adapted NPZ**（本单命名空间）；`captures/remote/` 只读 |
| P1' | 复用已适配 | `capture_input.load_adapted(npz)` `:466` | 重读实际源、三方 digest、逐帧 group 复算；`(canonical, points)` | 无 |
| P2 | 帧声明核对 | `capture_input.check_declared_frame(manifest, frame)` `:503` | CLI frame 必须 == manifest.declared.frame | 无 |
| P3 | 读人工选区 | 读 draft JSON（本单格式，§5） | 取 `up_axis`/`sensor_height_interval_m`/`fit_region`+`fit_frame_group`/`validation_regions`；缺任一 → exit 2，**无 fallback** | 无 |
| P4 | group-first 门 | `capture_input.gate_selection(points, manifest, fit_region, fit_indices, fit_frame_group, regions)` `:620` | 内部 `resolve_group:548`→`select_group_region:569`→`frame_of_row:513`；fit 帧集与各 validation 帧集不交、≥3 validation、region_id 唯一；返回 `(fit_rows, resolved_regions)` | 无（纯函数） |
| P5 | 约束拟合 | `ground.fit_ground_plane_constrained(points, settings=resolved, frame, up_axis, sensor_height_interval_m, fit_indices=fit_rows, fit_frame_group, validation_regions=resolved_regions)` `ground.py:597` | `resolve_constrained_settings`；`_unit_vector`；`_height_interval`；valid_index；fit/region 交集；标签/帧组一致性；RANSAC+逐区门 | 无（纯计算，不写） |
| P6 | 拟合结果校验 | `ground.validate_constrained_ground(result, expected_frame=frame)` `ground.py:1031`；`ground.ground_is_valid(result)` `:284` | result None 或非 valid → exit 2，**无 artifact** | 无 |
| P7 | input provenance | `capture_input.build_input_info(manifest, draft_path, None, draft_path)` `:682` | 组装 `source/constrained/frame/units/point_count/sha256/input_manifest{...}`；`source_kind=synthetic_fixture` 时覆盖 `input_info["source"]="synthetic_fixture"`（否则 `"capture_export"`） | 无 |
| P8 | 组装 artifact | `calibration.build_geometry_calibration(...)` `calibration.py:1210` | `statuses={"ground":"candidate","geometry_params":"candidate"}`；随后 `artifact["constrained_ground"]=result`；`validate_geometry_calibration(artifact)` `:1075` | 无 |
| P9 | 独占落盘 | `calibrate_sensors.save_exclusive_json(output, artifact)` `calibrate_sensors.py:46` | temp→`json.dump(allow_nan=False)`→`os.link` exclusive；已存在/竞争 → 拒且保留旧件 | **写 artifact JSON**（独占） |
| P10 | draft 落盘 | 新 `save_exclusive_json(draft_out, draft)`（复用同一 helper） | 空白/人工草案独占写 | **写 draft JSON**（独占） |

- **exclusive 点**：P1（adapted NPZ，`_publish_npz:383`）与 P9/P10（`save_exclusive_json:46`）三处均硬 `os.link` 独占；目标已存在即拒，不覆盖。
- **副作用边界**：仅 P1、P9、P10 三个写点，全部指向本单命名空间（建议 `docs/human_fall/evidence/2026-10-03_gl_i02_r1/` 或调用者显式路径）。`captures/remote/`、`ground.py`、`calibration.py`、生产 config、driver、webui、deploy 零写。
- **candidate vs synthetic**：`--source-kind capture_export`（默认）→ `artifact.input.source="capture_export"` + `artifact.status.ground="candidate"`；`--source-kind synthetic_fixture` → `artifact.input.source="synthetic_fixture"` + 独立输出命名空间，**永不混用**。两者都走同一 strict adapted route，`physical_verified` 恒 false。

### 3.1 关键设计张力（必须先由 Codex 裁决）

1. **`ground.status="candidate"` 的落点**：`GROUND_STATUSES`（`calibration.py:46`）= `("valid","orientation_unverified","invalid")` 约束的是 **ground 记录自身** `artifact["ground"]["status"]`（由 `validate_ground_plane`/`validate_constrained_ground` 校验）；而 `artifact["status"]["ground"]` 无枚举校验（`:1066-1071` 只拒 `=="valid"` 与 ground 记录矛盾）。因此：
   - 读法 R-a：`artifact["status"]["ground"]="candidate"` —— **schema 合法**，wrapper 传 `statuses={"ground":"candidate"}` 即可（`calibration.py:1241` 只因 ground 记录 `status!="valid"` 强制置 `"unknown"`，此处 ground 记录 status 为 `"valid"`，故 `"candidate"` 保留）。
   - 读法 R-b：`artifact["ground"]["status"]="candidate"` —— **schema 非法**（ground 记录枚举不允许），不编辑冻结 `ground.py` 无法实现。
   - 既有 adapted CLI（`calibrate_sensors.py:324`）硬编码 `statuses={"ground":"valid","geometry_params":"candidate"}`，产出的是 `status.ground="valid"`，**不满足 N01 字面**。
2. **“走 adapted CLI” vs “直接调用 API”**：J01 说“走 prepare+adapted CLI”，但白名单禁改 `calibrate_sensors.py`；若要字面 `status.ground="candidate"`，新 wrapper 必须**直接编排** `load_adapted`/`gate_selection`/`fit_ground_plane_constrained`/`build_geometry_calibration`（全部为 GL-I01 R1 及 core 既有公开函数），或把 adapted CLI 的成功产物再改状态（不可，无写前钩子）。推荐直接编排（仍是 thin wrapper，不新增 ROI 语义）。
3. **`physical_verified=false` 的落点**：artifact 无顶层 `physical_verified`。实际为 `artifact.verification.ground_physical_verified=false`（`default_verification:1205`）+ `artifact.input.input_manifest.provenance.physical_verified=false`（`build_input_info:698`）。J01 字面“artifact 中 physical_verified=false”需在验收复核时按这两处核对。
4. **N06 文案残缺**：“非 adapted → reference`、`--constrained`；adapted → strict reject” 语义不通。按 `07_diag_revision` R4 的既有实现理解：adapted 输入在非 constrained 下**任何写前 return 2**；legacy 普通 points 走 legacy/`--constrained`。请 Codex 确认 N06 的目标行为。
5. **`build_manifest` 在 J05 被列为“只调用”清单**，但 `calibrate_sensors` 不调用它；若新 wrapper 需要它（例如生成 draft 的 frame_groups 摘要）可调用，否则不引入。

## 4. J01–J06 逐条映射

| ID | 要求 | 本诊断对应（入口/反例/补充诊断） |
|---|---|---|
| J01 | 真实 163621 → prepare+adapted → candidate artifact（schema v1），`status.ground="candidate"`、`physical_verified=false`、provenance 兼容 GL-I01 R1；不写 GL02 生命周期/派生状态机 | 入口 P0–P9；`prepare_npz`+`load_adapted`+`gate_selection`+`fit_ground_plane_constrained`+`build_geometry_calibration`；`statuses={"ground":"candidate"}`（读法 R-a，见 §3.1）；**不传 `--ground-derived`**（`calibrate_sensors.py:211/306`），artifact 无 `GROUND_DERIVED_KEY`；不调用任何 GL02 状态转移 |
| J02 | 全只读 + 不动 `captures/remote/`；中间产物本单命名空间 | P1 只 `read_snapshot`；写点仅 P1/P9/P10 指向调用者命名空间；诊断后重算 `meta.json`/`points.bin` SHA 与 §1 比对（测试 T7） |
| J03 | synthetic 与真实严格分开，synthetic `synthetic=true`/`source=synthetic_fixture`；真实不混 synthetic | `--source-kind` 显式标签（P7）；synthetic 输出独立命名空间；manifest 本身无 synthetic 位（`capture_input` 一律 metadata_declared），故标签只加在 artifact `input.source`（不改 manifest） |
| J04 | freeze 前 ROI/fit/≥3 validation/up_axis/sensor_height_interval 以 draft JSON 记录，供人工决断；缺项**不自动 fallback 选地面** | P3 读 draft、P10 写 draft；缺 fit selector/frame_group/<3 validation/up_axis/height → gate_selection 或 wrapper 前置校验 exit 2；draft 格式 §5 |
| J05 | 新 entry 只调用 GL-I01 R1 公开 API（`prepare_npz`/`load_adapted`/`gate_selection`/`build_manifest`），不新增 ROI 语义；不兼容输入非零退出且无 artifact；GL-I01 严格拒绝语义保持 | P1–P4；`gate_selection` 保持 group-first（`:620`）不自实现 bounds；非 adapted/manifest 损坏沿 `classify_npz:107` + `load_points:99` 拒；回归 T5 + N05 跑 GL-I01 62 + 24 探针 |
| J06 | 白名单 (a)(b)(c)(d)，GL-I01 四文件 SHA 不变 | §2 白名单；阶段一零生产；阶段二完成后重算四文件 SHA 对照 §1 |

## 5. `capture_selection_draft.json` 草案格式（J04/N07）

```json
{
  "schema": 1,
  "kind": "gli02_capture_selection_draft",
  "status": "pending_human_review",
  "source_kind": "capture_export",
  "source": {
    "capture_dir": "<abs>",
    "meta_sha256": "<hex>",
    "bin_sha256": "<hex>",
    "frame": "innolidar",
    "units": "m",
    "time_domain": "<meta.time_domain>",
    "adapted_npz": "<abs or null>",
    "manifest_points_sha256": "<hex or null>"
  },
  "frame_scope": {"total_points": 4372400, "frames": 89, "frame_groups": ["frame:<sha24>", "..."]},
  "up_axis": null,
  "sensor_height_interval_m": null,
  "fit_region": {"frame_group": null, "indices": null, "bounds": null},
  "validation_regions": [],
  "default_refusal": "no_auto_ground_selection",
  "review": {"required": true, "by": null, "at_utc": null}
}
```

- `status` 恒为 `pending_human_review`；`up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions` 由人工填入。
- **缺省拒绝行为**：任一必填为 null（fit_region.frame_group、<3 validation_regions、up_axis、sensor_height_interval_m）→ wrapper exit 2、不写 artifact；**绝不**用整帧/整 pool/默认重力轴 fallback 选地面。
- `source_kind=synthetic_fixture` 时 draft 与 artifact 都标 synthetic，且写独立命名空间。
- 草案为 print/`save_exclusive_json` 独占写，不覆盖历史 draft。

## 6. 关键不变量

- GL-I01 R1 四文件 SHA **不变**（§1）；`ground.py`/`calibration.py` SHA 不变。
- `captures/remote/` 只读；所有写点在本单命名空间。
- adapted 输入仍走 strict route：`classify_npz` 内容判定、`load_adapted` 三方 digest + 逐帧 group 复算；含 marker 损坏**绝不**回退 legacy。
- 新 evaluation 不触碰 `ground.py`/`calibration.py`/生产 config/driver/webui/deploy/release YAML/`capture_server.py`。
- provenance 诚实：`point_index_domain=capture_export_row`、`original_bag_point_index=unknown`、`source_bag_hash_verified=false`、`physical_verified=false`、frame/units=`metadata_declared`。
- 不启动 ROS/板端网络；不做真实 fit；不预设 up_axis/sensor_height 完整值。

## 7. 本单最小测试集（`tests/test_gli02_candidate.py`，目标 8 项，>10 有风险）

| T | 覆盖 | 断言 |
|---|---|---|
| T1 | J01/N01 | synthetic adapted NPZ（7 帧、2000 点、3 独立区）→ artifact schema v1；`status.ground=="candidate"`；`verification.ground_physical_verified is False`；无 `ground_derived`；exit 0 |
| T2 | N02/J04 | draft 缺 fit/validation/up_axis/height → exit 2；无 artifact；不覆盖既有 draft |
| T3 | N03 | 目标 artifact 已存在 → exit 2；旧文件保留（`save_exclusive_json` exclusive） |
| T4 | N04/J03 | synthetic fixture → `input.source=="synthetic_fixture"`；独立命名空间；真实 candidate 不被混入 |
| T5 | N06/J05 | 非 adapted 普通 NPY/NPZ 走本 entry → strict reject（不静默 fit）；adapted 严格拒绝语义保持 |
| T6 | N07/J04 | draft 输出含 `up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions` 且 `status=="pending_human_review"`/`default_refusal` |
| T7 | J02 | 全流程后 `captures/remote/cap_20261002_163621` 两文件 SHA == §1；目录下无新文件 |
| T8 | J05/J06 | wrapper 仅 import GL-I01/core 公开 API（import 审计）；不复制 ROI/bounds 逻辑 |

（N05 的“GL-I01 62 + Codex 24 探针回归 + SHA 对照”属阶段二运行验证，不写成单元测试。）

## 8. 停写矩阵

### 8.1 验收条目映射

| ID | 本诊断如何对应 | 状态 |
|---|---|---|
| j01 | §3 P0–P9；§3.1 张力 1/2/3；入口 `prepare_npz`→`build_geometry_calibration`；T1 | 设计已映射，待裁决 candidate 落点 |
| j02 | §3 副作用边界；§6 不变量；T7 | 已映射 |
| j03 | §3 candidate vs synthetic；`--source-kind`；T4 | 已映射 |
| j04 | §5 draft 格式 + 缺省拒绝；P3/P10；T2/T6 | 已映射 |
| j05 | §2 白名单；P1–P4 复用公开 API；T5/T8；阶段二 N05 回归 | 已映射 |
| j06 | §1 SHA 表；§2 白名单；T8 | 已映射 |

### 8.2 操作/消费者矩阵（entry → 实际函数 → 赋值顺序 → 副作用点）

| 行 | entry → 实际函数 → 赋值顺序 → 副作用点 |
|---|---|
| n01 | `evaluate_gli02_candidate --capture-dir 163621` → `prepare_npz:357`(写受控 NPZ) → `load_adapted:466` → `gate_selection:620`(fit_rows, resolved_regions) → `fit_ground_plane_constrained:597` → `validate_constrained_ground:1031` → `build_input_info:682` → `build_geometry_calibration:1210`(`statuses={"ground":"candidate"}`) → `save_exclusive_json:46`（写 artifact，独占）。候选字段命名 `gli02_candidate_<ts>`；不写生产 config |
| n02 | P3 缺 fit/frame_group/validation/up_axis/height → `gate_selection:620` 或 wrapper 前置 → exit 2，无 artifact；无自动 fallback |
| n03 | P9 `save_exclusive_json:46` `os.link` EEXIST → 拒，旧件保留 |
| n04 | `--source-kind synthetic_fixture` → P7 覆盖 `input.source="synthetic_fixture"` → 独立命名空间 → P9；与真实 candidate 分离 |
| n05 | 阶段二：`unittest discover … test_gli01_capture_input`（62）+ Codex 24 探针 + 四文件 SHA 对照 §1 |
| n06 | 非 adapted → `classify_npz:107=="legacy"` → wrapper 明确拒绝/导向既有 `--constrained`；adapted → strict route（`load_adapted:466`）；wrapper 不复制 legacy restricted path（待 Codex 确认残缺文案） |
| n07 | P10 写 draft：`up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions` + `status=pending_human_review` 标签 |

### 8.3 不触碰边界确认

| ID | 确认 |
|---|---|
| b01 | 原袋 width/height/original_count 仍缺；`prepare_npz`/`load_adapted` 不生成 cited 原袋行索引；维持 BLOCKED，本单不伪造 |
| d01 | 不启真实物理/设备/板端/性能/GL05/部署/采集/网络；本单纯本地软件 |
| d02 | 不涉 GL04 真实 DPR/正式页；不属本单 |

## 9. 结论

- J01–J06 / N01–N07 已逐行映射到实际函数与赋值顺序；新增仅一个 thin evaluation script + tests + docs + returns。
- 最大待决项：J01/N01 字面 `ground.status="candidate"` 与冻结 schema 的落点（§3.1 张力 1/2），以及 J01/N01 的 `physical_verified=false` 与“adapted CLI”措辞；N06 文案残缺。以上请 Codex 设计复审裁决后再发阶段二。
- 本阶段**只写本文件**；未写任何 source/tests/config/contract/state/returns；未 commit/push/reset/checkout/clean；未 board/网络/采集/部署/模型/DB/global config；未对真实数据 fit。

READY_FOR_DESIGN_REVIEW
