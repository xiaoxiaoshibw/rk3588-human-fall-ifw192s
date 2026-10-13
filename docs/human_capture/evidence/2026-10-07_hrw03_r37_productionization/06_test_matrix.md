# 06 · 测试矩阵（R3.7–R3.9）

- 日期：2026-10-07；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full。
- 说明：**R3.7 本轮不实现、不运行任何测试**（设计轮，全部条目状态 = NOT_RUN）。本矩阵是 R3.8/R3.9 的实施与验收入口；层级别与仓库既有习惯一致（node 断言脚本 + 离线 harness；不引入测试框架）。
- 依赖：01（契约）、02（artifact）、03（gate）、04（状态/失败）、05（shadow）。

## 1. T37 — artifact / loader / gate 单元级（R3.8 实现）

| ID | 前置 | 动作 | 预期 | 对应失败场景 |
|---|---|---|---|---|
| T37-01 | 无 artifact 目录 | 载入 | `UNAVAILABLE(NO_ARTIFACT)`；SAFE | F1 |
| T37-02 | manifest 缺失 / 坏 JSON | 载入 | `REJECTED(SCHEMA)` | F2 |
| T37-03 | 对 registration/diagnostics/provenance 各做一个单字节翻转副本 | 载入 | `REJECTED(ARTIFACT_TAMPERED)`（三种各一） | F3 |
| T37-04 | kind/schema/from_frame/to_frame 逐项改坏 | 载入 | `REJECTED(SCHEMA)` | F4/F6 |
| T37-05 | `direction` 字段改为 ref→cur | 载入 | `REJECTED(DIRECTION)` | F5 |
| T37-05b | 方向自检：矩阵为 Bᵀ、t 逆用的"合法格式"夹具 | 创建侧检查 | `REJECTED(DIRECTION)`（前向残差劣于反向） | F21 |
| T37-06 | R 非正交 / det=−1 / NaN / Inf 四变体 | 载入 | `REJECTED(INVALID_MATRIX)` | F7 |
| T37-07 | 篡改 session meta/bin 的绑定值 | 载入 | `STALE(SESSION_SHA_MISMATCH)` | F8 |
| T37-08 | 篡改 leveling transform/report/manifest 绑定值（三变体） | 载入 | `STALE(LEVELING_SHA_MISMATCH)` | F9 |
| T37-09 | 绑定 job 从 `captures/leveled` 拷贝目录中移除 | 载入 | `STALE(LEVELING_JOB_MISSING)`；**断言未改用 mtime 最新 job** | F10 |
| T37-10 | refmap digest 绑定值与真实构建不符 | 载入（构建 ref 分支时） | `STALE(REFMAP_DRIFT)` | F11 |
| T37-11 | 修改 `code_id` 绑定 | 载入 | `STALE(METHOD_STALE)` | F12 |
| T37-12 | `gate_profile` 改为 `reg_gate_v99` | 载入 | `REJECTED(UNKNOWN_PROFILE)` | F13 |
| T37-13 | 快照与 `gate.checks` 不符 | 载入 | `REJECTED(INCONSISTENT_GATE)` | F14 |
| T37-14 | 每个指标在 pass/warn/reject 边界各取两点（表驱动） | band 复算 | 与 03 §3.2 表逐点一致 | F15 |
| T37-15 | 聚合：全 pass / 单 warn / 任意 reject / 缺指标 | 聚合 | `PASS / WARN / REJECT / REJECT(UNFROZEN_PROFILE)` | F15/F16 |
| T37-16 | 盆地四夹具：单盆地 / 竞争+优势明确 / 竞争+无优势 / 不可区分 | §4.2 规则 | pass / pass(resolved) / `WARN(WEAK_OBSERVABILITY)` / `REJECT` | F16 |
| T37-17 | sanity 各分量在 limit 与 limit+ε | 判定 | pass / `REJECT(SANITY_BOUND)` | F15 |
| T37-18 | 状态机全部边（07 条转移） | 转移 | 与 04 §1 表一致 | —— |
| T37-19 | 重复应用 / 对 raw 应用 / 对错误 sid 应用 | 应用岗 | `ERR_DUPLICATE_REGISTRATION` / `ERR_FRAME_MISMATCH`（两变体） | F17/F18 |
| T37-20 | audited pair canonical B 夹具 | 方向自检 | 前向 ≤ 反向（数值记录） | F21 |
| T37-21 | 写入两遍同一目录；跨进程重启复算 manifest | 写入/校验 | 第二次写入被拒；SHA/artifact_id 跨进程一致 | —— |

