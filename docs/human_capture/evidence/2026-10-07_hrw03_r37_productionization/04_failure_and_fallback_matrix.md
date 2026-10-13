# 04 · 失败矩阵 / Fallback / 防护契约（R3.7 冻结）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 核心原则（用户 2026-10-07 指令）：**宁可背景去除性能下降，也不要错误 transform 把人体吸收到静态背景里。** 任何可疑 transform 一律不进入 foreground 计算。
- 依赖：01（帧/方向/错误码）、02（artifact 与校验顺序）、03（gate 与原因码）。

## 1. 状态机（六状态，用户指定）

```text
UNAVAILABLE ──artifact 就绪──▶ VALIDATING ──┬─▶ VALID      （全部门通过）
                                           ├─▶ DEGRADED   （WARN：shadow only）
                                           ├─▶ REJECTED   （REJECT：结构/矩阵/门失败）
                                           └─▶ STALE      （绑定漂移）
STALE       ──提供匹配的新 artifact──▶ VALIDATING
REJECTED    ──提供新的 artifact──────▶ VALIDATING
VALID       ──绑定输入变化（下次载入时）──▶ STALE
```

| 状态 | 含义 | production foreground 允许的消费 |
|---|---|---|
| `UNAVAILABLE` | 没有已配置/存在的 artifact | `SAFE_FOREGROUND_ONLY`（§2） |
| `VALIDATING` | 载入校验进行中（瞬态，通常 <1 帧加载时间） | 不得开始消费；等待判定（页面载入路径本身即异步等待） |
| `VALID` | 结构 + 绑定 + 矩阵 + gate 全部通过 | 允许注册分支（R3.9 接入后） |
| `DEGRADED` | gate WARN（如盆地未消解、支撑偏弱） | **shadow only**；production 等同非 VALID |
| `REJECTED` | 结构/矩阵/gate REJECT（含未知 profile） | `SAFE_FOREGROUND_ONLY` |
| `STALE` | SHA/ID 绑定漂移（session/leveling/refmap/code） | `SAFE_FOREGROUND_ONLY` |

- **只有 `VALID` 允许 registered 路径**；`DEGRADED → shadow only`；其余 fail-closed。
- 状态判定顺序 = 02 §5 的校验顺序；首个失败即定状态，其余失败仍记录到日志（集中反馈）。
- 载入期内输入视为不可变；输入在载入后变化，其影响在下一次载入时体现（不存在"运行中热切换 artifact"）。

## 2. Fallback：`SAFE_FOREGROUND_ONLY`（冻结语义）

进入条件：状态 ≠ `VALID`（含 `DEGRADED`）。

行为定义（与生产现状 R2 链逐位一致，不得多也不算少）：

1. 点云保持在 `leveled_session:<current_sid>`（**不施加任何跨会话 transform**）；
2. 静态图 = 仅 online 静态图（`build_static_map`，语义不变）；
3. matcher（3×3×3、0.12 m、z 工作空间）不变；聚类/清理/人体/Fall 链不变；
4. 明确**禁止**的替代动作：换用其它 session 的 transform、用 euler 近似、扩大匹配半径"补"、静默降级到"看起来差不多"的解。

数值预期：`SAFE_FOREGROUND_ONLY` 下 R3.6 条件 A 即其口径（WD01 吸收 84.0%、WD02 34.2%——即"背景去除性能下降"是可接受的代价）。

## 3. 失败矩阵（场景 → 检测 → 状态 → 行为）

