# GL-I04 R1收口 / 2026-10-03

**离线软件独立二审PASS，无源码返工；B01/B02 BLOCKED，D01/D02 NOT_RUN，整单未ACCEPTED。**
Codex完成三份新生产文件后停止生产写入，指定OpenCode只读二审实际运行997.735秒/exit0/finish stop；session ses_efdc5ab31ffeBwyoFXmoG3GmHX，实际provider/model opencode-go/deepseek-v4.1-flash，default DB。派前唯一无工具probe12.703秒exit0/PROBE_OK。实际模型由29_review_session.json核实；原生ponytail在审查前已加载，路径C:/Users/30680/.claude/skills/ponytail/SKILL.md。原始CLI事件/命令/输出保留28_second_review.jsonl。

| ID | 最终结果 | 证据 |
|---|---|---|
| L01 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| L02 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| L03 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| L04 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| L05 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| L06 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R01 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R02 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R03 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R04 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R05 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| R06 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| S01 | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |
| B01 | BLOCKED | 原bag/layout来源链不足，无新增物理证据 |
| B02 | BLOCKED | 录制窗口extrinsic/世界up表达及区域地面身份未闭合 |
| D01 | NOT_RUN | 未设备/部署/采集/网络/GL05，未验证目标板性能 |
| D02 | NOT_RUN | 未GL04真实DPR/正式页面；SVG不代替DPR |

Q01–Q10全部PASS；完整逐行独立证据见二审§5与31_review_audit.json。本地423+2回归、额外独立反例和真实报告重算均通过，测试数量不代替ID判据。Python3.8 AST通过；实际本机Python3.12.10/NumPy1.26.4不冒称目标板Python3.8.10/NumPy1.17.4验证。

首尾完整tracked+untracked基线03/23/30，三新生产文件提交SHA与二审后完全一致，冻结ground/calibration/capture_input、GL-I03三文件、原config/tests/draft/capture/driver/UI/历史证据保持。32收口后的变更仅当前工单状态文档。本轮树外部差异见31_review_audit.json，保留未回滚；无reset/checkout/clean/commit/push。

## 研究决策

采用离线诊断工具用于观察：12_real_final包含356 box×frame记录与351255源索引点，全点统计/固定XYZ分箱与显示抽样分离；二审独立重跑四产物字节一致。approved/negative-X/FIT法向研究输入分开，raw冻结结果/replay/事后holdout分开，没有真实calibration/ground_derived。

**不采用搜索原型接入运行时。** 保留research_01/search_prototype.py作研究：逐个已见合格假设精炼、固定锚点包络证书/全跨度约束、预算不足持续未决，非传递链/晚到竞争不被吞。30场景+语义反例与同序列oracle通过；清洁/低噪正例可闭合，高噪/竞争/真实WHAT_IF未决。成本仍>2×基线，不声称速度收益或排除未见物理假设。被推翻的精炼结果逐个存储方案及replay早退错误、修订依据保留06/07及19，未降门/删除验证点。

下一步最小判别实验：软件上量化包络造成的额外拒绝、噪声/候选顺序与close-to-best见证关系，对照同序列oracle而不改协议门；物理上先取得与2026-10-02录制窗口绑定的配置/extrinsic及from/to轴，再依据独立空间身份核查四box高低几何尾部。若改ROI需新批准选择版本，不以FIT残差筛validation。当前不自动启动后续工单/接入/设备操作。

## 二审报告审计附记

二审报告称interface interactive/session未提供，实际是已保存CLI run，真实session及model/finish见29导出，本收口已补齐。其compare_real_reports.txt未落盘；对应命令的原始工具输出在28 JSONL，已新增抽取31_comparison_command_evidence.json，不伪造该文件。

二审曾修订自身certificate边界fixture（浮点1.05−1.0并不精确等于0.05），这是审查预期的修正，不是被审源码返工。其自身probe重复写出的日志，早期命令/输出仍完整保存在28 JSONL，原作者旧证据没有覆盖。

流程观察：审查者原生加载ponytail后，为对照字节另以只读shell读取了Codex技能文件哈希；这超出派工要求的仅native查找路径，予以保留并要求后续避免。原生技能先行使用已验证，无生产写入/权限变更，也不影响可独立复现的软件结论，不伪报其全程只访问native路径。

Manifest11捕获了正在写的stdout24的空SHA；只新增25日志SHA附记保留原证据。独立首尾111项清单按该附记全部匹配，无源码/input/report漂移。源码自验不是独审；本轮独审的model/session/exit实际齐全。
