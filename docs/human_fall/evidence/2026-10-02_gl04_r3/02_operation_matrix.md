# GL04 R3 消息组合与消费者矩阵

判据GL04_ACCEPTANCE v1。每行组合消费者：source / ground、unselected / locked实测 / predicted / baseline pending / ready；列表旧按钮 / 当前按钮 / drag进行中 / 无交互。允许裁剪时00_diag须解释依据，不能只跑孤立helper。

| 行 | 输入 / 顺序 | 所有消费者的预期 | IDs |
|---|---|---|---|
| C01 | startup无消息、legacy无R/t、合法source-only | raw仍可看；无变换禁用ground、不造identity；保留已有source选择/ack行为（不把缺新增渲染字段当坏源坐标） | V01/03/05/09 |
| C02 | raw→CAND→STATE、raw→STATE→CAND、STATE/CAND→raw | 只有raw源seq/stamp/frame与当前snapshot/state一致才给目标观测；首轮合格消息到齐立即同一套读数/RT/框，非等下一帧消息碰巧更新 | V01/03/06 |
| C03 | 同内容同ID reload、任一先到（state/cand） | 完整相同绑定保留资格/正常颜色；旧token内容相同可继续，新渲染token不无故拒选 | V05/06 |
| C04 | CAND cal2→STATE仍cal1→STATE cal2；反序STATE cal2→CAND cal1→CAND cal2 | 混配阶段unknown、position空、拒旧选择；两侧新绑定到齐只从当前实际目标恢复，events保留 | V03/05/06/07 |
| C05 | 新GDID、same-ID不同R/t/coordinate内容；state/cand交错 | GDID及可得坐标绑定比较；旧token失效，当前消费不借旧state/RT；实际新绑定恢复 | V01/05/06 |
| C06 | snapshot/state calibration.schema=2各自/双方2；snapshot schema2、坏frame、epoch/session不匹 | 错值相等也不能变成支持版本；unknown/不可选，不跨源数据 | V03/05/06 |
| C07 | candidate当前目标完整→缺详情/空list→只有other→恢复本目标；ready基线保留 | 只消费对应本目标的当前已发布几何；不能first candidate/nearest/重新跟踪；无本目标详情fall unknown/position null。匹配只比较已有标识/字段作一致性守门，不浏览器算候选或几何 | V06/07 |
| C08 | locked实测→prediction/occluded/ambiguous/lost/unselected；有/无other candidate | 保留旧锁/告警/预测语义；prediction不伪当前实测；没有本目标当前geometry不补position ground；baseline/history不删 | V07/09 |
| C09 | ws断连/重连、新消息恢复；socket open但quiet >TTL；无新STATE/CAND分别过期 | DOM、overlay、GPU同时失效（一次dirty重绘）；ground入口/panel不能保留旧有效色；raw可留但帧龄诚实；events保留、旧token拒绝 | V03/05/06/08 |
| C10 | ground valid→unknown→none→valid，verifier ok→unavailable→ok（state/cand先后） | unknown颜色/物理读数门控；不以ready基线/上次状态恢复资格；恢复同当前binding | V03/06/07 |
| C11 | caller原地改candidate/RT/源frame/metadata；render token后变化 | 当前按钮/drag提交都再核不可变原token，拒绝旧选择，原source candidate_id发回 | V05/06 |
| C12 | source/ground八角：camera rotate/zoom/resize/DPR-only，near/far/behind/退化 | 当前视锥/矩阵、两画布同步；当前mode命中，旧coordinate token不能投client id；不红屏。browser能力做不到DPR只写NOT_RUN | V04/05 |
| C13 | supports 0/3/3000/3001/9000点；2D ground_local合法/3D有限合法/3D null或NaN非法；显式frame/version/units错 | ≤3000/层与sampled_from/total/indices；未知3D分量不置0伪支持；支持与grid分离、known R/t作显示，两mode一致 | V02/03 |
| C14 | source units / transform units缺失或mm/其它；已知m正例 | 不以“显示m”掩盖未知/错单位，ground输入资格严格；合法source原义保留 | V03/06 |
| C15 | state.performance.kind/schema/enabled/queue_dropped有效、disabled/未知/非法、stale；source/ground/synthetic | 消费human_fall_node真实字段，未知不造0；render-fps仅renderer.render计数，pcSkip/Hz原义保留，三场景同屏同frame | V08/09 |

设备/物理D01一律NOT_RUN；core/GL02/03已审算法SHA未变，不跑326/7/12+2。生产R/t/support缺口V10 BLOCKED。正式页面已有外部Q/E及帮助不写不回滚。本单只四preview及本轮新证据/returns末尾。
