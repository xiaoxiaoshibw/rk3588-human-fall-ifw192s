# HF-MAINLINE-POINTS-01 · 人体点集保留链交付

冻结候选页面可运行、可同帧比较、可逐源行复查；**最终captures/remote已为空，当前原始数据复跑BLOCKED，不能声称当前可从原录制复跑**。此前基线与两轮全帧验证已完成，原证据不覆盖；FINAL_SOURCE_AVAILABILITY记录18个当前缺失原文件，删除行为来源未归因，本writer未删除。必须恢复与SOURCE_BINDINGS完全同SHA的原文件才能解除，禁止猜测替换。**没有获得可验证的完整人体保留/纯度收益，不包装成优化成功；交付删点诊断与UNKNOWN候选。** R1保持默认，生产晋级和confirmed保持BLOCKED。SUBMITTED，未ACCEPTED。唯一验收见ACCEPTANCE_V1.md；OpenCode结论原样另存，不代写。

执行位置D:/Code/ldiar。实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md及C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。本writer未改原core/actions/配置、R2/R3契约、旧GT、原录制及跨仓背景；全树同期外部漂移另列。另一个scene_change任务同期修改共享页面，实际字节及外部来源单列保存；不是本轮候选，不认领其算法/效果，也不回滚它。

## 绑定与基线

跨仓背景三文件与八registration SHA均与计划冻结相同。Python当前范围严格0.2<raw radius<15m、高度[-0.25,2.6]、3D背景tau=0.054923896541511696m；cluster及ROI排名复用原core/actions。1934动作＋32空场逐源行前景/背景/R1成员重现；R3固定锚点成员独立重算1966帧。数值registration可用于既有隔离链不代表物理资格。

JS原诊断raw inclusive0.35–25m、有限强度、变换后float32、体素0.12m背景半径与XY清理/聚类单列。687动作帧与133空场留帧；全P明确NONCAUSAL且流式建图，过去P<=10帧，冻结B/原C分别重现。原AB评分并未经过native cleanup，所以GT-free largest XYZ scorer与native XY账本分开，未拼口径。

## 逐点根因与实验

Python保存每条28B记录的local/global源行、raw/transformed XYZ、实际first_terminal_reason、overlap与COUNTERFACTUAL背景距离、nearest reference及cluster ID；opaque引用原始SHA/offset_bytes，帧时间在绑定摘要。*_qualification.npz追加精确候选资格/关联门原因，原stage档案不覆盖。重复XYZ仍为不同源行。恢复状态独立于原first reason；追加*_final_terminal.npz给出候选最终互斥终态（10当前目标/11候选池拒绝），验证最终目标集合精确等于完整成员数组，所有源记录终态闭合。逐帧写压缩数组，历史仅4帧独立锚点/0.4s，换ID/失锁/时间倒退/gap清空。

诊断159帧，先按CONTEXT_HOLDOUT_V2排除具名80帧及前5帧上下文。高度2×2（建图0.10/−0.25 × 提取0.10/−0.25）×全P/过去P/B/C已运行，不把旧低位失败归于旧已关闭的0.10m裁剪。现有近目标背景centroid在诊断中FIT覆盖为33/33；独立参考覆盖风险无鉴别力。首轮combined最大中心偏移0.355695m且新增9帧轴缺测，接旧R3辅助方向新增1次翻转；据此进行有依据护栏返工。护栏采用已有0.12m附件半径作为中心扰动界、旧R3的0.85原锚点占比及旧R2的30°方向变化界，整组拒绝而不挑点自证；不放宽正式门，不判人体/家具。两条护栏链合计拒绝51176个点次。局部厚度/法向MISSING，不编造这些字段。三单因素及当前连接×过去证据组合均保留；reference-only退化等事实不会被“多恢复了点”掩盖。

候选只纳入当前BACKGROUND_MATCH源点且在原ROI，无invalid/range/未来点、无跨帧身体点累计。只把独立选出的当前原FG锚点写入历史，不由恢复点续期。候选池与原FG/R3分开。固定R1链、接固定R3方向/当前成员重新算节点链、独立feedback分别运行；粗槽不当解剖精度。

## 全帧结果与失败边界

固定combined：UNKNOWN恢复299975点次，原目标删除0，新目标缺失0，中心最大偏移0.09399132365567024m，轴缺测69（新增0），符号翻转0（新增0），最大粗槽跳变1.0711511382688477m（R1原1.013777m，仍退化；80帧子表最大跳变由首轮0.113392m增至护栏0.226853m），姿态事件帧变化0。空场32帧目标0/新增事件0。这些是几何回归记录，不是人体效果。

保留首轮固定R3辅助对照（不作为护栏版）：仅上游BACKGROUND_MATCH新增325563，轴缺测6、新增缺测0，中心最大0.3556946930390908m；独立feedback：新增299975，新目标缺失0，中心最大0.09399132365567024m。R1/R2/R3完整对照、原9缺测、所有新轴退化/跳变/目标漂移及最差30帧各臂见ANALYSIS.json；逐帧原表保留全部帧。

