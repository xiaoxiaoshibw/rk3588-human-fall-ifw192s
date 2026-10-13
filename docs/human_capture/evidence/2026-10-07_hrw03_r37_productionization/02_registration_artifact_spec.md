# 02 · Registration Artifact 规范（R3.7 冻结）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 目标：把跨会话 transform 做成**构建一次、SHA 绑定、只读复用**的不可变 artifact（扩展 `captures/leveled` 的模式），运行时永不重算 ICP。
- 本规范只定义产物与校验语义；实现（writer/loader）在 R3.8 落地，**R3.7 不写代码**。
- 常量约定复用既有实现：`sha256(bytes)`、`manifest.json` + 逐文件 SHA 映射、`source` 绑定 `{"meta_sha256","bin_sha256"}`、`code_id`/`code_hashes`、`scope/physical_verified/extrinsics_verified/runtime_eligible` 旗标（对齐 `captures/leveled/<job>/manifest.json` 与 `tls/transform.json`）。

## 1. 目录与不可变性

```text
captures/
└── registration/
    └── <source_sid>__to__<reference_sid>/
        ├── registration.json      # transform 本体 + 绑定的最小摘要（不自我引用）
        ├── diagnostics.json       # 全量质量指标 + gate 判定的可复现记录
        ├── provenance.json        # 输入/代码 SHA 绑定与验证记录
        └── manifest.json          # 三个文件的 SHA256（最后写入；完整性锚点）
```

规则：

1. **独占创建**：目录与文件以"存在即拒绝"方式创建（对齐 `leveling.py` `output.mkdir()` / `open("x")` 模式）；**永不覆盖、永不原地编辑**。
2. **重算 = 新目录**：同一 pair 需要重新生成（新方法/新参数/新 leveling 之后）时，写兄弟目录 `<source_sid>__to__<reference_sid>__<artifact_id 前 8 位>/`；旧 artifact 保留。**不允许**删除或改写旧 artifact。
3. **artifact_id = `sha256(registration.json 文件字节)`**。不放入 `registration.json` 自身（避免自我引用），只登记在 `manifest.json` / `provenance.json` / 日志/UI 中。字节级哈希天然跨语言一致（Node/Python 均可复算）。
4. **选择规则（v1）**：消费方**显式**指定 artifact 目录（配置/工单/载入参数）。v1 不提供"自动取最新"解析器；即使未来增加 resolver，也只能在**通过本文 §5 全部校验**的候选中选择，且选择结果必须写日志。
5. 写入顺序：`registration.json` → `diagnostics.json` → `provenance.json` → `manifest.json`（最后）。任一步失败即整体作废该目录（实现可选择写 `.incomplete` 标记，但不得发布无 manifest 的 artifact）。

## 2. `registration.json`（transform 本体）

```json
{
  "kind": "offline_cross_session_registration",
  "schema": 1,
  "units": "m",
  "direction": "current_to_reference",
  "from_frame": "leveled_session",
  "to_frame": "reference_frame",
  "source_session": "cap_20261002_223757",
  "reference_session": "cap_20261004_203349",

  "rotation_row_major": [
     0.9991163122, -0.0417420305,  0.0049191038,
     0.0415732367,  0.9986699485,  0.0304959007,
    -0.0061855220, -0.0302644488,  0.9995227874
  ],
  "translation_m": [-0.01684841, -0.03178948, -0.00013234],

  "euler_deg_zyx": {"roll": -1.7343, "pitch": 0.3544, "yaw": 2.3827},

  "method": "fixed_icp_r3_2",
  "method_version": 1,
  "code_id": "sha256(identity(code_hashes))",

  "quality": {"status": "PASS", "gate_profile": "reg_gate_v1", "reasons": []},

  "scope": "offline_display_only",
  "physical_verified": false,
  "extrinsics_verified": false,
  "runtime_eligible": false,

  "created_utc": "2026-10-07T00:00:00Z"
}
```

字段语义（冻结）：

> 命名说明：本 schema 的顶层字段名对齐既有 leveling artifact 约定（`schema` / `from_frame` / `to_frame` / `kind`），与用户 2026-10-07 计划书示例中的 `schema_version` / `frame_from` / `frame_to` 为同一语义的仓库内统一写法；消费方只按本文件字段名实现。

