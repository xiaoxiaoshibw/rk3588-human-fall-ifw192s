# 首次OpenCode意见处理与v2修订

首次审核真实exit0，315.391秒，裁定READY，无阻断FAIL；完整原始stdout保留 `OPENCODE_REVIEW_01.jsonl`，提取全文 `OPENCODE_REVIEW_01.md`。意见不能因审核者提出就替代实际证据，逐项如下。

| 意见 | 处理 | 证据与结果 |
|---|---|---|
| P2-1 表格显示4会话却给全会话合计 | 接受 | v2补S4/S5/S7/S8，8个有效场景逐行加总510 PERSON、504/127/6和491/112/19；S9不入合计 |
| P2-2 物理P01与规划P01冲突 | 接受 | 计划§2/§7统一为PHY01；验收标准不变 |
| P3-1 probe readonly_permissions:false | 澄清 | 无工具probe不注入审核配置，但实际tool_use=0；正式审核read/glob/grep/list权限已注入，实际仅read/glob/grep；无写入/网络工具。新PROVENANCE JSON汇总，不把probe配置字段当写入证据 |
| P3-2 SOURCE_CHECK_01仅4会话 | 不采纳该事实判断 | 实际xgb_rows为9会话，重算等于totals，已由Python逐值验证。首次read输出长度可能截断；新简明SOURCE_CHECK_02直接每会话一行供复审。旧SOURCE_CHECK_01不改 |
| P3-3 PIPE tracker不影响FUSION retention | 不采纳该事实判断，接受措辞更精确 | lab engine 501→502→504～510明确由pipe_ctx.tracker的a_tracks更新引擎bank；322～336下帧读取。v2写出tracker→bank→当前点重提案调用链，强调bank非独立tracker |
| DEV01审核PASS | 保留“本轮算法未执行”语义 | 验收实际DEV01仍NOT_RUN。审核者PASS指没有虚称实施，不是算法通过 |
| 额外作者图文一致性检查 | 修订 | v1图retention直接入union可能误导；v2改为PA/PB入口重聚类，禁止绕过候选门 |
| 技能读取声明 | 要求定点复审补证 | 首审全文声称读ponytail，但tool日志未见对应read事件，不把声明当独立读取实证；作者已读技能不受此影响。第二轮要求实际读取并记录 |

本次只改计划细节与说明、工单版本标签、新证据辅助脚本；源算法、目标阈值、验收v1标准保持。提交v2冻结件后做新probe+只读复审；原意见与未采纳依据同时提供。
