# 01 · 坐标系与方向契约（R3.7 冻结）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 本文件冻结 R3.8/R3.9 一切实现、artifact、日志、WebUI 的**唯一**坐标语义。任何与本文件冲突的表述（含历史文档中的简写）以本文件为准；历史文档不改写。

> **复审修订 R1（2026-10-07，独立复审后；writer：OpenCode/DeepSeek v4.1 Flash）**：① §2.2 例证修正为“同一会话 TLS job 的 roll 可差 ≈1.54°（例：202456 的 `a480b987/27f870c6`）”——原 “~1.1°” 不精确（203349 三 job 实测 0.9705°）；② §3.2 “逐位对齐”改为“≤1e-6 对账”（canonical 为 10 位小数存档值、非 float64 全精度；与 05 §5.1 一致）；③ §5 例证数字同步。复算协议与逐值见 [returns/HR-W03.md](../../returns/HR-W03.md)「R3.7 复审修订 R1」。

## 1. 帧链（生产语义）

```text
RAW_SENSOR                    frame_id = "innolidar"（session meta；raw points.bin）
    ↓ per-session leveling    （captures/leveled/<job>/tls/transform.json，恰好一次）
LEVELED_SESSION:<sid>         该会话自己的配平帧（"ground_offline_display"）
    ↓ cross-session registration（captures/registration/<src>__to__<ref>/，恰好一次；仅 VALID 时）
REFERENCE_FRAME:<ref_sid>     reference 会话的 LEVELED_SESSION（见 §2.3）
    ↓ background matcher      （existing _bg_match / extract_foreground，语义零改动）
FOREGROUND
```

四条消除歧义的总规则：

1. **leveling 之后不是"世界系"**。LEVELED_SESSION 只保证 z≈0 为地面、且由**某一个确定的 leveling artifact**产生；其 x/y 朝向仍继承 raw 会话，不同会话之间可差数度（R3.6 实测该差 ≈ 2.58° roll 级）。禁止把任一 LEVELED_SESSION 称为世界系/全局系。
2. **REFERENCE_FRAME 不是另一个新定义的 frame**，它就是 **reference 会话的 LEVELED_SESSION**（冻结选择，§2.3）。
3. **方向只允许 `current → reference`**：`p_ref = R_cur_to_ref · p_leveled + t_cur_to_ref`。artifact 只准存这个方向的 R/t；日志/UI 也只准按这个方向打印。
4. **同一变换只允许应用一次**。每个会话的 leveling 恰好一次、每对 (source, reference) 的 registration 恰好一次；重复应用是错误而不是幂等（§4）。

## 2. 每一层的精确定义

### 2.1 RAW_SENSOR

- 来源：`captures/remote/<sid>/{meta.json, points.bin}`，`point_layout` = little-endian float32 `[x,y,z,intensity]`，28B/点；`sensor.frame_id == "innolidar"`。
- 身份：`{"meta_sha256","bin_sha256"}`（与 leveling 的 source binding 同构）。
- z 语义未标定（安装下俯 ≈26°、物理高度未独立验证）——不属于本契约的修改范围。

### 2.2 LEVELED_SESSION:<sid>

- 产生者：`pc_apps/human_replay/leveling.py` 的离线 job（`scope=offline_display_only`，`physical_verified=false`，`extrinsics_verified=false`，`runtime_eligible=false`），每会话恰好一次。
- 帧名：`ground_offline_display`（`tls/transform.json.to_frame`）。
- **帧身份 = (sid, job_id, transform_id, method, SHA 集)**，不是"sid"本身：
  - 同一会话的不同 job/ROI 会给出不同的配平解（本仓实测同一会话 TLS job 的 roll 可差 ≈1.54°，例如 202456 的 `a480b987/27f870c6`）——因此 LEVELED_SESSION 必须以 **artifact 级** 身份引用；
  - R3.8/R3.9 中当 registration 可用时，source 会话的 leveling artifact 由 registration artifact **显式绑定**（按 `transform_id` 解析，而非按 mtime 取最新；见 04 §5）。
- 变换语义（既有，冻结）：`p_leveled = R_lv · p_raw + t_lv`，`R_lv/t_lv` 来自被引用的 `tls/transform.json`。