| 字段 | 规则 |
|---|---|
| `direction` | 必须为 `"current_to_reference"`；消费方见到其它值 → `REJECTED`（04 §6） |
| `from_frame` / `to_frame` | 固定 `"leveled_session"` / `"reference_frame"`（01 §3） |
| `rotation_row_major` | 9 个 float64 行主序；必须在载入时通过正交/det/有限检查（01 I5） |
| `translation_m` | 3 个 float64（米），施加于**变换后的坐标**：`p_ref = R·p + t` |
| `euler_deg_zyx` | **仅诊断**；由矩阵导出（eulerFromR 同款）；消费方不得用其重建矩阵 |
| `method` / `method_version` | 生成方法标识；R3.8 审计 pair 用 `"fixed_icp_r3_2"`（= R3.2 固定 ICP 的语义冻结名）；方法实现变更必须升 version |
| `code_id` | `code_hashes`（provenance §4）的 `identity()`（leveling 同款：sorted-keys compact JSON 的 sha256） |
| `quality` | 摘要三元：`status ∈ {PASS, WARN, REJECT}`（门的三档输出，定义见 03）+ `gate_profile` + 机器原因码列表 |
| `scope/verified/runtime` | 与 leveling artifact 同族旗标；R3.8/R3.9 接入期间恒为 `offline_display_only / false / false / false` |

## 3. `diagnostics.json`（质量指标 + gate 记录）

```json
{
  "kind": "registration_diagnostics",
  "schema": 1,
  "pair": {"source": "cap_20261002_223757", "reference": "cap_20261004_203349"},
  "protocol": {
    "id": "r3.6_fine_static_v1",
    "fit_set": "curFinestrong(0.06m rebin) -> refFine(occ>=0.9, 0.06m rebin)",
    "normals": "refFine PCA 0.10m, min-eigvec",
    "residual": "point-to-plane |n·(Rs+t-q)|",
    "holdout": "even/odd half-split refit (fit-half -> eval-other)",
    "note": "metric definitions copied from R3.6 §4.2-4.3; no re-tuning"
  },
  "support": {"n_static_source": 0, "n_static_target": 0, "n_correspondence": 0,
              "coverage_xy": 0.0, "azimuth_sectors": [0,0,0,0,0,0,0,0], "max_sector_share": 0.0},
  "geometry": {"jtj_eigvals": [0,0,0,0,0,0], "eig_ratio": 0.0, "condition_number": 0.0},
  "residual": {"fit": {"n": 0, "p50": 0.0, "p90": 0.0},
               "holdout": {"n": 0, "p50": 0.0, "p90": 0.0},
               "holdout_fit_ratio_p50": 0.0},
  "basins": {"solutions": [{"init": "identity", "euler": {}, "t": [], "iters": 0,
                            "half_split": {"even": {}, "odd": {}}}],
             "pairwise_deltas_deg": {}, "resolution": {"resolved": true, "by": "split_half+holdout"}},
  "sanity": {"roll_deg": {"observed": 0.0, "limit": 0.0, "band": "pass"},
             "pitch_deg": {"observed": 0.0, "limit": 0.0, "band": "pass"},
             "yaw_deg": {"observed": 0.0, "limit": 0.0, "band": "pass"},
             "translation": {"observed": 0.0, "limit": 0.0, "band": "pass"}},
  "gate": {"profile_id": "reg_gate_v1",
           "thresholds": { "...": "reg_gate_v1 全部常量快照（03 §3）" },
           "checks": [{"id": "holdout_p50", "metric": 0.0, "band": "pass", "verdict": true}],
           "status": "PASS", "reasons": []},
  "created_utc": "2026-10-07T00:00:00Z"
}
```

- **指标定义与计算协议在 R3.8 冻结为 `r3.6_fine_static_v1`**（逐字沿用 R3.6 §4.2–4.3 的集合/重分箱/法向/残差定义），本文件只固定字段形状；实测数字在 R3.8 填充。
- `gate.thresholds` 必须写入所用 profile 的**完整常量快照**，使 artifact 自证判定依据；载入端只需按快照复算 band（确定性），无须依赖代码内的魔法数（03 §5）。
- `reasons` 机器码词表见 03 §4 / 04 §6；空列表表示无 WARN/REJECT。

## 4. `provenance.json`（SHA 绑定与验证记录）

```json
{
  "kind": "registration_provenance",
  "schema": 1,
  "source_session":      {"sid": "cap_20261002_223757", "meta_sha256": "71915d51...", "bin_sha256": "8afb660b..."},
  "reference_session":   {"sid": "cap_20261004_203349", "meta_sha256": "c3b55d1e...", "bin_sha256": "2ed3fc60..."},
  "source_leveling":     {"job_id": "6bc5aabf8f0041ffa961758b4e84da94", "method": "tls",
                          "transform_id": "de973fdbbec95379dfce52063cc8bdf473c9bbbf146a05a58452ec8f441b9a1f",
                          "transform_sha256": "7f1cd4f7...", "report_sha256": "5b8854eb...",
                          "manifest_sha256": "6a86d536..."},
  "reference_leveling":  {"job_id": "c9712acad48c4fb7a78cb119c08d4cdb", "method": "tls",
                          "transform_id": "5d8fd5c032f2b8131e5d5ef2027e0560605e9a7ba83376c55528b9c8edff6f03",
                          "transform_sha256": "c8459292...", "report_sha256": "e7455741...",
                          "manifest_sha256": "4fb6ae20..."},
  "background_reference": {"builder": "build_reference_map", "code_id": "sha256(identity(code_hashes))",
                           "params": {"bg_ref_hit_min_pts": 1, "bg_ref_occ_min": 0.5,
                                      "bg_voxel_xy": 0.15, "bg_voxel_z": 0.12,
                                      "ground_keep_below_m": 0.10, "z_max_m": 2.50},
                           "nframes": 102, "ref_voxels_total": 5286, "universe_count": 3707,
                           "digest": {"algo": "refmap_digest_v1", "value": "sha256:..."}},
  "code": {"files": {"human_pipe_lib.js": "f580778c...", "...": "..."}, "code_id": "..."},
  "verified": [{"check": "session_sha", "pass": true}, {"check": "leveling_sha", "pass": true}],
  "writer": {"tool": "TBD-at-R3.8", "version": "0", "runtime": "node v24.14.0 / python 3.x"},
  "created_utc": "2026-10-07T00:00:00Z"
}
```

