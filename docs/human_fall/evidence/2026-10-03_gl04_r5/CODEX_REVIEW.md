# Codex GL04 R5 独立复审 / 2026-10-03

**GL04_ACCEPTANCE v1：REWORK。** R4 的5+2条原FAIL已逐条闭合，但全矩阵补查发现source观察/physical fall消费者、坐标token和单位同族漏洞，真实R5 fixture还有绑定字段缺失。不能软件收口或并入正式页。R6集中设计已准备，≤1分钟指定模型/default DB probe超时，服务BLOCKED，尚未启动写入者。

## 提交与证据有效性

唯一生效编排/独立复审/状态收口Codex，唯一生产代码写入者仍OpenCode。实现者03_opencode_meta.json exit0仅作为停写记录，不代独立验收。当前master/HEAD `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`，外部HR提交/正式Q-E帮助/根目录重组保留。

| preview文件 | 本次现场SHA-256（与claude_r5_baseline_sha一致） | returns提交Git blob SHA（git hash-object吻合） |
|---|---|---|
| human_fall.js | d2e3278edbb7d9611cd0b0ecfdd1ae93f379e361a2bafdfabb6d2614966bc139 | 6adba784091007b0308e84596b87de724b9eed0f |
| human_fall_lib.js | 2788e71fd8f62e54e33a8c0621d5f85bf8d4b9ff82b7d51be652280bd58ff946 | 6827b256b0c4de8d8901e12c9a5218fee8ff2645 |
| human_fall_lib.test.js | 77e9cce9f48d8f27c36387d1de894c9d60f1e121511e9fbb1ddbaa795a055d3d | 842420cd2ae881e3fc6f13b34543cd92a1b15509 |
| index.html | 6e687d95d77144e04fa67fc473e3f8437dcca1e36f8717d72466d338f78cd62f | f7474577f017586435c8ad6bbc764dc2ec540f93 |

源码未变，故引用本轮此前Codex独立90/92/91，不重复相同断言：`90_codex_results.json`41PASS、`92_codex_consumers_results.json`2PASS、`91_codex_lib.txt`48PASS（原44+R5追加4）；`93_codex_exits.json`三个exit0。这不是引用实现者自验；其self结果另保留。现场新检查 `node 95_codex_source_fall_gate.js` exit1（valid正例PASS、unknown/none FAIL）；`node 97_codex_additional.js`真实exit1，详97结果/stdout/meta。数量只记录，不代条目结论。

范围tracked/untracked1572文件基线：`96_codex_scope_before.json`；独立辅助审查前后四源码SHA：`97_codex_additional_before_sha.json`。最终范围核查见`98_codex_final_verify.json`。本次只新增审查/浏览器/派工证据及状态文档，未写任何生产源码/原测试。

## R4原5+2 FAIL逐条闭合

| R4原反例 | R5独立依据 | 结论 |
|---|---|---|
| known snapshot GDID / absent state GDID | 90同名项；lib `_bindingMismatch`完整nullable比较 | PASS |
| known snapshot schema / null state schema | 90同名项；lib schema绑定 | PASS |
| only-other下prediction被当当前source位置 | 90 `prediction does not become current position...` | PASS（当前position为空；physical fall另外97仍FAIL） |
| caller原地改coordinate.source_frame旧按钮 | 90 `old choice rejects...source-frame change` | PASS |
| caller原地改transform.units旧按钮 | 90 `old leveled choice rejects changed transform units` | PASS |
| legacy source-only locked当前XYZ丢失 | 92 `legacy source-only locked current target...` | PASS（raw XYZ恢复；无地面physical fall另外97仍FAIL） |
| predicted旧pose+other成当前位置 | 92 `predicted old pose...` | PASS（预测诊断保留） |

## 全表结果