## 2. T38 — shadow 集成级（R3.8 执行）

| ID | 前置 | 动作 | 预期 | 对应门 |
|---|---|---|---|---|
| T38-01 | 冻结输入 + R3.6 归档 | Branch A/B 复跑 | 与 `03_results.json` 逐整数一致；矩阵差 ≤1e-6；r7 19/19 checks 复现 | S1 |
| T38-02 | WD01 组/代表帧 | P/S/A 三分支 | residual_S ≤ 0.5×residual_A；不低于 P | S2 |
| T38-03 | WD02 桶 | 同上 | residual_S ≤ 0.5×residual_A；不低于 P | S3 |
| T38-04 | f55/f150/f155/f160 分带 | 同上 | 高带不恶化（f55 ≤+1.0 pp）；混合带如实登记 | S4 |
| T38-05 | clean controls 10 帧 | 同上 | 总吸收 ≤5 点 | S4 |
| T38-06 | 共同门 | 同上 | `cleanup_split_delta==0`、无新 green/purple、track 不丢 | S7 |
| T38-07 | 临时副本：wrong artifact（跨会话使用 / 改 reference_session） | 载入 + Branch S | 非 VALID；S 输出 == P | S5/F1 |
| T38-08 | 临时副本：翻转 registration 字节 / 翻转 leveling 字节 | 载入 | `ARTIFACT_TAMPERED` / `LEVELING_SHA_MISMATCH`；S == P | S5/F2 |
| T38-09 | 无 artifact | 载入 | `UNAVAILABLE`；逐帧计数与 clusters/events 与 P **完全相等** | S5/F3 |
| T38-10 | 运行期守卫夹具（F4/F5） | 应用岗 | 两个错误码各触发一次 | S5 |
| T38-11 | 同输入跑 2 次 | 确定性 | digest 一致 | S6 |
| T38-12 | 全部运行日志 | 日志检查 | `[REG]` 行按 04 §5；非 VALID 必有具体 reason | §5.6 |

## 3. T39 — 最小生产接入级（R3.9 执行）

| ID | 前置 | 动作 | 预期 |
|---|---|---|---|
| T39-01 | 能力旗标 off（默认） | golden 会话跑 console 链 | 与当前 production 输出逐位/逐计数一致 |
| T39-02 | 旗标 on + artifact `VALID` | 同上 | registered 路径启用；`frame_after=reference_frame:*` 入日志 |
| T39-03 | 旗标 on + `DEGRADED/REJECTED/STALE/UNAVAILABLE` 四状态 | 同上 | SAFE：与 T39-01 输出一致；UI 显示状态 |
| T39-04 | 回退演练 | ①旗标 off ②移除 artifact 目录 ③revert R3.9 commit | 三种方式均回到 SAFE；无残留副作用 |
| T39-05 | 日志格式 | 文本比对 | 与 04 §5 模板一致（含失败 reason 词表） |
| T39-06 | WD01/WD02 浏览器检查 | human_detect 页面 | 无新 green/purple；静态物被吸收 |
| T39-07 | 注册路径下的 leveling 选择 | 在存在多个 job 的会话上 | 使用 artifact 绑定 job；**不**使用 mtime 最新 job（01 §5） |
| T39-08 | matcher 未动的机器证据 | 源码 SHA 对照 | `human_pipe_lib.js` 与 R3.7 基线一致（或仅经授权的最小 diff） |

## 4. 测试资产约定

- 夹具（合法/篡改 artifact）全部放 R3.8 证据目录；篡改副本在临时目录生成、用后删除，仅保留日志与哈希。
- 回归基线：R3.6 `03_results.json`（digest `23830ede…`）与 r7 19/19 checks 作为 S1 的对账对象；不得重算覆盖。
- 未跑状态：本矩阵全部条目的 R3.7 状态 = **NOT_RUN**（无实现）；R3.8/R3.9 各自报告按条目 ID 给 PASS/FAIL/NOT_RUN。
