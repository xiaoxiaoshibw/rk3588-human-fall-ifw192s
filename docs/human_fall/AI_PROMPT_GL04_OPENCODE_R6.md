# GL04 R6 集中返工（v1不变）

你是唯一生产代码写入者 OpenCode CLI opencode-go/deepseek-v4.1-flash/default DB。只处理本轮已有V02/V03/V05/V06/V07/V08/V09消费者、坐标token/单位与fixture同族缺陷（完整范围如下，不新增功能）。Codex独立复审；不要自行改验收结果列/REVIEW_LOG/DISPATCH。当前用户已明确恢复调用；02_resume_probe在8.828秒PROBE_OK/exit0，新的开工范围基线00_resume_before_manifest.json，旧BLOCKED保留为历史。

先读根AGENTS/CLAUDE、WORKFLOW v2、GL04_ACCEPTANCE v1、本轮 evidence/2026-10-03_gl04_r6/PLAN_REVIEW.md完整C01–C15设计矩阵、R5 00_diag及源码。开工必须读 ponytail SKILL.md，回传声明实际路径。先写r6/00_diag逐行映射函数/顺序/各消费者/守门/保留/失效，再实现；不能只有孤立if补丁。

反例：R5 95_codex_source_fall_gate.js/results：同绑定/当前source目标/ground unknown或none/verifier ok，raw XYZ合法但hfFall仍upright。R5分离sourceAlignmentQualified后physical状态与颜色未独立门控。保留source-only当前实际XYZ/track、首次selection与合法null绑定；physical fall/目标颜色在ground观察资格不足时unknown，不假观测，不清ready历史。沿DOM hfRenderState、hfFrame 3D目标与overlay、fallback/restore所有消费者查同根因；预测/告警历史/锁/ack保持原义。source/ground×valid/unknown/none/verifier/lifecycle组合都查。

R5真实浏览器normal两mode：fixture.state.calibration缺schema而snapshot schema1，正确被nullable门拒。r6新generator/fixtures完整复制node_runtime当前已输出绑定、snapshot_id、coordinate、ground、sensor_quality与current actual字段；无地面source实际位置的position_source_from仍actual_points。只新r6证据，不覆盖旧fixture，不放松门。离线新fixture提供资格正/负例断言，physical flags false，normal/tilted/no_extrinsics。同样本同frame，浏览器只消费。

同族集中反例见R5新97_codex_additional.js/results（独立证据）：V05/C11旧按钮漏snapshot.units.length、candidate.center_ground_m、ground block.kind/schema_version调用者原地修改；source/ground两个入口都必须再核，保留当前合法原ID/同内容重载/相机变更不影响token。V02/03/C13/14显式source units.length=mm不能仍当m显示/ready；support_units=mm不能ready。缺字段合法legacy兼容按原断言保留，显式错误拒，不做全对象哈希。C08预测/无track_id/lost/ambiguous/unselected不能以旧匹配几何显示当前fall绿色/实测；保留合法预测灰诊断与锁/历史，source当前实际XYZ资格和physical资格分离。集中查所有DOM/3D/overlay消费者后一次修复，不再遗漏同族字段。

只允许四preview最小必要改动+新r6证据+returns/GL-04.md末尾追加SUBMITTED/BLOCKED。原44断言语义文字保留，不改core/config/driver/正式页/其它webui/旧证据/原数据。不commit/push/reset/checkout/clean，不板端网络/部署/采集/GL05，不换模型/DB/全局配置。正式同步条件尚未满足。复用SHA不变的无关回归，不跑326/7/12+2。

自验：原90/92/91（在r6新文件输出，不覆写r5）+95新反例+新增所有消费者负/恢复例与fixture资格断言。证据与before/after SHA写r6，按RETURN_TEMPLATE逐V/C结果、实际模型/session/命令/exit/ponytail路径追加回传，仅SUBMITTED。真实browser/DPR由Codex完成，未做标NOT_RUN；V10 BLOCKED/D01 NOT_RUN分层。完成停写。
