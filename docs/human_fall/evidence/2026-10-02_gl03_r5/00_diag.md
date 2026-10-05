# GL-03 R5 集中诊断与设计（2026-10-02）

范围：只闭合 R4 独立复审的 R4-A（G04/G05：standalone reload 重读 caller、只比较 canonical）与
R4-B（G03：错误 kind 父冒充 legacy、父 frames.lidar 与 T.from 未绑定）。G01/G02/G07/G08、已审
的 R4 十/九/四/八方法、O01 统计与设备边界不重做。基线 HEAD
`49eb7581faabdda031642e04d3ef4ffe75d48331`；`00_before_manifest.json` 覆盖 tracked+untracked
1319 个文件；`calibration.py a2d06194…`、`node_runtime.py 9bd65ff9…`、
`lidar_candidates.py 318abc78…`、GL03 tests `1e7edb6b…` 与 R4 提交 manifest 一致。

## 1. 修复前复现（旧检查只读，未改断言）

`01_context_before.txt`（真实命令/exit）：R4 `context_checks.py` **3 FAIL / 1 ok，EXIT=1**：

- `test_G03_full_parent_wrong_kind_cannot_become_legacy_summary`：完整 artifact 的
  `kind='unsupported_geometry_calibration'` 仍输出 `center_reference_m`；
- `test_G03_parent_lidar_label_must_match_reference_source`：父 `frames.lidar='other_lidar'`
  与 `T.from='innolidar'` 矛盾仍投影；
- `test_G05_standalone_binding_stays_fixed_across_same_id_reload`：
  `STANDALONE_RELOAD {'changed': False, 'before': [1.0,-2.0,0.7], 'after': [9.0,-2.0,0.7],
  source_before: [2.006022…], source_after: [-5.993978…]}`，同 ID reload 后遮挡预测错 8 m。

## 2. 共享根因（R4-A / R4-B）

| 缺陷/ID | 根因 | 受影响入口、消费者与状态转换 |
|---|---|---|
| R4-A G04/G05 | `node_runtime.py:373 self.transform = transform` 保存 caller 活引用；`:460 _resolve_reference_binding` 每次 reload 都重新读取；`:563-568` 同 ID 只比较父 canonical 记录，不比较本节点实际有效绑定 | `apply_ground_context` 的 reload 准备；locked/occluded 预测（`:1337 invert_transform`）、`process` 快照（`:700`）、`_source_frame_mismatch`（`:838`） |
| R4-B G03 | `calibration.py:331` 只有 `kind==KIND` 才走整份 `validate_geometry_calibration`；错误 kind 完整 artifact 落入 legacy 路径后仅 `validate_known_transform` 内部 R/t，绕过父类别验证；`:352-362` 只查 frame_id/T.from 与 frames.reference/T.to，未把父 `frames.lidar` 与 T.from/实际 source 绑定 | 共享 `resolve_reference_transform`，即 `build_snapshot`（纯 API/decoder/node/replay）与 `FallNodeCore` 启动/reload 全部 reference 消费者 |

## 3. PLAN_REVIEW 操作表逐行映射（实现前先核对全部组合）

