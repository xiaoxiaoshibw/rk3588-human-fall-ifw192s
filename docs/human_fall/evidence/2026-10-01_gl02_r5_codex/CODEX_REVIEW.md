# GL-02 R5 Codex独立复审 / 2026-10-01

结论：软件 **REWORK**，D01 **NOT_RUN**，P01 **BLOCKED**。用户本轮授权Codex直接通过OpenCode CLI `opencode-go/deepseek-v4.1-flash`处理当前工单返工；不再需要用户搬运提示词。GL-03、部署、采集仍不在本轮范围。

## 已闭合与独立证据

15项提交SHA全部匹配。原R4三方法、R3五方法、R2七方法、R2静态六方法、Claude R5四方法均由Codex在仓库根原样复跑exit0（50–54）。fall 271、follow 2、两页UI各18通过（55–58）。同内容空/paired/ground-only/full reload完整metadata与合法扩展、caller解绑、损坏其他块拒绝、同版本锁存连续性、辅助IMU降级与release、新请求恢复重新采样均独立通过。

## 全表结果

| ID | R5独立结论 | 证据与边界 |
|---|---|---|
| A01 | PASS | 55数学/逆变换回归，既有契约源码核对 |
| A02 | FAIL | 64：完整父artifact接受空/null/数字calibration_id、bool/float schema_version；validator/startup/reload均有反例 |
| A03 | PASS | 51–55；未升级physical/IMU/extrinsics/confirmed，老v1未知外参原义保留 |
| A04 | FAIL | 合法四类入口绑定通过，但startup缺ID绕过全量校验；与A02同根因 |
| A05 | PASS（版本切换） | 51/54，新ID同GDID失效旧资格，时间/历史不变量保持；monitor ready资格单列A09/10 |
| A06 | PASS | 50/64，完整父产物与合法扩展保留、深复制；局部更新新ID，不复用矛盾旧关联信息 |
| A07 | PASS | 52/55，可信ROI和支持门槛未放宽 |
| A08 | PASS | 51/52/55/64，双向散点、10%遮挡、整片平移、同版本reload和好帧不清锁存 |
| A09 | FAIL | 64：ready在坏帧/watchdog后仍ready，可恢复原资格；辅助IMU/release检查通过 |
| A10 | FAIL | 64：缓存前门控改变重放/冲突回执；watchdog与postcompute stale丢ACK路由；ready失效退休缺失 |
| A11 | PASS | 55，新文件导出、冲突不覆盖与失败拒绝回归；A06关联字段复核 |
| A12 | PASS | 55–58与提交SHA，driver和冻结资产未动；原R1裸块历史例外不重新要求支持 |
| D01 | NOT_RUN | R5原12_board_isolation SSH255/timeout；本轮不重复不可达操作 |
| P01 | BLOCKED | 无现场真值；不伪造安装角或将光学窗口高度当点云原点高度 |

## 四个根因及最小返工范围

1. **A02/A04，父artifact校验及startup旁路。** `_validate_geometry_calibration`用`==1`接受True/1.0，没有与构造器相同的非空字符串calibration_id验证；startup用ID truthiness决定是否校验，空ID直接走fallback复制ground/derived。严格共享validator并使任何显式传入的artifact启动时完整校验。合法无标定/ground-only保留。现有schema数值语义不变。
2. **A09/A10，ready生命周期未接入失效路径。** `_cancel_pending_baseline`明确不处理ready。真实process得到ready后，短时坏地面帧及无帧watchdog都不退休；同版本恢复无需新请求即可复用。v1请求矩阵已经选择“失效退休，恢复重新采集”。复用collector.invalidate/retired，避免每帧重复退休，先失效再让features/fall消费。
3. **A10，缓存查询位于新鲜度/monitor门控之后。** 同request_id同内容在monitor坏/云stale时得到新拒绝而非原缓存回执+idempotent_replay；不同内容也变成ground拒绝而非request_id_conflict。原终态不能覆写原accepted/pending缓存。缓存重放本身不执行新动作，应先按既有SelectionBackend契约分流，未缓存新动作仍受全部门控。
4. **A10，终态ACK只在纯core闭合，实际运输未闭合。** status_state返回baseline_ack，但真实`_publish_state`只发state话题，现有WebUI读`/selection_ack`且不读state.baseline_ack。另一个路径：process已经将pending置failed并生成ACK，worker随后判断compute超时直接continue，既丢result ACK又无法由status_state重新生成。保留候选/事件/位置的stale抑制，仅确保任务终态在既有ACK话题恰当送达，避免重复发送。允许必要ROS包装层改动，不能用改前端契约掩盖丢回执。

独立脚本`codex_r5_lifecycle_checks.py`最终12方法：4通过、8失败，其中严格父字段方法含15个失败子例，总failures=22，exit1（64）。60首次测试的ready/sample夹具把4000地面点合成人体同簇，导致前置不足；61修夹具只在合成候选配置裁去0.1m以下地面，monitor仍吃完整原云。62纠正“失败必须删内存样本”过强断言为契约要求的“恢复不拼接/新请求重新采样”（PASS），64为最终全覆盖。所有初始证据保留，未把夹具问题归因生产缺陷。

ACK运输检查执行实际ROS包装层函数AST，mock transport/clock，不是仅查字符串；不宣称真实ROS/板端运行。这四个缺口在v1入口/恢复/消费者矩阵已经列出，本轮首次验证，属于实现遗漏与此前审查覆盖遗漏，不是新增需求。

## 后续执行

按用户最新授权集中派OpenCode R6。单生产写入者，保留R5已通过行为；完成后Codex核SHA并复跑失败脚本/受影响回归，统一收口。CLI模型/版本以本轮实际查询为准（1.18.34，列表含指定模型）。检测到已有TUI会话，最新导出为plan/finish=stop、非活动实现，不中断用户TUI。
