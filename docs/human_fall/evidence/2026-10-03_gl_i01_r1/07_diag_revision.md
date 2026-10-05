# GL-I01 R1 阶段一修订诊断（依 06_DESIGN_REVIEW 裁决，仍只诊断）

- 日期：2026-10-03（Asia/Shanghai）。工单 `AI_PROMPT_GLI01_OPENCODE_R1_DIAG.md`；唯一表 `GLI01_ACCEPTANCE.md` v1；`PLAN_REVIEW.md`；**`06_DESIGN_REVIEW.md` 覆盖初版 00_diag 冲突设计**。
- 状态：`06_DESIGN_REVIEW` 判定初版设计 REWORK_DESIGN（准软件实施的只有本轮修订版）。初版 `00_diag.md` 作为写前事实保留不覆盖。
- 本轮只写 `07_diag_revision.md`；不写/不改任何 source/tests/config/contract/state/returns；不 commit/push/reset/checkout/clean；不 board/网络/采集/部署/GL05/模型/DB/global config；真实 capture 只 read/hash/count，不 fit/ROI/物理结论。
- ponytail：实际读取本地 `C:\Users\30680\.claude\skills\ponytail\SKILL.md`（与本轮副本同 SHA `1316a2f3…`），full；本轮聚焦最小修订，不新增抽象。

## 0. 只读基线与 SHA（未修改）

| 对象 | SHA256（前缀） |
|---|---|
| ponytail SKILL（本地=副本） | `1316a2f3f95741d2…` |
| `calibrate_sensors.py` | `07046d89124b6693…`（与初版一致） |
| `core/ground.py` | `2d25ccfd9b41b4e1…`（与初版一致） |
| `src/human_capture/core/bag2session.py` | `e3c3a62cd581650c…`（与初版一致） |
| `AI_PROMPT_GLI01_OPENCODE_R1_DIAG.md` | `76e9787fd168cf2b…` |
| `GLI01_ACCEPTANCE.md` | `326894fdf2ee0e8d…` |
| `PLAN_REVIEW.md` | `ed95f617014bd401…` |
| `06_DESIGN_REVIEW.md` | `fa92915fed07c77f…` |

真实数据事实沿用初版 §1.4（不改）：163621 = 89 帧 / 4372400 点 / 0 drop / bin 精确 122427200 B / meta SHA `675c23de…` / bin SHA `b81797f9…` / 89 帧 offset 连续 / 零点≈673315（15.4%）；另 3 原始会话零丢；clip 会话 `human_replay_trim/0.1` 无 `source_bag_sha256`/drop → 拒绝。

## 1. 06_DESIGN_REVIEW 裁决对初版的覆盖（逐条）

| # | 裁决 | 对初版 00_diag 的改动 |
|---|---|---|
| R1 | prepare 只 `--source-dir`（固定 meta.json+points.bin）、`--frame` required、`--units` required 且仅 `"m"`、`--output`；无默认 innolidar/m，无任意 `--meta/--bin/--groups`；meta.frame 非空且一致，meta.units 若有记录须一致，unknown 拒绝；始终 metadata_declared/physical false | 删初版 `--meta/--bin` 与 `--groups`；新增 units 声明与 unknown 拒绝 |
| R2 | 固定每帧一个 group，无 caller 分区/alias；group ID 由 path-independent 源内容身份+frame ordinal/seq/stamp 确定性公式生成，成员为完整 frame range；loader 重建并核公式与完整 ordered members；独立仅指源帧集合不交 | 删初版任意 `frame_groups` 分区；改为确定性逐帧 group |
| R3 | loader 读实际 meta/bin 重建 canonical source XYZ f4，NPZ points 必须精确 Nx3/little-endian f4、无 object/额外列/静默转换；源 XYZ digest == NPZ 原 points 字节 digest == manifest 期望 digest；meta/bin SHA、layout、声明/unknown flags、frames/group 逐层核；只核自身 3 个声明 hash 不算防伪；缺源拒绝 | 新增“三方相等”与禁静默转换；hash 校验从“自洽”升为“重读实际源” |
| R4 | 所有入口识别 manifest key；adapted 只允许 constrained；非 constrained 在任何写前 return2；含 marker 损坏绝不 fallback；无 key 普通 points 仍旧行为，不给 adapted lineage 资格 | 初版只在 run_constrained 探测 → 改为 main + 共享 `load_points` 双入口 |
| R5 | 保留 selector 类型、group-first：bounds 先限实际成员再做坐标 bounds，映回 pooled 原行；组外坐标命中不算错误；显式 pooled indices 必须都在声明 group，越组拒绝；fit/val 同 helper；禁止先在全 pool 变 indices 丢类型；缺 selector/group/priors 或 <3 显式 validation 拒绝；ground 仍校隔离不改数学 | 初版 M09“跨 pool bounds 既通过又拒绝”删除；改为 group-first 单一路径 |
| R6 | adapted 首版拒绝 `--diagnostics`（写前明确错误）；完整诊断在 `artifact.constrained_ground`；旧普通 points diagnostics 原义不变；所有 source/selection/fit/export/derived/reference_axis/完整 artifact 验证在首写前；adapted invalid fit 与缺导出条件 return2 无 artifact；成功只发一个 immutable calibration JSON；不声称两路径事务原子 | 初版允许 diagnostics → adapted 拒绝；强调单输出 |
| R7 | 新 NPZ 只用同目录完整 temp+flush/fsync+`os.link` exclusive publish，无此能力明确拒绝，**不降级 O_EXCL 拷贝**；adapted calibration 仅在支持 link 时复用现 `save_exclusive_json`（旧 legacy fallback 不改），预校完整 JSON 后单输出；构造/输入/算法拒绝在写前；目标竞争保留已有；temp 清理只动自身 | 删初版 M11 的 O_EXCL fallback；link 为硬条件 |

