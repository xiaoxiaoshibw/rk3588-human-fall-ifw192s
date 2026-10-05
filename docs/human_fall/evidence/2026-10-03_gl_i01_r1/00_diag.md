# GL-I01 R1 阶段一集中诊断（只诊断，禁止源码/测试/配置/状态写入）

- 日期：2026-10-03（Asia/Shanghai）
- 工单：`AI_PROMPT_GLI01_OPENCODE_R1_DIAG.md`；唯一表 `GLI01_ACCEPTANCE.md` v1；本轮计划 `evidence/2026-10-03_gl_i01_r1/PLAN_REVIEW.md`。
- 目标：为本单 M01–M13 及 I01–I08 逐行映射现有函数/赋值顺序/校验、source hash/layout/时间/索引/绑定/副作用/原子写顺序、fit/validation 实际源帧隔离、正负例与保留/失效，形成可审设计。**本轮不写任何生产代码/测试/配置/contract/return，仅本文件。**
- 工作树：`master`，HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（baseline `00_before_manifest.json` 记录 `cbd0be1...`）；本单不改任何 source/tests/config/contract/state/returns，不改 frozen 资产。
- ponytail：已实际读取 `C:\Users\30680\.claude\skills\ponytail\SKILL.md` 与本轮副本 `evidence/2026-10-03_gl_i01_r1/ponytail_SKILL.md`，两份 SHA256 均为 `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`（一致），强度 full。
- 只读入口已读：`WORKFLOW.md` 首段与 §1–§4 核心；`GLI01_ACCEPTANCE.md`；本轮 `PLAN_REVIEW.md`；`calibrate_sensors.py`（全文）；`core/ground.py` 的 `region_indices`/`resolve_constrained_settings`/`fit_ground_plane_constrained`/`validate_constrained_ground`；`src/human_capture/core/bag2session.py`（全文，28B 布局）；真实 `captures/remote/cap_20261002_163621/meta.json` 经 Python 打印 top-level 与首末帧摘要（未全文灌 frames）。未读历史全量。

## 0. 受审源码基线 SHA（本设计锚点，未修改）

| 文件 | SHA256 |
|---|---|
| `src/human_fall_detection/scripts/calibrate_sensors.py` | `07046d89124b669376aa9425a1becb7cc485b200cda92269b786c1af22b672b7` |
| `src/human_fall_detection/core/ground.py` | `2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3` |
| `src/human_capture/core/bag2session.py` | `e3c3a62cd581650c7c7439412e6b77d1b813f82f411e277c7b38af87310703b3` |
| `src/human_fall_detection/core/calibration.py` | `d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3` |
| `src/human_fall_detection/scripts/sensor_health.py` | `e77f9d7583b81661a26d8119181115307049863e1e94638a54475d1138d38ca1` |

计划只新增：`src/human_fall_detection/core/capture_input.py`、`src/human_fall_detection/scripts/prepare_capture_input.py`、`calibrate_sensors.py` 的 opt-in manifest 分支、`tests/test_gli01_capture_input.py`、本单 contract/evidence/追加 return。ground 数学、runtime、config、driver、webui、采集器不改，不导入 replay HTTP/采集器。

## 1. 现有调用链实测（写前事实，非猜测）

### 1.1 `calibrate_sensors.py`

