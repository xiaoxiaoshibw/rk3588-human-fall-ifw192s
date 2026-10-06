# GL-E 独审（复审 r1）

## 独立性声明

- 复审者：Claude（claude-fable-5）。与作者 OpenCode（opencode-go/deepseek-v4.1-flash）**不同提供方、不同模型**，2026-10-05 ONESHOT 授权下同一会话独立复审。**未参与实现**。
- ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（skill 工具加载，full）。
- 基线：`master @ b190834edd3b5ec4f74d2a662ee65fd0e88460f4`。

## 复审对象

- 工单：`docs/human_fall/tickets/GL-E_adaptive_offline_leveling.md` v1（作者 SUBMITTED）
- 回传：`docs/human_fall/returns/GL-E.md`
- 证据源目录：`docs/human_fall/evidence/2026-10-05_agl_e_r1/`
- 复审产物目录：`docs/human_fall/evidence/2026-10-05_agl_e_r1/review_01/`

## 范围核对

| 文件 | 回传 SHA | 实测 SHA | 一致？ |
|---|---|---|---|
| `core/adaptive_ground/transform.py` | `41dbca95…` | `41dbca95…` | ✅ |
| `tests/test_agl_e_offline.py` | `a8d2f1ac…` | `a8d2f1ac…` | ✅ |

## 逐条验收

复跑日志：`review_01/01_rerun_tests.log`（GL-E 专项 5/5 OK，0.008s）。GL-E 依赖 A/B/C/D 模块（均已复审通过）。

| 验收 ID | 判据字面 | 复跑证据 | 结论 |
|---|---|---|---|
| AGL-E-01 GT / gauge / inverse | source-plane→Rx@Ry/tz=d；yaw/tx/ty=0 gauge；R@n=up、proper R、det=+1、Z=signed residual、inverse 误差 ≤1e-12；已知 GT sign 正确；显示修正不能冒名安装角 | `test_gt_transform_gauge_inverse_invariance_AGL_E_01` ok。复审 `transform.py::validate_display_transform` 行 82–92：`|rotation[0,1]| ≤ 1e-15`（yaw gauge）、`translation[0]==0.0 and translation[1]==0.0`（tx/ty gauge）、`translation[2] > 0.0`（tz 正）、`orthonormal / det=+1`、`rotation @ rotation[2] = [0,0,1]`（R@n=up）——所有 ≤1e-12/1e-15 字面校验；`build_display_transform` 行 58：`mode: "display_only"`、`physical_verified/extrinsics_verified/runtime_eligible: False`——不冒名安装角 | PASS |
| AGL-E-02 source 绑定 / 输出独占 / 抽样确定性 | 同 source 行/frame/时间/units/accepted model 绑定；异常点计数保留；显示抽样不参与 fit/验收；输出新 ID 独占不改原输入 | `test_source_binding_invalid_rows_and_sampling_AGL_E_02` ok。复审 `transform.py::run_offline` 行 167–206：`require(digest(transform["frame_key"]) == digest(frame_key))` 帧绑定；`result_id = "agl-offline:" + digest(...)` 内容绑定；`apply_display_transform` 行 118–132：`output = array.copy()`（输入不变）；`_valid_mask`（行 113–115）：`isfinite & any(!=0)`——NaN/全零行原样保留并计 `invalid_row_count`；`display_sample` 行 156–164：确定性 stride 抽样、不修改输入、返回值 `.copy()`；author 测试覆盖 2 NaN + 2 全零不计入 | PASS |
| AGL-E-03 分层 / fallback / 坏 model 拒 | raw/filter/accepted/reference 分开；无 accepted 不补 identity；HOLD 数值保持但 fresh/geometry expiry 正确；坏 model/reload 不半应用 | `test_reference_fallback_hold_and_bad_model_AGL_E_03` ok。复审 `transform.py::run_offline` 行 187–193：`transform is None` → `mode="reference_only"`、`transform=None`、`mapped_points=None`——**不补 identity**；行 198：`mode = "accepted" if result["applied"] else "hold_numeric"`——applied / hold 分层；行 194：`validate_display_transform(transform)` 在 apply 前重校验——坏 kind/字段立即拒 | PASS |
| AGL-E-04 physical 1.14 只读 / 资格不升级 | physical_height_m 1.14 只读；observed tz 独立；kind 与 physical/runtime 资格不能升级；d_over_nz / refit_RMS optimizer 不存在；参与 fit / 独立验证区分 | `test_physical_reference_readonly_AGL_E_04` ok。复审 `transform.py` 行 21：`PHYSICAL_HEIGHT_M = 1.14` 硬编码只读常量；`build_display_transform` 行 58–63：`physical_verified / extrinsics_verified / runtime_eligible: False`、`measurement_reference.note: "independent laser-user measurement; read-only; never a fit target"`——只读记录；`validate_display_transform` 行 100–102：三字面 false 强制；整个变换 schema 中**不存在** d_over_nz / optimizer 键 | PASS |
| AGL-E-05 frame report / 历史 FAIL 引用 | per-frame raw/filtered/accepted 角/offset 及 RMS/P95/pose spread 完整；P02 四区/留一区历史 FAIL 不追改；参数/selector 变更新 epoch | `test_frame_report_and_historical_failures_AGL_E_05` ok。复审 `transform.py::build_frame_report` 行 209–251：per_frame 含 raw/filtered/accepted 三角+offset+rms_m+p95_m 一套；`pose_spread.pitch_std_deg/roll_std_deg/offset_std_m` 用 `np.std`（ddof=0，与独立 oracle 一致）；`historical_leave_one_out_failures` 仅以 `copy.deepcopy` 引用传入值，`historical_note: "citation only; not recomputed; not to be greened by filtering"`——历史 FAIL 不追改、不被新过滤绿掉 | PASS |
| AGL-E-S01 流程 | one writer / ponytail / diag / 有效回归 / SHA / 原始命令 / 停写 / 指定独审；无设备/实时接入 | 复审：`transform.py` 只 import `copy/hashlib/math/numpy` + 项目内 `ground_evidence/numeric/contracts`——无 ROS / 无 SDK / 无文件写盘；HEAD 未动；未接 runtime / WebUI；离线 runner 是纯函数（result 内存对象 + result_id digest） | PASS |
| AGL-E-D01 设备/物理 | 离线单 | 未运行 | NOT_RUN |

