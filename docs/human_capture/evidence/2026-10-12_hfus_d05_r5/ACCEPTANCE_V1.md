# HFUS-D05-R05 唯一验收 v1（2026-10-12，实验前冻结）

用户持续离线授权及“继续”；不是D05a/D05b，不启D06/D07。Codex唯一writer，两代理/OpenCode只读。实际ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。基线15463文件覆盖tracked/untracked/ignored，master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27，errors/drift/missing为空；非原子扫描，.git内部除外。仅新源码`sidequests/human_fusion_lab_next/d05/r05/`与本证据目录、HC入口/追加D05 return。冻结资产/历史只读，无Git写、部署、采集、驱动网络、生产模型/链、ML激活。

## H4 单因素：银行锚点来自当前独立证明候选

前置核查纠正：原bank已仅允许FG+confirmed的pre-fusion A候选刷新，MERGED/RETAINED不能直接续bank。家具是独立误接受播种→有限延续→过期→独立高分再入；不能将持续输出当直接自支持。原银行保存内部PIPE t.x/y；内部tracker同帧允许多候选命中同ID，并执行EMA/投票。因此锚点可能偏离产生独立证明的候选，需实际事件证明，不能先称真人/家具。

H4仅改变每次原本合法bank更新的x/y：选同PIPE track的FG且原概率>=.55候选中分数最高者（同分candidate_id字典序），保存它的当前centroid.x/y。原bank建立/确认数/更新时间/30帧和180秒寿命、0.4m半径、候选/模型/分类门/两个tracker/UNKNOWN A06/split均不改。GT/未来帧不入推理。当前R04是control；D04 frozen原对照保留。先真实control事件账测锚点偏移、多候选命中和票来源，再实际完整anchor重跑；若偏移不存在，不虚构收益。

仪表单独记录pre-fusion PA候选内部trackID、成员FG/retained、分数/决策、当前与PIPE centroid、bank before/update/after、建立/过期/再入；retained点恢复owner仅按实际当前live anchor半径匹配，不能把终态A/B/A+B当FG来源。记录每帧最多/多次tracker命中，不修改它的票数。本轮不同时修tracker或分类。

H4算法收益门：所有正式场景strict observed TP不得减少，near f220–224五次既有严格成功逐帧保留；家具human/propagated已标错误接受不新增；至少一个已标严格FN真实转TP或已标家具错误接受/有限错误延续减少，才能称有算法收益。独立负例资格不足仍BLOCKED，工程诊断不等于负例泛化。没有收益就停止扩大H4，不调参掩盖。

| ID | 冻结要求 |
|---|---|
| R05-01 | 起止branch/HEAD/status与tracked/untracked/ignored SHA，运行中文件/范围外变化/不可读单列 |
| R05-02 | 原直接续bank假设纠正、实际pre-fusion事件/原票/锚点证据，源码GT-free，单因素及反例检查 |
| R05-03 | control九会话合计2605帧完整新跑，相对R04逐帧点/候选/确认/跟踪/strict/legacy精确一致，真实退出和加载SHA |
| R05-04 | anchor九会话完整实跑，全部人工失败逐层账，strict/legacy与来源分别对照；原门与上述收益门，不拼接数字 |
| R05-05 | near220–224/turn既有成功/still53个人参照保持；重复/逆序/gap/reset/跨会话真实契约；真实ID/退出未标BLOCKED |
| R05-06 | 无竞争串行纯算法统一预热前5帧，p95<50ms；instrument/read/render另列，Windows不冒充板端 |
| R05-07 | 新Demo三窗与九会话/控制/SHA，同帧control/anchor、独立观测/retained/有限coast/UNKNOWN及锚点原因，真实浏览器证据 |
| R05-08 | 指定OpenCode opencode-go/deepseek-v4.1-flash只读审核，完整指令/技能/实际模型/退出/缺陷处理 |
| R05-09 | SHA、完整逐帧/逐场景/连续成功失败索引与最小人工包，追加return，工程/算法/GT/生产分别裁定，不ACCEPTED |

额外工程诊断：far f5/f7/f8现有PA混簇各约11700点、human纯度约.53、coverage约.976，上层只有一个合格核心，原H1需至少两个核心所以没触发。可记录该事实但本轮不同时引入单核分离新算法。
