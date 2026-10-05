# Codex GL04 R4 独立复审 / 2026-10-03

GL04_ACCEPTANCE v1不变；结果 **REWORK**。OpenCode指定Go Flash/default DB exit0，2026-10-03 00:06停止写入。独立90运行时36 PASS/5 FAIL、92消费者2 FAIL；91 lib44项exit0。源码SHA见94_scope_sha，与R4回传相符；HEAD外部HR-03..05提交从8633eac推进cbd0be1，提交仅human_capture/human_replay，保留不归因。三core SHA继续与GL03 R7相同。

| ID | 结果 | 实际依据和限制 |
|---|---|---|
| V01 | PASS | source/ground R/t、实际ground AABB、原始回退、当前raw frame绑定已过独立回归；端到端缺口另V10 |
| V02 | PASS | 独立layer、预算/索引、显式3D null Z拒绝、grid说明已过 |
| V03 | PASS | 单位/版本和当前mode标签源码/纯检查已过；R4新版真实浏览器六图待最终复核 |
| V04 | NOT_RUN | 真实rotate/zoom/resize及运行时DPR已过，当前IAB未能改变实际DPR，不能称全矩阵PASS |
| V05 | FAIL | 旧按钮render token未覆盖coordinate.source_frame及ground R/t的units：同ID同帧原地改字段仍发select（90）；原 candidate_id提交及列表/拖选正常路径局部通过 |
| V06 | FAIL | state缺GDID但snapshot已知g1仍upright；state.calibration.schema_version=null而snapshot schema1仍upright（90）。null/null合法及null/known拒绝局部通过，undefined/known遗漏 |
| V07 | FAIL | 无/空/other source和ground旧实测详情已拒；predicted=true、other仍在时来源旧position=3m仍显示为当前source位置（90、92）；需保留预测诊断，物理位置空 |
| V08 | PASS | 真实state.performance.queue_dropped路径、计render调用与unknown、三离线场景已审源码/既有browser；新版截图待最终复核 |
| V09 | FAIL | 合法legacy source-only未选人首次选择已恢复；锁定后同当前source帧/候选存在，页面却写“未对齐当前帧”、位置`--`（92），退化了原raw监视。原44断言文字保留且exit0，core/正式无本轮写入 |
| V10 | BLOCKED | 生产build_snapshot无R/t/support，冻结core/topic |
| D01 | NOT_RUN | 真实板端/物理未跑 |

## 操作矩阵

C01 FAIL（source-only锁定后状态/位置），startup/首次选择局部PASS；C02/C03/C04 PASS（到达顺序、同内容、非空版本交错），C05 FAIL（缺字段与coordinate/units token），C06 FAIL（已知schema1/缺失state schema）；C07 FAIL（predicted旧位置仍在，other+旧实测两mode已PASS）；C08 FAIL（预测位置被当当前读数，原track/lock有局部保留）；C09/C10 PASS（quiet/断连/ground状态/monitor及GPU一次失效）；C11 FAIL（coordinate.source_frame/units调用者原地变更旧按钮）；C12 NOT_RUN（真DPR，纯8角及browser rotate/resize部分过）；C13/C14/C15 PASS（支持预算+3D有限、单位门、实际性能字段）。本轮没有因先发现FAIL就停掉安全可跑的纯检查；真实browser已有R2记录，但R4变化后的全套仍须最终复核，不虚报新画面。

## 根因和后续边界

R4实现把R3字段presence改成唯一候选匹配，解决当轮4FAIL；遗留仍是v1已列消费者组合：nullable绑定把undefined当“免比较”，token缺已声明坐标元数据，预测诊断复用物理position，以及source-only选择资格虽恢复却未恢复当前锁定读数。R4 PLAN_REVIEW要求单侧missing和C01/C08消费者，Codex事前仅测null/known、首次选人，漏测undefined/known和选后锁定，承认覆盖遗漏；实现者按窄检查修复未覆盖全部矩阵。无模型能力对照，不归因模型。R5把这些交叉点先映射到函数/更新顺序再实施；v1不变，无新功能。R4约131k上下文超该提示词100k收尾目标，记录执行偏差。

未跑326/7/12+2，未触正式/core/配置/设备，未commit/reset/deploy/capture。外部Q/E/帮助、HR提交与文件重组留原样。正式页同步仍不放行。
