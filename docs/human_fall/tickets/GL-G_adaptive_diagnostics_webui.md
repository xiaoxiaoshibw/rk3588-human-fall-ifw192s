# GL-G：三估计器与FINAL诊断WebUI / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；前置D/E接口验收、F可重放schema与明确启动。来源：[最终计划§9/10](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本文件唯一验收表v1。

## 目标与范围

先独立离线/preview UI，沿现有三列增加各方法confidence/valid/reason、CONSENSUS→TEMPORAL→FINAL、last_good age/qualification、事件日志；保留手动reference与四区残差/失败。不得替换生产WebUI，不把browser当算法writer，不发布机器人控制命令。

操作矩阵：同帧三结果/一个invalid/超时；旧新frame混合/顺序错；INIT无FINAL、ACQUIRING、STABLE、DEGRADED、HOLD/expired、RECOVERING；参数/epoch/source切换、断流/重连/无输入；view/frame切换、显示尺度、unknown/falsequalification；日志过滤/导出。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-G-01 | TLS/SVD/RANSAC同frame/domain/ROI/source样本/坐标范围三列；normal/pitch/roll/d/RMS/P95/support/count/coverage/score/valid/reason完整 | renderer binding + geometry scalar + actual browser | NOT_RUN |
| AGL-G-02 | CONSENSUS所有pair差/支持簇与家族、TEMPORAL raw/filter/limited、FINAL accepted R/t/score/state/IDs/age明确；无FINAL不fake zero/identity | each state/invalid missing fields screenshots | NOT_RUN |
| AGL-G-03 | STABLE绿色、DEGRADED/RECOVERING黄色、HOLD/BAD红色均有文字；physical1.14与observed compensation分开；TLS/SVD关联与score非概率常驻 | accessibility/text/content verification | NOT_RUN |
| AGL-G-04 | stale/crossframe/schema/source/epoch错配不给可用FINAL；断流、恢复、manual/reference不会沿旧帧资格；失败表不被新overall平均覆盖 | complete source/lifecycle UI matrix | NOT_RUN |
| AGL-G-05 | transition日志原因/frame/time/version、filter/export可定位；所有示例值标synthetic；浏览器截图/DPR与Node mock分层，不绕file协议限制 | real browser + Node checks + exported events | NOT_RUN |
| AGL-G-S01 | 只新/获准preview，生产页面不替换；UI不修改core/config/1.14，WF诊断/自验/停写/独审与SHA | scope/return/review | NOT_RUN |

## 交付

独立诊断页面/消息schema适配、浏览器证据与Node纯逻辑检查；`evidence/<date>_agl_g_rN/`、`returns/GL-G.md`。若实际browser被策略阻断，原样NOT_RUN/BLOCKED，不拿mock替代验收，也不借此启用生产。
