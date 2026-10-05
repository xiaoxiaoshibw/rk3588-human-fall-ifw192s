# Codex GL04 R1 独立复审 / 2026-10-02

GL04_ACCEPTANCE v1不变。结论：软件 **REWORK**，正式页同步不放行。OpenCode `ses_f03dbb94affeLd27gZz6bQalDp` / `opencode-go/deepseek-v4.1-flash` default DB，CLI真实exit0，已停止写入。逐条结论来自独立运行时、真实浏览器、源码范围检查，不来自32项自验总数。

| ID | 结果 | 独立证据 / 边界 |
|---|---|---|
| V01 | FAIL | 双模式点云消费有实现，缺R/t明确回退通过；但`syntheticScenario`在浏览器构造坐标、逆变换、AABB（且只转源AABB两角），违反浏览器仅消费字段。另只接受自创ground_render而不是用户要求coordinate ground子块 |
| V02 | FAIL | 独立预算检查通过；只消费ground_render.support，忽略snapshot.ground.support_polygon/support_polyline；原始模式支持层消失，图例未明确区分面/线颜色；支持schema入口不符 |
| V03 | FAIL | 真实浏览器21/23：ground模式下frame仍innolidar，目标位置/候选列表仍source；缺当前frame seq/stamp和geometry版本读数；缺input回退通过 |
| V04 | FAIL | 独立CSS resize/DPR-only overlay checks通过；但DPR-only未同步renderer像素比，drag取source框而非当前ground框，影响重投影交互；真实browser resize已跑，zoom/rotate/DPR-only未完整闭合 |
| V05 | FAIL | 独立10：same ID candidate内容、同ID R/t、caller原地修改后的旧列表按钮均发请求；drag源码依然source框且绕过hfSelectCandidate；identity不含变换内容及candidate签名 |
| V06 | FAIL | 独立10：unknown/none、unsupported calibration.schema仍ground；verifier不可用仍upright；未来帧snapshot R/t直接重写当前帧点云（源X从2.8到22.8）；断连/静默过期拒旧选择且历史保留通过 |
| V07 | FAIL | 独立10：无candidate snapshot或空candidate列表、ready baseline、fresh匹配state仍显示upright和旧位置。hfStateAligned不要求当前实际候选详情 |
| V08 | FAIL | 真实浏览器20–25六图已跑（三样本、固定seq7/stamp1000/108点）；无外参ground请求明确回退。FPS取pcPresHz=1–2而不是render帧率；queue_dropped取pcSkip未呈现计数而非实际队列丢弃，指标含义不符 |
| V09 | FAIL | 12_scope_sha：正式四文件/core/config/driver已核SHA不变，旧18断言完整原前缀保留，node32 exit0；但browser几何构造越过任务边界，新增交互未闭合，不可宣称旧语义全保留 |
| V10 | BLOCKED | 现有build_snapshot确实缺R/t/support；不改core，synthetic不能冒充生产端到端 |
| D01 | NOT_RUN | 真实板端/人体物理/性能未运行 |

## 全矩阵覆盖记录

| 行 | 结果 | 证据与已查范围 |
|---|---|---|
| M01 | FAIL | 10 runtime valid→unknown/none保持ground；valid恢复未独立闭合 |
| M02 | PASS | actual_points ground AABB消费/缺字段不造box源码+lib；不证明synthetic源框正确（V01失败） |
| M03 | FAIL | runtime CSS resize/DPR overlay通过；current-mode drag及renderer DPR未闭合；真实resize已跑，其余browser未闭合 |
| M04 | FAIL | 同ID内容/caller mutation旧list发送；source/ground拖选源码错框；旧ID请求拒绝不足 |
| M05 | FAIL | runtime断连/静默旧选拒绝/history保留通过；verifier/ready状态失效失败；真实ws交互未跑 |
| M06 | FAIL | same-ID R/t变化未拒绝，unsupported schema未拒；新ID identity拒绝lib证据适用，same-content正例可用 |
| M07 | FAIL | ready baseline +无/空当前candidate仍upright/旧position |
| M08 | FAIL | 六张真实browser图已保存，ground/source读数及指标语义失败 |
| M09 | FAIL | 缺R/t原始回退通过，unsupported calibration schema失败 |
| M10 | FAIL | 预算0/3/3000/3001/9000及索引通过，requested support入口/source layer未覆盖 |
| M11 | NOT_RUN | lib near/far/behind检查通过；真实camera边界/退化尚未完整跑，不以pure冒充browser |

## 集中根因 / 下一轮最小修复

1. 权威输入和当前显示帧未统一：独立保留当前raw frame_id，绑定snapshot/state/frame/calibration/schema/GDID及变换内容；只在当前presented entry更新整套点/框/轴/标签/支持，未来/外来消息不能抢改当前坐标。接受用户指定coordinate.ground及ground.support_*位置，不造生产消息字段。生产缺口继续BLOCKED。
2. 消费资格和提交前绑定不足：单一display/selection guard覆盖ground状态、verifier、schema、freshness、当前候选详情；ready baseline不代替当前观测。按钮闭包捕获不可变render token，包含候选内容/transform版本；drag使用当前模式框并通过同一提交守门。
3. synthetic和性能证据误义：将所有场景几何预生成在evidence离线fixture，浏览器只加载字段/点云；渲染FPS独立计真实renderer.render次数，queue_dropped仅取已知snapshot/state字段或显示unknown，保留原pcSkip说明。补当前seq/stamp/schema/geometry及当前坐标读数、图例和支持两模式。

责任：操作组合矩阵已经明确列出失效/caller mutation/同ID异内容/当前frame，实施未覆盖；Codex R1提示词对“单一入口”描述不够明确，允许了自创ground_render设计，R2需直指用户原字段位置而不变验收。R1会话上下文到约178k，未按120k及时压缩；下轮续接前按CLI_RECOVERY压缩，同模型同session，不用隔离DB。

## 范围 / 证据真实性

12_scope_sha含四preview及正式源码SHA；与returns提交SHA相符。原断言未降级，node独立32 exit0（11_codex_lib）。10 runtime独立6 PASS/12 FAIL只是检查记录，验收仍逐ID。辅助VM只在内存公开闭包，使用仓库真实Three.js相机/矩阵/geometry，DOM/时钟/wire为mock，不冒充browser。真实browser20–25为Codex in-app browser（127.0.0.1:8875，未连接板端），viewport1280×1000；8874旧缓存造成初次取旧外部script，换本地origin后确认新版本，旧画面不作为通过证据。

全树检查看到WORKFLOW/tickets INDEX及human_capture/replay文件外部变化，OpenCode修改工具清单只含四preview、00_diag/fixture_check/returns；其它差异保留、不归因、不回滚。初始PowerShell基线35路径不可读（Git quoted Unicode+Windows软链接），这属于Codex基线枚举缺口，R2基线用git -z无quote补齐；不假称这些路径已有起点SHA。core三SHA与R7逐项相同。未重跑326/7/12+2，无正式页变化/部署/采集/commit/push/reset。