不保留项：初版 M09 跨 pool 双行为、初版 M11 O_EXCL fallback。已核事实：初版 `run_constrained` 只探测 manifest、prepare 漏声明/自定义 groups 无 canonical、旧 invalid 先写 diag——均由本轮修订替换/修正。

## 2. 修订后新增接口（纯文件，不改 ground/runtime/config/driver/webui/采集器）

### 2.1 `core/capture_input.py`（stdlib+NumPy，Python3.8，无 ROS/replay/采集器导入）

- 常量：`MANIFEST_KEY="input_manifest"`、`SCHEMA=1`、`FORMAT="human_capture_session"`、`FORMAT_VERSION=1`、`TOOL="bag2session/0.1.0"`、`STRIDE=28`、`ROW_DTYPE`（同 `bag2session:104-113`）、`UNITS="m"`。
- `class CaptureInputError(ValueError)`。
- `sha256_file(path)`：分块 sha256（同 `calibrate_sensors.sha256_file:88` 语义）。
- `classify_npz(path)` → `"legacy" | "adapted"`：`np.load(allow_pickle=False)`；非 NPZ 或 NPZ 无 `input_manifest` → `legacy`；有 key → `adapted`；**有 key 但值非标量 str/非 JSON/非 dict/schema 不符 → 抛 `CaptureInputError`（绝不回退 legacy）**。
- `read_source_meta(meta_path, declared_frame, declared_units)`：严格 JSON；校验 format/version/tool/layout(fields/dtypes/stride/endian/pad) 逐字段；`sensor.frame_id` 非空且 ==declared_frame；`units` 若有须 ==declared_units，类型未知拒绝；`extraction.tool`/`total_dropped_points`。
- `validate_frames(meta)`：`seq/stamp_sec/stamp_nanosec/offset_points/count_points` 严格 int（拒 bool/float/str），`0<=nanosec<1e9`、`sec>=0`；offset 从 0 连续、`offset[i+1]==offset[i]+count[i]`；`sum(count)==total_points`；`dropped_points==0` 且 `total_dropped_points==0`。
- `canonical_source_xyz(meta, bin_path)`：按 frame 原序读全行 XYZ（little-endian f4），**不滤零点/不重编号**；校验 `size==total*28`；空帧 count=0 仍占一条 frame 记录。
- `source_identity(meta, bin_path)`：`sha256(bin_sha256_hex + "|" + meta_sha256_hex)`（path-independent 内容身份）。
- `frame_group_id(identity, frame)`：`"frame:"+sha256(identity+"|"+ordinal+"|"+seq+"|"+stamp_sec+"|"+stamp_nanosec).hexdigest()[:24]`。
- `build_manifest(meta, bin_path, frame, units)`：生成上方 schema（见 §3）；`frame_groups` 为逐帧一项，成员 `rows=[offset, offset+count)`；三条 hash（源 XYZ digest / NPZ points digest / manifest 期望 digest）在此确定。
- `prepare_npz(source_dir, frame, units, output)`：`read_source_meta`→`validate_frames`→`canonical_source_xyz`→`build_manifest`→同目录 temp `np.savez`（仅 `points`+`input_manifest` 标量 Unicode JSON）→flush+fsync→`os.link(temp,output)` exclusive；**无 `os.link` 直接拒绝**；EEXIST/失败删除仅自身 temp。
- `load_adapted(npz_path, declared_frame)`：`classify==adapted`；从 manifest.source 的 canonical meta/bin 路径重读实际源；重核 meta/bin SHA、bin size、layout、声明/unknown flags、frames；用 `canonical_source_xyz` 重建；**三方 digest 相等**（实际源 XYZ == NPZ `points` 原字节 == manifest）；重新计算 `frame_groups` 公式与完整 ordered members 并要求与 manifest 完全一致；NPZ `points` 必须精确 `(N,3)` little-endian f4，无 object/额外列/静默转换；源不可达/任一层不符 → `CaptureInputError`。
- `frame_of_row(ctx)`：由连续 frame rows 边界（含空帧零宽）经 `searchsorted` 得每 pooled 行的 frame ordinal。
- `resolve_group(ctx, group_id)`：group_id 必须为 manifest 中确定性 id；返回该帧完整成员 pooled 行区间；别名/未知 id 拒绝。
- `select_group_region(ctx, region)`（**group-first，保留 selector 类型**）：先取 `region["frame_group"]` 的完整帧成员行；若 selector 为显式 `indices`（pooled）→ 每个必须落在成员集，越组拒绝，返回唯一 pooled 行；若为六界 → 仅在成员子集上做坐标 bounds，返回命中的 pooled 原行；组外坐标即使满足 bounds 也不计入、不报错。fit 与 validation 共用此 helper。
- `gate_selection(ctx, declared_frame, fit_frame_group, fit_region_or_indices, validation_regions)`：fit selector 与 fit group 必有，否则拒绝；`resolve_group` 校验各 `frame_group` 合法；逐 region 调 `select_group_region`；要求 fit 帧集与每个 validation 帧集不交、validation 之间不交；region_id 唯一；≥3 validation；缺任一 → `CaptureInputError`。返回 pooled 原行的 fit indices 与带 `indices` 的 regions，供既有 ground 调用。

