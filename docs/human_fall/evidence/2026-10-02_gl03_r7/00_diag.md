# GL-03 R7 集中诊断与父/摘要结构资格设计（2026-10-02）

范围：只修 G03 结构资格（完整父 frames 类型、旧摘要 container/label/child 类型）。R6 分类规则已独立
PASS，G04/G05 保持；`node_runtime.py 889ead5e` 不动。基线工作树 HEAD
`8a5a2b28f922794bc25277319fd8dc85681802f1`（外部 HC-01..04 提交，非本轮；未触碰），四源 SHA
`calibration 913cc2df`/`node_runtime 889ead5e`/GL03 tests `63eabfd5`/`lidar_candidates 318abc78` 与
R6 提交 `22_source_manifest.json` 逐一相符（`00_baseline.txt`/`00_before_manifest.json` 1440 文件）。

## 1. 修复前复现（R6 旧检查只读）

`01_matrix_before.txt`：`input_matrix_checks.py` **6 FAIL + 2 ERROR，EXIT=1**：

- 完整父 `frames.lidar=42/True/['innolidar']` 仍投影（validator 只按 truthiness，resolver 只对 str 做
  一致性比较，非 str 被跳过）；`frames.reference=[]/{}` 被当未声明仍投影；
- 真摘要 `frames='damaged'`/`transforms='damaged'` 在 `.get` 处裸 `AttributeError`（无法返回明确
  unavailable）；
- 摘要 `transforms.T_reference_lidar='damaged'` 被 `calibration_reference_transform` 当作
  “无 known canonical”，随后合法 standalone 成功回退投影。

## 2. 实际消费者与缺失结构检查

| 消费者 | 现状 | 缺口 |
|---|---|---|
| `_validate_geometry_calibration`（完整父） | frames 必须 dict，但 `lidar` 仅 truthy；`reference` 未检；`transforms/rotations` 经 `or {}` 吞掉假值；子记录直接 `.get` | 非 str 名称、容器 reference、非 dict container/child 可通过或裸异常 |
| `calibration_reference_transform` | `(transforms or {}).get(...)`；非 dict 子记录返回 None（等同缺失） | 坏子记录与 absent/unknown 不分，导致 standalone 回退 |
| `resolve_reference_transform` | R6 分类正确；legacy 未验 container/label 类型；标签只对 str 比对；tail 直接 `.get` | 坏 container 异常；非 str 标签跳过 from/to 绑定 |
| `build_snapshot` coordinate 块（`lidar_candidates.py:607`） | `(calibration or {}).get("frames", {}).get("reference")` 直接读原始输入 | 真摘要 `frames='damaged'` 时在 resolver 已判 unavailable 后仍裸 `AttributeError`（14d 的 frames ERROR 实际落点） |

## 3. 已审结构规则映射（PLAN_REVIEW 类型矩阵）

| 对象 | 合法/兼容 | 损坏处置 | 实现位置 |
|---|---|---|---|
| full `frames` | dict；`lidar` 必需非空 str；`reference` None 或非空 str | 数字/bool/list/空串/容器 → `GeometryCalibrationError`，不跳过一致性比较 | `_validate_geometry_calibration` |
| full `transforms`/`rotations` | None/缺失=空；dict | 其它类型（含 `[]`、字符串）→ 明确 raise；子记录非 dict（含 None）→ 明确 raise | 同上 |
| 真摘要 `frames`/`transforms` | 缺省/None=未声明；dict（空 dict 也未声明） | 非 dict（含非空 str/list/数字）→ resolver `reference_calibration_invalid`，无 AttributeError | `_legacy_summary_reason`（新） |
| 摘要帧标签 | 缺省/None=未声明；已声明必须非空 str | 非 str/空串 → invalid，不能省略 from/to 绑定 | 同上 |
| 摘要 `T_reference_lidar` | 缺省/None、合法 unknown → 原 standalone fallback 保留 | 非 dict（str/list/数字）→ invalid，不得回退 standalone | 同上 + `calibration_reference_transform` 防御 |
| known 子记录 | dict → 原 `validate_known_transform`/冲突/from/to/parent 绑定 | 数值/名称坏 → 原严格拒绝 | 原路径不变 |
| R6 分类/full blocks/schema | 原规则完整保持 | 不新增单值补丁、不降级 legacy | 不变 |

