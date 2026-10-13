# HFUS-D05 R02→R04 完整实跑审查包

状态：SUBMITTED（自验，最终补审02已实际完成）；以下是实际结果，不ACCEPTED。当前选择R04（R02 split等价优化），R03失败分类保留可操作对照。主控唯一writer，两个代理和指定OpenCode只读。实际ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。master/026e06303f60ed1bbe4ddc4d037836db68da6d27；全树基线包含tracked/untracked/ignored，结束边界见FINAL_TREE_SHA与BOUNDARY_COMPARISON（已完成，15402文件；后续本轮源/证据另增量记录）；不声明原子冻结。

## 逐场景严格实际检出

只统计有资格PERSON对象，本帧实际成员与确认；coverage>=.5/purity>=.8。未标与S9 UNKNOWN。不是预测框或候选存在数。

| 会话 | PERSON GT | frozen base TP/FN | A06 | R02 split=R04 | R03 gate |
|---|---:|---|---|---|---|
| cap_20261010_175227 | 0 | 0/0 | 0/0 | 0/0 | 0/0 |
| cap_20261010_175429 | 258 | 111/147 | 184/74 | 184/74 | 179/79 |
| cap_20261010_175553 | 99 | 14/85 | 20/79 | 67/32 | 67/32 |
| cap_20261010_175804 | 11 | 3/8 | 9/2 | 10/1 | 10/1 |
| cap_20261010_175943 | 6 | 0/6 | 4/2 | 4/2 | 4/2 |
| cap_20261010_180235 | 71 | 7/64 | 10/61 | 10/61 | 10/61 |
| cap_20261010_180337 | 12 | 5/7 | 7/5 | 7/5 | 7/5 |
| cap_20261010_180557 | 53 | 51/2 | 51/2 | 51/2 | 51/2 |
| cap_20261010_180751 | 0 | UNKNOWN/UNKNOWN | UNKNOWN/UNKNOWN | UNKNOWN/UNKNOWN | UNKNOWN/UNKNOWN |

- H1成立部分：far A0620→67、走停走9→10，其他正式strict TP不减。f238 baseline高分候选存在但混簇，A06/split变纯成功。far仍32FN、turn2FN、occl61FN，不能称目标完全解决。
- H2无回退假设被证伪：家具human已标accepted overlaps1→0、propagated351→48（工程诊断，不是独立负例精度），near observed184→179，accepted186→181；f220–224前序分类拒绝→bank资格改变→retained人体补充缺失。NEAR_REGRESSION_WINDOWS和CLASSIFICATION_RETENTION_FEEDBACK保存完整邻帧与真实before/after银行。保留直立家具高分碎片，不晋级此gate，不盲调门。
- H3等价优化成立：120稀疏/稠密/minLocal/minRef反例通过，9会话2605帧所有真实阶段、组件、候选、分数、跟踪、strict/legacy精确一致（PARITY_SUMMARY/FRAME_PARITY）。minLocal=1邻居条件恒真，因此A06不提供额外密度资格；UNKNOWN仍需参考支持且z>.1，恢复不是人体判定。注册外无效NaN配置不是本轮能力声明。

## 不隐瞒回退和误接受

far legacy confirmed FP协议计数R02 split比A06105→188；这是部分GT协议下的结果，未标输出一律UNKNOWN，不能全部当家具，也不能把strict FP零当安全。occl legacy confirmed base65→R02/R04 64，保持回退。全部strict与legacy及PERSON/FURNITURE、human/propagated/auto来源在COMPARISON和完整ledger。S9永远INVALID_BINDING，不修原GT。不使用GT点/位置/未来帧生成候选。

转身剩余f0/f117主要BG保留不足；远行剩余30混簇、2确认；遮挡53混簇、7BG、1确认。原始RAW/valid/配平/BG/cleanup/retention/组件/候选/model_calls/轨迹均保存。全点cleanup删除真实存在；GT探针为零不能证明全场零删除；bare_b/chain_b是保留点，不是删除点。

家具ghost仍未解决：银行可不断从分类确认续命，timeout180s/maxlost30；输出coasting最多lost2仅保留最后观测位置，并无运动外推。Demo已明确标注。未标连续区不能证明身份稳定；first仅首次合格GT支持观测。exit残留与真实跨遮挡ID资格仍BLOCKED，软件seek/逆序/重复/gap/reset/跨会话契约exit0。

## 纯算法性能（Windows，单次完整串行复核）

前5帧预热，tick内无trace/shadow/读取/render/序列化，retention快照在计时外；当前原门<50ms不降低，单次Windows扫帧不作为统计置信区间或板端实时承诺。instrumentation计时另保留；R04完整仪表回归初段与R03分析并行，不能用其p95作纯性能。

