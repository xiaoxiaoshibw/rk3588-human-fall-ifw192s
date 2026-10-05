# Codex GL04 R6 独立复审 / 2026-10-03

**REWORK：仅 V07/V09 的 source 位置来源消费者仍FAIL。** R5原阻断（95/97）均闭合；v1不变。不是CLI自验代验收：独立结果在`codex_review_01/`，真实浏览器在`browser_01/`，旧R1–R5证据不覆盖。

## 模型、范围、SHA与执行

02_resume_probe8.828秒PROBE_OK/exit0，指定opencode-go/deepseek-v4.1-flash/default DB。唯一writer session `ses_f01ba3f48ffepSrGKkcHrb3onk`：03上下文159269时由Codex主动暂停CLI/exit1，保留00_diag与部分lib修改；官方同session summarize31.968秒完成，导出summary=true/原模型/finish=stop。05同session续接于04:41:39+08:00 exit0、SUBMITTED后停写。初始03退出不是服务/算法失败；续接峰值141208已到收尾，未为形式再次压缩，不宣称全程≤120k。

现场SHA-256与R6提交after逐项一致：

| 文件 | SHA256 |
|---|---|
| preview/human_fall.js | a77452b96e2697ee358b22a12a87a2e7b5dd02ffbd566d85f5a32c20053dae90 |
| preview/human_fall_lib.js | 2fc2cd25a73be3ccb3c9291a663e6ee9843bf675e60049bcc66499c1c8b7fbee |
| preview/human_fall_lib.test.js | 4c1e030f25228d69aee411c7c34d5b030623b2aba4e5fdf0406c5259182d66ef |
| preview/index.html | 6e687d95d77144e04fa67fc473e3f8437dcca1e36f8717d72466d338f78cd62f |

HEAD master/cbd0be1未变。1679文件范围基线`00_resume_before_manifest.json`，最终范围`codex_review_01/94_scope_verify.json`：无冻结源码/正式页/旧证据意外改变，原48可重构到R5完全相同SHA（包含原44）。Windows src/CMakeLists.txt仍原不可hash软链接表示，未替换。index回传before列误用了40字符Git blob，但现场SHA256、after与原基线一致，不当成源码漂移。ponytail实际read记录为`C:/Users/30680/.claude/skills/ponytail/SKILL.md`；回传误称.config路径/skill加载，审查附记据原CLI read纠正，确实先读过，不虚报skill工具调用。

## 独立结果与真实发现

`codex_review_01/prepare_review.py`只复制原Codex90/92/95/97及VM harness并调整嵌套目录深度，断言不改，原日志不写。独立41/2/3/20项全部PASS，54 lib PASS，五命令exit0（93_codex_exits.json）。不能以数量代完成。

新`98_codex_lifecycle.js`暴露已有C08测量来源缺口：locked、同当前source/frame与唯一candidate几何匹配，`position_source_from=unavailable`或`predicted`但`position_predicted=false`，仍显示3m XYZ/“实测”。HF.actualObservationQualified只进入physical门，hfRenderState取值与hasMeasuredPos仍只看三元组/布尔flag。实际Node _state_payload:1156–1186/1208–1216定义 unavailable=无source位置、predicted=预测；INTERACTION:165/178禁止伪装新实测。真实browser15及DOM独立复现。预期当前位置空、无“实测”，physical unknown；缺字段legacy继续兼容，bbox_observed=false且来源actual_points的raw中心保留。最小修复是位置provenance共享门，不把bbox门整体套到raw上。

98原始结果3PASS/7FAIL/exit1保留。其中5条“所有失活/过期预测灰诊断必须隐藏”的assert超出现行契约，Codex与只读契约助手核对后不当验收FAIL；实际五例current '--'/physical unknown/灰预测已经非测量。原正式页也不一律按track_status/stale隐藏诊断。它们是非合法Node组合的容忍限制，不新增严格组合校验；详`codex_review_01/99_contract_adjudication.md`。纠正Codex预期，不降低原44/48/54或source实测要求。

## 固定V条目