### 2.2 `scripts/prepare_capture_input.py`

- `parse_args`：`--source-dir`（required，固定 `meta.json`+`points.bin`）、`--frame`（required）、`--units`（required，仅 `"m"`）、`--output`（required）；无其它扩展。
- `main`：调 `capture_input.prepare_npz`；成功打印 manifest 摘要（计数/hash），失败非 0 退出且无半截目标。

### 2.3 `calibrate_sensors.py` opt-in 接线（不改 ground 数学）

- `parse_args:157`：adapted 相关仅在 constrained 组内新增/复用；`--diagnostics:193` 对 adapted 在写前明确拒绝。
- `load_points:96`（共享入口）：先 `capture_input.classify_npz`；`adapted` → 抛 `CaptureInputError`（不再静默 legacy）；`legacy` → 原逻辑不变（I08/M07）。
- `main:337`：`args.points` 为 adapted 且**非** `--constrained` → 任何写前 `print`+`return 2`（R4）；otherwise 原路径。
- `run_constrained:222`：`--bag` 拒绝（:224）后；adapted 用 `load_adapted`+`gate_selection`，legacy 用 `load_input:204`；先做 output/diagnostics 存在性预检（:245）；adapted 拒绝 `--diagnostics`；`fit_ground_plane_constrained:597`/`validate_constrained_ground:1031` 调用**不变**；完整 source/selection/fit/export/derived/reference_axis/artifact 验证在 `save_exclusive_json(args.output):318` 之前；adapted 先确认 `os.link` 可用，否则写前拒绝。

## 3. 修订 manifest（NPZ 仅 `points` + `input_manifest` 标量 Unicode JSON）

