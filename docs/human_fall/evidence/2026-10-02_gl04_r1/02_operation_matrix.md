# GL04 R1 派工前操作组合矩阵

沿GL04_ACCEPTANCE v1；所有检查新写证据，不改历史断言。每个操作与消费状态交叉，不只孤立helper。

| 操作 | 输入来源 | 消费状态 | IDs / 必需检查 |
|---|---|---|---|
| startup | 无消息、legacy实际build_snapshot、完整显式ground渲染fixture | source/ground requested/unselected | V01/03/10：原始可显示、无R/t禁用；拒绝默认identity |
| same-content reload | 当前同session/frame/calibration/GDID | source/ground/locked/pending/ready | V03/05/06/09：坐标与选择资格不误变；请求/ack保留 |
| same-ID different-content | R/t、coordinate source_frame、geometry schema任一变化 | ground/locked/list cached/drag begun | V03/05/06：内容比较/失效，不复用旧颜色、位置和选择 |
| new-ID reload | calibration_id、ground_derived_id变化 | source/ground/locked/pending/ready | V03/05/06/07：先失效旧快照，当前匹配恢复；历史保留 |
| caller in-place mutation | snapshot coordinate/box/ID/frame改变 | list closure/drag/current presentation | V04/05/06：使用当前内容与版本重新核对，无旧closure选择 |
| foreign frame / invalid input | source frame异名，同seq+stamp不同frame；ground from/to错；NaN/坏AABB/重复candidate ID | source/ground/list/drag | V01/03/04/05/06：匹配frame及版本，不投错ID、不伪有效 |
| damaged / unsupported | calibration.schema、geometry schema、R/t缺失或非有限，ground unknown/none，verifier unavailable | source/ground/locked/ready baseline | V01/03/06/07：unknown/null/拒旧选择；保留原始和历史 |
| missing current details | current snapshot候选丢失，但state旧position+ready baseline | locked/source/ground | V06/07：unknown/null，不能拿baseline代观测 |
| ws lifecycle | disconnect、无消息超TTL、reconnect后旧消息/新消息 | list/drag/locked/pending/ready | V05/06/07/09：旧选拒绝、颜色失效、事件保留，不重放选择 |
| camera lifecycle | rotate/zoom/resize/DPR only；near/far/behind/退化 | source/ground/list/drag | V04/05：8角当前矩阵实时投影、DPR backing正确、裁剪守门 |
| support budget | empty/polygon/polyline、0/3/3000/3001/9000点，source/ground坐标 | source/ground/unavailable transform | V02：独立层、预算/源索引/抽样元数据，不由网格造支持 |
| performance scenarios | normal/tilted/no_extrinsics同样本同帧 | source/ground requested | V08：六图，frame/schema/calibration/ground/FPS/queue/connection同屏；缺外参明确回退 |

裁剪：core startup/reload/基线物理规则不在本单实现范围，复用GL02/03获审源码SHA；浏览器消费状态仍全部检查。设备/真实人体与采集为D01 NOT_RUN。正式页同步本轮可选，preview复审前禁止；若未改正式页不重跑用户指定326/7/12+2回归。
