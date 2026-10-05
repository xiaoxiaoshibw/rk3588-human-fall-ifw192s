# GL-03 R4 集中诊断（2026-10-02）

范围：只闭合 R3 独立复审的 F1/F2/F3（reference 严格资格、同 ID 内容变化、standalone 解绑）及节点启动冲突。G01/G02/G07/G08 与 O01 统计/R3 已过检查不重做；G06/O01 真实身份、D01 设备继续 NOT_RUN/BLOCKED。基线 HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`，R3 四文件 SHA 与 `2026-10-02_gl03_r3/22_source_manifest.json` 逐一相符（`00_baseline.txt`）。

## 1. 修复前复现（R3 review_checks 原样只读）

`python -B -W error docs/human_fall/evidence/2026-10-02_gl03_r3/codex_review_01/review_checks.py` → **10 FAIL / exit 1**（`01_r3_review_before.txt`）：

- F1a：malformed standalone（from/to 缺、status=broken、units=mm）与损坏父 artifact（schema 99、缺 calibration_id）仍输出 `center_reference_m`；
- F1b：节点 `calibration=record` + 显式冲突 T 时静默丢弃显式 T，仍用 canonical 投影；
- F2：同 ID 把 T.x 1→9，`apply_ground_context` 返回 `changed=false`；随后空帧遮挡预测用新 inverse 解出 source x=-5.993978，与旧 track 原 source x=2.006022 差 8 m；
- F3：standalone caller 在绑定后原地改 `translation_m[0]=9`，同点 reference x 3.006→11.006。

## 2. 共享根因

| 缺陷/验收ID | 根因 | 受影响入口与消费者 |
|---|---|---|
| F1 G03 | `resolve_reference_transform` 只用 `_load_transform` 校验 R/t 数值，不校验名称/方向/units/status/evidence；canonical 父 artifact 未整份校验；节点 `_resolve_reference_binding` 在调用 resolver **之前**就把显式 T 置 None | `build_snapshot`（纯 API/decoder/node/replay 共用）、`FallNodeCore.__init__`、所有 reference 坐标消费者 |
| F2 G04/G05 | `apply_ground_context` 的 `changed` 只比较 calibration_id/GDID，同 ID 换 T 后无条件换 `_reference_transform`，旧 snapshot/track 资格未失效 | `apply_ground_context`、locked/occluded 预测、`_latest_valid_snapshot`/`tracker`/baseline 资格 |
| F3 G05 | resolver 返回调用者传入 dict 本体，`self._reference_transform` 是活引用 | 节点快照/预测 inverse 绑定 |

## 3. 最小修复位置

1. `core/calibration.py`：新增 `validate_known_transform`，复用既有 `make_transform` 严格构造器（非空互异 frame、direction、units=m、evidence、status/evidence 一致、刚性 R、合理 t）；`resolve_reference_transform` 对 `kind==KIND` 的完整 artifact 先过 `validate_geometry_calibration` 整份校验，记录再走 `validate_known_transform`，返回深拷贝。**无 kind 的旧最小 calibration 摘要与合法 standalone 保持原路径**。
2. `core/node_runtime.py` `__init__`：显式 transform 与 artifact-owned T 同时存在时先调用共享 resolver；`reference_transform_conflict` 明确 `ValueError` 拒绝，不再静默丢弃。reload 仍由 artifact T 权威覆盖旧 standalone（`_resolve_reference_binding` 原行为保留），新版本合法切换不被旧 standalone 阻塞。
3. `core/node_runtime.py` `apply_ground_context`：同 calibration_id 且 reference 记录内容不同时，在任何状态写入前 `ValueError` 拒绝，要求新 ID；同内容 reload 仍 `changed=false` 保持资格。比较用 JSON 结构相等，`None≡None` 视为相同。
4. 共享 resolver 返回值深拷贝，快照与 prediction inverse 消费同一份固定绑定；legal standalone/no-artifact 行为不变。

## 4. 保留行为与检查计划

保留：G01/G02 逐点几何；R2 四方法与 R3 其余通过项；无 canonical 时合法 standalone 支持；无 kind 最小摘要；artifact-owned T 上 unknown→standalone 回退；新 ID 全量重载采用新 T + caller 解绑；O01 脚本仅依赖未改动的 `lidar_candidates.py`，R3 统计证据继续适用。

计划与结果（真实命令、exit、日志见本轮目录）：原 R3 review_checks 复跑 10/10 OK（`02`）；R1 九方法 9/9 OK（`04`）；R2 四方法 4/4 OK（`05`）；R4 新增对抗检查 8/8 OK（`06/07`）；GL03 42/42（`03`）；fall 全量 314/314（`08`）；follow 2/2（`09`）；GL02 12/12+2/2（`10/11`）；Python3.8 语法检查通过（`13`）；UI 18+18（`14/15`）；范围检查仅 3 个声明文件变化（`16`）；最终源码 SHA 见 `17_source_manifest.json`。
