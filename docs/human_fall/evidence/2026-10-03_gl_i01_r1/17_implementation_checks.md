# GL-I01 R1 实施自验（PHASE TWO）

日期 2026-10-03。本轮仅跨白名单写：`core/capture_input.py`、
`scripts/prepare_capture_input.py`、`scripts/calibrate_sensors.py` 的 adapted route、
`tests/test_gli01_capture_input.py`、`GLI01_INPUT_CONTRACT.md`、本证据、`returns/GL-I01.md`。
冻结 ground/math/runtime/calibration/config/driver/webui/captures 未改。

## 源 SHA256（本轮）

- `core/capture_input.py` `56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16`
- `scripts/prepare_capture_input.py` `648a8da63a6656b02d169957cede2df4aca3a48e94dcc787c3c48c7f10c5d000`
- `scripts/calibrate_sensors.py` `3f30cf945d70b06f0fce22bdec9ba738f774f98dde2f9a33ce466eeaf9c6c785`
- `tests/test_gli01_capture_input.py` `50f615d7a5ffdc490f1011b316df30da1e65c958cce93f18ad4cf0c88547030e`

## 命令与结果

- `python -B -W error -m unittest discover -s src/human_fall_detection/tests` → Ran 399, OK
- `... test_gli01_capture_input` → Ran 62, OK
- `... test_gl01_constrained_ground` → Ran 33, OK
- `py_compile` capture_input / prepare_capture_input / calibrate_sensors → OK

## 真实 163621（只读，M13）

`python src/human_fall_detection/scripts/prepare_capture_input.py --source-dir captures/remote/cap_20261002_163621 --frame innolidar --units m --output evidence/.../prepared/cap_20261002_163621.npz` → exit 0。

- points 4372400 / frames 89 / groups 89 / dtype `[('<f4')...]`
- bin_sha256 `b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff`
- points_sha256 `a4ad287ea14edd1ba584dd24dce866d7c4eacdc7ce2594edb2ddb1eef1b51c27`
- time_domain `device_stamp_s_unanchored`；zero_rows 673315
- reload exit 0（`prepared/cap_20261002_163621_reload.json`）；`frame_of_row([0,-1,-1])` → `[0,88,88]`
- 无源修改；**未**对真实数据拟合/选 ROI/写生产 config。

## Synthetic-only CLI adapted fit（明确标签）

`17_synthetic_fixture.py` 生成含首/尾空帧的 7 帧合成 export（z≈-1.2m 平面）→
`cap_synthetic_01.npz`（2000 点）。真实 CLI：

- `calibrate_sensors.py --points .../cap_synthetic_01.npz --constrained --frame innolidar --fit-frame-group frame:... --fit-region ... --validation-regions ... --up-axis 0 0 1 --sensor-height-interval 0.5 2.5 --output .../synthetic_geometry.json` → exit 0，
  `status valid`，`sensor_height_m ≈ 1.20004`（合成标签，非物理声明）。
- adapted + `--diagnostics` → exit 2
- adapted 无 `--constrained` → exit 2
- 已存在输出 → exit 2，无覆盖
- 跨组显式 indices → exit 2，无产物
- 无选择器 region → exit 2

## Codex 审计项回归（本轮新增测试）

- 按内容检测（重命名 `.dat`）/ path-like
- 归档多余键、`input_manifest` 非标量 → 拒绝
- canonical 类型稳定：bool 冒充 int、float schema、矛盾验证标志 → 拒绝
- 自改源并自重算 digest 仍 → 拒绝
- `frame_of_row` bool/负数/越界/浮点 → 拒绝；顺序/重复保留
- `select_group_region` 无选择器 → 拒绝（不再返回整组）；有限/非 bool/非字符串 bounds；
  空组不跳过非法 bound
- 非有限源 XYZ → 整输入拒绝（`canonical_source_xyz`）
- 用 otherwise-valid 选择器测实际帧重叠/组冲突
