# GL-I05 R1：候选竞争判别、保守搜索成本与固定区域证据复核

状态：GL-I05 R2软件独审PASS / STOPPED。Codex唯一研究writer已停写，指定Go Flash/defaultDB最终不可变二审通过；C/E/S/Q软件PASS，B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。只离线研究，不接生产/不启动GL-05。详见evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md。

唯一验收：[GLI05_ACCEPTANCE.md](GLI05_ACCEPTANCE.md) v1。主开发：[AI_PROMPT_GLI05_CODEX_R1.md](AI_PROMPT_GLI05_CODEX_R1.md)。独立二审：[AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md](AI_PROMPT_GLI05_OPENCODE_SECOND_REVIEW_R1.md)。

## 为什么做这一单

GL-I04诊断软件及研究安全检查已独立二审PASS，真实标定仍无资格。新工单不返工已通过代码，解决两个具体研究问题：

1. 固定首个锚点的半角包络会不会把“证明方法不够强”误当成“已见候选存在竞争”？如何在有界资源内区分它与真正近优竞争？
2. 每个合格raw假设都精炼导致>2×基线成本。相同采样inlier成员是否足以证明精炼可复用，从而降低成本，而不丢弃晚到/不同候选？

并行保留物理证据工作：用既有固定box和源索引做逐帧空间复核，定界检查新增本地录制资料。缺失录制extrinsic不阻synthetic软件研究，软件判别也不解除该缺口。

## 已有证据与反例

- [GL-I04收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)：诊断4×89帧、351255源索引点可复现；原型不接运行时。
- [最终成本](evidence/2026-10-03_gl_i04_r1/22_final_research_summary.json)：清洁/8mm噪声原型中位约.087/.084s，对照冻结完整fit约.037/.035s；比较阶段不同，不能据此预言新算法真实加速。
- [本次只读旧trace审计](evidence/2026-10-03_gl_i05_r1/02_existing_trace_audit.json)：32条已有记录，**没有新抽样/新原型实验**。high_noise_seed7原序：best支持434、近优池422，best与近优之间distinct对0，但近优池内部distinct对33。全部6个high-noise及2个close记录存在此类反例。
- 因此“只要没有候选与best distinct就闭合”已被反例否定；**必须检查近优池内部，包括非传递链两端**。真实negative-X WHAT_IF：best1209、近优693，池内distinct对3519；仅诊断，不是物理双地面证据。不能为得到真实成功而直接清门。

## 本单研究契约（新增研究定义，不改GL-I04或冻结生产规则）

同一已见有限序列经过冻结qualification/refine门后得到多重集合W。拒绝/预算未完成也有事件，不能假设未处理项弱于best。对两个合格精炼见证，distinct沿用角度>10°或offset差>.05m，similar是其否定，不是等价关系。

定义三个独立指标，并显式输出各自判别域：

- ALL：W中任意两见证是否distinct；用于“全部已见见证两两相似”的严格性质。
- NEAR：S=max support_count，近优池C={w: support_count>=.8*S}；检查C内**所有两两关系**，保留所有最高支持tie。不能只检查best对其它人，不能依赖第一名/第二名或代表排序。
- BEST_ONLY：best/tie与近优候选的关系，只作对照暴露漏判，不得作为闭合资格。

完成所有资格/精炼事件且候选/trace/迭代/精炼预算无缺口时，研究终态允许：

| 终态 | 证明要求 | 可以说什么 |
|---|---|---|
| seen_pairwise_closed | W非空且ALL无distinct，有完整证明 | 该有限已见序列的精炼见证两两相似 |
| seen_dominant_pool_closed | W非空、NEAR无distinct，ALL有distinct；完整证明近优池成员和其内部关系 | 已见近优池闭合，存在已披露的较弱distinct见证；不是全候选唯一 |
| unresolved | 近优池distinct/无合格见证/任何处理或证明预算缺口/证书无法证明 | 按原因区分实际竞争、证明不足、未处理，不假称通过 |

这是本单新的离线研究报告语义，**不替换**GL-I04的seen_sequence_closed_single，也不转为ground.status=valid/calibration/candidate/physical。输出独立kind/schema；冻结fit原生status/validation单独保存。未见假设仍未排除。

