# WD02 历史代码检查与裁定建议

**状态：BLOCKED_CONTRACT_ADJUDICATION；WD02处理帧数0。** 本轮仅只读诊断，未改审核器断言、未换job/重配平、未重签/安装/调用生产loader。

规则来源：`2026-10-08_hrsemshadow_r1/shadow.js:level()` 的 report.code_hashes 循环，逐个将历史生成源码SHA与当前 pc_apps/human_replay 的同名源码做 assert.strictEqual（message=leveling code binding）。`negatives.js` 对该异常记 BLOCKED_INPUT_BINDING 并跳过WD02；这是真实执行逻辑，而非源meta/bin不一致。

冻结 SEM 唯一表 v1 SEM-01 要求源/变换/参数/代码SHA绑定及无漂移，工单§3要求核输入与代码绑定，没有明确写“历史配平生成源码必须等于当前版本”。R3.7 `01_coordinate_contract.md` §2/5将帧身份绑定sid+job+transform_id+SHA；`02_registration_artifact_spec.md` §4第2条冻结leveling产物摘要，第4条要求registration生成算法文件集与当前消费者不符→METHOD_STALE。**后者是正式registration消费契约，不能外推为所有历史leveling生成脚本字节必须等于现在的脚本。** 若团队本意将它包含在SEM冻结代码集合内，需明确裁定；本轮不自作规范变更。

真实 `pc_apps/human_replay/registration.js:levelingBinding()` 检查固定job/TLS推荐/transform身份/源归属/manifest摘要/矩阵，不检查 report.code_hashes 历史==当前。`wd02_audit.js` 同时调用未修改的 H.level 和此纯绑定函数，后者接受、前者因代码等式拒绝。未以levelingBinding接受替代WD02验收，也未调用数据处理入口绕过H.level。

## 实测 SHA 关系

输入 cap_20261004_203349，唯一固定job c9712acad48c4fb7a78cb119c08d4cdb。

- raw meta：c3b55d1e11ed8a043bd3645af7ed07e920024c05f3cb48b15d523405edd38392。
- raw bin：2ed3fc60d99b3a2f42e0951835ad847fae2f490859e487b167fbccb1b5f10323。
- TLS transform：c845929272d350faa35deb0c1595e93cda46a9562e23aa9927476029cb46c194。
- report：e7455741fc74a1fb24c9e5d5d21dab0eda4f927428088f76057799e001d55a15。
- manifest：4fb6ae20b7ee462807b4cf113e718bf3d5c89c2026a614a4fbc9230acd260e7b。
- leveling.py历史：4b8d7ae12b958a55e0c62342ace29b12cdfb639039516ef7cc2078550b7514da；当前：3c3a88196cfd9851e2cadac76690a8343d6c949c4c7f467950495c32e6b54a6e。

wd02.run.json exit0 / WD02_contract.json：source在tf/report/manifest三处一致；TLS/SVD/RANSAC全部12产物、report、domain.npz摘要逐文件实读匹配；只有1个历史代码差异。诊断脚本成功仅表示以上关系被验证，**不是WD02算法PASS**。

## 两种裁定及影响

1. 若正式要求历史生成源码==当前：继续阻断，需可追溯历史实现/环境，或经批准生成新独立产物并保留旧job；不得改历史SHA。需要重现生成结果与审查消费者兼容性，不能仅凭摘要相同通过。
2. 若正式要求使用已冻结的历史产物：建议明确区分历史provenance与当前消费代码，保留全部历史code_hashes、固定源/产物SHA、当前consumer/codeSHA与版本兼容验证，再经授权最小修正harness。**尚未裁定，因此本轮不移除检查，也不把额外条件继续描述成已证实的正式合同条款。**

直接移除等式虽能解除硬断言，但只证明历史字节完整，不证明当前源码能够再生成同一结果、不证明版本/浮点/有效点处理兼容。可复现性必须由历史代码/环境恢复或固定产物消费的独立同输入对照支持；GT和旧负例覆盖仍独立阻断SEM-10。旧REVIEW/R1 return中的“输入绑定不符”表述只在本轮新增说明中更正，不重写历史。