| # | 场景 | 检测点/机制 | 状态 | 行为/用户可见 | 测试 ID |
|---|---|---|---|---|---|
| F1 | artifact 目录不存在 / 未配置 | loader 步骤 1 | `UNAVAILABLE(NO_ARTIFACT)` | SAFE；日志一行 | T37-01, T38-F3 |
| F2 | `manifest.json` 缺失/坏 JSON | 步骤 1–2 | `REJECTED(SCHEMA)` | SAFE；日志 | T37-02 |
| F3 | 任一文件字节被改动 | 步骤 2 SHA 比对 | `REJECTED(ARTIFACT_TAMPERED)` | SAFE | T37-03, T38-F2 |
| F4 | kind/schema 不匹配 | 步骤 3 | `REJECTED(SCHEMA)` | SAFE | T37-04 |
| F5 | `direction` ≠ current_to_reference | 步骤 3 | `REJECTED(DIRECTION)` | SAFE | T37-05, T38-F1 |
| F6 | frames 字段不匹配（from/to） | 步骤 3 | `REJECTED(SCHEMA)` | SAFE | T37-04 |
| F7 | R 非正交 / det≠1 / NaN | 步骤 4 | `REJECTED(INVALID_MATRIX)` | SAFE | T37-06 |
| F8 | source/reference session 字节变化 | 步骤 5 | `STALE(SESSION_SHA_MISMATCH)` | SAFE | T37-07, T38-F2 |
| F9 | leveling artifact 变化（transform_id/SHA 任一） | 步骤 5 | `STALE(LEVELING_SHA_MISMATCH)` | SAFE | T37-08, T38-F2 |
| F10 | artifact 绑定的 leveling job 不存在 | 步骤 5（按 transform_id 找 job） | `STALE(LEVELING_JOB_MISSING)` | SAFE；**禁止**改用"最新 job"顶替（01 §5） | T37-09 |
| F11 | reference map digest 漂移 | 步骤 5（构建 ref 分支时复算） | `STALE(REFMAP_DRIFT)` | SAFE | T37-10 |
| F12 | 代码与 `code_id` 不符 | 步骤 5 | `STALE(METHOD_STALE)` | SAFE | T37-11 |
| F13 | 未知 gate profile | 步骤 6 | `REJECTED(UNKNOWN_PROFILE)` | SAFE | T37-12 |
| F14 | 快照与 checks 不一致 | 步骤 6 | `REJECTED(INCONSISTENT_GATE)` | SAFE | T37-13 |
| F15 | gate REJECT（残差/支撑/条件/盆地恶化） | 创建时写入 `quality.status` | `REJECTED(reasons…)` | SAFE | T37-14 |
| F16 | gate WARN | 同上 | `DEGRADED(reasons…)` | shadow only | T37-15 |
| F17 | **重复应用** registration | 应用前 frame 已是 `reference_frame:*` | 运行期错误 `ERR_DUPLICATE_REGISTRATION` | fail-closed（开发/测试期必须暴露，不允许生产吞错） | T37-16 |
| F18 | 对非 leveled frame 应用 | `frame != leveled_session:<artifact.source>` | `ERR_FRAME_MISMATCH` | fail-closed | T37-17 |
| F19 | 把 A→B 的 artifact 用于 A→C / C→A | 绑定（session id 或 SHA）不符 | `REJECTED/STALE`（同 F8/F9） | SAFE | T38-F1 |
| F20 | 应用期数值溢出/非有限（防御性） | 应用前后断言 | 错误 + SAFE | fail-closed | T37-18 |
| F21 | 手工把 ref→cur 写成 current_to_reference（writer 方向 bug） | 创建时方向自检（§4.4） | `REJECTED(DIRECTION)` | 不发布 artifact | T37-05b |
| F22 | 生产现状（无 reference 分支） | —— | `UNAVAILABLE` | SAFE = 现状 | T39-01 |

## 4. 防护契约

### 4.1 重复变换防护（机器可查的不变量）

- frame tag 语义与错误码见 01 §4；本层不变量：
  - **I2/I3 由唯一的应用入口强制**：`applyRegistration()` 只接受 `frame == "leveled_session:<artifact.source_session>"` 的对象，成功后写回 `"reference_frame:<artifact.reference_session>"`；
  - 对已注册对象再次调用 → `ERR_DUPLICATE_REGISTRATION`（不允许幂等短路）；
  - leveling 同理只允许 `raw → leveled_session`。
- 实现形状（R3.9 落地；R3.7 冻结语义，不实现）：

```js
function applyRegistration(cloud, artifact) {           // cloud: {buf, frame, ...}
  if (cloud.frame === "reference_frame:" + artifact.reference_session)
    throw new Error("ERR_DUPLICATE_REGISTRATION");
  if (cloud.frame !== "leveled_session:" + artifact.source_session)
    throw new Error("ERR_FRAME_MISMATCH");
  /* 单遍 R·p+t（与 leveling apply_Rt_inplace 同款） */
  cloud.frame = "reference_frame:" + artifact.reference_session;
}
```

- 布防位置：任何未来出现的"第二处 apply"必须在 `applyRegistration` 入口被 I2 拦住（禁止绕过写 `cloud.frame`）。

### 4.2 绑定的失败语义（为什么必须 STALE 而不是回退）

- 任一绑定漂移（F8–F12）意味着"该 transform 只对旧的输入成立"；**没有**任何合法的自动修补（重新配准属新 artifact，不在运行时做）。因此只允许 `STALE → SAFE`，直至新的 artifact 提供并重新通过校验。

### 4.3 载入器与 `leveled_latest` 的关系（消除 mtime 不确定性）

- 注册路径下：source/reference 两侧 leveling 由 artifact 显式绑定；载入器按 `transform_id` 解析（01 §5）；找不到 → F10。
- 未注册路径（无 artifact / SAFE）：保留现状 mtime 规则，行为不变。