```
{ "schema":1, "kind":"capture_input_adaptation",
  "source": {"format":"human_capture_session","format_version":1,
             "tool":"bag2session/0.1.0",
             "meta_path":<canonical abs>,"bin_path":<canonical abs>,
             "meta_sha256":..,"bin_sha256":..,"bin_size_bytes":..,
             "total_points":..,"total_dropped_points":0,
             "source_bag_sha256_declared":..,"source_bag_hash_verified":false},
  "layout": {"fields":..,"dtypes":..,"stride_bytes":28,
             "endian":"little","pad_offsets_bytes":[18,24]},
  "frames":[{"ordinal":i,"seq":..,"stamp_sec":..,"stamp_nanosec":..,
             "bag_time_sec":..,"offset_points":..,"count_points":..,
             "dropped_points":0}, ...],
  "frame_groups":{"<deterministic gid>":{"ordinal":i,"seq":..,
                  "stamp_sec":..,"stamp_nanosec":..,"rows":[off,off+count)}, ...},
  "points":{"key":"points","dtype":"<f4","shape":[N,3],"sha256":..},
  "declared":{"frame":<--frame>,"frame_provenance":"metadata_declared",
              "units":"m","units_provenance":"metadata_declared",
              "time_domain":<meta.time_domain>},
  "provenance":{"point_index_domain":"capture_export_row",
                "original_bag_point_index":"unknown",
                "source_bag_hash_verified":false,"physical_verified":false} }
```

不变量：一个 bundle 一份完整 source；`frame_groups` 为逐帧确定性映射（成员=完整该帧 pooled 行，空帧零宽）；group id 只由内容身份+帧字段决定，与路径无关；`points.sha256` 对 little-endian f4 规范字节；units/frame 恒 metadata_declared，physical 恒 false。

## 4. M01–M13 更新后的实际函数/顺序/检查矩阵

