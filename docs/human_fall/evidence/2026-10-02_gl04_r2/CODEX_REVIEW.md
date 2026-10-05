# Codex GL04 R2 独立复审 / 2026-10-02

判据仍GL04_ACCEPTANCE v1。结论 **REWORK**，正式同步不放行。OpenCode `ses_f03b3fab4ffe7wBIOh6rRUJMwM`、指定Go Flash、default DB，真实exit0，19:31停止写入；独立复审时preview SHA仍与提交相符（50_scope_sha）。

R1已列21个反例由Codex独立复跑全部通过；扩展既有全表消费者组合后8个FAIL（20_codex_runtime/20_codex_results）。38项lib exit0（21_codex_lib），不以数量代替条目。R2实现者曾运行Codex预置脚本，那是其自验，Codex新20日志才是独立结果。

| ID | 结果 | 证据 / 边界 |
|---|---|---|
| V01 | PASS | 合格显式m/R/t的source/ground消费、未来/外来snapshot不抢改points、alias冲突拒绝、无R/t回退；browser只fetch静态fixture，Node-only generator不向browser暴露。生产缺口另列V10 |
| V02 | FAIL | requested ground.support_*、两模式独立layer、LineLoop≤3000及源索引通过；3D支持点Z=null仍ready并被置0，未知坐标被冒充有效支持 |
| V03 | FAIL | frame seq/stamp/源与显示系/标定读数改善；ground输入units=mm仍ready；ground位置值0.80却静态行名“位置 source (m)”，候选列表仍source且未标系；schema/geometry版本未分列明确 |
| V04 | NOT_RUN | 独立resize/DPR-only runtime和实际browser旋转/缩放/resize通过；真实DPR改变未完成：IAB仅支持viewport尺寸，Ctrl+Equal执行失败、native Ctrl+plus无倍率变化（canvas ratio仍1）。不冒充实跑DPR PASS |
| V05 | PASS | 独立immutable token、same-ID候选/R/t、caller mutation、foreign frame拒绝，合法same-content选择原ID；真实browser列表+ground拖选均wire candidate_id=c0000/snapshot_id=seq:7，capture_baseline/ack路径保留（40_wire_requests/42/43） |
| V06 | FAIL | unknown/none/verifier、source/ground切换、旧按钮拒绝、历史保留通过；snapshot cal2/state cal1及反序仍upright；双方schema2仍有效source状态；静默过期DOM变unknown但无GPU重绘、旧框/支持区和配平“可用”颜色保留。真实browser44/45/48复现 |
| V07 | FAIL | 无/空候选＋ready基线门控通过；仍有其他候选时`hfAnyGroundCandidate`取第一人代当前目标：state本目标缺ground详情，position从3m变成other的12m、仍upright；真实browser46复现 |
| V08 | FAIL | 30–35b真实三场景六图（初始未对齐35补为35b，旧图保留）、108点/seq7/stamp1000/syn-cal-1/GDID已标synthetic；render-fps计数已改正确、未知不造0；但实际发布字段是state.performance.queue_dropped，UI不消费（mock该字段=3，UIunknown）。源码human_fall_node.py:285/387支持该真实入口 |
| V09 | PASS | 本轮生产写入工具仅四preview，core/config/driver/依赖SHA不变，原18断言前缀完整且R1新增断言保留，38项通过；原ack/release/capture handler语义不改。外部formal Q/E/提示及目录重组不归因、不回滚；GL02/03旧回归未重跑 |
| V10 | BLOCKED | 实际生产build_snapshot仍无R/t/support，未改core/topic；fixture能力不冒充集成通过 |
| D01 | NOT_RUN | 板端/人体物理/真实性能未操作 |

## 全矩阵逐行

| 行 | 结果 | 覆盖 |
|---|---|---|
| M01 | PASS | runtime+真实browser valid→unknown→none→valid，入口disabled/回退、顶层unknown、ready/history保留 |
| M02 | PASS | actual_points/缺ground框/source框，当前mode消费；不证明失去本目标详情而存在其他人（M07 FAIL） |
| M03 | NOT_RUN | camera当前投影、resize/runtime DPR、source/ground原ID通过；real DPR仅ratio1未发生变化 |
| M04 | PASS | token/caller/同ID/外来spatial frame及真实两选择入口；与state新旧标定混配属于M06 |
| M05 | FAIL | ws真实断连unknown/位置空/history1通过；quiet超TTL的GPU与配平panel保留旧“有效”，48图 |
| M06 | FAIL | 同内容reload及候选token内容变化关闭；snapshot/state交错、schema2双方都错但相等不拒，44/45及20 |
| M07 | FAIL | empty候选ready基线通过；target缺失而other仍在时借位置，46图 |
| M08 | FAIL | 六图及计真实render次数通过；实际performance.queue_dropped消费遗漏 |
| M09 | FAIL | no R/t和startup明确原始可用；unknown单位/unsupported源观测仍有效 |
| M10 | FAIL | 预算及正常supports/frame通过；3D null Z未拒 |
| M11 | NOT_RUN | pure near/far/behind保守拒绝通过；完整真实browser clipping/退化尚未实跑 |

## 真实浏览器

localhost8876无cache服务，本机Codex in-app browser；8881 Node stdlib Foxglove v1 mock，同真实ROS1 wire消费，均synthetic/offline、未连板端。`44_browser_matrix.jsonl`记录ground unknown/none、empty候选、混标定、schema2、other目标、quiet、disconnect；history始终1。`40_wire_requests`保持原选择/基线请求结构与原ID。浏览器读取snapshot/state cal2/cal1同时显示（45）；本目标缺ground详情仍给other位置12.00（46）；quiet时UIunknown，但GPU cached线/支持区和gRender有效保留（48）。

30/31 normal、32/33 tilted、34b/35b no_extrinsics为同样本/同帧source与ground/fallback图；35原图在first feed未对齐，明确不用作通过证据，后补35b。36旋转/缩放/resize。V04/M11未跑部分如实保留。

## 范围与责任

50_scope_sha独立核对四preview提交SHA；三core SHA与R7相同。已有外部改变包括formal Q/E/帮助、human_replay、sidequests、根文档与build/open脚本迁移到tools及旧dataset zip移除（五路径起点有SHA、现在不可读另记）；OpenCode日志没有对它们的写入。保留这些变化，不回滚、不把它们当本轮实现成果。未部署/采集/板端联网/切模型/commit。

V06资格/版本/生命周期与V07当前目标资格连续R1/R2失败，触发WORKFLOW WF-CODEX-R1/R4设计前置，下一轮先完整消息到达顺序×消费者矩阵，不能只修8个孤立方法。R2明确要求snapshot/state比对却只比较snapshot binding；Codex事前组合表对“STATE旧/CAND新”和反序、本目标缺失但其他候选还在、DOM清除与GPU重绘的粒度不足，承认覆盖遗漏。模型能力不足无对照证据。R2上下文约203k仍未按120k停写，本轮记录执行偏差；下一轮紧凑派工，不重读全部历史/manifest原文。
