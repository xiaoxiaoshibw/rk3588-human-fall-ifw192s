# GL-I01 R1 阶段一：只集中诊断，禁止源码/测试写入

工作区D:/Code/ldiar。用户授权开始/继续上一聊天下一阶段本地软件开发，GL-P01软件已审，本单为离线capture export适配。唯一表GLI01_ACCEPTANCE v1。

**本次只允许写本轮证据00_diag.md及必要只读探查结果。禁止任何源码/测试/配置/contract/状态/return写入。写完完整M01-M13设计矩阵后回复READY_FOR_DESIGN_REVIEW并停止；即使设计认为完整，也不能在本次消息实施。只有Codex核源码未改并另发实施提示后才能写代码。** 这是R2诊断倒序的具体流程修复，不是例行用户确认。

只读入口：根AGENTS/CLAUDE和WORKFLOW当前覆盖（只读当前首段与核心规则，勿全读历史）；GLI01_ACCEPTANCE.md；evidence/2026-10-03_gl_i01_r1/PLAN_REVIEW.md；现calibrate_sensors.py的load_points/load_input/run_constrained，ground.py region_indices/constrained group门相关片段；src/human_capture/core/bag2session.py28B布局片段；真实captures/remote/cap_20261002_163621/meta.json用Python打印top-level/首末frame摘要，不全文灌frames。实际读r1本轮ponytail_SKILL.md（原完整副本SHA一致），full。

在00_diag逐M映射函数、type/layout/hash/时间/索引/绑定/副作用/原子写顺序、fit/validation实际源帧隔离、正负例与保留/失效；解释原bag index未知。设计优先一个纯core/capture_input.py + scripts/prepare_capture_input.py，opt-in manifest route集成calibrate_sensors.py；新集中tests。数值NPZ含points+Unicode input_manifest，加载含manifest必须验证源及成员，普通旧points不受影响。不导入replay HTTP/采集器，不为适配改ground数学。

读真实数据只做格式/源hash/抽样数值/全行计数，不能拟合/选ROI/给单位/帧/物理verified。4个原始source zero drop可用；clip/source unknown/drop拒绝。point_index_domain=capture_export_row，original bag未知；bin f32点timestamp不恢复ns，使用meta整数headerstamp。不猜安装角/拿1.1m当原点高度。

诊断最多针对当前调用链片段读文件，不重复已审全历史；上下文近120k先停、保留session交Codex压缩。baseline00_before_manifest.json；本次只写evidence/2026-10-03_gl_i01_r1/00_diag.md。不得改任何其它文件、commit/push/reset/checkout/clean、board网络/采集/部署/GL05/模型/DB/global config。停止后交Codex做实际门控。