| ID | 结果 | 独立证据/限制 |
|---|---|---|
| V01 | PASS | 90显式R/t、actual ground AABB/回退；browser01–06同frame/两坐标，offset=t[2]正确；生产另V10 |
| V02 | PASS | 90/97/54：支持预算/索引/独立层、显式support mm拒；网格仍非已核验地面 |
| V03 | PASS | 97/54 source单位错拒、transform单位门、当前选择单位守门；新fixture绑定schema完整 |
| V04 | NOT_RUN | 纯8角/near/far/behind/DPR检查过；真实rotate/zoom/俯瞰/resize做；真实DPR1和1.2均测得，但发生跨页面/布局变化，未隔离DPR-only；真实完整clip/退化矩阵未做 |
| V05 | PASS | 90/97 identity/key/signature全既定子字段拒旧；current select wire seq:7/c0000+ACK实跑，列表/拖选共享guard |
| V06 | PASS | 95/97+browser14：ground unknown源XYZ可留，physical unknown；单位/schema/verifier/绑定门、静默/断连恢复保留 |
| V07 | FAIL | 98及browser15：显式非实际source来源仍当前位置/实测；预测当前位、空候选灰诊断与lost/ambiguous两mode原反例已闭合 |
| V08 | PASS | 新schema/完整state三fixture正确；六图/同frame、FPS/queue/连接明确；无外参ground禁用、原始cloud/candidate可见、flags false |
| V09 | FAIL | 原48完全保留、54独立exit0、正式/core/driver未改；source来源实测标签仍不诚实，原raw与bbox语义需分别保留 |
| V10 | BLOCKED | 生产无显式R/t/support，冻结core/topic |
| D01 | NOT_RUN | 不设备/真实人体/板端性能；仅本地synthetic/offline |

## C01–C15

| 行 | 结果 | 依据 |
|---|---|---|
| C01 | PASS | legacy source-only first select/locked XYZ、physical unknown，90/92/97 |
| C02 | PASS | 到达顺序原入口保留，90/既有有效证据 |
| C03 | PASS | 同内容reload和相机变化保留原ID，90/browser20 |
| C04 | PASS | 双侧cal交错未知/恢复，90 |
| C05 | PASS | known/null/undefined绑定及坐标子字段token，90/97 |
| C06 | PASS | schema2/frame/epoch/verifier已有拒，90/97 |
| C07 | PASS | 0/多/only-other current目标不背书，90/97；来源否定另C08 |
| C08 | FAIL | 来源unavailable/predicted当前XYZ/“实测”未分门；bbox-only negative/legacy positive保留，98+真实15；不新要求删除灰诊断 |
| C09 | PASS | 90 GPU一次失效；browser16–21 pending/ready、断连/当前终态重连、silent未知，历史synthetic-e1不删 |
| C10 | PASS | valid/unknown/none/verifier物理门95/97，真实browser14源XYZ与physical分离 |
| C11 | PASS | 不可变token和提交再核、当前原ID，90/97/54 |
| C12 | NOT_RUN | 实际相机/resize部分已做，隔离DPR-only/完整clip退化未完成 |
| C13 | PASS | 点预算和显式support非米/非finite拒，90/97 |
| C14 | PASS | 当前source mm选择/测量和transform拒，legacy缺units容忍，97/54 |
| C15 | PASS | 新fixtures绑定、source实际来源、normal/offset/t一致，实际浏览器六图/metrics |

M01/M02/M04/M05/M06/M08/M09/M10 PASS（M05浏览器pending仅注入backend状态、不做任何真实基线采集；终态/历史/选择ACK已验）；M07 FAIL（明确来源不可用却旧XYZ仍作current，与C08/V07共同映射）；M03/M11 NOT_RUN。

## 浏览器与后续

新browser_01包含三场景source/ground六图（无外参请求入口禁用、回退source如实截图）、metrics、DOM和console日志。01/02正常、03/04全倾斜、05/06无外参；10健康、11实际zoom键尝试（当次DPR未变）、12俯瞰、13 resize初始尚未同步而14以后canvas正确同步、14 ground unknown修好、15 provenance实测FAIL、16 pending输入、17断连、18当前failed终态重连、19旋转滚轮、20当前选择ACK、21 ready静默expiry未知。pending由localhost测试输入，不是采集；仅127.0.0.1:18090/18091，页面关闭/视口reset。DPR1→1.2跨导航且伴布局变化，只记实际观测不伪报DPR-only PASS。

责任：R6设计前置已列负向actual字段，但只映射physical消费者，漏当前位置/实测标签；Codex最初追加的灰诊断hide断言也过严，已按冻结契约纠正并保留原失败。续派同工作项R7仅补provenance消费者，先完整矩阵+设计映射，v1不动，仍唯一OpenCode。V10/D01分层不挡合格软件，但当前有source FAIL及V04 NOT_RUN，不能软件收口或并入正式。无GL05/部署/采集/板端网络/commit/push/reset，未重跑326/7/12+2。
