# R6 同session上下文恢复 / 2026-10-03

生产writer会话ses_f01ba3f48ffepSrGKkcHrb3onk，原provider/model/default DB。03日志末步159269 tokens；Codex在134943附近发现上下文风险并准备暂停，04:25:02对已验证PID15176及子PID37756结束这次CLI，03_opencode_meta真实exit1（编排主动暂停，不是算法/服务失败）。00_diag已按C01–C15形成；lib.js已有部分修改，SHA ccdd5f2e45ca7acec5a540fc96a09a1e6f49ad42b28240d830a0b0edc19e51cb，其他三文件仍R5 SHA，保留不回滚。

按CLI_RECOVERY启本次localhost headless helper 127.0.0.1:18092（default DB，仓库cwd），本机/doc schema存04_server_openapi.json。POST同session summarize只指定原providerID/modelID；压缩完成必须导出核summary=True/实际模型/finish后才续接原session，不以HTTP成功或新会话代替压缩。此时没有并行production writer，不改认证/全局配置/DB/模型。

提交前只读计划辅助还指出C08/C15已列输入遗漏：合法occluded预测+空候选需保留source灰预测框/age、current position/fall未知；显式bbox_observed=false或position_source_from=unavailable/predicted不能背书physical实际观测（缺字段legacy兼容保留）；fixture源平面normal=R[2]时offset_m应等t[2]，R5复制器的负号与冻结几何契约矛盾。沿当前设计矩阵补同族正/负例，不新增算法/领域/参数/设备要求。

续接摘要应直接引用已完成00_diag/当前源码与这个补组合说明，勿再完整读取所有历史；先补必要诊断映射再最小修复，最终只SUBMITTED/BLOCKED。原03日志保留，续接用新05日志。

04:27:31+08:00本机官方summarize返回true/HTTP200（31.968秒），导出04_session_after_compaction.json确认assistant summary=true、原opencode-go/deepseek-v4.1-flash、finish=stop；server session/status为空，无活动writer。压缩是真的同session，不是紧凑新会话假称压缩。接续05仍指定同session/模型/default DB。

设计复核补组合：C08 source/ground两mode的lost/ambiguous/unselected都不能显示保留的旧current中心，即使ground字段仍匹配候选；预测框是独立诊断，不要求非空候选背书，但仍要求fresh/正确session/frame/绑定/units，不变成current position/fall。C14显式source units错误须同查当前列表/拖选消费者，不能只修旧token；缺字段合法legacy继续兼容，不将明确mm套入meter raw框选择。上述点来自现行固定坐标/观察/版本要求，先补00_diag再续写，原44/48断言不降。
