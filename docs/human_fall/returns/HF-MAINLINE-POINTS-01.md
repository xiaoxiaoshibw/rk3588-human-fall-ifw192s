# HF-MAINLINE-POINTS-01 回传

## 2026-10-14 · 计划制定与OpenCode只读审核

- 用户授权：多轮分析制定下一阶段开发计划并交给OpenCode审核；本轮仅计划，未启动实现。
- 作者Codex；起始HEAD c21c443b0befe559e08283edb0efc2af02dcc6b8，既有脏工作树保留，原状态见证据目录GIT_STATUS_BEFORE.txt。
- ponytail实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 当前唯一计划：[v3](../HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V3.md)。[交付索引](../evidence/2026-10-14_hf_mainline_points_plan_r1/CURRENT_DELIVERY_INDEX.md)。
- 执行：三轮作者分析→v1 OpenCode PLAN_REVISE→v2 PLAN_PASS→v3最终PLAN_PASS。CLI请求模型opencode-go/deepseek-v4.1-flash；会话及工具事件见REVIEW_EXECUTION_AUDIT.json；底层模型权重未独立核验。
- 实际修订：KS1因果纠正、JS/Python口径分开、逐源行删除账本、候选background_removed与R3 FG契约分开、80帧具名context holdout、跨仓整链阻断、JS固定C_V2_DIAGNOSTIC基线、家具未知与proxy-only边界。
- 实际变更：新计划/证据/本回传，WORKFLOW/HC README/REVIEW_LOG顶部追加入口；未改算法、旧GT、原始录制、旧证据、R1默认或服务。331条保护核验无漂移，指明范围，不冒称全树冻结；登记文档属于本轮明确变更。
- 审核：仅read/glob/grep/list，无writer/命令/算法/测试；首轮外部目录受限、参数失败与快照初始化中止日志保留。v2已允许外部只读并读到技能/依赖。计划PASS不等于实现PASS。
- 当前状态：PLAN_REVIEWED / SUBMITTED，未ACCEPTED；PR01–10及PR07a/b/c NOT_RUN，PR11/12 BLOCKED。设备、物理、部署、训练、采集、提交推送、confirmed均未运行。
- 下一步：按计划P0–P4开展隔离开发需下一轮实施指令；不让身份GT缺失阻止离线研究，最终身份/纯度/物理结论保持独立门禁。

## 2026-10-14 实施回传 · Codex

状态SUBMITTED；当前原始源复跑BLOCKED，非ACCEPTED。唯一验收docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V1.md，SHA256 c9961e50528fd8faa5b8ab115a6f82c1d3508e35932ed575d759d12128b01dd6。实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md及C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。起始branch/HEAD/全树差异见BASELINE_BEFORE、ENVIRONMENT、GIT_STATUS_BEFORE，源码SHA见FINAL_SOURCE_MANIFEST。

### 集中诊断与实际变更

Python当前background_removed近目标真实点可追溯恢复，独立FIT覆盖33/33无鉴别力；JS近地1159标签点实际first reason背景而非高度。复用原加载/掩码/聚类，隔离research_retention.py和guard.py，旧R3仅FG契约保留。首轮中心0.355695m/新增9轴缺测，按旧参数依据加整组扰动护栏；中心最大0.093991m、新轴缺测0，仍有粗槽跳变退化。新增点UNKNOWN，不声称人体改善。共享页面scene_change外部变更单列保留。

### 逐条验收

PR01 FAIL外部漂移；PR02当前BLOCKED（此前基线/1966帧成员重现PASS，最终原始源缺失）；PR03/04/05/06/07a/07b/09作者自验PASS；PR07c NOT_EVALUATED缺家具分母；PR08当前原录制查询BLOCKED，冻结页面/实际下载49130条可用；PR10交付及独审另记；PR11/12 BLOCKED。逐ID命令、范围、退出码以唯一验收及报告引用的原日志为准，单测总数不替代结果。

### 未闭合与独审

FINAL_SOURCE_AVAILABILITY记录18个主链原文件缺失，恢复SOURCE_BINDINGS同SHA原文件才能重跑，不能猜测替换；本writer未删除。所有旧全帧验证/失败日志保留，80帧标REUSED_REGRESSION。完整召回/家具污染/解剖/泛化UNKNOWN；设备物理未跑，无部署/Git写/confirmed/默认晋级。独审读取FINAL_REPORT、唯一表、索引、FINAL_SOURCE_MANIFEST和各轮ALL_FRAME_VERIFICATION；结论原样另存。

## 2026-10-14 独审后补充 v2

当前唯一ACCEPTANCE_V2.md，SHA256 bcf1d3dd230831284c4ada198aa56ca853cfd9b0bb01de6b7c00d2ea4203b226；FINAL_REPORT_V2及REVIEW_RESPONSE_V2逐项回应审核02，原REVIEW_WITH_FINDINGS全文保留。feedback相对R1锚点和combined成员1966帧分歧均0，明确零分歧退化臂；护栏是后验拟合式过滤、复用80帧回归；历史验证与缺源检测显式时序绑定，当前不可重跑。S8逐帧reference/已审GT/初始快照SHA补绑，原始映射当前重放仍BLOCKED；空失败工件不作成功证据。算法与冻结配置不变，申请只读03复核。
