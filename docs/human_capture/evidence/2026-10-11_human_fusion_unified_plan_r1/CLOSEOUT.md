# HUMAN-FUSION-UNIFIED-PLAN 最终收口

2026-10-11。**PLAN_READY / SUBMITTED**；当前统一计划v2、唯一规划验收v1。三轮事实/架构/反例设计与修订已完成；完整指定OpenCode审查READY，无阻断缺陷。未宣布算法/系统ACCEPTED，不实施下游任务。

## 当前开发顺序

1. HFUS-D01测量/实际点集/预处理契约，D02人工待审包与split资格。
2. D03把BG-B真正接PA/PB共同入口，模型与跟踪固定，测终端输出。
3. D04混合/稀疏/因果支持各自消融，D05a固定候选与困难负例分类。
4. D05b身份、时间、retention与输出一致；D06同版本联合全链验收。
5. D07已审真人成员上的区域表面代理；真实姿态/跌倒、生产接入、采集/部署另有当前授权。

## 审核与纠错记录

首审真实read且READY，但多行CLI参数被cmd截断；第二次也只收首行。原意见/log保留，仅作读审参考。原生exe probe03收到完整单行且多了一对传输引号，严格原文guard保守FAIL；不作服务失败或隐去失败。

最终probe04真实exit0、15.632秒PROBE_OK，无工具调用；正式review03改用单行文件入口，实际read完整任务书并核SHA未变，actual provider/model=opencode-go/deepseek-v4.1-flash，实际仅read/glob/grep，技能实际read完成。review03真实exit0、277.701秒，裁定READY。对传输引号仅剥一对首尾，未补空白/内容；没有切model/provider/DB/auth。

首审两项事实误判（JSON只有4会话、PIPE不驱动FUSION retention）均被完整复审纠正。四项非阻断注释由REVIEW_RESPONSE_03补齐；v2获审计划字节保持。审查者尚未回填的P02/P08/P09由结束实际证据完成。

## 边界与完整性

BASELINE_BEFORE：12412文件；BASELINE_CHECK_01：12454文件，零读取错误/读取中漂移，HEAD未变。全树差异45项，其中44在授权文档/本evidence内；范围外仅既有 `sidequests/human_fusion_lab/results/chrome_q01b.log` 从4366增至5470字节。日志为Chrome PID27448的GCM连接失败；该进程于16:58:43已启动，早于本轮。没有停止该进程、覆盖或回滚日志。**整树SHA并非全相等**；生产源码、旧研究源码、当前模型/GT/captures和旧证据无变化，已有日志增长单独登记。

最终源SHA/文档引用/完整调用核验另见FINAL_CHECK.json；baseline完整对账另见BASELINE_FINAL_DELTA.json。当前获审plan/acceptance与SUBMISSION_02逐字节相同。无源码实现、训练、GT签审、设备/采集/部署、driver/network变化、commit/push/reset/checkout/clean。

## 最终逐ID状态

| ID | 状态 | 证据/责任 |
|---|---|---|
| P01 | PASS | 两入口/AGENTS/技能及授权范围；OpenCode完整R3 |
| P02 | PASS | 作者全树before/after、源码/数据/旧证据保护、已识别既有Chrome日志漂移；非整树全冻结声明 |
| P03 | PASS | 实际源码/JSON与归一表；完整R3独核 |
| P04 | PASS | BG共同入口、union、dual状态迁移、GT隔离；完整R3 |
| P05 | PASS | legacy/strict、partial/UNKNOWN/负例/预测等契约；完整R3 |
| P06 | PASS | 阶段/文件/依赖/失败路径与联合晋级；完整R3 |
| P07 | PASS | ROUND_01/02/03、两版冻结；完整R3 |
| P08 | PASS | 实际probe04/review03、模型/会话/完整指令/只读工具/技能read结束检查；作者编排核验 |
| P09 | PASS | 两轮意见逐项处理、反驳证据与完整复审READY、最终追加回传/引用检查；作者收口 |
| DEV01 | NOT_RUN | 所有后续算法指标尚未实施 |
| DEV02 | BLOCKED | 独立负例、连续身份、区域/关节及新场景人工资格缺口 |
| D01 | NOT_RUN | 无设备/采集/部署执行 |
| PHY01 | BLOCKED | 无新的物理/现场/生产证据 |

PASS仅对应本规划交付及审查范围；当前人体泛化、双人ID、全身关节和真实跌倒没有被升级成PASS。首批实施建议为D01+D02工具和待审包，需要后续明确开发指令；本轮不自行启动。
