# GL04 R6 设计前置 / 2026-10-03

判据保持 GL04_ACCEPTANCE v1；唯一生产写入 OpenCode Go Flash/default DB，Codex 独审。
R5 提交四文件 SHA-256 与 claude_r5_baseline_sha.txt 相同、Git blob SHA 与 returns 一致。
90/92/91 独立旧检查 41/2/48 PASS、exit0可复用；95 新消费者检查 exit1：source 模式、绑定一致、当前候选存在、ground unknown/none、verifier ok，fall 仍 upright。

根因：R5 分离 sourceAlignmentQualified 后把 raw XYZ 与 ground 跌倒颜色/状态仍放在同一资格中。source-only 当前实际 XYZ/track 应保留；fall/告警颜色需单独有 observationQualified 支持，不可因 raw 测量合格冒充地面观测。对应已有 V06/C10 与 R5 PLAN_REVIEW C01/C08消费者区分，不新增要求。Codex 90 原 unknown/none 只测 ground 模式拒绝，漏 source fall 消费者，记录审查遗漏。

R5 fixture.state.calibration 缺 schema_version，而快照 schema1。真实浏览器 normal 两 mode正确拒绝，V08 fixture无法显示有效目标。generator未完整复制 node_runtime.py:1259–1320 已输出绑定字段，no_extrinsics还把有实际source几何写 unavailable。V08/C15证据生成缺陷；不能放松nullable门。新目录修 fixture，不覆写R5。

同族扩大检查（不是新需求）：97_codex_additional 对V05/C11的旧按钮覆盖显式snapshot.units.length、candidate.center_ground_m、ground block.kind/schema_version原地修改；原token漏这些已声明坐标/版本，旧按钮仍发select。V02/03/C13/14 source显式mm仍标m、ground.support_units=mm仍ready。source raw观察、physical fall、预测与无目标/lost/ambiguous状态应按C08分别核查；不依据旧state字段存在维持实测或绿色。原lib兼容缺units的既有用例保留，显式错误单位必须拒，不做全对象哈希框架。

## 设计前置矩阵

下表与原 C01–C15 操作矩阵一起使用。实施者必须先在本轮00_diag映射实际函数、赋值顺序、选择/当前source测量/ground跌倒/预测诊断/DOM与3D颜色各消费者后才写生产。

| 行 | 组合与消费者 | ID | 预期与检查 |
|---|---|---|---|
| C01 | startup / legacy source-only / locked，双方cal/GDID absent/null | V06/07/09 | first select原ID；实际source XYZ/track保留，fall unknown、目标颜色unknown；ground入口禁用 |
| C02 | raw/state/candidate任一先到 × source/ground | V03/06 | 当前绑定到齐恢复，交错不冒旧状态 |
| C03 | 同内容reload × locked/ready/prediction | V05/09 | token/原ID保留，测量与physical资格各自不变 |
| C04 | 同ID异cal内容 / 新cal ID / 双侧交错 × 列表/拖选/目标 | V05/06 | 单侧混配unknown/拒旧，当前完整双侧恢复 |
| C05 | known/null/undefined GDID、schema、cal × 完整/partial输入 | V05/06 | 原44断言不降；known对缺失拒，both-null legacy source可看 |
| C06 | schema2 / frame错误 / epoch错误 × source/ground | V03/06 | 明确坏绑定全部拒；无伪绿色/旧选择 |
| C07 | 当前目标→空/other/重复→唯一恢复 × ready基线 ×两mode | V07 | 当前position空、fall unknown；ready历史不背书；恢复只当前候选 |
| C08 | locked实际→predicted/occluded/ambiguous/lost × ground有效/无 | V06/07/09 | 预测独立灰诊断，不成当前position；锁/事件/原预测框原义；无地面fall不green |
| C09 | silent expiry/disconnect→reconnect × ready/pending ×两mode | V06/07/09 | unknown/空/拒旧、DOM-overlay-GPU一致；历史/ack保留；只当前数据恢复 |
| C10 | ground valid→unknown→none→valid / verifier false、monitor unknown | V06 | source实际XYZ可保留（合法source门），physical fall/目标颜色unknown；ground模式禁用/回退；valid恢复upright原色 |
| C11 | caller改candidate/R/t/source_frame/units × list/drag | V05 | token再核，旧拒，当前原ID；仅相机变化不改绑定 |
| C12 | rotate/zoom/resize/DPR、near/far/behind/退化 ×两mode | V04/05 | 原8角保守裁剪；真实DPR切不动NOT_RUN，不改数值冒实测 |
| C13 | 0/3/3000/3001/9000支持 ×两mode | V02 | ≤3000、有源索引/metadata，grid常显非地面 |
| C14 | 显式units missing/mm/other ×同ID旧token | V03/05 | 错单位不ready/旧选择拒 |
| C15 | Node形状performance/全部fixture绑定 ×normal/tilted/no_extrinsics | V08 | 新fixture复制真实已发布字段与物理false；资格正/负例断言。queue真实字段、FPS实际、offline明确 |

范围：最多 preview human_fall.js/lib.js/test.js/index.html；先找最小共享physical观察门与所有DOM/3D调用者。不改原44断言，只追加有效负例。新fixtures/generator只写r6。正式/core/config/driver/其它webui/旧证据/原数据冻结；不部署/采集/板端网络/GL05/commit/push/reset/checkout。基线见 ../2026-10-03_gl04_r5/96_codex_scope_before.json（tracked/untracked范围1572文件）。