- `load_points(path)`（:96）：`np.load(allow_pickle=False)`；NPZ 取 `points` 或 `files[0]`；`np.asarray(float64)`；`shape[1]>3` 截前 3 列；非 (N,3) 抛 `GeometryCalibrationError`。**无 manifest 概念，无任何内容 hash/源绑定。**
- `load_input(args, input_info)`（:204）：`--points` 走 `load_points`，记录 `source=points/path(basename)/sha256(file)/frames=None`；`--bag` 走 `load_points_from_bag`（:123）。`point_count=len(points)`。**只对文件整体做 sha256，不校验内部布局/成员。**
- `run_constrained`（:222）：先拒绝 `--bag`（:224–229，`constrained --bag is not supported`）；`resolve_constrained_settings`（:233）；`load_input`（:239）；**副作用前**对 `args.output` 与 `args.diagnostics` 做存在性预检并拒绝覆盖（:245–249）；再解析 `--fit-region/--fit-indices/--validation-regions`，`region_indices`/`load_indices`，各自记录 basename+sha256（:251–268）；调用 `fit_ground_plane_constrained`（:272）；`validate_constrained_ground`（:278）；诊断先写（:282–287）；`build_ground_derived`（:293–307）；`build_geometry_calibration`+`validate_geometry_calibration`（:308–316）；`save_exclusive_json(args.output)`（:318）。所有写点都在完整构造之后。
- `save_exclusive_json`（:43）：同目录 `NamedTemporaryFile` → json.dump(`allow_nan=False`) → `os.link(temp,target)` 独占（EEXIST 抛错），无 link 平台退化为 `O_EXCL` 拷贝；finally 删 temp。**可复用的独占原子写范式。**
- `main`（:337）：`--constrained` 走 `run_constrained`；否则 legacy `fit_ground_plane`+`save_json`（:350–365）。

### 1.2 `core/ground.py`（GL-01 约束路径）

- `region_indices(points, region)`（:504）：region 为 `{"indices":[...]}`（`np.unique(_normalise_indices(...))`，拒绝 bool/float/越界）或六界 `x/y/z_min_m|max_m`（`_finite_number`，倒置拒绝），返回 `np.nonzero(mask)[0]`。**对整份 pooled points 取界，无 frame/group 概念；返回 pooled 行号。**
- `fit_ground_plane_constrained`（:597）关键顺序：
  1. `resolve_constrained_settings`（:607，floor/cap 不可放松）；`_unit_vector(up_axis)`；`_height_interval`；points (N,3) 校验。
  2. `finite` 掩码；`norms`；`valid_index = nonzero(finite & norms>0)`（:614–617）→ **零点/非有限自动落入 valid 之外，但 pooled 行号不重编号**。
  3. `fit_index = valid_index`（未给）或 `intersect1d(_normalise_indices(fit_indices), valid_index)`（:619–624）。
  4. 逐 validation region：要求非空 str `region_id`；`selected = intersect1d(region_indices(array,region), valid_index)`（:627–634）。
  5. `fit_frame_group` 必须非空 str；每个 region 必须非空 str `frame_group`；重复 `region_id`/`frame_group` → `REASON_METADATA`（:661–675）。
  6. fit∩region、fit_frame_group==region.frame_group、region 间点交/同名 group → `REASON_OVERLAP`/`REASON_GROUP_LEAKAGE`（:677–695）。**全部是字符串标签比较，不核实实际源帧。**
  7. 采样+RANSAC+候选/SVD/竞争/歧义；height interval 过滤；`_balanced_sample` 只稀疏 fit 样本，返回原 source 索引（:703–706、:542）。
  8. 每 region 未截断 RMS/p95/support 门（:857–905）；至少 `independent_regions_min=3`；任一失败 → `REASON_VALIDATION_FAILED`。
  9. `_result(STATUS_VALID,...)` + `_attach` 诊断（:918–925）。
- `validate_constrained_ground`（:1031）：对持久化记录重放同一结构/物理门；`constrained is True`；settings 重解析；`up_axis` 已是单位向量；height 区间；`fit_support_indices` 唯一且在 range；合法 valid 记录要求 regions≥3、每组 `usable/passed`、count 与 indices 一致、indices 唯一且与 fit/其他 region 不交、total≤holdout cap。（:1047–1115）
- 默认约束参数（:299）：`min_inliers=100`、`fit_point_cap=5000`、`holdout_point_cap=10000`、`independent_regions_min=3`、`points_per_region_min=20`、`max_candidates≤3`、`ransac_iteration_hard_cap≤2000`、`seed=20261001`、`inlier_threshold_m=0.05`、`max_angle_rad≈15°`。

### 1.3 `src/human_capture/core/bag2session.py`（现有 28B 导出，**不是原 bag**）

