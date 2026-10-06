## 2026-10-05 GL-E R1 / OpenCode / SUBMITTED

# GL-E R1 回传（transform / 只读离线应用；实现者自述）

状态 SUBMITTED。离线软件链 A→B→C→D→E 本轮连续开发到此收束；实现者停写，指定独审待批量进行。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-E（AGL-E-01..05）/ R1 / OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash）/ 2026-10-05。
- 验收表：`tickets/GL-E_adaptive_offline_leveling.md` v1，SHA256=01345d5b4a5b7d7402c73087f7ed9a5385b9f1d162dc7531b1aeda5f8a72bac8。
- HEAD：0d5ab424…（外部提交；本 writer 未执行任何 git 写命令；A/B/C 部分文件已被外部收录）。
- ponytail 路径：`C:\Users\30680\.config\opencode\skills\ponytail`（复用 display_rotation/strict_numeric_array/digest；无新依赖；单模块+单测试）。
- 证据：`evidence/2026-10-05_agl_e_r1/`。

## 集中诊断与根因覆盖

| 项 | 根因/说明 | 修复位置 | 保留行为 |
|---|---|---|---|
| E 自检（正名） | 无效行仅按非有限计数；未对齐采集链路"全零占位符"语义 | `transform.py` 统一 `_valid_mask`=有限且非全零（apply/residual/runner 一致） | 有效行映射公式不变；输入永不被修改 |
| 设计要点 | 无 accepted 不得补 identity；HOLD 数值与资格分层；physical 只读 | `run_offline`/`validate_display_transform` | 旧 kind/consumer 拒收保持 |

操作矩阵见 00_diag.md。

## 实际变更

| 文件 | 用途 | SHA256 |
|---|---|---|
| `core/adaptive_ground/transform.py` | 新增：FinalTransform 构建/校验、apply/inverse、只读 runner、frame report | 41dbca95be97a324c35b4fd84a5b9c545d83fde4a038cf84b51e597e455007ce |
| `tests/test_agl_e_offline.py` | 新增 5 用例 | a8d2f1ac1c5b15deb17337fdcebb21f5ac884b8eddcc90b736807cb71e3b8460 |

## 逐条验收（自验）

| ID | 结果 | 证据要点 |
|---|---|---|
| AGL-E-01 | PASS | GT 10/26.623/−1.395/45°+roll−10°：R@n=up、det=+1、正交、yaw gauge、tx/ty=0 均 ≤1e-12；inverse 往返 ≤1e-12；signed residual 与显示 z 不变式 ≤1e-12；旧 `validate_known_transform`/`validate_geometry_calibration` 均拒收本 kind |
| AGL-E-02 | PASS | source rows/frame/units/accepted model 绑定；无效行（2 NaN+2 零）计数=4 且原样保留；输入字节不变；输出新 result_id+mapped sha；display 抽样确定性、不参与 fit/验收；重复运行逐位一致 |
| AGL-E-03 | PASS | 无 accepted → `reference_only`（不补 identity）；HOLD 带 last_good 数值 → `hold_numeric` 且 fresh/eligible=false；坏 kind 变换即拒、无半应用、输入不变 |
| AGL-E-04 | PASS | physical 1.14 只读记录 + measurement_reference；observed tz 独立可变化；physical 篡改/资格升级/未知字段（d_over_nz、optimizer 等）全部拒绝；字段集封闭 |
| AGL-E-05 | PASS | 逐帧 raw/filtered/accepted 角与 offset、RMS/P95、pose spread（std 与独立 oracle 一致）完整；P02 四区/留一区历史 FAIL 以只读引用携带（source 标注、不被 caller 修改、不重算不追改；数值证据在 GL-B P02 用例） |
| AGL-E-S01 | 流程完成（自验）；独审 NOT_RUN | 单 writer/ponytail/诊断/回归/SHA/停写；无设备/实时接入 |

回归：专项 5/OK/exit0；全量 488/OK/exit0（483+5；A 基线 458 起累计 +30）；冻结 10 blob=基线。

## 未闭合与限制

- 指定独审待批量（A R2/B/C/D/E）；不伪报。
- 离线 runner 为纯函数/内存工件；写盘 CLI 与 WebUI 集成属后续单（GL-G/P 方向），本轮不引入文件输出。
- 显示集成约束（用户要求）：最终展示在**总控制台算法工作台**，保持解耦——本模块只产出 JSON 安全工件（transform/离线结果/帧报告），显示层只消费版本化字段与引用摘要，不反向 import core 数组、不在 UI 重拟合。
- 设备/物理/全场外推仍 NOT_RUN/BLOCKED；软件通过不替代物理精度，不自动放行 H/F/G/H/I。

## 交给复审

- 证据：00_baseline、00_diag、10_test_agl_e_log、11_regression_after_e、30_scope_check。
- 本轮连续开发汇总（A R2 后）：GL-B/C/D/E 各回传与证据已分别落盘；失败与修正全部保留；不自动派发下一单。
