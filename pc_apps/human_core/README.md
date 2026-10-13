# human_core 离线接口 v2

2026-10-11新增只读候选归因工具 `audit_fusion_candidates.js`，使用已审会话绑定GT快照及新输出目录；[R4唯一验收](../../docs/human_capture/HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md)。GT compact索引映射回raw；A+B重建联合评分点集；未标帧UNKNOWN，交叠类别不自动转换为候选身份。不修改引擎、生产、模型或GT。

当前唯一验收表：[HUMAN_UNIFY_R1_ACCEPTANCE v1](../../docs/human_capture/HUMAN_UNIFY_R1_ACCEPTANCE.md)。本模块不接管浏览器或板端生产。

```javascript
const {UnifiedEngine} = require('./engine.js');
const {make_frame_context} = require('./schema.js');
const engine = new UnifiedEngine({mode:'BASE_A'});
const generation = engine.begin_session('sid');
engine.set_online_background(frames.map(f => f.xyzi), {meta});
const diagnostics = engine.tick(make_frame_context({
    session_id:'sid', session_generation:generation, frame_index:0,
    timestamp:frames[0].timestamp, xyzi:frames[0].xyzi, meta,
}));
```

- `meta.leveling`或`already_leveled:true`表示点已配平，背景入口与tick必须使用同一标记。否则采用显式`leveling:{R,T}`/构造参数`leveling_rt`或缺省REF；REF仅为生产B参考的离线变换，不是本轮物理标定。冲突拒绝。
- `begin_session`每次重置本会话报告、背景、跟踪、保留和帧守卫，并返回新代际；所有tick必须携带代际。同sid循环旧回调也会拒绝。重复帧strict抛错，lenient忽略；回退必须重新begin；索引跳帧清track/票窗/保留，新身份带`track_segment`，不把未知帧计作观测。
- BASE_B保持原生产聚类/关联参数，单独执行原`find_clusters`/`associate`闭包。B不采用A去噪。A/U模式采用独立PIPE/RF闭包，实例配置不修改生产常量。
- U1沿用A；U2添加保留；U3在U2上使用rf51；U6将A跟踪器lost寿命设为30（可显式配置）。U4/U5没有推理artifact，抛BLOCKED。非B背景只支持online；none分类器/融合背景等未实现选项拒绝，不能靠填写配置模拟实现。
- 保留bank只由连续独立FG确认建立；仅补当前点云中存在但被背景/清理排除的邻近点，raw索引去重。retained/merged确认不刷新寿命，到期退出。它不能凭空恢复被遮挡的人，也不保证从一开始静立的人能建立bank。机制测试不等于真实保留收益。
- Candidate.point_indices指向本帧raw点；point_count与索引数一致。foreground_source区分fg/retained/merged；A包围盒为实际三轴范围。
- 输出v2删除furniture/person计数旧名称：accepted/rejected是分类器决策，不是GT身份。current只计末帧当前确认；ever是历史曾确认track身份，包含片段号，不是人数。算法匹配未实现，prf始终BLOCKED，不从标签存在推断可测精度。

```powershell
node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js
node --max-old-space-size=2048 pc_apps/human_core/test_baseline_parity.js --out <新文件.json>
node --max-old-space-size=2048 pc_apps/human_core/test_perf.js --out <新文件.json>
node --max-old-space-size=2048 pc_apps/human_core/runner.js --session captures/remote/<sid> --modes BASE_A,BASE_B,U1,U2,U3 --leveling ref --outdir <全新空目录>
```

runner必须显式给新目录，非空拒绝。每模式生成JSON+逐帧CSV，manifest记录完整SHA及输入/实际实现/模型/参考包络/坐标契约；加载器与背景建模时间不在逐帧性能门内。heapUsed门只针对JS堆，另记录RSS/external，不能说总内存受同一门约束。
