# Context continuation / Change Proposal / 前置诊断

当前user明确“区域是 annotator 的 #3val区域”。根因：旧v11静态PNG/JSON #3与当前annotator代码#3不同，前轮恢复/诊断用旧静态编号。当前源码pc_apps/human_replay/annotator.html:76 #3VAL=pick04，X[1.30,1.78]Y[-.40,.22]，source→display Ry(+26°)+tz1.34。只修本轮来源引用，不改旧文件/原网页/任何production。

只读完整ABC正确域：A/C全高度范围约[-.05,.10]m，无箱顶；B新增约.23m抬高点，低位点median630→502→631，raised median0→250→0。用户原现场correspondence/horizontal确认继续有效；session操作身份以附件的实验顺序+本轮数据核验支持，不伪造meta标签。

Change Proposal：一个research脚本冻结A91+C102全部frame源行，XY2cm内缩[1.32,1.76]×[-.38,.20]，finite/nonzero，保留全部高度。内缩在拟合前声明，排除ROI边界；不使用groundZ/拟合残差gate。B不入拟合。same array float64→RANSAC raw hypothesis评分/TLS covariance/SVD centered；无prior height gate/点cap/各自inlier精修。全部方法在同一域全点统计；引用ground.py冻结.05/861/seed20261001与2°/.03工程参考。

只新增新目录脚本/产物、唯一P02验收表、追加return/review记录。回滚=忽略本research产物，运行时未接入，无需回滚用户文件。单writer Codex；数学原语已读ground.py/ground_diagnostics.py/joint_leveling.py，约束不变。ponytail与scientific-toolkit已读，实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md和scientific-toolkit-skill/SKILL.md。

| 操作/状态 | ID | 预期 |
|---|---|---|
| current annotator #3 vs static #3 | C | 精确源码SHA/当前常量绑定，不用旧meta编号 |
| A/C全frame vs B | C | A/C全部193帧、B只诊断；frame/source/index隔离 |
| 同一source pose变更/重复脚本运行 | C/S01 | frozen source rows不随estimated R重选；已有输出拒覆盖 |
| source/caller/content坏绑定 | C/S01 | 输入actualSHA与基线逐个匹配，不隐式fallback |
| RANSAC抽样 vs最终输入 | D | 861全域评分，不将自己的inliers喂另一个estimator |
| TLS vs SVD | D | 各自全相同float64数组，同符号与全点残差；不称独立物理证据 |
| consensus FAIL vs PASS | D/E | FAIL不生成E，保留数据；PASS候选但无runtime资格 |
| estimator/frame/state spread | D/E | 完整min/max/std，不删异常帧；不是独立holdout |
| candidate success vs production consumer | E/S01 | research kind+runtime_eligible=false，无正式calibration写入 |

当前全树基线00含tracked/untracked/ignored；未变文件复用前轮全hash及size/mtime，新文件/源码/current annotator/本次captures fresh hash。无写capture/driver/UI/旧evidence。
