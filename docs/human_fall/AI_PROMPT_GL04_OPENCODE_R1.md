# OpenCode GL-04 R1

你是唯一生产代码写入者；Codex编排/独立复审。使用default DB，本轮同模型 `opencode-go/deepseek-v4.1-flash`。不改auth/DB/全局配置，不切模型，不启第二写入者。HEAD基线8633eac（外部HR-02推进，保留）；全树SHA在本轮00_before_manifest。无commit/push/reset/checkout/clean/部署/采集/板端联网/GL05。

## 开始前

先读GL04_ACCEPTANCE.md v1、本轮02_operation_matrix.md、WORKFLOW.md v2、tickets/GL-04_webui_level_view.md、GEOMETRY_CONTRACT.md、INTERACTION_CONTRACT.md、CLI_RECOVERY.md、RETURN_TEMPLATE.md和ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。GL02/03旧回归已获审，不能重跑326/7/12+2凑数，不改core。必要引用R7复审而非所有历史。

实现前在 `evidence/2026-10-02_gl04_r1/00_diag.md` 逐行映射操作组合矩阵到实际函数、赋值顺序、守门、保留/失效、检查计划，诊断完整后才改生产代码。不只修孤立helper。最后按RETURN_TEMPLATE追加 `returns/GL-04.md`，标题 **OpenCode GL-04 R1**；只SUBMITTED/BLOCKED，逐ID自验不能宣称整体PASS。

## 边界

唯一可修的文件（一次一堆）：`webui/human_fall_preview/{index.html,human_fall.js,human_fall_lib.js,human_fall_lib.test.js}` + `human_fall` 的同名四个文件同步（preview 修改验证通过后，才同步到正式页）。冻结资产（config/driver/webui 其他文件/旧数据/历史证据/旧断言）不动。用户本轮修正仅这条路径，任务/验收/浏览器约束完全不变。

旧断言原样保留，可追加测试。R1先不改生产human_fall，只交可选同步patch，待preview独立通过才可同步。所有辅助样本/检查/日志放本轮新evidence目录，不覆写旧文件/旧证据。冻结driver/config/core/其他webui/原数据/依赖版本。Three.js/OrbitControls/foxglove协议复用，无新库/WebGPU/深度模型。

## 实现

1. source/ground两模式；ground_local俯瞰+Z向下（这是摄像机俯瞰方向，后端ground_local高度符号保持R/t权威语义）。点云只应用snapshot显式已知ground R/t，框消费actual_points ground AABB；标签/轴/支持区一致，不推导基底/拟合地面。同样本同帧切换不变原点数组或候选ID。
2. GridHelper始终可见、单独支持层，明示无限网格≠地面已验证。polygon/polyline只能消费snapshot显式字段，≤3000/层，抽样meta及原索引；缺失显示未提供，不能自动造平面或区域。
3. panel真实frame/m/calibration/schema/geometry/ground状态、physical flags，配平候选“配平预览（未地面核验）”。无有效显式变换禁用或明确source回退；unknown不身份矩阵。
4. 8角当前camera视锥投影min/max；near/far/behind守门，rotate/zoom/resize/DPR-only实时重算、overlay backing变化；两套AABB原candidate ID。列表点击和drag提交前验证current snapshot身份/内容/frame/session/calibration/schema/geometry/freshness；闭包旧snap不可提交。同seq/stamp不同frame不能匹配。
5. 同ID异内容/新ID/schema换代/frame不匹/断连/ws静默过期/ground unknown-none/verifier unavailable/旧快照失效→unknown颜色、拒select，历史保留；candidate缺当前详情但ready baseline仍在→fall unknown/current position null，不继承旧位置。保持旧watcher/lock/ack、release/capture按钮、消息结构、原raw fallback/IMU/设备/颜色语义。
6. synthetic normal/全倾斜/no_extrinsics同样本同帧，可提供明确offline synthetic场景入口供真实浏览器6图；此入口不得连接板端或发真实请求。渲染FPS近似/queue_dropped/connection同时panel，标注frame/版本。未知queue不要造0。样本显式提供R/t和support，禁止通过浏览器计算ground几何/AABB。优先证据目录JSON fixture、共用真实消费路径，勿建第二网站。

## 已知集成缺口

实际build_snapshot目前仅发GDID、ground实际框及ground摘要，无R/t/support数据。不得为完成V01/V02改变core/topics，也不得从normal/offset造变换或支持区。严格缺字段source fallback可闭合，完整变换渲染能力只以显式synthetic fixture证明；V10生产端到端BLOCKED。新增可选输入字段明确记录为synthetic渲染扩展而非现有生产已提供，未经明确版本绑定不可显示有效。坐标消费取单一文档化入口，不兼容猜测一堆位置。

## 回传与证据

新lib单测原始node输出/exit/SHA，旧18断言保留。源码diff、before/after manifest、逐V01–V10/D01及M01–M11证据，不以数量替代。真实browser若你可运行，六图注明synthetic/offline/frame/schema/calibration，旋转/zoom/resize/DPR、选择、失效、history验证独立记录；不能运行则NOT_RUN交Codex完成，不能造截图。真实板端/物理全部NOT_RUN。结束后停止写入，最后CLI消息必须给returns路径/evidence路径/未闭合ID与实际model/session。
