# 本轮之外的RF依赖变化

起始全树SHA和第一批对拍/矩阵/perf记录的`pc_apps/human_replay/rf_person.js`：`78c4ce6625ee847b6c1a06eb915bce779edca340227e282f12978c35abf56d22`。

冻结结束检查检测到当前SHA：`f3e984538a1de51d4a9a7d4e998d3368367e9548d1f751b86c89e51477ab0c83`。当前LastWriteTime显示2026-10-10 17:35:56。差异是PCA特征值与轴分量实现，不是换行或本轮human_core修改。保留当前文件，不重置、不改写，源码副本和Git差异另存`external_rf_01.js`/`external_rf_diff_01.txt`。

Codex本轮对该生产文件没有写入；截至核对时，指定OpenCode只读复审的实际tool_use命令也没有写此文件。现有证据只能确认范围外依赖变化，不能猜测作者、授权或证明当前新RF特征的正确性。

第一批runs_01/parity_02/perf_01仍是其各自SHA对应实现的真实历史证据，**不用于当前RF版本的验收**。另做当前依赖的新测试/对拍/矩阵/性能；不覆盖第一批文件，也不把范围外变更加入本轮提交范围。

S02“全冻结资产未变”因此BLOCKED，不能给全树不变PASS。当前human_core作者提交SHA未被改写；软件修复条目与当前依赖重验分别报告。模型json仍同一原artifact，不自动部署/换模型/采集。
