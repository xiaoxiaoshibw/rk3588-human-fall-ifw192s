# GL-03 R6 集中诊断与 G03 输入分类设计（2026-10-02）

范围：只收敛 G03 父输入分类（完整产物 kind 缺失/null + 不支持 schema 不得降级为旧最小摘要）。
G04/G05 的 R5 固定 standalone/prospective reload 已独立 PASS，本轮不动；`node_runtime.py` 除非同根因
否则不改。基线 HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`；`00_before_manifest.json` 覆盖
tracked+untracked 1375 文件；`calibration.py 1c1d40ef…`、`node_runtime.py 889ead5e…`、GL03 tests
`6c0ce2f6…`、`lidar_candidates.py 318abc78…` 与 R5 提交 `22_source_manifest.json` 逐一相符。

## 1. 修复前复现（R5 旧检查只读，未改断言）

`01_closure_before.txt`（真实命令/exit）：R5 `closure_checks.py` **2 子例 FAIL / 1 方法 2 其他 PASS，
EXIT=1**。完成 artifact（构造器生成，保留 units/created_at_utc/status/verification/rotations/input/
ground 等）设 `schema_version=99` 后删除 `kind` 或置 `null`，`build_snapshot` 仍输出非空
`center_reference_m`（`14b_closure_checks.txt` 同因）。

## 2. 根因

`core/calibration.py` `resolve_reference_transform` 当前只按 `kind` 值分类：`kind==KIND` 走整份
`validate_geometry_calibration`；显式非 None 错误 kind 拒绝；`kind` 缺失/None 一律落入旧最小摘要路径，
其原始 `transforms.T_reference_lidar` 经 `validate_known_transform` 内部 R/t 通过，于是不支持 schema99
绕过完整 validator。上一轮只修了“错误 kind 字符串”分支，未定义 legacy 的正向形态。

## 3. 已审分类规则映射（PLAN_REVIEW，先分类再验证，失败不降级）

| 输入类 | 判定规则 | 实际函数/顺序 | 结果 |
|---|---|---|---|
| 合法完整 artifact | `kind == KIND` | `resolve_reference_transform` 先整份 `validate_geometry_calibration(deepcopy)`，之后原 canonical/记录/绑定链 | 不变 |
| 完整产物缺 kind（删除/null） | `kind is None` 且出现构造器专属完整块 | 同一整份 validator → kind 不符 → `reference_calibration_invalid` | 拒绝/unavailable，不进入 legacy 投影 |
| 显式错误 kind | `kind is not None and != KIND` | 直接 invalid（R5 行为保留） | 拒绝 |
| 真旧最小摘要 | `kind` 缺失/None 且无完整块；`schema_version` 缺省或为受支持 v1 | 原 legacy 路径：`calibration_reference_transform` + `validate_known_transform` + 冲突/from/to/parent/frame 绑定 | 合法好记录照旧投影；坏记录/frame 拒绝（既有） |
| 真旧摘要带非法/未知 schema | `schema_version` 键存在且非 `int`（或 bool）或 != 1 | 分类处即 `reference_calibration_invalid` | 拒绝，不冒充 v1；缺 schema 仍兼容 |
| 合法 standalone / 无 calibration | 原路径 | `transform` 严格资格/冲突/绑定不变 | 不变 |

完整产物结构标志取构造器专属块（键存在即算）：`units`、`created_at_utc`、`rotations`、
`verification`、`status`、`input`、`ground`、`ground_derived`、`sensor_height_m`。旧摘要可见字段
`calibration_id`/`schema_version`/`ground_status`/`ground_derived_id`/`frames`/`transforms`/`note`
不作标志；不为未知普通扩展字段建黑名单，不补造 kind、不把 schema99 改 1、不新增 schema/框架。

## 4. 全部组合检查映射（实现前核对）

| 组合 | 预期 | 现有/新增覆盖 |
|---|---|---|
| 合法 full artifact + 合法旧摘要 + 无标定 standalone | 原几何/兼容行为保持 | R5 GL03 tests、R2 4、R4 8 |
| 完整 artifact kind 删除/null（schema99） | unavailable，不投影 | R5 closure（修复前 FAIL → 修复后 PASS） |
| 完整 artifact kind 删除（schema1） | unavailable（完整块不可降级） | R6 新增套件回归 |
| 完整 artifact 错误 kind 字符串 | unavailable | R4 06、R5 套件（保留） |
| 完整 artifact kind 合法但 schema99/ID 坏 | unavailable | 既有 GL03 `test_damaged_full_artifact…` |
| 真摘要无 kind 无 schema，好/坏记录 | 好记录投影；坏记录 unavailable | R4 06、既有 GL03 legacy 测试 |
| 真摘要 `schema_version=1` / 99 / True | 1 可用；99、True 拒绝 | R6 新增套件回归 |
| 摘要 from/to/frame/parent 绑定坏 | unavailable | 既有 R2/R3/R4 检查 |
| full artifact+ground/derived+扩展 | 原完整 validator，源索引/旧几何不变 | GL02 12+2、GL03 套件 |
| caller 修改/reload/occluded、同/新 ID | R5 已过固定绑定保持 | R5 closure 两个 G05 方法 + context 4 |

## 5. 最小修复

1. `core/calibration.py`：新增 `FULL_ARTIFACT_KEYS` 常量与 `_has_full_artifact_shape()`；重排
   `resolve_reference_transform` 分类：`kind==KIND` 或（缺 kind 且有完整块）→ 整份验证；显式错 kind
   → invalid；真摘要 → 检查存在的 `schema_version` 必须为受支持 v1，再走原路径。更新 docstring。
2. `tests/test_gl03_candidates_geometry.py`：追加 R6 回归（旧断言不改）：kind 删除/null（schema99 与
   schema1）不投影；真摘要 schema1 投影、schema99/True 不投影。
3. `node_runtime.py` 不改（R5 逻辑无同根因）。

## 6. 保留行为与检查计划

保留：G01/G02/G04/G05/G07/G08 全部已过证据；合法旧摘要/standalone/unknown 原义；node/ROS 严格加载。

检查（真实命令/exit 全留本轮目录）：`01` 修复前 closure exit1（已留）→ 修复后 `14b`；R1 `10` 9、
R2 `11` 4、R3 `12` 10、R4 `13` 8、R5 context `14` 4；GL03 `15`、fall `16`、follow `17`、GL02
`18/19`；py38 AST `20`、范围 `21`、manifest `22`、反向重建 diff `23`。O01/UI 不受影响：O01 依赖
`lidar_candidates.py` SHA 未变故沿用；不重复 UI 凑数。设备/真实身份/D01 仍 NOT_RUN/BLOCKED。
