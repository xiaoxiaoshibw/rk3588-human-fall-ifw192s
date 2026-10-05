# GL-I02 真实离线候选标定计划（阶段二实施记录）

- 日期：2026-10-03（Asia/Shanghai）。派工：Claude Code（CLAUDE_STANDBY 顶替）；唯一生产 writer：OpenCode `opencode-go/deepseek-v4.1-flash`（default DB）。
- 唯一验收表：`GLI02_ACCEPTANCE.md` v1（`b8e17282…`）。
- 设计门：`evidence/2026-10-03_gl_i02_r1/04_DESIGN_REVIEW.md`（PASS）。

## 1. 目标与边界

在本地离线、不连板、不采集、不部署、不切 config、不启 GL05、不动 GL02 生命周期的前提下，
把已适配的 capture 输入编排为 **candidate** ground-plane calibration artifact（schema v1），
并把现场协议冻结前需要人工决断的地面选择以 **draft** 形式落地。

- 唯一新增生产文件：`src/human_fall_detection/scripts/evaluate_gli02_candidate.py`（thin wrapper）。
- 真实 163621 **只 read/hash/count**，不 fit、不写 capture dir；synthetic fixture 允许合成拟合。
- 不新增 ROI 语义、不改 `core/ground.py` / `core/calibration.py` / `core/capture_input.py` /
  `scripts/calibrate_sensors.py` / `scripts/prepare_capture_input.py` / 任何 config YAML / driver / webui。

## 2. wrapper 编排链（只调用既有公开 API）

```
--capture-dir (prepare_npz) 或 --prepared-npz (load_adapted)
  -> check_declared_frame
  -> 读 draft（人工填写）
  -> gate_selection                      # group-first，不自实现 bounds
  -> fit_ground_plane_constrained        # core 既有数学，不重写
  -> validate_constrained_ground + ground_is_valid
  -> build_input_info                    # provenance，physical_verified=false
  -> build_geometry_calibration(statuses={"ground":"candidate"})
  -> artifact["constrained_ground"]=result
  -> validate_geometry_calibration
  -> save_exclusive_json                 # os.link 独占，不覆盖
```

- `--capture-dir` 与 `--prepared-npz` 至少一个必填；两者同给以 `--prepared-npz` 为准。
- 非 adapted 普通 NPY/NPZ → `classify_npz=="legacy"` → exit 2，不 fallback。
- 缺 fit selector / frame_group / <3 validation_regions / up_axis / sensor_height_interval → exit 2，无 artifact、无 fallback。
- draft 模板由 `--emit-draft --draft-out` 独占落地：`status="pending_human_review"`、
  `default_refusal="no_auto_ground_selection"`、`up_axis`/`sensor_height_interval_m`/`fit_region`/`validation_regions` 为 null/空待人工填写。

## 3. candidate vs synthetic 的严格分离

| 维度 | 真实 candidate | synthetic fixture |
|---|---|---|
| `--source-kind` | `capture_export` | `synthetic_fixture` |
| `artifact.input.source` | `capture_export` | `synthetic_fixture` |
| `artifact.input.synthetic` | `false` | `true` |
| 命名空间 | 调用者本单目录 | 独立 synthetic 目录 |

两者都走同一 strict adapted route，`status.ground="candidate"`、`ground.status="valid"`、
`verification.ground_physical_verified=false`、无 `ground_derived`、`physical_verified` 恒 false。

## 4. 自验入口

- `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_gli02_candidate.py`（8 项）
- GL-I01 62 + 全回归 407 + Codex 24 探针
- 合成 7-frame candidate artifact readback；真实 163621 read-only reload 计数一致
- 本单四文件 GL-I01 SHA + 冻结 `ground.py`/`calibration.py` + 真实 capture SHA 不变
