# GL-I03 现行唯一验收表 v1 / 2026-10-03

2026-10-03 当前结果：按用户新分工由Codex开发并停写，指定Go Flash/defaultDB完成独立二审，软件范围无FAIL/无需返工；K04 REAL仍BLOCKED、整单未ACCEPTED。[最新收口](evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md)/[OpenCode二审](evidence/2026-10-03_gl_i03_r1/opencode_second_review_01/00_review.md)。原服务失败保留历史，判据v1不变。

来源：用户接管指令（路线B、可选显式参数、独立config仅两值）、后续Codex开发/OpenCode二审与边研究执行优化计划授权；WORKFLOW v2；[工单](AI_PROMPT_GLI03_OPENCODE_R1.md)。状态：软件二审PASS / REAL candidate BLOCKED。真实目标未降低，二审不等于设备或物理通过。

M=手工输入，S=本地软件（synthetic/offline分开），B=来源证据，D=设备/物理。用户审定up_axis `[0.438371,0,0.898794]`、height `[1.2,1.7]`和当前draft四区不调整。按ID报告PASS/FAIL/NOT_RUN/BLOCKED，不以总数验收。

## K条目

| ID | 可观察预期/负例 | 检查入口 | 层级 | 当前结果 |
|---|---|---|---|---|
| K01 | 新可选--constrained-config默认None/冻结默认；显式路径复用load_config+resolve；坏路径/YAML语法/结构/缺ground_constrained/unknown key/非法值exit2无candidate不fallback；emit-draft原义保持 | P02/P03/P04及源码 | S | PASS（OpenCode二审） |
| K02 | 新独立geometry_constrained_gli03_r1.yaml可解析、全键保留，spatial_cell_m=0.05/max_points_per_cell=8，完整SHA | P05配置/resolved比较 | S | PASS（25键/两值/SHA独立核对） |
| K03 | 默认原synthetic成功、标签/settings不变；同真实draft默认80/ground_points_insufficient/exit2无candidate；原GL-I01/GL-I02/受影响ground回归有效 | P01/P02/原tests/旧24探针 | S SYNTH/OFFLINE | PASS（实现后独立复现/回归） |
| K04 | 变体synthetic合法candidate；真实审定单组采样≥冻结min_inliers且ground.status=valid产本地candidate才算REAL PASS。status.ground=candidate/physical=false/无ground_derived/source分层；其它ground状态拒绝无artifact。未产真实candidate即目标未闭合 | P03/P04/真实CLI/schema/settings；研究25/26/30 | S SYNTH/OFFLINE；M既定输入 | SYNTH PASS / REAL BLOCKED（先验/搜索/holdout未闭合） |
| K05 | 新旧YAML唯一值差为两采样参数；其余全部阈值/预算/键保持，冻结文件SHA不变 | P05全字典/P06 | S | PASS（完整字典及冻结SHA二审） |
| K06 | 仅三生产白名单，wrapper允许SHA变化；GL-I01四文件、原GL-I02tests、core/其余config/data/driver/UI/HR/旧证据不变；含全部tracked+untracked基线，无越权操作 | P06范围/diff/CLI/Python3.8 AST | S | PASS（3文件合法改动/其余冻结保持） |
| B01 | 原bag width/height/original_count等源证据仍缺，不将export升物理验证 | GL-I01/GL-I02分层沿用 | B | BLOCKED |
| D01 | 设备/物理/性能、GL05、部署/采集/网络未授权，本机fit/AST不替代 | 日志/范围 | D | NOT_RUN |
| D02 | GL04真实DPR不属本单，正式合并不放行 | GL04 R7独审 | D/browser | NOT_RUN |

## P组合矩阵（本表子行，同一判据）

| ID | 输入×运行/消费者及预期 | K关联 | 检查入口 | 当前结果 |
|---|---|---|---|---|
| P01 | 默认+审定真实NPZ/draft→单组fit1214/采样80/insufficient/exit2无candidate，冻结来源SHA不变 | K03/K06 | 真实默认CLI/直接fit | PASS |
| P02 | 默认原synthetic；显式冻结config同输入结果/settings一致；重复新CLI不串配置，同/新calibration ID保留独占输出；emit-draft不变 | K01/K03 | synthetic逐次调用/旧tests | PASS |
| P03 | 显式变体synthetic成功；坏路径/空或坏YAML/非mapping/缺section/unknown key/bool/NaN/negative/floor拒；同路径改内容下次生效、对象不污染默认；已有output字节不变 | K01/K02/K04 | 新tests/独立负例 | PASS |
| P04 | 显式变体+真实审定单组，实际采样/拒绝或candidate留档；无draft/缺先验/frame不符/坏manifest/跨组泄漏/重叠仍拒；capture-dir保留只读和adapted中间产物语义 | K01/K04/K06 | 真实CLI/gate/source/physical | SOFTWARE PASS / REAL candidate BLOCKED |
| P05 | 配置全键值仅0.05/8变更；ground.settings留resolved；默认仍0.2/4，其余门不变 | K02/K05 | 完整dict/source | PASS |
| P06 | 全文件首尾manifest含untracked；captureSHA/Windows src/CMakeLists.txt表示保留；wrapper最小diff/原tests旧证据不改；AST与本机环境分开 | K06 | snapshot/scope/AST/CLI审计 | PASS（提交与二审首尾核验） |

## 定稿说明

删除未派工草稿“改默认/协议R5/自动R2”等噪点；P01真实默认与P02synthetic分清；pool2382不作单组门槛；orientation_unverified不是candidate成功。K04目标未降低；本轮preflight新事实1193→ground_degenerate如实BLOCKED。旧草稿/诊断留证，GL-I02路线3档案不覆写。