## 开发顺序和决策门

1. **先建立独立oracle和拒绝原因归因。** 使用同source、selector、seed、sampling序列、冻结阈值，报告ALL/NEAR/BEST_ONLY，拆分budget、固定锚点证书不足、实际distinct。oracle仅在测试/证据保存全部见证。先独立手算支持比边界、最高支持tie、0/6/12°链及“中间best”的漏判反例。
2. **再开发最小有界原型。** 比较GL-I04固定锚点原型与本单新原型。用0/4/8°全相似见证的所有到达顺序暴露半角包络的保守性；同序列oracle确认是否仅证明不足。可以研究有界见证/包络证明，不预定必须使用某一聚类或永远清旗。任何未能证明的合格假设仍unresolved。
3. **最后才做成本优化。** profiling确认热点后，研究相同sampled inlier成员的精炼复用。需要证明依赖包括source内容/fit全量与sample映射/up/height/settings/实现SHA；哈希键必须核对实际成员字节，禁止仅normal近似或哈希碰撞合并。不同mask、caller原地改、同路径异内容、不同setting/先验/源码版本不能命中旧结果。有界cache满可回退真实精炼；预算耗尽必须unresolved。cache并非硬性交付，证明不成立就不采用，保留未缓存正确对照和否定证据。
4. **复核空间与录制证据。** 复用GL-I04四box×89frame全点统计/源索引，可生成单个离线空间审查页或等价逐帧产物，至少按frame/box定位source XYZ点、读源row/seq/残差，明确显示数量与全统计数量。几何尾部和WHAT_IF参考平面不能自动成为物理身份。只定界核查GL-I04之后新增或此前明确漏检的本地记录；无新记录就沿用缺口，不重复全历史或远程采集。输出录制窗口/提取时间/配置绑定/SDK变换/证据SHA表及缺失项。
5. 自验停写→指定Go Flash/defaultDB独立二审→按唯一ID收口→采用/不采用/需补实验决策。本单最多推荐后续接入，不能真正接入。

实验至少含：清洁/8mm/35mm单平面、弱distinct和强竞争、近优链两端/中间best、support ratio=.8两侧与tie、晚到更强best/晚到第二平面、0/4/8°固定锚点反例、重复相似/真正distinct、3固定seed及原/置换顺序、candidate/refine/trace/iteration/cache预算边界、同输入重跑及内容/settings/caller变更。统计匹配oracle/误闭合/额外未决，保留反例原数据，不硬编码指定噪声必须闭合。

## 范围和产物

本单**不新增或编辑任何src/生产路径**。所有研究实现/集中tests/报告/离线空间产物仅在新run_root；默认`docs/human_fall/evidence/2026-10-03_gl_i05_r1/`，若跨日新建当天目录并记入口。现有planning文件和GL-I04全部证据只读，不覆盖。

最小范围建议research_01下`oracle_analysis.py`、`search_prototype.py`、`experiment.py`、`test_gli05_research.py`；空间审查如确需要可加`source_review.py`。可合理合并/减少，新增额外路径先在00_diag记用途。只stdlib+NumPy；复用冻结loader/selector/replay/refine/config入口；无需新依赖/服务/框架/生产webui。冻结src、原tests/config、批准draft/capture/NPZ、driver/HR/pc_apps/UI、旧证据。共享树其它任务差异分类保留，不能归为本单改动或回滚。

交付：设计/依赖与Q矩阵映射；带source/代码/settings/seed/抽样序列SHA的JSON+MD实验台账；可运行有界原型和独立oracle/tests；逐帧局部空间产物/录制证据表；原始命令/exit和资源/成本记录；最终提交manifest（日志关闭后哈希）、returns/GL-I05.md追加、实际OpenCode二审及最终决策。软件必要检查未跑NOT_RUN；B01/B02沿用BLOCKED，无设备/GL04DPR就D01/D02 NOT_RUN。

没有速度收益或研究否定可以是有效成果；误闭合、掩盖竞争、无正例、必要实验未跑不能用“研究性质”免责。只有通过独审且证明/成本/保守性均可解释，才推荐下一单的具体接入范围。