| 会话 | R02 split p95 ms | R03 gate | R04 fast | 原50ms门 |
|---|---:|---:|---:|---|
| cap_20261010_175227 | 30.843 | 28.811 | 27.275 | PASS |
| cap_20261010_175429 | 36.721 | 36.777 | 35.918 | PASS |
| cap_20261010_175553 | 55.693 | 51.598 | 44.836 | PASS |
| cap_20261010_175804 | 41.550 | 38.702 | 35.404 | PASS |
| cap_20261010_175943 | 45.546 | 40.154 | 37.839 | PASS |
| cap_20261010_180235 | 45.284 | 39.073 | 33.598 | PASS |
| cap_20261010_180337 | 170.302 | 159.106 | 47.170 | PASS |
| cap_20261010_180557 | 34.002 | 31.130 | 33.815 | PASS |
| cap_20261010_180751 | 73.227 | 65.174 | 43.592 | PASS |

R02纯性能FAIL保留；R03 far/5m/S9 FAIL保留；R04本机9会话PASS。读盘、SHA与渲染不在纯算法时间，不能将仪表开销剔除后改写旧门失败。

## 实物、命令和新证据

- R02 full_*_EXIT.json：实际base/a06/split各9会话；analysis_v2 exit0，旧analysis/pilot失败原样保留。27ledger7815行/33source SHA代理核查一致。
- R03 FULL_GATE_EXIT.json/ANALYSIS_EXIT.json/PERFORMANCE_EXIT.json：各实际exit0；固定147真实候选反事实43拒绝，不能替代全链。
- R04 FULL_FAST_EXIT.json/PARITY_EXIT.json/PERFORMANCE_EXIT.json：均实际exit0；9份完整新ledger2605帧，不通过引用ledger假冒新跑。
- 消费资产：CONSUMED_ASSETS_BASELINE_BINDING列AUDIT/每会话GT/manifest/原输入与三轮起始SHA三方匹配；实际结束SHA另补证，模型实际sha84edb5f02b9f480fdfd4f5609fe678008051914400c977033e1ef6f6aac890d8。SUMMARY的GT文件SHA缺字段不修改旧评分账，以伴随清单补齐。
- SOURCE：TOOLING_SOURCES_V1所有R04工具/算法/demo，SUMMARY SOURCES保存真正加载的依赖；REF原inputs/config均冻结。
- 所有成功/失败±5上下文CASE_INDEX；完整逐帧原因R02/R03 FAILURE_LEDGER，R04逐帧等价继承并保存真实新ledger，不拼接变体最佳数字。
- 当前Demo http://127.0.0.1:8915/ ，九会话、三同步视图、同帧时间、原始参照/冻结D04/当前，含R03失败对照；快照及浏览器日志在本目录。只有人工参照区域显示聚焦，绝不进入推理。
- 独审：旧OPENCODE_SOURCE_01是中途review，wrapper exit1/child exit未保存，不报PASS；最终指定模型审核另存完整brief/model/exit与缺陷处理。

## 当前最小人工复核包

MINIMAL_HUMAN_REVIEW_PACKAGE_V2明确原家具0/40/150与独立negative_reviewed/会话分组资格、far5/40/80/463及连续±5身份、turn0/52/117/162、occl98/110/128/187/188、near210–227，S9需真实原meta+points绑定和人工审核。草稿不写回GT，不进入训练。资格不足阻止负例精度、连续身份与模型晋级，工程诊断照常完成。

## 本轮结束方向

已解决：部分远行混簇/走停走严格检测；同语义性能超门；Demo真实同步/SHA与来源/延续标签。未解决：混簇剩余、转身BG loss、遮挡、家具高分和自维持。证伪：宽水平分类拒绝无法同时保住near连续恢复。停止扩大H2。下一轮有依据的方向是从retention银行剥离自支持确认，并针对far单核混簇生成最小GT-free候选；需先冻结单因素与家具ghost反例，不能泛降门或把研究失败归咎传感器。此报告不预授权新编号工单或生产。

## 最终逐ID自验（不等同ACCEPTED）