- `POINT_STRIDE_BYTES=28`；`FORMAT="human_capture_session"`、`FORMAT_VERSION=1`、`SERVICE_VERSION="0.1.0"`、`EXTRACTION_TOOL="bag2session/0.1.0"`。
- 唯一行布局（:104–113）：`x<f4@0, y<f4@4, z<f4@8, intensity<f4@12, ring<u2@16, _pad1<u2@18(0), timestamp<f4@20, _pad2<f4@24(0)`；`little`；`pad_offsets_bytes=[18,24]`；源 `point_step=26`。
- 每帧 `_message_points_array`：`is_bigendian` 拒绝；`point_step<26` 拒绝；缺字段拒绝；**xyz 任一非有限即丢点**，记 `dropped_points`；空帧返回 `b"",0,0`（写 0 字节，仍 append 一条 frame 记录）。
- `extract`（:134）逐帧按 bag 顺序 `bin_fh.write(packed)`；frame 记 `seq/stamp_sec/stamp_nanosec/bag_time_sec(round6)/offset_points/count_points/dropped_points`；`offset_points` 单调连续累加；结尾写 `total_points=offset_points`、`total_dropped_points`、`point_layout`、`extraction{source_bag, source_bag_sha256, point_step_bytes_src:26, dropped_frames:0}`。meta 原子写（temp+fsync+replace），随后附 `_computed{points_bin_sha256,points_bin_size_bytes}`（**仅内存返回，不写回 meta 文件**）。
- `timestamp` 为**点级 f4**，注释明确 ns 精度丢失（:10–11）；`meta` 无 `units`、无 `width/height/original_count`、无原 bag 逐点索引。

### 1.4 真实数据事实（只读、格式/hash/计数/抽样）

5 个 `captures/remote` 会话：

| 会话 | format/ver | frames | total_points | total_dropped | extraction.tool | source_bag_sha256 | 判定 |
|---|---|---|---|---|---|---|---|
| `cap_20261002_163621` | human_capture_session/1 | 89 | 4372400 | 0 | bag2session/0.1.0 | 有 | 原始零丢，可用 |
| `cap_20261002_165321` | 同上 | 29 | 1424701 | 0 | bag2session/0.1.0 | 有 | 原始零丢，可用 |
| `cap_20261002_182355` | 同上 | 18 | 884305 | 0 | bag2session/0.1.0 | 有 | 原始零丢，可用 |
| `cap_20261002_223757` | 同上 | 165 | 8105838 | 0 | bag2session/0.1.0 | 有 | 原始零丢，可用 |
| `cap_20261002_165321_clip_1989287-1989294` | 同上 | 8 | 393023 | （无字段） | `human_replay_trim/0.1` | 无（有 source_session/source_range） | **clip → 拒绝** |

163621 深查（本地只读）：
- `meta.json` SHA256 `675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692`，18815 B。
- `points.bin` SHA256 `b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff`，122427200 B = 4372400×28（精确）。
- top-level keys：`created_iso,duration_sec,extraction,format,format_version,frames,human_annotations,point_file,point_layout,point_stride_bytes,sensor,session_id,time_domain,topic_message_counts,topics,total_dropped_points,total_points`。`sensor={model:IFW192S,frame_id:innolidar}`、`time_domain=device_stamp_s_unanchored`、`point_layout.fields=[x,y,z,intensity,ring,timestamp]`、`dtypes=[<f4,<f4,<f4,<f4,<u2,<f4]`、`stride=28`、`endian=little`、`pad_offsets=[18,24]`。
- 首帧 `{seq:1979438, stamp_sec:183460, stamp_nanosec:2503000, bag_time_sec:1790930182.177557, offset_points:0, count_points:49130, dropped_points:0}`；末帧 `{seq:1979526, stamp_sec:183469, stamp_nanosec:124948000, offset_points:4323271, count_points:49129, dropped_points:0}`。
- 89 帧 offset 从 0 连续到 4372400，`continuity_bad=0`；`sum(count)=total`。
- 按 28B memmap 抽样：`zero_rows=673315`（约 15.4% 全零 XYZ），`finite_rows=4372400`。**只记录数值，不拟合/不选 ROI/不给单位或物理结论。**

