# R2 回归与独立复核

## 实测结果

| 检查 | 结果/失败数 | 日志与产物 |
|---|---|---|
| SEM-12最终正负自测 | 4正例接受、17负例拒绝，0失败，34案例切帧/陈旧row清理；真实GT0 | sem12_verified.run.json / sem12_verified_results.json |
| 独立源/守恒/实际帧票窗 | 1276原始帧、1561分支帧、4311簇、11744951无效raw row，0不一致 | data_r2.run.json / data_audit.json / stage_hashes.json |
| 全帧管线独立重放 | 1561帧、4311簇、9366阶段序列、1561票及原Tracker快照、12019508成员坐标，0不一致 | full_recompute.run.json / recompute.json |
| 旧可用负例重放/冻结空场样本 | 448分支帧、2210簇、458区域、12冻结空场样本，0不一致 | negatives.run.json / negative_recompute.json |
| 原边缘/cleanup线索 | 52228源row/281帧，185+5精确一致 | edge.run.json / edge_source_audit.json |
| 独立R2显示receipt | 不导入校验器：34案例、100簇、2358删除点、183340成员坐标原始字节与实际显示一致，0失败 | receipts_final.run.json / independent_receipts_final.json |
| human_pipe_lib | 38通过、0失败 | regression_pipe.run.json/stdout.log |
| human_replay_lib | 45通过、0失败 | regression_replay.run.json/stdout.log |
| registration实际run | 23个PASS ID、0失败，T37-20不在该套 | regression_registration.run.json/stdout.log |
| WD02契约诊断 | 12产物+源/report/domain SHA完整；1历史代码差异；仍BLOCKED，0处理帧 | wd02.run.json / WD02_contract.json |
| 实际浏览器 | 初始化、篡改拒绝/禁止保存、全索引+raw正常重建3441点、投影、row拾取、合成UNKNOWN导出/校验通过；关键帧截图 | browser_ui_status.json / browser_export_validation.run.json / browser_review.jpg |

Python统一 `python -B -W error -X utf8`，Node v24.14.0，Python3.12.10。执行器record.py逐命令独占写run/stdout/stderr；汇总commands.md含失败。语义自检在full_recompute中执行30检查/24原ROI特征对账，冻结w_min=.06；negative重算另核12原空场样本。

原始数据/输出JSONL保留R1。data_audit重新读取两对pass2/pass3和negative3/negative4实际文件内容，重哈希而非信pass:true；两对digest仍一致。独立重放复用未修改生产纯函数和冻结分类函数，同时独立raw row/float32坐标重建及票窗约束；不声称另一套全新算法实现。Pythonreceipt审核无新validator调用，与明确的篡改测试预期并用，避免用被测工具PASS自证。

SEM-01/02/03/04/09/11/13/14原PASS项由上述实际回归支持；SEM-15由最后完整性检查，SEM-16由完整回传、GT限制与停止点支持。空场两口径仍0 HUMAN（V2_IDENTITY 0簇；WORKSPACE1582=1097OBJECT+485UNKNOWN）。43碰撞帧、114205过期确认88帧仍如实披露，不改原Tracker；同簇有效成员比较不证明无效XYZ未污染背景/拓扑。

## 保留的实际失败/工具问题

- 最初data命令exit1，复制审核工具后基线文件名未改为00_baseline.json；修正R2输出适配后data_r2实际成功。前置PowerShell嵌套引号的SyntaxError发生在改文件步骤，随后使用apply_patch修正，无旧资产写入。
- receipts_independent exit0但stderr有ResourceWarning（文件未显式关闭），不计干净验收；修正with后receipts_final exit0且stderr为空。
- sem12_final exit1为结果文件独占写EEXIST，断言已执行但不计该轮成功；新增命名输出后final_r2/release/verified实际exit0。不是修改拒绝条件或降低断言。
- 浏览器首次连接在临时本地server启动前ERR_CONNECTION_REFUSED；启动仅绑定127.0.0.1后实际UI通过，未绕过任何浏览器安全策略。最终server停止，不触板端。

所有历史R1失败和R2失败均保留。当前最终检查无失败；这不把SEM-05～08、10或WD02变为PASS。
