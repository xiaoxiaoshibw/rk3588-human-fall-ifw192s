# RF-OPTIMIZATION-R1 作者提交

状态 **BLOCKED（可用性资格）/ SUBMITTED（离线探索）**。统一融合 R3、生产跌倒/RK3588验收 R4均 NOT_RUN。不能把本轮称为“人体识别优化到可用水平”。

| 路线 | 维度 | 弱标签Precision | 弱标签Recall | FP | FN |
|---|---|---|---|---|---|
| 新簇级固定RF基线 | 51 | .8672 | .9989 | 140 | 1 |
| RF-v2，嵌套调参 | 51 | .8772 | .9989 | 128 | 1 |
| RF-v3，增加18项 | 69 | .8772 | .9989 | 128 | 1 |
| HistGradientBoosting对照 | 69 | .9870 | .9989 | 12 | 1 |

数字是六个外层留会话折、各自内层阈值的描述性合并，不是统一阈值成绩，也不是人体真值指标。两个折无负例，六段同房间静态/弱标签。RF增加18维未改善混淆计数；不继续盲目扩维/增树。GBDT值得下一轮可靠GT对照，未授予生产替换资格。

GBDT留出permutation第一项为X中位数（六折平均分数降幅约.0749），提示位置依赖；`v3_no_position`只是局部删除显式XY/距离特征，仍保留径向std，不声称排除位置捷径。追加`sensitivity01`同时删除41径向std，RF与GBDT用相同58维，属事后诊断，不用于选模型。GBDT误判由12增至34（122637会话），RF仍128；收益有位置依赖且跨会话稳定性不足。删除的新层结构或新PCA组也没有改善RF计数；不以低permutation单独否定这些物理特征在其他域的价值。

本机特征提取51+18维耗时P50/P95约3.975/8.338ms（不含读取/变换/候选生成）。每候选推理为6折32候选循环均值的平均：RF-v2约6.066ms、RF-v3约4.330ms、GBDT约.736ms；森林配置不同且测量样本小，不据此解释严格速度优劣。全量研究工件83113/95097/213312B；均production_eligible=false。不是RK3588端到端性能。

## 验收逐项作者结果

| ID | 结果 | 本轮证据/解除条件 |
|---|---|---|
| RFO-01 | PASS（基线范围限定） | 00/06基线与复算；7755条非忽略tracked/untracked。除本轮README新增外，发现4项外部变化，见下文；不声称整树未变 |
| RFO-02 | PASS（审计） | 01_AUDIT逐索引定义、错位/冗余/PCA/JS差异/空场泄漏/域错配；prepared feature_audit相关性 |
| RFO-03 | BLOCKED | 1239候选源点重现PASS；背景删除/碎簇/粘连/Track完整因果需要逐点及轨迹GT，当前UNKNOWN |
| RFO-04 | BLOCKED | 自动弱标签未人工签核，未增加可靠困难样本；逐候选review_queue已生成 |
| RFO-05 | PASS（探索执行） | run01真实51/69/69维三路训练、limited grid、模型SHA与列清单 |
| RFO-06 | BLOCKED（泛化目标） | 嵌套会话划分PASS，跨组重复0；新人员/家具/场景资格无可靠证据 |
| RFO-07 | PASS（描述性探索） | 外层permutation、相关性、实际删列重训、逐会话PR PNG/SVG和阈值scan；未用于外层再调参 |
| RFO-08 | BLOCKED（完整覆盖） | 本机性能已测；弯腰/遮挡/动态/远距层缺可靠标签，RK未跑 |
| RFO-09 | BLOCKED | 缺独立source:human、至少3场景/各层2会话，不能检验预注册资格门 |
| RFO-10 | NOT_RUN（提交时待独审） | OpenCode CLI已启动；以后续独审原文与修复/复测记录为准 |
| RFO-11 | PASS（实验检查） | 03_tests_run01：3项综合检查，-B -W error，exit0；实际模型n_features检查、非有限/退化/重复组检查 |
| RFO-12 | PASS | 工单/唯一表/入口/回传、R3/R4停留NOT_RUN；未改Track/生产模型 |
| D01 | NOT_RUN | 未进行设备/物理/采集/部署 |

## 保护核查

`06_protected_compare01.json`全量复算：README为本轮有意新增登记；另外以下4项在会话期间由外部变化，Codex本轮没有写入也没有恢复：`docs/sidequests/evidence/2026-10-10_cl2_13_r1/00_SCOPE_AND_ACCEPTANCE.md`、`02_RECOMPUTE_RESULTS.json`、`02_independent_recompute.py`、`pc_apps/console/console_test.py`。因此不能声称整个生产树或旧证据全部字节不变。RF分类器、human_replay实现、背景包络、六源点云与C1旧证据的基线核查未发现变更。禁止将外部差异归属本工单或rollback。

## 可追溯入口

- `workspace/prepare.py`：只读重建，已运行1239/1239全向量一致；源文件SHA/候选局部索引SHA在prepared。
- `workspace/experiment.py --out .../workspace/run01`：7路线×6外折，内层3折有限搜索；exit0，完整日志02。
- `python -B -W error -m unittest discover -s .../workspace -p test_research.py -v`：3/3，exit0，日志03。
- `workspace/plot_results.py`：PR图实际生成并视觉核查，无遮挡/缺字。
- `workspace/position_sensitivity.py`：事后58维同输入诊断，日志07、sensitivity01；不覆盖run01。

writer实际读取pony tail路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；使用scikit-learn/matplotlib技能。核心未闭合项是可靠候选GT和真正跨人跨景数据，而不是“还需要加多少维”。下一轮先人工核对失败候选并补齐独立标签/元数据；本轮无采集授权，不能自动补录。