### 2.3 REFERENCE_FRAME:<ref_sid>

- **定义（冻结）**：REFERENCE_FRAME := reference 会话的 LEVELED_SESSION（即该会话被注册 artifact 绑定的那个 leveling artifact 的帧）。
- 禁止构造"另一个 reference 系"（另行标定的世界系、融合图坐标系等）。reference 静态图（R3.1 builder）天然构建在这一帧上；任何未来语义变化必须新开阶段并升版本，不得在本阶段内隐式发生。
- 身份同样以 artifact 级引用：(ref_sid, job_id, transform_id, SHA 集)。

### 2.4 FOREGROUND

- matcher（`_bg_match`：3×3×3 邻域、点到静态体素形心 `< bg_match_radius=0.12`）的输入点与静态图记录必须**同帧**。
- registration VALID 时：整体点云在 REFERENCE_FRAME，reference 静态图天然在 REFERENCE_FRAME，online 静态图在变换后的帧上重建 —— matcher 代码与语义零改动。
- registration 非 VALID（fallback `SAFE_FOREGROUND_ONLY`）时：保持在 LEVELED_SESSION(current)，只使用 online 静态图（= 生产现状 R2 链），**不做任何跨会话几何运算**。

## 3. 方向冻结与归档值对照

### 3.1 唯一允许的形式

```text
p_ref = R_cur_to_ref · p_leveled + t_cur_to_ref
```

- `rotation_row_major`：9 个 float64，行主序；`translation_m`：3 个 float64（米）。
- artifact 字段 `direction` 必须为 `"current_to_reference"`；`from_frame` 必须为 `"leveled_session"`；`to_frame` 必须为 `"reference_frame"`。
- 允许存在的反向转换仅用于显示/调试，必须在**内存中**由上述值推出（§3.3），禁止把反向值写入 artifact 或日志字段。

### 3.2 与 R3.2/R3.6 归档值的对照（只做表示法转换，不重新估计）

R3.2 固定 ICP 的归档形式是 **ref→cur**：euler ZYX `(1.7476°, −0.2818°, −2.3924°)`、`t = [0.0182, 0.031, 0.0012] m`（`R_r2c = Rz(yaw)·Ry(pitch)·Rx(roll)`；R3.6 CHECK 容差：euler ±0.02°、t ±0.002 m）。
R3.6 工具在建立条件 B 时按下式转为 cur→ref（`10_r36_registration.js` L727–728）：

```text
R_c2r = R_r2cᵀ
t_c2r = R_c2r · (−t_r2c)
```

本轮按同式对**归档存值**做只读转换，得到 canonical B（供 R3.8 按 ≤1e-6 对账；canonical 为 10 位小数存档值、非 float64 全精度；R3.6 由复跑矩阵得到的结果与此差 ≤ 7.9e-7，见 05 等价门）：

```json
"rotation_row_major": [
   0.9991163122, -0.0417420305,  0.0049191038,
   0.0415732367,  0.9986699485,  0.0304959007,
  -0.0061855220, -0.0302644488,  0.9995227874
],
"translation_m": [-0.01684841, -0.03178948, -0.00013234],
"euler_deg_zyx": {"roll": -1.7343, "pitch": 0.3544, "yaw": 2.3827}   // 诊断字段，非契约
```

- `euler_deg_zyx` 只是诊断/人读字段，定义与 `eulerFromR`（R3.6 工具）一致，**任何消费方不得用 euler 重建矩阵**（矩阵是唯一权威）。
- C/C_ALT 的归档值（`(−2.3102, 0.0813, 2.2269)` / `(−2.3373, 0.5931, 2.2435)`，t 见 00 §3）已是 cur→ref 表示，不在本对照表内。

### 3.3 反向转换（仅显示/调试，公式冻结）

```text
R_ref_to_cur = R_c2rᵀ
t_ref_to_cur = −R_c2rᵀ · t_c2r
```

禁止把 `R_ref_to_cur` 用于把点云"变回" current 帧再匹配。

## 4. 不变式与机器检查（duplicate-transform 防护）