| ID | 操作×消费者 | 实际函数/顺序 | 设计（声明/身份/hash/时间/索引/绑定/副作用/原子） | fit/validation 实际帧隔离 | 检查（正/负） | 覆盖 |
|---|---|---|---|---|---|---|
| M01 | valid 多帧 export→NPZ→constrained loader | `prepare.main`→`read_source_meta`→`validate_frames`→`canonical_source_xyz`→`build_manifest`→`prepare_npz`；`main:337`→`classify_npz`→`run_constrained:222`→`load_adapted`→`gate_selection`→`fit_ground_plane_constrained:597`→`validate_constrained_ground:1031`→`save_exclusive_json:318` | 仅 `--source-dir/--frame/--units(m)/--output`；帧原序全行 XYZ f4；整数帧时间与 seq/time_domain/bag_time 各自来源；逐帧确定性 group；meta/bin/points 三级绑定；唯一 NPZ，temp+fsync+`os.link` exclusive（无 link 拒绝）；构造/校验全部在写前 | group=帧；loader 重建 `frame_of_row` 与 `resolve_group`；fit/val 帧集不交由 gate 核 | 正：N/行序/整数帧时间/声明 frame+units/三级 digest 一致且成功只发一个 JSON；负：任一不符拒绝 | I01/02/03/04/07 |
| M02 | zero XYZ / 帧首尾边界 / 不同 count / 空帧 | `canonical_source_xyz`；`validate_frames`；`frame_of_row`；`fit_ground_plane_constrained:614-617` | 零点保留原行、不预滤不重编号；空帧 count=0 占一条 frame/group（rows 零宽），offset 不减；range 不重排；`valid_index` 仅排除零/非有限但索引映射为 pooled 原行 | 空/边界帧归属其自身 group；索引仍 pooled | 正：零点行存在、空帧不伪点、边界 count 正确；负：把空帧当截断/重编号拒绝 | I01/02 |
| M03 | meta/bin 截断 / 尾数据 / overlap / gap / total 矛盾 | `validate_frames`；`read_source_meta`；`prepare_npz` 预检 | `size==total*28`；offset 连续从 0；`sum==total`；`dropped==0`；尾多/缺口/重叠拒绝；**构建/写前拒绝，无副作用** | 分区源于连续帧，损坏则无法建 group | 正：163621 精确通过；负：截断/多字节/空洞/重叠/total 不符拒绝且无输出 | I01/06 |
| M04 | unknown 格式 / version / layout / endian / clip / drop | `read_source_meta`；`prepare_npz`；`load_adapted` | format/version/tool/layout 逐字段精确；`total_dropped==0`；clip（`human_replay_trim`，无 `source_bag_sha256`/drop）拒绝；不猜格式、不提物理资格 | layout 不符无合法帧映射 | 正：4 原始会话通过；负：clip、改 version/stride/endian/drop 拒绝 | I01/07 |
| M05 | bool/float/string count/seq/stamp、非法 ns/frame/units | `read_source_meta`；`validate_frames`；`gate_selection` | 严格 int 类型（拒 bool/float/str）；`0<=nanosec<1e9`、`sec>=0`；`--frame` 与 meta.sensor.frame_id 一致；`--units` 仅 `"m"` 且与 meta.units（若有）一致；不从 f4 点 timestamp 恢复 ns、不混算时钟；CLI 与 manifest frame 冲突拒绝 | frame/units 校验先于 group 解析 | 正：真实整数帧时间通过；负：float count、string stamp、ns=1e9、units≠m、frame 冲突拒绝 | I01/03/06 |
| M06 | 改 source/meta/bin/points/manifest/members/group 后 reload | `load_adapted`；`canonical_source_xyz`；`frame_group_id`；`classify_npz` | loader 重读实际源：meta/bin SHA、bin size、layout、声明/unknown flags、frames 逐层；**三方 digest 相等**（实际源 XYZ / NPZ 原字节 / manifest），禁静默转换；重算 group 公式+完整 ordered members 必须一致；含 marker 损坏绝不 fallback；缺源/路径不可达拒绝，不从 hash 串推断 | 改 group 名/成员不能自报通过（公式+成员重核） | 正：未改可加载；负：改任一级/缺源/别名/伪造 manifest 拒绝 | I04/06 |
| M07 | ordinary legacy NPY/NPZ（无 manifest）→ 现入口 | `classify_npz`；`load_points:96`；`main:337`；`run_constrained` | 无 `input_manifest` key → `legacy`；`load_points`/`load_input` 原逻辑与返回不变，不要求 capture source，也不给 adapted lineage 资格 | 不适用 | 正：普通 `.npy`/无 manifest `.npz` 行为与既有回归一致；负：新增适配不改 legacy | I08 |
| M08 | fit/val 点交叉 或 同源帧不同 group 名 | `gate_selection`；`resolve_group`；`select_group_region`；`fit_ground_plane_constrained:661-695`；`validate_constrained_ground:1113` | 无任意 groups：逐帧一个确定性 id，caller 不得自定义/别名；region.frame_group 必须是 manifest id；显式 pooled indices 必须全在该 group 成员行，越组/未知 id 拒绝；fit 帧 != 各 validation 帧且 validation 间帧不交；点交叉在 gate 与 ground 双检；**失败不写输出** | 实际帧集为唯一依据，标签不可绕过 | 正：真不相交帧通过；负：同帧异名、点交叉、未声明组、越组 indices 拒绝，无 output/diagnostics | I04/05/06 |
| M09 | bounds across pooled frames + group 限制（修订） | `select_group_region`；`region_indices:504`；`_balanced_sample:542` | **group-first 单一路径**：先限声明 group 的完整帧成员，再在成员子集上做坐标 bounds，映回 pooled 原行；组外坐标命中不计入、不报错；不做全 pool→indices 的预转换；fit 与 validation 同 helper；索引仍 pooled、无残差预筛 | fit 同样先限实际 group 成员 | 正：bounds 只命中本帧成员且返回 pooled 原行；负：显式 pooled indices 越组拒绝；不按残差预筛 | I02/05 |
| M10 | missing ROI/group/priors/<3 validation 区域 | `gate_selection`；`fit_ground_plane_constrained:658-699`；`run_constrained:224-235` | 缺 fit selector/fit group/up/height 或显式 validation <3 → 明确拒绝/现有 invalid；**绝不自动选地面**；adapted 缺显式选择在任何写前 return2 | group 缺失无法建实际帧集 | 正：显式提供通过；负：缺任一先验/组/<3 区拒绝 | I05/06/07 |
| M11 | output exists / 失败 / 重复写 / 竞争出现目标（修订） | `prepare_npz`；`save_exclusive_json:43`；`run_constrained:245-249,318-321` | NPZ 同目录 temp+flush/fsync+`os.link` exclusive；**无 `os.link` 明确拒绝，不降级 O_EXCL 拷贝**；adapted calibration 仅在支持 link 时复用 `save_exclusive_json`（旧 legacy fallback 不改）；预校完整 JSON 后单输出；目标竞争保留已有；temp 清理仅自身 | 不适用 | 正：新路径原子成功、单产物；负：已存在/竞态/无 link/写失败拒绝，旧/半截产物不受影响 | I06/08 |
| M12 | adapted CLI 成功+失败 → artifact input provenance | `run_constrained:204-321`；`build_geometry_calibration`；`input_info` | adapted 写前拒绝 `--diagnostics`；成功只发一个 immutable calibration JSON，`input_info` 带实际 source/hash/frame-group map 与 provenance；完整诊断在 `artifact.constrained_ground`；旧普通 points diagnostics 原义不变；invalid fit/缺导出条件 return2 无 artifact；不声称两路径事务原子；physical 恒 false | 记录的 group/frame map 与实际一致 | 正：成功含实际 map/hash 且单产物；负：失败无副作用、diagnostics 被拒；provenance 不冒充已核 | I04/05/06/07/08 |
| M13 | 真实 163621 全 89 帧 4372400 行 → 适配/加载 | `prepare_npz`；`load_adapted` | 只读；诚实记录 total=4372400/89 帧/zero≈673315/time_domain=device_stamp_s_unanchored；三方 digest 与逐帧 group 固定；**不拟合/不选 ROI/不给单位或物理结论；不改源** | 逐帧 group 按 89 帧声明，不做 fit/val 选择 | 正：prepare+reload 一致、源零改动；负：不产生任何 calibration/物理结论 | I01/02/03/04/07 |