| ID | 状态 | 实证或限制 |
|---|---|---|
| R02-01 | PASS | 全树起止SHA，外部lock消失/非原子扫描单列 |
| R02-02 | PASS | D05六套实物/历史缺件审计 |
| R02-03 | PASS | 完整逐层ledger与失败原因 |
| R02-04 | PASS | 净恢复/accepted/human-supported分列 |
| R02-05 | PASS | 冻结GT-free H1守恒互斥 |
| R02-06 | BLOCKED | strict收益子条件PASS；家具独立资格不足；legacy回退保留 |
| R02-07 | BLOCKED | 软件契约PASS；连续未标/退出资格不足 |
| R02-08 | FAIL | 原viewer race保留；最终R04 v2修复另验 |
| R02-09 | FAIL | far55.693/5m170.302ms原门失败保留 |
| R02-10 | PASS | 指定OpenCode最终01实际0/model/brief；缺陷处理与补审02均完成 |
| R02-11 | PASS | 实物/SHA/索引/人工包/本次追加return |
| R03-01 | PASS | 起止范围/源SHA和处理中增长补账 |
| R03-02 | PASS | 真实147固定候选反事实/原69D/raw/effective |
| R03-03 | PASS | 原模型不变，9会话完整实际exit0 |
| R03-04 | FAIL | near184→179；家具诊断改善不抵消回退 |
| R03-05 | BLOCKED | bank反馈实证；连续身份/负例/退出资格不足 |
| R03-06 | PASS | 当前R04 v2含R03真实失败对照；原分数/判定理由/同步/SHA |
| R03-07 | FAIL | far/5m/S9纯perf超原50ms门 |
| R03-08 | PASS | 指定最终01实际exit0，缺陷处理补审02完成 |
| R03-09 | PASS | 全账/回退窗口/源SHA/人工包/return |
| R04-01 | PASS | before/end加增量SHA；不宣称全树冻结 |
| R04-02 | PASS | 等价短路/120反例exit0；注册配置范围 |
| R04-03 | PASS | 实际9会话合计2605帧完整新账，所有点/状态精确parity |
| R04-04 | PASS | 纯算法9场p95<50ms；p99far50.294保留；板端NOT_RUN |
| R04-05 | PASS | v2实际完整DOM/9会话/全部控件/SHA/截图，空导出失败保留 |
| R04-06 | PASS | 指定独审01实际流程PASS；工程缺件已修，补审02实际完成 |
| R04-07 | PASS | 源SHA/实账/案例/人工包/追加return，四类独立裁定 |

工程：实跑/可审查代码/当前可操作Demo/真实独审与回传已交付（补审02已完成并附真实进程状态），保留旧两轮工程失败。算法：FAIL，部分收益不等于目标整体达成。GT：BLOCKED，独立负例/连续身份/退出/S9不足。生产：BLOCKED，部署/采集/板端/物理均NOT_RUN。未ACCEPTED。

当前唯一导航CURRENT_DELIVERY_INDEX_V2.md与demo_v2/README.md，人工包V2；旧8914与空导出不作为完成证据。实际浏览器完整BROWSER_OPERATIONS_V3/BROWSER_FULL_VERIFICATION；独审P1/P2处理FINAL_REVIEW_DEFECT_HANDLING、GROWTH_PROVENANCE。指标来源保留完整COMPARISON与原评分账，绝不拼接最优变体。


## 追加纠正与独审闭合（2026-10-12，V2）

旧FINAL_REPORT及return中的“9×2605”措辞保留为历史，明确纠正为九会话**合计2605帧**：304/258/464/239/202/238/251/523/126。五套新实跑base/A06/split/gate/fast各2605帧，共13025 ledger行；不是每会话2605帧，不改任何原始计数或评分。各轮验收表ACCEPTANCE_V1保持冻结；此处只是最终材料V2。

OPENCODE_FINAL_02：PID27084、420.659秒、child exit0、wrapper exit0、export exit0、actual model opencode-go/deepseek-v4.1-flash；完整brief/ponytail实际路径读取、carrier核验、只读grep/read、REVIEW_COMPLETE。STATUS与EXPORT为实际进程/模型依据，不以审核自述替代完成。其逐项确认P1-1真实九会话/19条DOM、P1-2独审完成、P2-3跨轮未完成分析增长已经披露、P2-4当前8915导航闭合；未发现阻断当前工程交付的缺件。独审未重跑浏览器或多GB评测，其判断限于实际文件证据；不能等同人工算法接受。

非阻断限制保留：播放/暂停原日志只记录停下后的“播放”按钮态；旧8914 README明确为历史，由本V2入口引导，不修改其冻结SHA。补充BROWSER_OPERATIONS_V4保存近距f220 gate/fast同帧实物与键盘221；其中初次fill输入尚未触发change的f0/输入220不一致行标为未完成，不能纳入PASS。实际键盘ArrowUp+Tab触发同步加载，完整V3验收结果不被该未完成行替代。

结束全树15402文件实际SHA之后新增的Demo v2/审核/报告/return等，在FINAL_INCREMENTAL_BOUNDARY逐项重新SHA登记，并复核所有实跑SUMMARY加载源与TOOLING_SOURCES_V3。未变化size+mtime沿用先前实际SHA，不冒称再次全树内容冻结；.git内部、自身输出不在扫描，外部lock历史消失仍单列。H1/H2/H3源、配置、原模型与GT不因补审修改。新增两个收口脚本是材料工具，不进入算法和性能。

工程PASS为材料与当前可操作Demo闭合；算法FAIL、GT BLOCKED、生产BLOCKED，设备/部署/采集/物理NOT_RUN，不ACCEPTED。下一轮证据依据仍是银行自支持与单核混簇，未登记或运行该方向，不能将建议当成果。