| # | 不变式 | 检查时机 | 违反行为 |
|---|---|---|---|
| I1 | 每会话 leveling 恰好一次（leveling artifact 级） | 载入 | 现状既有行为，不改 |
| I2 | 每对 (source, reference) registration 恰好一次 | 应用前/后 | `ERR_DUPLICATE_REGISTRATION`（见下） |
| I3 | frame 链单向：`raw → leveled_session:<sid> → reference_frame:<ref_sid>` | 应用前/后 | `ERR_FRAME_MISMATCH` |
| I4 | artifact `direction=="current_to_reference"`、frames 字段匹配 | 载入 | `STALE/REJECTED`（见 04） |
| I5 | R 正交（`max|RRᵀ−I| ≤ 1e-6`）且 `|det(R)−1| ≤ 1e-6`、全部数值有限 | 载入/应用前 | `REJECTED` |
| I6 | 应用 registration 时，点云 frame 必须 `leveled_session:<artifact.source_session>` | 应用前 | `ERR_FRAME_MISMATCH` |
| I7 | 应用后 frame 必须变为 `reference_frame:<artifact.reference_session>` | 应用后（断言） | `ERR_FRAME_MISMATCH`（实现缺陷，fail-closed） |

### 4.1 frame tag 的载体（最小契约）

现状（`human_detect.js` `load_sid`）用布尔量 `S.leveled` 标记 leveling 已应用；点数据本身（Float32Array）不携带元数据。R3.8/R3.9 引入**最小并列状态**，不改变点数据格式：

```text
frame := "raw"                                   // 初始
       | "leveled_session:" + sid                // apply_leveling 之后
       | "reference_frame:" + ref_sid            // apply_registration 之后
```

- 机器检查（应用前）：

```python
assert cloud.frame == "leveled_session"        # 且 cloud.sid == artifact.source_session
apply_registration(cloud, artifact)            # 唯一允许的注册入口
cloud.frame = "reference_frame:" + artifact.reference_session
```

- 重复应用（对已是 `reference_frame:*` 的对象再应用 registration）必须直接报错：

```text
ERR_DUPLICATE_REGISTRATION
```

- 其它错误码（完整清单与语义见 04 §6）：`ERR_FRAME_MISMATCH`、`ERR_REGISTRATION_STALE`、`ERR_REGISTRATION_REJECTED`、`ERR_ARTIFACT_SCHEMA`、`ERR_ARTIFACT_TAMPERED`。

### 4.2 Python / Node 双侧约定

artifact writer、shadow harness（Node）与任何 Python 工具使用**同一组** frame tag 字符串与错误码常量；本文件即常量来源。禁止各侧自造别名。

## 5. 与现有 `leveled_latest` 选择规则的关系（重要）

- 现状控制台/页面按 `report.json` mtime 取"最新 TLS job"（`leveling.py` `/api/leveling/leveled_latest`）。
- 当 registration 参与时：**source 与 reference 两侧的 leveling artifact 都由 registration artifact 显式绑定**（记录 job_id + transform_id + SHA 集）。载入器必须：
  1. 按 artifact 记录解析对应 job；找不到 / SHA 不匹配 → `STALE`，禁止改用"最新 job"顶替；
  2. 在应用 registration 前验证当前载入的 leveling 变换就是 artifact 绑定的那一个；
  3. 未注册路径（无 registration）保留现有 mtime 规则，行为不变。
- 理由：registration 的正确性只对"确切的 leveling artifact 对"成立；mtime 规则会在存在多个 job 时静默换底座（本仓实测同会话 job 差最大 ≈1.54° roll，202456）。

## 6. 明确禁止（本契约下）

- 禁止把 leveling 后帧称为世界系；禁止定义第二个 reference 系；
- 禁止在 artifact/日志/WebUI 中使用 ref→cur 方向（历史和既有 leveling artifact 除外）；
- 禁止变更 reference 侧点云/静态图来"凑" matcher（只允许变换 current 侧整体点云）；
- 禁止重复 leveling / 重复 registration / 用 euler 重建矩阵做计算；
- 禁止在 registration 非 VALID 时做任何"近似对齐"或自动回退到其它 session 的 transform（fail-closed，见 04）。