80帧CONTEXT_HOLDOUT另表，属于1966回归的子集，不加为额外样本，历史已见、仅4/8会话，不称新独立泛化。首轮阈值/组合冻结后才读取新候选结果；本次护栏返工已读取首轮完整回归和80帧结果，全部明确标为REUSED_REGRESSION，不再具有本轮选择独立性。所有源点/前缀重放相等，详见ALL_FRAME_VERIFICATION。

JS/S8基线固定原C_V2_DIAGNOSTIC：53帧57045部分人体标签，前景54069/57045、selected54063/57045精确重现；未拿A/B选优替换C。JS高度/上下文消融见JS_METRICS/JS_FRAME_METRICS。094333人体分母0，只保留几何/旧proxy边界。S8家具标签分母0、Python无家具标签，PR07c均NOT_EVALUATED，不能说0污染。全部新候选身份UNKNOWN，完整召回/纯度/解剖精度/泛化null；参考物理资格UNVERIFIED。

逐点账本证实原C的1163个已标近地点中1159点实际first reason=BACKGROUND_MATCH，0点为HEIGHT_LOW；并非0.10m裁剪。C建图0.10/提取−0.25保留626个近地点，但全523帧所选UNKNOWN达5117662（原C477846），是扩大未知混入风险，不作为改善候选或替换基线。

裁决：既有目标附近确有上游被删的当前源点，已能可追溯纳入候选；但独立参考风险无法区分，新增污染缺可信负例，方向/粗槽变化另有退化。只交付**未验证候选与删除诊断**，不声称人体优化成功，不自动晋级。诊断→单因素/组合候选→全帧/前缀→明确无可信收益裁决闭环完成；失败出口不改成成功。

## 页面、验证与保护

原页面http://[::1]:8944/，仅localhost。R1默认；R1/R2/R3/新候选同步视角，九层显示及完整计量分开。源点查询包含raw/transform/global_row/opaque/原first reason/恢复状态，NPZ导出完整所有记录。实际浏览器连续播放、多视角、困难帧、seek/reset、非法API及完整导出见BROWSER_CHECK/API_CHECK_FINAL；最终原文件缺失时仅返回冻结账本与MISSING_ORIGINAL_SOURCE、opaque=null，不将冻结输出冒充当前原始验证。截图是观察记录，未写GT。

新SYNTHETIC契约（原保留3＋护栏3＋独占socket2）和原pointset/pipe/registration/console回归见REGRESSION_RUNS，均带所需Python -B -W error。本机性能计时在BASELINE_REPRODUCTION/FRAME_METRICS/ALL_FRAME_VERIFICATION；并行任务竞争环境下仅实测，不外推板端。保护重hash48587项，changed=12、missing=33、errors=0；变化逐项单列，不冒称整树原子冻结。早先SCOPED_PRESERVATION核对本工单31668个核心保护项无差异、跨仓依赖无漂移；这不是最终源可用性保证，最终18个主链原文件缺失见FINAL_SOURCE_AVAILABILITY；整树12变化/33缺失未逐文件归因，PR01保守FAIL。215540与旧203349等历史源在首尾之间消失，对应支线BLOCKED，不猜变换或用131958替代。

原工具会话消失导致首批基线/JS不完整，保留输出；新baseline_02/js_02完整。首次Python提前启动被保护门拒绝；UI补丁匹配失败未写入；JS VM取证太慢，停止本任务进程并以原模块只读instrumentation新ledger_v2重算；原日志/部分输出保留。JS成员导出首版出现unclosed-file ResourceWarning，修复为with关闭文件并在selection_v2重算，原警告和首版导出保留。具体退出记录、源码快照/哈希见交付索引。

## 复跑

新实验必须使用不存在的run ID，不覆盖本交付。原始源恢复同SHA后可用以下入口复跑；当前执行会因缺源而失败，不宣称当前可直接复跑：

```powershell
python -X utf8 -B -W error sidequests/human_fusion_lab_next/pointset/r01/research_retention_guard.py --run-id <新run> --config sidequests/human_fusion_lab_next/pointset/r01/config_research_retention_guard.json
python -X utf8 -B -W error tools/hf_mainline_points/verify_retention_v2.py <新run>
python -X utf8 -B -W error tools/hf_mainline_points/summarize_retention.py <新run>
python -X utf8 -B -W error sidequests/human_fusion_lab_next/pointset/r01/server.py --port 8944 --ipv6
```

当前IPv6回环[::1]:8944已运行。IPv4同端口曾被另一PLANE-01服务以复用套接字响应，原错误404/截图保留；仅停止本任务IPv4进程，另一服务未停止。同一原页使用--ipv6、SO_EXCLUSIVEADDRUSE及IPV6_V6ONLY，避免串页，仍为8944/仅localhost。不要重复启动同一回环地址端口。新baseline可用prepare --baseline-id <不存在目录>，但证据根内汇总为wx，完整从零复跑须另改新的证据根版本并冻结，而不能删除旧证据重跑。JS最终通过只读源内循环下标instrumentation携带记录身份；JS_ORDINAL_IDENTITY_PROOF证实19臂及cleanup全部成员相等，重复XYZ/XYZI的SYNTHETIC源ID7/11不合并。旧坐标顺序匹配仅作为等价核验，不作为最终身份依据。JS同样先指定新js目录，结果wx保护；完整新证据轮复跑需新E。没有训练、采集、部署、提交推送、旧GT/原录制/正式门修改或confirmed启用。
