# GL-I03 R1 Codex开发 / OpenCode二审收口 / 2026-10-03

**软件范围独立二审PASS，无需返工；K04 REAL candidate仍BLOCKED，整单未ACCEPTED。** 本轮已实际实现3文件，并完成研究对照/反例归纳/计划修订；不再以CLI服务作为Codex实现门槛，也不将成功跑完旧步骤当作真实标定完成。

用户明确授权Codex开发、OpenCode二审；root写前完整read WORKFLOW/ponytail、已有诊断门与设计门，18基线十SHA一致。生产现有仅wrapper变、新增独立config/tests，停止写入后交指定Go Flash/defaultDB只读二审。27probe12.781秒exit0/PROBE_OK，实际模型已以mode=ro核验；28二审408.547秒exit0，实际session ses_efe2d04ceffea7iUqS4WOjUxvE/Go Flash/defaultDB/finish stop。native ponytail完整加载，未改权限/DB/auth。当前无活动writer/审核进程。

## 唯一验收v1当前结果

| ID | 结果 | 主要证据 |
|---|---|---|
| K01 | PASS | 显式helper/配置全部拒绝边界/默认/emit独立二审 |
| K02 | PASS | YAML25键/0.05与8/提交SHA |
| K03 | PASS | 原默认与显式冻结一致、415+2独立回归、真实默认80/exit2 |
| K04 | SYNTH PASS / REAL BLOCKED | 合成候选source/physicalfalse/exclusive；真实变体1193仍无candidate |
| K05 | PASS | 全键值只有两项差，原冻结SHA保留 |
| K06 | PASS | 仅3生产文件/冻结+旧tests+data+UI+旧证据保持，首尾SHA |
| P01/P02/P03/P05/P06 | PASS | OpenCode逐格二审及独立反例/真实默认/范围 |
| P04 | SOFTWARE PASS / REAL BLOCKED | 入口/gate/拒绝/只读语义通过，真实成功目标未达 |
| B01 | BLOCKED | 原bag/layout完整来源证据仍缺 |
| D01/D02 | NOT_RUN | 设备/物理/GL05与GL04真实DPR未由本单闭合 |

正式二审原文及脚本/命令/exit在opencode_second_review_01/00_review.md；Codex自验与只读助手复核分别署名，不伪装独立二审。三SHA提交和结束同：wrapper fddeeee0b4c6e014b608b64d8805b90997977b0e6eee357d6cc28f02726322c8，config16c9d983c0202bb122be300db6faf70e7415300756392569acafa7d444cd49aa，tests6433fa21200d1cbae0236c3701e31a5ec7b96d6d34549279909cacb6d948eccb。

## 研究改变了什么判断

真实ROI→positive up差52.28°，不是再调spatial cell能解决；negative/ROI-normal WHAT_IF虽然通过角度门，仍因搜索证据截断保守拒绝；手算三holdout残差全部fail且89帧中稳定存在。旧“正X26°角差2.7°”由方程对照推翻，旧“延长录制增加单帧FIT点数”也缺当前证据支持。纠错追加于research_01而不追改旧档案，不擅换用户先验/ROI/阈值或清competition标志。

新版计划见research_01/27_PLAN_REVISION.md及31_EVIDENCE_AND_NEXT_STEPS.md：先核source坐标/录制extrinsic，再分辨局部几何/尾部身份；最后设计保留竞争拒绝语义的受控搜索实验。不盲调采样、不把validation筛成贴合FIT的点集，不把研究诊断升格physics。

## 二审报告核查与限制

OpenCode实际源码首尾不变，独立415/2回归与CLI反例/真实默认变体拒绝复现，范围内无FAIL，故无需再派返工。其src/CMakeLists.txt“current_vs_28_drift”来自不同不可读软链的序列化方式；root完整manifest以lstat/WinError表示核对一致，不能把它写成真实软链改动。其D02文案“未授权”应理解为本单未跑/本单范围外；GL04浏览器验证此前已获授权，但现环境无法完成，正式不合并。

巨大integer预算不额外设上界属于冻结resolver契约范围，当前不用新增wrapper限制去扩大验收。真实K04不闭合不能用“已知限制”后PASS；物理参数/算法新语义需要有具体证据与变更记录，后续授权以用户最新指令为准，不由二审模型单方面限定用户研究授权。

HEAD master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6保持；原接回9冻结SHA不变，wrapper是本轮合法变化不mask。26scope2061保护文件零变化；29scope二审期间仅范围外limb文件/日志变，生产/data/UI零漂移。外部共享树差异保留、不归因、不回滚；无reset/checkout/clean/commit/push/部署/采集/设备/网络变化。原服务失败/旧审核记录完整保留，本次恢复不追改旧事实。