| ID | 结果 | 独立依据、具体限制 |
|---|---|---|
| V01 | PASS | 90：缺R/t不造identity、冲突两坐标入口拒；source/ground按显式变换和实际ground AABB消费。真实normal/tilted两mode截图见browser_01；生产消息缺口另V10 |
| V02 | FAIL | 预算/索引/3D有限/独立网格与支持层通过；97显式support_units=mm仍support.ready，违反显式单位绑定，parseSupport未检units |
| V03 | FAIL | 变换units缺/mm原反例已过；97 snapshot.units.length=mm仍位置source(m)/3m，ground变换仍ready，单位标签与消息矛盾 |
| V04 | NOT_RUN | 纯8角/裁剪与VM DPR同步通过；真实rotate/zoom/resize/俯瞰已做；真实DPR始终1.2000000476837158、viewport能力只有尺寸，Ctrl+-未改变DPR。真实near/far/behind/退化完整矩阵未做，不虚称PASS |
| V05 | FAIL | 原frame/transform.units token反例闭合；97 source/ground旧按钮仍接受原地改snapshot.units.length、candidate.center_ground_m、ground block.kind/schema_version，缺已声明坐标/版本字段。列表当前原ID正例在browser wire日志通过，拖选兄弟入口由同hfSelectCandidate守门 |
| V06 | FAIL | nullable/schema/verifier、静默/断连通过；95/97 source ground unknown/none仍upright/绿色，raw XYZ资格错误背书physical fall。真实browser_01/14与15同样复现。需保留rawXYZ，单独门控physical fall/颜色 |
| V07 | FAIL | 原only-other实测source/ground、空/重复候选和prediction当前位置清空通过；97预测无当前实测仍upright；lost/ambiguous/unselected（validState=true）带旧source字段仍当前XYZ/绿色。不能借旧几何或ready基线背书 |
| V08 | FAIL | 六图及FPS/queue/连接指标已落browser_01；R5三fixture.state.calibration均缺schema，normal/tilted正确被拒而无有效目标读数。make_fixtures_r5未完整复制Node已发布绑定；no_extrinsics还误标source_from=unavailable。localhost完整Node形状mock正例正常，证明此处为fixture缺陷，不能放松nullable门 |
| V09 | FAIL | 原44断言+追加4独立exit0，正式/core不变，无关R7回归复用；source-only XYZ/first select已保留，但legacy/prediction/失效track消费者仍有physical fall及旧测量退化（97）。Q/E/帮助/HR/重组保留 |
| V10 | BLOCKED | 实际build_snapshot没有显式R/t/support；只读core/lidar_candidates与node_runtime确认，不改core/topic，不用synthetic冒充端到端 |
| D01 | NOT_RUN | 未授权设备/人体物理/板端性能；本次浏览器输入仅静态fixture与127.0.0.1mock，未联网板端 |

## C01–C15设计矩阵

| 行 | 结果 | 依据/未闭合 |
|---|---|---|
| C01 | FAIL | startup/legacy first select/rawXYZ通过；legacy无ground仍physical upright/绿框（97） |
| C02 | PASS | 90及R3/R4仍适用入口，到达顺序/当前frame匹配保留；本轮未变该入口 |
| C03 | PASS | 90 fresh/same-content reload原ID通过，禁止将相机变化当新坐标版本 |
| C04 | PASS | 90双侧cal交错unknown/拒旧；当前恢复，nullable修复未破坏 |
| C05 | FAIL | known/null/undefined原反例通过；同ID坐标内容token仍漏center_ground及block kind/schema（97） |
| C06 | PASS | 90/97明确schema2、frame/epoch/known对null拒绝；这些守门保留 |
| C07 | FAIL | only-other/重复几何当前实测拒绝通过；prediction无当前目标时physical fall仍upright（97，关联C08） |
| C08 | FAIL | 预测当前位置空/灰诊断通过；预测fall及lost/ambiguous/unselected旧source观察未闭合（97） |
| C09 | PASS | 90 GPU一次失效/旧选择拒；browser_01/16/18/19/20静默、断连、当前重连恢复，事件synthetic-e1保留。pending真实浏览器单列未跑 |
| C10 | FAIL | ground模式禁用/回退通过；source ground unknown/none却physical upright（95/97+真实browser14） |
| C11 | FAIL | 原source_frame/transform.units修好；source/ground旧按钮漏snapshot单位/ground中心/blockkind-schema（97） |
| C12 | NOT_RUN | 真实rotate/zoom/resize部分已跑；真实DPR变化及确定near/far/behind/camera退化完整组合未跑 |
| C13 | FAIL | 0/3/3000/3001/9000预算及索引通过；显式support mm仍ready（97） |
| C14 | FAIL | 旧transform units门通过；显式snapshot source mm仍meter测量/ground ready（97） |
| C15 | FAIL | 90及mock真实performance.queue_dropped=3、实际render FPS正确；R5 fixture完整Node消费者资格缺schema等字段，未支撑有效六图 |

## 验收表M矩阵