### 1.5 未决事实（必须诚实标注）

- `point_index_domain`：只能声明 `capture_export_row`（pooled 行号）；**原 bag 逐点行索引 unknown**，capture schema 未持久化 `width/height/original_count`，`frame_id` 为 extractor 硬编码。
- `source_bag_sha256` 只 **declared（extractor 写入），本地未读原 bag 核验**。
- 点级 f4 `timestamp` 在该批 ULP≈0.015625 s，**不能恢复 ns**；帧时间只能用 meta 的整数 `stamp_sec/stamp_nanosec`；`bag_time_sec` 为另一来源，不能与设备时钟跨域混算。
- `units` 原记录缺失，须显式声明为 `m` 并标 `metadata_declared`（不暗转 mm）。
- 约 1.1 m 是光学窗口离地、安装向下角未知：**不得当作已核原点高度或先验**；不猜安装角/up/source 轴。

## 2. 设计总览

新增两个纯文件 + 一个 opt-in 分支；不改 ground 数学、不改 legacy 语义与 constrained `--bag` 拒绝。

- `core/capture_input.py`（纯 stdlib+NumPy，Python3.8，无 ROS/replay/采集器导入）：
  - 常量：capture 格式/版本/28B 行 dtype/`MANIFEST_KEY="input_manifest"`/`CAPTURE_INPUT_SCHEMA=1`。
  - `class CaptureInputError(ValueError)`。
  - `sha256_file`；`read_source_meta(meta_path)` 严格 schema/layout；`validate_frames(meta)` 连续/长度/drop=0；`load_source_xyz(meta_path, bin_path)` 全行按原序读 XYZ（f4，不预滤零点/不重编号）；`build_manifest(...)`；`prepare(...)` 独占原子写 NPZ；`read_context(path)` 判定是否 adapted（**含 key 即 adapted；含 key 但损坏必须抛错，不回退 legacy**）；`load_adapted(path)` 重核源并返回 `(points, context)`；`frame_of_row(context)`；`group_frame_set(context, group_id)`；`gate_selection(context, fit_frame_group, fit_indices, validation_regions)`。
- `scripts/prepare_capture_input.py`：CLI，`--source-dir`（含 meta.json+points.bin）或 `--meta/--bin`，`--output`，`--groups`（canonical frame_group → frame ordinal 区间/清单）。只读 source，输出独占原子 NPZ。
- `calibrate_sensors.py`：`run_constrained` 内在 `load_input` 之前探测 `capture_input.read_context(args.points)`；为 None 走原 legacy 路径（零改动）；非 None 走 adapted，解析 fit/regions 后调用 `gate_selection`，再调用**不变的** `fit_ground_plane_constrained`/`validate_constrained_ground`。

## 3. manifest 设计（固定到 NPZ 的 `input_manifest` 标量 Unicode JSON）

```
{
 "schema": 1,
 "kind": "capture_input_adaptation",
 "source": {"format":"human_capture_session","format_version":1,
            "tool":"bag2session/0.1.0",
            "meta_path": <canonical abs path>, "meta_sha256": <hex>,
            "bin_path": <canonical abs path>, "bin_sha256": <hex>,
            "bin_size_bytes": <int>, "total_points": <int>,
            "total_dropped_points": 0,
            "source_bag_path": <meta.extraction.source_bag>,
            "source_bag_sha256": <meta.extraction.source_bag_sha256>,
            "source_bag_hash_verified": false},
 "layout": {"fields":[...],"dtypes":[...],"stride_bytes":28,
            "endian":"little","pad_offsets_bytes":[18,24]},
 "frames": [ {"ordinal":i,"seq":..,"stamp_sec":..,"stamp_nanosec":..,
              "bag_time_sec":..,"offset_points":..,"count_points":..,
              "dropped_points":0}, ... ],          # 原序完整
 "frame_groups": {"<gid>": [[first,last],...], ...},  # canonical 分区
 "points": {"key":"points","dtype":"<f4","shape":[N,3],
            "sha256": <canonical XYZ bytes>,"point_count":N},
 "declared": {"frame_id":"innolidar","frame_provenance":"metadata_declared",
              "units":"m","units_provenance":"metadata_declared",
              "time_domain": <meta.time_domain>},
 "provenance": {"point_index_domain":"capture_export_row",
                "original_bag_point_index":"unknown",
                "source_bag_hash_verified": false,
                "physical_verified": false}
}
```