### 4.4 方向自检（creation-side，新增于本设计）

- 动机：F21（writer 方向 bug）在结构上无法由正交性检查发现；必须有一个不依赖"direction 字段"的独立检查。
- 定义（创建时执行，协议同 `r3.6_fine_static_v1`）：对同一对应集分别评估
  - 前向：`|n·(R p + t − q)|` 与
  - 反向：`|n·(Rᵀ p − Rᵀ t − q)|`（同一序列化数据的"逆用"）
- 规则（v1）：`fit_p50(前向) ≤ fit_p50(反向)` 必须成立，否则 `REJECTED(DIRECTION)`。
- 数据支撑：本会话实测（只读、协议同 R3.6）在 audited pair 的 D1 解法族上，前向残差显著优于逆用（misalignment 量级 0.5°–2.6° 时差 ≥ 2×）；两会话几乎重合（misalignment ≪ 0.5°）时两者接近，此时方向误用无害但仍会被门以其它指标约束。**R3.8 须在实现时把本检查纳入 gate 附加度量并冻结具体实现；未冻结前 artifact 不发布。**

## 5. 日志契约（R3.9 生产输出）

成功（每次载入输出一次，字段如实、未测填 `null`）：

```text
[REG] state=VALID
[REG] source=cap_20261002_223757
[REG] reference=cap_20261004_203349
[REG] artifact_sha=sha256(registration.json)
[REG] method=fixed_icp_r3_2 gate=reg_gate_v1
[REG] holdout_rmse=<holdout.p50 或 null>
[REG] support=<n_correspondence / inlier_ratio 或 null>
[REG] conditioning=<condition_number 或 null>
[REG] transform rpy=(-1.7343,0.3544,2.3827) translation=(-0.01684841,-0.03178948,-0.00013234)
[REG] frame_after=reference_frame:cap_20261004_203349
```

失败（示例；`reason` 只允许 03 §4.4 / 本文件词表）：

```text
[REG] state=REJECTED reason=WEAK_OBSERVABILITY
[REG] state=REJECTED reason=HOLDOUT_MISMATCH
[REG] state=STALE reason=LEVELING_SHA_MISMATCH
[REG] state=UNAVAILABLE reason=NO_ARTIFACT
```

- **禁止**只写 `registration failed` 一类无原因日志；`state=` 行必须无条件出现（含 VALID）。
- `DEGRADED` 时额外输出 `[REG] gate=WARN reasons=[...]`；UI 显示"registration: DEGRADED (shadow only)"一类明示，并保持 foreground 与 SAFE 完全一致。

## 6. 错误码 / 状态名 / 原因码总表（冻结词表）

| 类别 | 值 |
|---|---|
| 状态 | `UNAVAILABLE` `VALIDATING` `VALID` `DEGRADED` `REJECTED` `STALE` |
| 运行错误码 | `ERR_DUPLICATE_REGISTRATION` `ERR_FRAME_MISMATCH` `ERR_REGISTRATION_STALE` `ERR_REGISTRATION_REJECTED` `ERR_ARTIFACT_SCHEMA` `ERR_ARTIFACT_TAMPERED` |
| 原因码（03 §4.4 + 04） | `NO_ARTIFACT` `SCHEMA` `ARTIFACT_TAMPERED` `DIRECTION` `INVALID_MATRIX` `SESSION_SHA_MISMATCH` `LEVELING_SHA_MISMATCH` `LEVELING_JOB_MISSING` `REFMAP_DRIFT` `METHOD_STALE` `UNKNOWN_PROFILE` `INCONSISTENT_GATE` `UNFROZEN_PROFILE` `WEAK_SUPPORT` `SPARSE_CORRESPONDENCE` `LOW_COVERAGE` `WALL_CONCENTRATION` `ILL_CONDITIONED` `WEAK_OBSERVABILITY` `RESIDUAL_HIGH` `HOLDOUT_MISMATCH` `SANITY_BOUND` |

## 7. 回退（rollback）路线

1. **能力旗标**（R3.9）：registration 消费默认关闭（配置项）；关闭时行为与当前 production 逐位一致（= F22 / SAFE）。
2. **删除/改名 artifact 目录** → 下次载入 `UNAVAILABLE` → SAFE；**无需改代码**。
3. **R3.9 commit 单一职责**（仅 registration integration）；出问题 `git revert` 单个提交即回到 SAFE 行为；不得与 matcher/参数改动混提。
4. 任何状态下都**不删旧 artifact、不原地改 artifact**；新版本 = 新目录（02 §1）。
5. `captures/registration/` 属用户数据：代码不得自动清理；工单不授权删除。