| 行 | 结果 | 证据/限制 |
|---|---|---|
| M01 | FAIL | source unknown/none仍upright（95/97/browser14），ground回退通过 |
| M02 | PASS | 实际ground AABB/缺字段不造框，90+lib，source/ground正常mock |
| M03 | NOT_RUN | rotate/zoom/resize实跑，真实DPR变化未跑；browser11–13 |
| M04 | FAIL | 97新token漏字段；90原frame/旧list/drag共享守门局部通过 |
| M05 | NOT_RUN | locked/ready静默断连恢复和事件保留真实通过；baseline pending真实浏览器生命周期未跑（未冒称全组合） |
| M06 | FAIL | 同内容/cal交错守门过；同ID block.kind/schema/candidate中心及sourceunits旧按钮仍过（97） |
| M07 | FAIL | 原实测only-other/ready通过；预测与失效track仍旧physical/current（97） |
| M08 | FAIL | 六图已保存，R5 fixture缺绑定schema导致目标不对齐；无外参入口确实禁用 |
| M09 | FAIL | 缺R/t/malformed/schema已有拒；显式source mm仍ready（97） |
| M10 | PASS | 支持点预算/元数据/索引两mode原独立检查保留 |
| M11 | NOT_RUN | pure8角/near/far/behind保守裁剪检查过，真实camera确定退化/完整clip矩阵未跑 |

## 真实浏览器记录

入口：`http://127.0.0.1:18090/webui/human_fall_preview/?synthetic=<name>&fixture=/docs/human_fall/evidence/2026-10-03_gl04_r5/fixtures/<name>.json`。真实IAB，WebGL/Three.js/OrbitControls，未向浏览器注入DPR或替代camera值。静态fixture三场景同seq7/stamp1000/frame/样本版本。截图、DOM、canvas CSS/backing尺寸、DPR、版本/读数/FPS/queue都在新`browser_01/`，原证据不覆写。

| 场景 | source | ground请求/回退 |
|---|---|---|
| normal | 01_normal_source.jpg | 02_normal_ground.jpg |
| tilted | 03b_tilted_source_settled.jpg | 04_tilted_ground.jpg |
| no_extrinsics | 05b_no_extrinsics_source_settled.jpg | 06b_no_extrinsics_ground_disabled_settled.jpg（入口禁用，保持source，不是假ground图） |

初始03/05/06截图加载未齐也保留，正式证据使用带settled后缀，metrics记录各次实际状态。`metrics.json`、`console_errors.json`、14/16/19/20 DOM文件保留。

localhost mock：由R2已审Foxglove v1 stdlib脚本复制到browser_01新文件，调整require相对层级和端口18091、日志只写本次目录。只连接`ws://127.0.0.1:18091`，serverInfo明确synthetic/offline。10健康source→11真实拖动rotate/滚轮zoom→12 ground俯瞰→13 resize→14 source ground unknown FAIL→16 silent→17当前ground恢复→18 ground silent回退source→19点击断开→20重连当前数据。事件synthetic-e1保留，选择wire保持原snapshot_id=seq:7/candidate_id=c0000。near/far/behind和baseline pending真实浏览器未完成，明确NOT_RUN。测试tab关闭、视口override已reset、仅本次两个localhost助手终止（退出证据99），无残留板端连接。

## 责任、返工与正式页边界

新反例均在已有C01/C05/C08/C10/C11/C13/C14与V条目内。Codex先前90仅测ground入口禁用和prediction位置，漏source physical fall、失效track与坐标子字段，记录覆盖责任；实现者虽分门rawXYZ，未分physical颜色/DOM/3D消费者，也没对新fixture做资格正例。没有对照证据，不归因模型能力，不改v1/原44语义。

集中返工唯一入口：[R6提示词](../../AI_PROMPT_GL04_OPENCODE_R6.md)、[设计矩阵](../2026-10-03_gl04_r6/PLAN_REVIEW.md)。正式probe55.313秒超时、真实exit1，详[R6服务BLOCKED](../2026-10-03_gl04_r6/CODEX_BLOCKED.md)。R6没有实施/算法结果，服务失败不算一轮算法失败。恢复后同模型/default DB先probe，不能换模型/隔离DB或并行第二写入者。

当前正式页仍冻结，R5没有获审，不执行并入；找到的2026-10-03裁决转述在AI_PROMPT_GL04_CODEX_R5_CLOSEOUT.md:19与ticket:3，尚未查到询问卡原始回答。通过后依用户第4步确认链路执行，同版本特性集、保留Q/E/帮助、禁止整文件覆盖；本单源码同步也不授权部署。V10/D01分层不应单独阻止合格软件，但当前软件自身仍FAIL/NOT_RUN。未启动GL05、部署、采集、板端网络、commit/push/reset/checkout/clean；未重跑326/7/12+2。