## 5. 保留 / 失效 / 不变量（修订后）

- 保留：legacy `--points` NPY/NPZ 全路径；legacy `fit_ground_plane`/`save_json`；constrained `--bag` 拒绝；ground 数学与全部 `REASON_*`/status；`save_exclusive_json` 旧 legacy fallback；frozen 配置、driver、webui、采集器、原 captures 与旧证据。
- 失效（写前拒绝且无副作用）：任何声明/hash/长度/连续性/layout/类型/时间/单位/frame 冲突；含 marker NPZ 损坏不回退 legacy；source 缺失/不可达不推断；未知/别名 group、越组 indices、帧集交叉、缺先验、<3 validation；目标已存在/竞争/无 `os.link`。
- 不变量：`point_index_domain=capture_export_row`、`original_bag_point_index=unknown`、`source_bag_hash_verified=false`、`physical_verified=false`、frame/units=`metadata_declared`；一 bundle 一完整 source；逐帧确定性 group（内容身份公式）；adapted 单产物；无 link 不发布。

## 6. 检查入口（阶段二实现/复核用）

- 新 `tests/test_gli01_capture_input.py`：覆盖 M02–M09、M11 的格式/类型/三方 digest/成员/group-first/link-only 原子写；合成反例。
- 真实 export（只读）：`captures/remote/cap_20261002_163621` 跑 prepare+load，核 `4372400/89/hash/zero_rows/time_domain`，不拟合。
- CLI：`prepare_capture_input.py --source-dir … --frame innolidar --units m --output …`；`calibrate_sensors.py --constrained --points <adapted.npz> …`；非 constrained + adapted → return2；adapted + `--diagnostics` → 写前拒绝。
- 范围/SHA：本文件 §0 + 提交后 Codex 重算源码 SHA。

## 7. 结论与停止

修订已把 06_DESIGN_REVIEW 七条裁决逐 M01–M13 映射到实际新函数与旧入口顺序；删除初版任意 groups/`--meta/--bin`、M09 跨 pool 双行为、M11 O_EXCL fallback；确立显式 frame/units、实际源三方相等、全入口 manifest 识别、group-first selector、adapted 单输出/无 diagnostics、link-only 原子。B01/D01 不变，严格软件适配不推出原 bag 行索引与单位/安装/地面/性能 verified。

本轮**只写本文件**，未改任何 source/tests/config/contract/state/returns，未 commit/push/reset/checkout/clean，未 board/网络/采集/部署/模型/DB/global config 改动。

READY_FOR_DESIGN_REVIEW