## 复审期间发现

1. **作者 E 自检（正名）已落地**：回传记录"无效行仅按非有限计数；未对齐采集链路'全零占位符'语义"——复审 `transform.py::_valid_mask` 行 113–115：`np.all(np.isfinite(array), axis=1) & np.any(array != 0.0, axis=1)`——非有限 + 全零两种无效行统一计。该修复属本单内的有效行映射公式语义闭环。
2. **`transform_id` digest 包含 epoch/revision/frame_digest**：行 64–65（build）与行 107–109（validate）双向校验——跨 epoch/revision 重用同一 R/t 不会产生同 id，旧 transform 无法被误重放。
3. **`run_offline` 不写盘**：纯函数、内存对象、result_id 内容绑定；"离线 runner"不引入副作用；写盘 CLI/WebUI 集成属后续单（GL-G/P 方向）。

## 观察

- 模块层次：**A（schema/domain）→ B（quality 评分）→ C（consensus 仲裁）→ D（temporal/controller 状态机）→ E（transform 应用与离线 runner）**。每层只产 artifact JSON + digest 内容绑定；后层只 validate 前层 artifact。
- `validate_display_transform` 把"判据字面"全部落到 require 断言：yaw gauge / tx/ty gauge / tz 正 / 正交 / proper R / R@n=up / mode / 三字面 false / measurement_reference / transform_id 内容绑定——审 reader 直接在源码中阅读判据。
- `_valid_mask` 用 NumPy 向量化(n,)掩码：`apply_display_transform` 只用 `output[finite] = array[finite] @ rotation.T + translation` 替换有效行——**输入 array 不被就地修改**（`array.copy()` 在行 126）。
- `run_offline` 显式支持"HOLD 数值保留但 fresh/eligible 分开"：decision.fresh / eligible_for_geometry 由 GL-D 提供；GL-E 不重复判断，只用 decision 字面。

## 复审结论

**软件 PASS**（AGL-E-01..05 全过；D01 NOT_RUN 属本单边界）。范围越界无、不冒名旧 kind、physical 1.14 只读、不补 identity。

整单 **不报 ACCEPTED**：D01 NOT_RUN。GL 六单批量独审就此全部完成。
