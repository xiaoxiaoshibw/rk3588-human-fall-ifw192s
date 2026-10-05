# GL-I01 离线 capture 数值输入契约 (v1)

范围：严格只读现有 28B `human_capture_session` export，生成带可追溯 manifest 的
数值 NPZ，并在 constrained 数值入口校验“实际源帧组成员”。本文件是
`core/capture_input.py` 与其 CLI/loader 的行为契约，不改 ground 数学/配置/driver/
网页。Python 3.8 + stdlib + NumPy。

## 1. 源格式

真实导出目录含 `meta.json` 与 `points.bin`。`meta.json` 必须：

- `format == "human_capture_session"`，`format_version == 1`；
- `point_file == "points.bin"`，`point_stride_bytes == 28`；
- `point_layout` 精确为 little-endian 28B：`x,y,z,intensity` 为 `<f4`，
  `ring` 为 `<u2`，`timestamp` 为 `<f4`，pad 偏移 18/24；
- `extraction.tool == "bag2session/0.1.0"`，`extraction.point_step_bytes_src == 26`；
- `extraction.dropped_frames == 0`（strict int）；`total_dropped_points == 0`；
- 每帧 `dropped_points == 0`，`count/seq/stamp_sec/stamp_nanosec/offset_points`
  为 strict int，`offset_points` 连续、`total_points` 等于各帧 count 之和；
- `sensor.frame_id` 必须等于 CLI `--frame`；`units`（若出现于 `sensor`/顶层）必须
  等于 CLI `--units`（只允许 `"m"`，不暗转 mm）；
- `time_domain` 非空字符串；header 时间为整数 `stamp_sec`/`stamp_nanosec`，
  不从 `<f4` 点 `timestamp` 反推 ns，也不跨时钟混算。

违反任一 → 整个输入拒绝（`CaptureInputError`），不静默过滤、不重编号。

## 2. 适配产物（NPZ）

- 归档仅两个键：`points`（`(N,3)` little-endian `<f4`，按原帧/原行顺序，保留零点）
  与 `input_manifest`（**标量** Unicode JSON 字符串，`ndim==0`）；
- `allow_pickle=False`；
- 以 `np.savez` 写入临时文件，写入后 `flush`+`fsync`，再 `os.link` **独占**发布；
  目标已存在或平台无 `os.link` → 拒绝，绝不复制覆盖、无 `O_EXCL` 回落。

### manifest 内容

- `source`：`format`/`tool`、`meta_path`/`bin_path`（绝对路径）、
  `meta_sha256`/`bin_sha256`、`bin_size_bytes`；
- `points`：`sha256`（规范 raw `<f4` 字节）、`shape`、`dtype`；
- `declared`：`frame`、`units`、`time_domain`；
- `frames`：有序完整帧 range（`seq`/`stamp_sec`/`stamp_nanosec`/行区间）；
- `frame_groups`：每完整源帧一个 **确定性 content-based** group
  （`frame:<sha256[:24]>`），成员为 half-open 原行区间；
- `provenance`：
  `point_index_domain = "capture_export_row"`，
  `original_bag_point_index = "unknown"`，
  `source_bag_hash_verified = false`，
  `physical_verified = false`，
  `units/frame = "metadata_declared"`；
- `schema`、`kind = "capture_input_adaptation"`。

## 3. 加载校验（不降级 legacy）

`classify_npz(path)` 按**内容**（是否含两个规范键）判定 `"adapted"`/`"legacy"`，
不看扩展名（`os.fspath` 接受 path-like）。含 marker 但损坏的 NPZ **绝不**回退
legacy，直接拒绝。

`load_adapted` 在单次加载内：

1. 读取实际源 `meta.json`/`points.bin` 的两个字节快照，校验其 hash 与 manifest
   绑定一致（源被改动 → 拒绝）；
2. 从**同一**快照解析声明并解码 XYZ，从零重建规范 manifest，与归档内 manifest
   按 **类型稳定** 的 canonical JSON 比较（bool/float 不因 `1 == True` 蒙混）；
3. 要求规范 raw `<f4` 字节 == NPZ `points` == manifest digest；
4. 全部帧逐成员复核，源非有限 XYZ → 整输入拒绝。

## 4. group-first 选择

- `select_group_region` 先解析声明 `frame_group`，再在**该组成员行**内应用选择；
- 必须显式提供 `indices` 或完整六个 `x/y/z min/max` bounds（二者不可混用）；
  缺失 → 拒绝，**不**返回整组；bounds 为有限数值（拒 bool/NaN/Inf、拒倒置），
  且在组成员为空的早返回**之前**校验；
- 显式 `indices` 越出声明组 → 拒绝；返回的仍是 pooled 原行索引，无残差预筛；
- `frame_of_row` 拒绝 bool/负数/越界/非整数行号（不在 NumPy 索引处负向环绕），
  并保留请求顺序与重复。

## 5. constrained 入口

- adapted NPZ 仅在 `--constrained` 下可用；非 constrained → 写前 return 2；
- adapted 拒绝 `--diagnostics`（完整诊断在 `artifact.constrained_ground`）；
- fit 区 + ≥3 独立 validation 区外部显式提供；fit 与各 validation 不得共享源帧，
  validation 之间亦不得共享；缺少选择/组名/<3 区 → 拒绝，不自动选地面；
- 仅产出一个不可覆盖的 calibration JSON（`save_exclusive_json` + `os.link`）；
- 任一构造/拟合/导出/派生失败发生在**任何写之前** → return 2，无半截产物；
- legacy 普通 points/NPY/NPZ 与 `--diagnostics` 语义不变。

## 6. provenance 诚实性（不变式）

`point_index_domain = capture_export_row`；`original_bag_point_index = unknown`；
`source_bag_hash_verified = false`（原 bag hash 仅 declared 未实核）；
`physical_verified = false`；`frame`/`units` 为 `metadata_declared`。
真实 export 数值 ≠ 已核标定/单位/安装；synthetic 检查必须明确标签。