顺序：分类（R6）→ 完整父整份 validator（含新帧类型）或摘要结构守卫 → canonical 子记录严格资格 →
冲突 → from/to/parent/frame 绑定。**不用 catch-all 吞错；不把类型失败当“无声明”跳过绑定。**

## 4. 全部组合检查映射（实现前核对）

| 组合 | 预期 | 覆盖 |
|---|---|---|
| full frames.lidar=42/True/list/''/None | unavailable | R6 14d + R7 新回归 |
| full frames.reference=[]/{}、数字/bool/空串 | unavailable；None/缺失保持 | R6 14d + R7 |
| full transforms/rotations=字符串/list、子记录=字符串/None | 明确 ValueError/unavailable | R7 新回归 |
| 真摘要 frames/transforms 缺省/None/空 dict | 未声明，standalone/known 原义 | R7 正例 |
| 真摘要 frames/transforms='damaged' 或数字 | unavailable，无裸异常 | R6 14d + R7 |
| 真摘要 label=数字/bool/list/空串 | unavailable；None/缺失未声明 | R7 |
| 真摘要 child=字符串/list/数字 + standalone | unavailable，不回退 | R6 14d + R7 |
| 真摘要 child 缺省/None/status=unknown + standalone | 合法 fallback 保留 | R7 正例 |
| 合法 full/legacy 普通扩展/无标定 standalone | 几何/兼容不变 | 原 9/4/10/8/4/3 与 GL03 套件 |
| G04/G05 reload/同新 ID/caller 冻结 | R5 逻辑不变 | 14/14b + node SHA 不变 |

## 5. 最小修复

1. `_validate_geometry_calibration`：`frames` 必须 dict；`lidar` 非空 str；`reference` None/非空 str；
   `transforms`/`rotations` 为 None 或 dict；子记录必须 dict（复用原 record 数值资格）。
2. 新增 `_legacy_summary_reason(summary)`：version（R6 语义移入）+ container/label/child 结构检查，
   resolver legacy 分支调用；Tail 读取改为经 `isinstance(frames, dict)` 保护。
3. `calibration_reference_transform`：container/child 非 dict 时返回 None（防御）；损坏路径已由前两层
   提前拒绝，合法 unknown/缺失回退语义不变。
4. `lidar_candidates.py` `build_snapshot` coordinate 块：先取 `calibration["frames"]` 并确认 dict 再读
   `reference`（否则 None）；损坏 container 下 resolver 已 unavailable，此处不得再抛。该改动只涉及
   coordinate 元数据读取，不触碰候选连接/索引/几何算法；`lidar_candidates.py` SHA 因此变化，R3 O01
   统计的依赖 SHA 需要在 R7 内重跑对照（见检查计划），不能只口头沿用。
5. 测试追加 R7 回归；不新增 class/schema/框架；node_runtime 不改。

## 6. 检查计划

`01` 修复前矩阵 6 FAIL+2 ERROR exit1（已留）→ 修复后 `14d` 全绿；原 R1 `10` 9、R2 `11` 4、
R3 `12` 10、R4 `13` 8、R5 context `14` 4、R5 closure `14b` 3；GL03 `15`、fall `16`、follow `17`、
GL02 `18/19`；py38 AST `20`、范围 `21`、manifest `22`、反向重建 diff `23`。O01：因
`lidar_candidates.py` 本轮有 coordinate 元数据安全性改动，把 R3 `20_o01_planes_ablation_r3.py` 复制
到 R7（仅将 OUT 指向 R7 新文件）重跑，与 R3 `21_o01_planes_ablation_r3.json` 逐项对照；不在原地覆写
旧证据。UI 不受影响沿用。设备/真实身份/D01 仍 NOT_RUN/BLOCKED。