| PLAN_REVIEW 边界 | 实际函数/位置 | 固定来源 | prospective 有效绑定 | 校验/比较/赋值顺序 | 失效消费者 |
|---|---|---|---|---|---|
| startup 输入 | `FallNodeCore.__init__` `node_runtime.py:373` | 在节点持有入口把 standalone 深拷贝冻结（`self.transform = copy.deepcopy(transform)`），caller 之后原地修改不可达 | `_prospective_reference_binding(calibration)`：`canonical=calibration_reference_transform`；有 canonical 用 canonical，否则用冻结 `self.transform`；都交 `resolve_reference_transform` | 先 `validate_geometry_calibration` → 冻结 standalone → 用冻结副本做显式冲突检查（`:374-388`）→ 绑 `_reference_transform`（`:392`） | `process` 快照、`_prediction_in_source` inverse、`_source_frame_mismatch` |
| 解析父资格 | `resolve_reference_transform` `calibration.py:330-335` | 父 `kind` 显式存在（非 None）时必须 == KIND；无 kind/None 的旧最小摘要仍走 legacy | 同上 | `kind` 错 → 直接 `(None, reference_calibration_invalid)`，不读取 transforms；`kind==KIND` → 原整份 `validate_geometry_calibration` 不变；legacy 原路径不变 | 所有 reference 投影消费者 |
| 跨记录源 | `resolve_reference_transform` 尾部 `calibration.py:352-362` | 父 `frames.lidar`（声明 source）与调用方实际 `frame_id` | 有效 record 的 `from_frame` 必须同时等于两者中所有非空标签；`to_frame` 仍绑定 `frames.reference` | 在 `validate_known_transform` 之后、返回前逐项比较，任一矛盾 → `(None, reference_from_frame_mismatch)` | 同上 |
| reload 准备 | `apply_ground_context` `node_runtime.py:553-577` | 固定 startup standalone（不是 caller 当前内容） | `_resolve_new_context` 先整份验证新 artifact；随后 `new_binding = _prospective_reference_binding(new_calibration)`（新 canonical 优先，known→unknown 时才用冻结 standalone） | 全部在写任何状态之前完成 | 旧 snapshot/track/baseline 资格（只有新 ID 才在事后失效） |
| 同 ID | `apply_ground_context` `:563-577` | `self._reference_transform`（实际有效）+ 父 canonical | `new_binding` | `same_canonical`（原 JSON 相等，None≡None）**且** `same_binding`（`_reference_transform` 与 `new_binding` JSON 相等，None≡None）都成立才放行；任一变化 → 赋值前 `ValueError` | 无（拒绝即零副作用，pending/locked/status 保持） |
| 新 ID | `apply_ground_context` `:587-593` | 新 artifact + 冻结 standalone | `new_binding` | 校验/比较通过后原子赋值 calibration/ground/derived，并直接绑 `new_binding`（同一份已解析记录，不再重读任何来源）；随后执行原 `changed` 失效块 | baseline/snapshots/positions/requests/action_history；旧 events/seq/stamp/epoch 不动 |
| 消费 | `_process_locked:700`、`_prediction_in_source:1337` | `self._reference_transform` 单份记录 | 同左 | 快照与预测 inverse 消费同一对象；resolver 返回 None/无效时保持 source-only/unavailable 原义 | — |

组合核对（全部在实现前列明）：known canonical + standalone 相同/冲突；unknown artifact + 合法
standalone（startup 与 reload）；legacy 无 kind 摘要好/坏记录；错误 kind 完整父（纯 API 与节点不可
达路径）；同 ID 相同/不同 reference + caller 原地改；新 ID canonical 采用与 known→unknown
fallback；locked/occluded/pending/无新帧 status/request/invalid 恢复。规则来源为 GL03 v1
G03/G04/G05 与已审 PLAN_REVIEW，无新 schema、无用户取值、无契约矛盾。

## 4. 最小修复

1. `core/calibration.py` `resolve_reference_transform`：
   - 父记录 `kind` 显式非 None 且 != KIND → `reference_calibration_invalid`（错误 kind 不再冒充 legacy）；
   - 有效 record 的 `from_frame` 必须与父 `frames.lidar`（若有）及实际 `frame_id`（若有）一致，
     否则 `reference_from_frame_mismatch`；其余 canonical/legacy/standalone/深拷贝路径不变。
2. `core/node_runtime.py`：
   - `__init__` 冻结 standalone（深拷贝），冲突检查改用冻结副本；
   - 新增 `_prospective_reference_binding(calibration)`，`_resolve_reference_binding` 复用它；
   - `apply_ground_context` 在任何赋值前计算 `new_binding` 并与 `self._reference_transform`
     比较；同 ID 时 canonical 或实际绑定任一变化都拒绝；放行时直接绑定 `new_binding`。
3. `tests/test_gl03_candidates_geometry.py`：追加 R5 回归（不改旧断言），覆盖同 ID caller 修改、
   新 ID known→unknown fallback、occluded/预测 inverse、pending 无副作用、无新帧 status/request、
   invalid 恢复、错误 kind/父 lidar 的纯 API 与节点入口。

## 5. 保留行为与检查计划

保留：无 kind 旧最小摘要、合法 standalone、unknown 原义、新 ID 采用新 T 并按原语义失效、同 ID 同
内容 `changed=false` 保持资格、启动冲突拒绝、G01/G02 几何与 G06/G07 开关。

检查（真实命令/exit 全留本轮目录，先旧后新）：`01` 修复前 context（3 FAIL，已留）→ 修复后
context 4/4；R1 9、R2 4、R3 10、R4 8；GL03 套件（追加 R5 后）；fall discover；follow；GL02
lifecycle/pending；Python3.8 AST；范围/未跟踪 SHA manifest。不重跑未受影响的 UI/O01；O01 依赖的
`lidar_candidates.py` 未改，R3 统计继续适用。设备/真实身份/D01 仍 NOT_RUN/BLOCKED。