绑定规则（冻结）：

1. **session 字节**：两侧 session 的 meta/bin SHA 必须与 artifact 创建时刻一致；任一变化 → `STALE`。
2. **leveling artifact**：每侧绑定 `job_id + transform_id + transform.json/report.json/manifest.json SHA`；任一项变化 → `STALE`。解析时**按 `transform_id` 找 job**，找不到或不匹配禁止用最新 job 顶替（01 §5）。
3. **background reference**：绑定 builder 参数 + 冻结计数（`ref_voxels_total`、`universe_count`）+ **`refmap_digest_v1`**：
   - 定义：对 `occ ≥ bg_ref_occ_min` 的全部体素按整数键升序，逐行 `key|x|y|z|occ`，其中 `x/y/z/occ` 按固定 `"%.5f"` 格式化（含负号、无科学计数），换行连接；前缀一行 `refmap_digest_v1|voxel_xy=0.15|voxel_z=0.12|hit_min=1|occ_min=0.5|nframes=<N>`；整体 sha256。
   - 用途：R3.9 在构建 reference 分支静态图时复算并比对；不匹配 → `STALE`（意味着 builder 代码、参数或参考会话数据已经漂移）。
4. **code_id**：生成侧算法文件集（至少 `human_pipe_lib.js` + 生成本 artifact 所用脚本/方法模块）的 SHA 映射 + `identity()`；消费侧若当前代码与 `code_id` 不符 → `STALE`（原因码 `METHOD_STALE`）。
5. **创建时间戳**：`created_utc`；不参与任何算术，仅供审计。

## 5. 载入校验顺序（loader 契约）

按序执行；首次失败即定状态，后续检查仍应继续记录（集中反馈）：

1. 目录存在 + `manifest.json` 可解析 → 否则 `UNAVAILABLE` / `REJECTED(ARTIFACT_MISSING|SCHEMA)`；
2. `manifest` 中三个 SHA 与文件字节逐一比对 → 任一不符 → `REJECTED(ARTIFACT_TAMPERED)`；
3. `registration.json` schema/kind/`direction`/frames → 不符 → `REJECTED(SCHEMA|DIRECTION)`；
4. 正交性/det/有限检查（01 I5）→ 不符 → `REJECTED(INVALID_MATRIX)`；
5. 绑定比对（session/leveling/refmap/code）→ 任一不符 → `STALE(<对应原因>)`；
6. `quality.status` + `gate.thresholds` 快照复算 band（确定性复算，不重算指标）：
   - profile_id 不认识 → `REJECTED(UNKNOWN_PROFILE)`；
   - 快照与 `diagnostics.gate.checks` 不一致 → `REJECTED(INCONSISTENT_GATE)`；
7. 汇总状态：`PASS→VALID` / `WARN→DEGRADED` / `REJECT→REJECTED`（状态机见 04 §2）。

## 6. 示例（audited pair，canonical B）

- `registration.json` 的 R/t 用 §2 中的示例值（= 01 §3.2 canonical B；与 R3.6 `conditions.B` 矩阵差 ≤ 7.9e-7）。
- `registration.json.quality.status` 与 `diagnostics.gate` 的**实际值**在 R3.8 创建时按 `reg_gate_v1` 计算；R3.7 仅登记示例形状，不预判 PASS/WARN（dry-run 预期见 03 §6）。
- `provenance.json` 的两侧绑定值 = 00 §3 的实测 SHA（本轮已逐位复核）。

## 7. 明确不包含

- 不包含在线/运行时状态（登录、会话、tracker 状态一律不进 artifact）；
- 不包含车辆/机器人控制语义；全链路只读；
- 不包含 reference 静态图本体（只绑 digest）；如需缓存图，属 R3.9 之后的独立增量；
- 不包含任何"自动选最新"逻辑；
- 不承诺物理标定语义（`physical_verified/extrinsics_verified/runtime_eligible` 恒 false；本 artifact 是**离线数据对齐**产物，不是外参标定）。