不变量：`frame_groups` 必须是对 `[0,n_frames)` 的互不重叠完整分区；`points.sha256` 对 `load_source_xyz` 的 little-endian f4 规范字节计算；manifest 自身不参与 points hash；NPZ 仅含 `points` 与 `input_manifest` 两个键。

## 4. M01–M13 设计 / 函数 / 检查矩阵

列含义：**操作×消费者**＝输入操作与下游；**映射函数**＝现有/新增符号与行号；**设计/绑定**＝type/layout/hash/时间/索引/绑定/副作用/原子写顺序；**源帧隔离**＝fit 与 validation 的实际源帧处理；**检查（正/负）**＝可观察预期与保留/失效。

| ID | 操作×消费者 | 映射函数 | 设计 / 绑定 | 源帧隔离 | 检查（正/负） | 覆盖 |
|---|---|---|---|---|---|---|
| M01 | valid 多帧 export → NPZ → constrained loader | `prepare.prepare`；`capture_input.load_adapted`；`run_constrained:239`；`load_input:204`；`save_exclusive_json:43`；`bag2session.extract:134` | 按 frame 原序/offset 全行读 XYZ f4；整数 `stamp_sec/nanosec`、`seq`、`time_domain`、`bag_time_sec` 各自来源入 manifest；meta/bin/points 三级 hash；显式 frame/units 声明；NPZ exclusive 原子写 | manifest `frame_groups` canonical 分区；loader 重建 `frame_of_row`；fit/val 组帧集后续由 gate 核 | 正：点数=N、逐行字节与 export 一致、整数帧时间与声明 frame/units、hash 三连一致；负：任一 hash/计数不符拒绝 | I01/02/03/04/07 |
| M02 | zero XYZ / 帧首尾边界 / 不同 count / 空帧 | `load_source_xyz`；`validate_frames`；`frame_of_row`；`fit_ground_plane_constrained:614-617` | 零点保留原行不预滤不重编号；空帧 `count_points=0` 但占一条 frame 记录，`offset` 不减；range 不重排；后续 fit 仍用 pooled 原行（ground 内 `valid_index` 天然排除零点但保留索引映射） | 空/边界帧归其 canonical group；索引仍 pooled | 正：零点行存在、边界帧 count 正确、空帧不伪点；负：把 count=0 当截断/重编号拒绝 | I01/02 |
| M03 | meta/bin 截断 / 尾数据 / overlap / gap / total 矛盾 | `validate_frames`；`read_source_meta`；`sha256_file`；`prepare` 预检 | bin 精确 `size==total*28`；frame offset 从 0 连续、`offset[i+1]==offset[i]+count[i]`；`sum(count)==total`；`dropped==0`；尾部多余/缺口 → 拒绝；**创建/加载前拒绝，无任何输出副作用**（先全面校验后再写） | 分区来自连续 frames，损坏则无法构造 group | 正：真实 163621 通过（size 精确、continuity_bad=0）；负：截断/多字节/重叠/空洞/total 不符均拒绝且不产生文件 | I01/06 |
| M04 | unknown 格式 / version / layout / endian / clip / drop | `read_source_meta`；`prepare`；`load_adapted` | `format=="human_capture_session"`、`format_version==1`、`tool=="bag2session/0.1.0"`、`fields/dtypes/stride/endian/pad` 逐字段精确匹配；`total_dropped==0`；clip（`human_replay_trim`）无 `source_bag_sha256`/drop 字段 → 拒绝；不猜格式、不提物理资格 | layout 不符则无合法 frame 映射 | 正：4 原始 export 通过；负：clip 会话、改 version/stride/endian/加 drop 均拒绝 | I01/07 |
| M05 | bool/float/string count/seq/stamp、非法 ns/frame/units | `read_source_meta`；`load_adapted`；`gate_selection` | 严格类型：`seq/stamp_sec/stamp_nanosec/offset_points/count_points` 必须 Python int（拒 bool/float/str），`0<=nanosec<1e9`、`sec>=0`；`frame==meta.sensor.frame_id`；`units=="m"`；`--frame` 与 manifest 冲突拒绝；不从 f4 点 timestamp 推 ns，不跨时钟混算 | frame/units 声明校验在 group 解析前 | 正：真实整数帧时间通过；负：float count、string stamp、nanosec=1e9、CLI `--frame` 冲突、units≠m 拒绝 | I01/03/06 |
| M06 | 改 source/meta/bin/points/manifest/members/group 后 reload | `sha256_file`；`load_adapted`；`frame_of_row`；`group_frame_set` | 逐级校验：meta hash、bin hash、bin size、points 规范字节 hash、members（shape/dtype/行数）、`frame_groups` 必须等于 canonical 分区；**含 `input_manifest` 的 NPZ 损坏一律拒绝，绝不降为 legacy**；source 路径不可达明确拒绝，不从 hash 字符串推断已读源 | 改 group 别名使同源帧“独立” → 实际帧集仍重叠 → 拒绝 | 正：未改可加载；负：改任一级/缺源/组别名/伪造 manifest 均拒绝 | I04/06 |
| M07 | ordinary legacy NPY/NPZ（无 manifest）→ 现入口 | `load_points:96`；`main:337`；`run_constrained` 探测 | `read_context` 仅在 NPZ 且含 `input_manifest` 键时返回非 None，其余 None 走原 `load_input/load_points`，语义/默认/已有返回不变，不要求 capture source | 不适用（无 group 概念） | 正：普通 (N,3) `.npy`/无 manifest `.npz` 行为与既有回归一致；负：不因新增适配改变 legacy | I08 |
| M08 | fit/val 点交叉 或 同源帧不同 group 名 | `gate_selection`；`region_indices:504`；`fit_ground_plane_constrained:677-695`；`validate_constrained_ground:1113` | gate 用**实际帧集**（`frame_of_row`+`group_frame_set`）判独立：fit 组帧集与每个 val 组帧集两两不交、val 之间不交；region 的 `frame_group` 必须是 manifest 已声明组；标签不同但实际帧重叠 → 拒绝；点交叉在 gate 与 ground 双检；**不写输出** | 字符串标签不能绕过；实际帧集为重 | 正：真正不相交组通过；负：同帧异名、点交叉、未声明组 → `CaptureInputError`/`REASON_*`，无 output/diagnostics | I04/05/06 |
| M09 | bounds across pooled frames + group 限制 | `gate_selection`；`region_indices:504`；`_balanced_sample:542` | 先按声明组的实际帧成员取掩码，再对该子集应用六界/显式 indices；返回 pooled 原行号（不重编号、不残差预筛）；bounds 只作用于组内成员 | fit 同样先限实际组成员 | 正：跨帧 bounds 只命中本组行；负：试图用全 pool bounds 跨组取点 → 越组拒绝；不按平面残差预筛 | I02/05 |
| M10 | missing ROI/group/priors/<3 validation 区域 | `gate_selection`；`fit_ground_plane_constrained:658-699`；`run_constrained:224-235` | 缺 fit 选择/`--fit-frame-group`/region group/up/height → 明确拒绝或现有 invalid；val 有效组 <3 → `REASON_VALIDATION_INSUFFICIENT`；**绝不自动选地面**；adapted 路线缺显式选择直接返回 2 不写文件 | group 缺失即无法建实际帧集 | 正：显式提供通过；负：缺任一先验/组/<3 区 → invalid/拒绝 | I05/06/07 |
| M11 | output exists / 失败 / 重复写 / 竞争出现目标 | `save_exclusive_json:43`；`prepare` 独占写；`run_constrained:245-249,318-321` | output 先存在性预检拒绝；NPZ 用同目录 temp + `os.link` 独占创建（EEXIST 拒绝），无 link 平台退化为 `O_EXCL` 拷贝，finally 删 temp；完整构造后才写；失败/竞争出现目标不覆盖旧产物、不留半截 | 不适用 | 正：新路径成功、原子可见；负：已存在/竞态/写失败 → 拒绝且旧/半截产物不受影响 | I06/08 |
| M12 | adapted CLI 成功+失败 → artifact input provenance | `run_constrained:204-321`；`build_geometry_calibration`；`input_info` | 成功后 artifact `input_info` 带实际 source meta/bin/points hash、frame_groups 实际 map、declared provenance；失败返回 2 不写 calibration/diagnostics；legacy 语义不变；所有 `physical_verified=false`、`original_bag_point_index=unknown`、`source_bag_hash_verified=false` | 记录的 group/frame map 与实际一致 | 正：成功含实际 hash/map；负：失败无副作用；provenance 不冒充已核 | I04/05/06/07/08 |
| M13 | 真实 163621 全 89 帧 4372400 行 → 适配/加载 | `prepare.prepare`；`load_adapted`；`capture_input.*` | 只读、不拟 merge；诚实记录 `total_points=4372400`、`zero_rows≈673315`、`duration`、`time_domain=device_stamp_s_unanchored`；三级 hash 固定；**不拟合/不选 ROI/不给单位或物理结论** | 分区按 89 帧 canonical 声明，未做 fit/val 选择 | 正：prepare+reload 一致、源零改动；负：不产生任何 calibration/物理结论 | I01/02/03/04/07 |

