# HFUS-D05 R02→R04 完整实跑审查包

状态：REVIEW_READY；以下是实际结果，不ACCEPTED。当前选择R04（R02 split等价优化），R03失败分类保留可操作对照。主控唯一writer，两个代理和指定OpenCode只读。实际ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。master/026e06303f60ed1bbe4ddc4d037836db68da6d27；全树基线包含tracked/untracked/ignored，结束边界见FINAL_TREE_SHA与BOUNDARY_COMPARISON（扫描中，完成后另核对）；不声明原子冻结。

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
- 当前Demo http://127.0.0.1:8914/ ，九会话、三同步视图、同帧时间、原始参照/冻结D04/当前，含R03失败对照；快照及浏览器日志在本目录。只有人工参照区域显示聚焦，绝不进入推理。
- 独审：旧OPENCODE_SOURCE_01是中途review，wrapper exit1/child exit未保存，不报PASS；最终指定模型审核另存完整brief/model/exit与缺陷处理。

## 当前最小人工复核包

MINIMAL_HUMAN_REVIEW_PACKAGE明确原家具0/40/150与独立negative_reviewed/会话分组资格、far5/40/80/463及连续±5身份、turn0/52/117/162、occl98/110/128/187/188、near210–227，S9需真实原meta+points绑定和人工审核。草稿不写回GT，不进入训练。资格不足阻止负例精度、连续身份与模型晋级，工程诊断照常完成。

## 本轮结束方向

已解决：部分远行混簇/走停走严格检测；同语义性能超门；Demo真实同步/SHA与来源/延续标签。未解决：混簇剩余、转身BG loss、遮挡、家具高分和自维持。证伪：宽水平分类拒绝无法同时保住near连续恢复。停止扩大H2。下一轮有依据的方向是从retention银行剥离自支持确认，并针对far单核混簇生成最小GT-free候选；需先冻结单因素与家具ghost反例，不能泛降门或把研究失败归咎传感器。此报告不预授权新编号工单或生产。