## 5. 保留行为与失效边界

- 保留：legacy `--points` NPY/NPZ 全路径；legacy `fit_ground_plane`/`save_json`；`--bag` 直通（非 constrained）；constrained `--bag` 仍拒绝；ground 数学与全部 `REASON_*`/status 语义；frozen `default.yaml/geometry.yaml`、driver、webui、采集器、原 captures 与旧证据。
- 失效（拒绝且无副作用）：任何 hash/长度/连续性/布局/类型/时间/单位/frame 冲突；含 manifest 的损坏 NPZ 不回退 legacy；source 不可达不推断；组别名/点交叉/跨组 bounds/缺先验；目标已存在或竞态。
- 不变量：`point_index_domain=capture_export_row`、`original_bag_point_index=unknown`、`source_bag_hash_verified=false`、`physical_verified=false`、units 与 frame 均 `metadata_declared`；NPZ 仅 `points`+`input_manifest`；`frame_groups` 为 canonical 分区；prepare 只读 source；所有写点独占原子。

## 6. 机器可核对的检查入口（供阶段二实现/复核）

- pure adapter 合成反例：`tests/test_gli01_capture_input.py`（新），覆盖 M02–M09、M11 的格式/类型/hash/成员/组/原子写。
- 真实 export 数值输入：对 `captures/remote/cap_20261002_163621`（只读）跑 prepare+load，核对 `4372400/89/hash/zero_rows/duration/time_domain`，不拟合。
- CLI 成功/拒绝+副作用：`calibrate_sensors.py --constrained --points <adapted.npz> ...`（新 manifest 分支）+ 现有 `test_gl01_constrained_ground.py` 回归。
- 范围/SHA：本文件 §0 锚点 + 提交后 Codex 重算源码 SHA。

## 7. 结论与停止

M01–M13 均已在现有源码上定位到函数/顺序，并给出新增 `capture_input.py`/`prepare_capture_input.py` 与 `run_constrained` opt-in gate 的最小设计；未改 ground 数学，未触碰 frozen/legacy/采集。未决与 BLOCKED 项（B01 原 bag 布局/索引证据、D01 现场物理/设备/部署）不在本单软件范围，不因 I01–I08 PASS 而解除；真实 export 数值不构成真实标定/单位/安装 verified。

本轮**只写本文件**，未改任何 source/tests/config/contract/state/returns，未 commit/push/reset/checkout/clean，未做 board/网络/采集/部署/模型/DB/global config 改动。

READY_FOR_DESIGN_REVIEW
