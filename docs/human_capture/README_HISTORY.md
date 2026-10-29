## 2026-10-16 HFUS-DL-OPT-01 深度学习开发封存（SEALED）

用户「算了先暂停深度学习开发，之后再说先封存」。HFUS-INDOOR 侧链深度学习（PointNet）开发自本条起封存停写：R1 交付（三缺陷协议修复 + 合成自验，SUBMITTED）与[缺件清单](evidence/2026-10-16_hfus_dl_opt_r1/MISSING_INPUTS.json)原样留仓，真实效果/独审维持 BLOCKED/NOT_RUN，不删除、不重算、不补数、不重写历史判定。恢复条件=用户明确恢复口令 + 真实效果所需三 ZIP 回 `ML/data/` 或下载授权；恢复时从 DL01 输入门重核。（追加更正 R3：合成输出三件 `SYNTHETIC_RUN.json`/`SYNTHETIC_RUN.stderr.txt`/`TEST_OUTPUT.txt` 已按用户指令删除，删除前 sid/bytes/sha256 清单见回传；代码与文档记录保留，历史不改写。）RF-EVAL 计划（EV01–EV14）仍为未开工状态，不在本封存内启动或取消。见[封存记录](returns/HFUS-DL-OPT-01.md)。本条不接管其他主线。

## 2026-10-16 HFUS-DL-OPT-01 PointNet 训练协议三缺陷修复（合成自验 SUBMITTED；真实效果 BLOCKED）

用户「继续优化深度学习」+ 选择「不补数据先做合成自验」「只修三缺陷+公平重评」，承接 TRAIN-AI01 R2 审查发现 2（PointNet 折间模型/Adam 复用、pos_weight≈526 与实际采样分布不符、后 3 折非有效 OOF）。新隔离实现 `sidequests/hfus_indoor_ai_test/dl_fix01/`（pointnet_cv.py+test_pointnet_cv.py，不复刻旧训练器）：每折新建模型+Adam、pos_weight 取各训练折实际采样分布、OOF 1:1 且当前模型对验证折零见（成员追踪断言）。4 单测 `-B -W error` exit 0（开发中抓出并修复 2 处新码自身缺陷）；合成可分集固定协议 OOF P/R=1.0、同 seed 逐值一致；随机标签下旧协议对照污染计数 [0,32,32,32] vs 固定 [0,0,0,0]，数值膨胀 +0.053 F1 如实小口径。真实输入（三 ZIP/候选与标签账本/原训练器/run4 工件）经原路径+全盘+worktree+回收站实测仍缺失 → 真实训练/真实效果/独审 NOT_RUN·BLOCKED，解除清单 [MISSING_INPUTS](evidence/2026-10-16_hfus_dl_opt_r1/MISSING_INPUTS.json)；不下载、不重写历史判定。唯一判据 [DL01–DL08](evidence/2026-10-16_hfus_dl_opt_r1/ACCEPTANCE_D1.md)/[逐条结果](evidence/2026-10-16_hfus_dl_opt_r1/RESULTS.md)/[回传](returns/HFUS-DL-OPT-01.md)。技能 ponytail（skill 工具，full，`C:\Users\30680\.config\opencode\skills\ponytail`）。本条不接管其他主线。

## 2026-10-16 REPLAY-FRESH-NEXT-01 dev_r2 GT消费补充（SUBMITTED；语义仍BLOCKED）

用户提供gt r1交付后完成只读消费：[报告/24组条件表](evidence/2026-10-16_traditional_perception_dev_r2/gt_consume_r1/REPORT.md)/[当前索引](evidence/2026-10-16_traditional_perception_dev_r2/CURRENT.md)/[追加回传](returns/REPLAY-FRESH-NEXT-01.md)。仍用[唯一验收v2](evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)。113清单SHA、4源会话SHA与74条raw/compact/工作台点集映射均通过；24冻结组复评+6控制回放。AI已标人体范围XY在线12/41、10/21，离线41/41、21/21；18个退步窗口在线2/13、2/5，回填13/13、5/5，原base为0/13、0/5。3D全已标范围仍缺f70/71和另一段f114；窄凳抽样反例点集成立，111738四杆样本未覆盖误认领1/5/6/9，不跨帧补标或强填全会话假目标数。GT为model/unreviewed、部分范围、未人审未冻结，FN06/FN07及全会话语义统计继续BLOCKED。生产/测试及GT源不变，新工具自检通过、独审NOT_RUN；无数据/GT写、Git写、板端/网络/驱动/模型训练或采集部署。

## 2026-10-16 REPLAY-FRESH-NEXT-01 fix3 目标级评分（SUBMITTED；FN06/FN07 维持 BLOCKED）

用户"继续开发传统聚类"直派 FIX_PLAN_R2 顺序 2（Fix 3），OpenCode 唯一生产 writer；仍以[原唯一验收 v2](evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)逐项回传不改表。GT 适配器消费 gt_store draft（gt r1 AI 标注）→normalized v1，compact-local→原始源行双重值级自检 74/74 全过，SID/meta/points SHA 强校验；稀疏 GT 目标级评分落地 §4 冻结定义（≥0.5 归属/一对一/MISMATCH/IDSW/假目标按轨迹/provisional 单列），范围外一律 UNKNOWN、假目标总数保持 BLOCKED。默认 XY 复用 dev2c 预测（源SHA==当前生产源）：082829 P1 在线 12/41（0.293）回填 41/41、082906 P1 在线 10/21（0.476）回填 21/21，缺失即低姿起始段（f70–98/f95–105 逐帧 P1 真值），三口径与 dev_r2 逐项一致（2/13、13/13、3.007031s/29帧；2/5、5/5、1.650004s/16帧）；窄凳×3 与四杆状物默认 0 被认领（GT 锚定正确排除），111738 默认 0 认领帧。阳性对照 birth05_pipe05 三会话窄凳假轨迹 79/90/122 与 probe_false_r1 精确一致且被 GT 判 N 匹配=假目标；birth07 杆状物 f2/f100 不可判（f2 无 confirmed 认领、f100 认领与 B1/B2 零重叠→UNKNOWN 如实保留，须补标注帧）。19 套回归 exit0、新评分器 15 组断言 exit0、20 项输入（captures 5 会话 meta/points、gt_store 4 draft、gt_r1 3 证据、生产 3 源）首尾 SHA 相等、生产 3 文件零改动。真值为 AI 视觉标注非人工 GT，FN06/FN07 维持 BLOCKED，AD08 NOT_RUN；IDSW 分段边界差一读法另录。无数据/GT/板端/驱动网络/模型写、无采集/训练/部署/Git 写。见[逐项自验](evidence/2026-10-16_traditional_perception_fix3_r1/RESULTS.md)/[目标级汇总表](evidence/2026-10-16_traditional_perception_fix3_r1/TARGET_LEVEL_TABLES.md)/[追加回传](returns/REPLAY-FRESH-NEXT-01.md)。技能 ponytail（skill 工具，full）。本条不接管其他主线。

## 2026-10-16 HFUS-RF-EVAL-01 完整目标评价与错误回放（仅计划）

用户要求制定下一步开发计划，本轮仅交付[计划包](evidence/2026-10-16_hfus_rf_eval_plan_r1/CURRENT.md)/[唯一拟实施EV01–EV14 v1](evidence/2026-10-16_hfus_rf_eval_plan_r1/ACCEPTANCE_V1.md)/[回传](returns/HFUS-RF-EVAL-01.md)。冻结B0/RF，拟补全部候选OOF分数、全GT一对一匹配、UNKNOWN及错误回放；原路径输入缺件EV01 BLOCKED，其余实现NOT_RUN，无新训练/算法标签修改/采集部署。此前[TRAIN-AI01 R2审查](evidence/2026-10-16_hfus_indoor_train_ai01_r2/REVIEW.md)指出：P=.955/R=.724只属P/N候选子集；PointNet模型/优化器跨折复用，旧“路线FAIL确证”不成立。此处追加更正，以下旧记录保留，不改写历史。仅计划不授权开工，不接管其他主线。

## 2026-10-16 HFUS-INDOOR-TRAIN-AI01 AI 标签域内训练闭环(SUBMITTED;T06 PointNet FAIL)

用户指令替代人审后一日闭环:ND02 yaw 契约闭合→AI 视觉判读入账(24 帧 53 框,`reviewer_kind=AI` 哈希链)→BEV 资格过门(AMENDMENT_A1 事后登记,3D-R1 保留)→**组折 RF 域内 B0 P=0.955/R=0.724**(tp21/fp1/fn8;场景泛化 BLOCKED,独立组 0);**PointNet FAIL 确证**(全步数跑满仍 ≈全正分类器,不粉饰)。HDBSCAN 流召回 0.30=簇切碎首因候选(未调参)。三轮 OpenCode 只读复审抓到并修复:域泄漏折/时序泄漏折/事后维度未登记/负类依赖 AI 完备(conditional 披露)/凭记忆数字失实等 17 项。逐项终表 [RESULTS](evidence/2026-10-16_hfus_indoor_train_ai01_r1/RESULTS.md)/[回传](returns/HFUS-INDOOR-TRAIN-AI01.md)/[DATA-QUAL R2](returns/HFUS-INDOOR-DATA-QUAL-01.md)。补门=真实人审/二审(最高优先)、独立组、有界搜索。本条不接管其他主线。

## 2026-10-16 REPLAY-FRESH-NEXT-01 dev_r2（SUBMITTED；目标级GT BLOCKED）

用户本轮明确派发FIX_PLAN_R2实施，Codex唯一生产writer；仍以[原唯一验收v2](evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)逐项回传，不修改历史表。当前[交付索引](evidence/2026-10-16_traditional_perception_dev_r2/CURRENT.md)/[逐项状态](evidence/2026-10-16_traditional_perception_dev_r2/RESULTS_DELIVERY.md)/[24组与三口径](evidence/2026-10-16_traditional_perception_dev_r2/METRICS_TABLES_DELIVERY_V2.md)/[追加回传](returns/REPLAY-FRESH-NEXT-01.md)。仅traditional_perception及测试两生产文件：结构provisional旁路、零XY升起转正、confirmed-only在线认领、独立离线回填、可关闭运动候选。XY两个退步窗口online为2/13、2/5，backfill为13/13、5/5，延迟3.007s/29f、1.650s/16f；不混报。主会话291/295，两空场0/186、0/272，24组overflow全0；错参考XY163→137退步和诊断降门窄凳79/90/122失败保留。27引擎组、18JS+Python45全exit0；24消融、原探针副本、347保护文件/30原文件SHA复核齐。OpenCode只读R1 REVISE→R2 REVIEW_PASS，复审后仅补容量边界测试，生产SHA保持；当前快照R4、最终矩阵dev2c。外部GT接口与产物未找到，评分器normalized adapter仅软件自验，真实目标覆盖/假目标/IDSW/MISMATCH及FN06/FN07保持BLOCKED；浏览器本轮实录/页面性能、长会话内存、≥9候选新出生、慢起身与跨窗缺测、设备/物理/EXE等边界明确。无数据/GT/模型/板端/驱动网络写、采集训练部署或Git写，未宣称工单ACCEPTED。

## 2026-10-16 REPLAY-FRESH-NEXT-01 传统人体/姿态/跌倒候选链（SUBMITTED；语义GT BLOCKED）

用户明确派发「按计划开发、交OpenCode审核，借助视觉与算法继续传统聚类和架构更新，参考外界案例，推进完整人体/跌倒项目」。本项仅本机PC会话回放候选链，Codex唯一生产writer；当前[唯一FN01–10/AD01–08验收v2](evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)/[逐项状态](evidence/2026-10-16_traditional_perception_dev_r1/RESULTS_FINAL.md)/[最终报告](evidence/2026-10-16_traditional_perception_dev_r1/FINAL_REPORT.md)/[回传](returns/REPLAY-FRESH-NEXT-01.md)。同页“人物高亮”默认关，开启默认新架构XY，可选3D/原版及参考空场；真实源点→证据→聚类→人体准入→互斥身份→姿态→候选事件→颜色/审计整链接通。主会话291/295认领、140帧低姿、确认身份始终#1；111738固定旧配平162→0、**页面实际配平42→0**，两者分列；221808匹配空场0/272；24组最终v2 overflow均0。R1曾由overflow造成假0，结论撤回并保留R2 152/186失败；3D未胜过XY、低姿起始两段少13/5、错参考下XY仅163/295均保留。19套回归exit0（含Python45），19引擎边界组含门限隔离宽家具反例；15会话30原SHA和保护源不变。OpenCode实际Go Flash只读R1 REVISE返工→R2/R3/R4 REVIEW_PASS、后3轮exit0，最终两P2闭合，见[完整审查](evidence/2026-10-16_traditional_perception_dev_r1/REVIEW_FINAL.md)。站/躺/起和空场实图齐；页面计算/着色CPU P95约25ms、JS堆约1.1GB（不含GPU，不代表板端）。FN06/FN07语义GT BLOCKED，AD08真实跌倒/跨场景/设备物理/EXE部署NOT_RUN；未宣称产品或工单ACCEPTED。无数据/GT/板端/驱动网络/模型写入、训练、采集部署或Git写；不接管HF/GL与公开数据学习并行项。技能ponytail实际路径为 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。

## 2026-10-16 HFUS-INDOOR-DATA-QUAL-01 OD1 数据契约与人工审核资格（R1 SUBMITTED；人审 BLOCKED）

用户「现在深度学习继续开发」派发上一单审后包。ND02 **闭合**：末列=绕+Z yaw（度）、z=几何中心、GT 无实例ID 列——作者 commit `275989e` 多读取器/已入库预测件五路一致 + 本地 526 框 PCA/值域/相邻帧持久性物理实测互证（[解释注册表](evidence/2026-10-16_hfus_indoor_data_qual_r1/INTERPRETATION_R1.json)/[几何实测](evidence/2026-10-16_hfus_indoor_data_qual_r1/ROTATION_GEOMETRY_R1.json)/[结论](evidence/2026-10-16_hfus_indoor_data_qual_r1/ND02_CONCLUSION.md)）；撤回上一轮“49 实例ID”读数；作者侧导出器未入库、`crane_dataset` ≥8 数值 bug、度/弧度口径矛盾均保留不掩盖。ND04 **BLOCKED**：三 ZIP 全量 SHA 重核=冻结；精确重复 2 组、track 3 时间簇入册，作者无录制元数据→可信独立采集组 0、拟 test 0。ND03/ND06：冻结 24 帧审核队列（规则预注册）+ 本地审核台交付（旋转后 GT 三栏、每框必填判定/理由、完备性三态、追加式哈希链账本，入口 `sidequests/hfus_indoor_ai_test/qual_r01/start_qual.bat`）；真实人工审核 0 条待用户实审，ND05 P/N/U 计数随人审产生。训练 0、E1/HR09 未解锁、无设备/采集/部署/整包解压；唯一判据 ND01–ND08 见[回传 R1](returns/HFUS-INDOOR-DATA-QUAL-01.md)。本条不接管其他主线。

## 2026-10-16 REPLAY-FRESH-01 会话回放「人物高亮」开关（SUBMITTED）

用户直派「设计一个开关，放在回放工具条，叫"人物高亮"。开启后从头播放，显示背景渐黑、人物高亮和低姿续接；关闭后恢复原始着色」，并以「继续开发」授权收口整段核对。实现为工具条显式开关 `#highlightSwitch`：开 → 保留 `sid` 重载并**从 f0 逐帧重建时序**（中途开启不漏人物身份）、背景渐黑 + 认领人形亮白/亮蓝 + 低姿续接；关 → 同一会话原样回到原始 LUT 着色。高亮层复用 sidequest `fresh_map` 的站姿/低姿算法与既有 `HUMAN_DETECT_OVERLAY` 单钩子（`fresh_map_lib.js`/`fresh_overlay.js`/`fresh_view.js`，`replay.js` 仅 +2 行传配平 R/T），不新增第二条着色管线；高亮期间隐藏原人检按钮、停用原始着色菜单，避免两套颜色互相覆盖，参考未就绪/失败明确报「人物高亮未启用」不冒充成功。整段核对：主线 `cap_20261013_082623` 295 帧，291/295 帧有认领着色，**低姿续接 140 帧（f109–f252）**，锚点连续计数 c19→c293 无 reset、相邻帧身份跳变 0 次；站（z≈1.05）→ 倒（z≈0.36）→ 起（z≈1.08）三态截图齐；换会话切到 272 帧空场后旧身份清空、空场 f31–f90 `claim_hot=0 claim_cool=0`。14 个 JS 套件 + Python 45 tests 全 exit 0。NOT_RUN：设备/物理/真实跌倒语义、EXE 重打包与部署（未授权）、独立复审；关态截图沿用 R1（本轮浏览器截图因桌面窗口不可见失败）。旧有空场误认领不隐藏、未宣称人体 GT。无 commit/push/reset/部署/采集，未写 `data/`。见[唯一验收 RF01–RF08](evidence/2026-10-16_replay_fresh_switch_r1/ACCEPTANCE_V1.md)/[R2 核对与收口](evidence/2026-10-16_replay_fresh_switch_r2/README.md)/[开关两态与换会话实测](evidence/2026-10-16_replay_fresh_switch_r2/switch_states.md)/[回传](returns/REPLAY-FRESH-01.md)。技能 ponytail（skill 工具，full）。

## 2026-10-15 HFUS-MARKOV-EXPERIMENT-01 离线马尔可夫时序实验（SUBMITTED；语义效果BLOCKED）

用户附件直接授权独立侧链，Codex唯一代码writer，论文/测试子代理只读。当前[唯一M01–M12验收v1](evidence/2026-10-15_hfus_markov_r01/ACCEPTANCE_V1.md)/[逐项结果](evidence/2026-10-15_hfus_markov_r01/RESULTS.md)/[最终报告](../../sidequests/human_fusion_lab_next/temporal_markov_r01/FINAL_REPORT.md)/[回传](returns/HFUS-MARKOV-EXPERIMENT-01.md)。1934动作+90空场复用冻结E0 G0候选/关联并重提几何/真dt/原RF；EMA/投票/滞回/保持/MC/presence-posture-event HMM/Forward-Viterbi/显式秒持续HSMM、同帧本地Demo实际运行。真实RF二值0切换，无人体稳定性增益可证；姿态单帧53→Forward26/Viterbi30仅描述；真实候选0。10单测/35交付检查/九会话时序重算相等、浏览器与只读审查完成；282核心+66第二人未审、K=0，语义P/R/F1及真实延迟BLOCKED/UNKNOWN。PC HMM均值0.070ms、HSMM2.451ms，非板端速度。入口http://127.0.0.1:8947/（启动方式见侧链README）。原数据/GT/模型/生产源码保持，无训练、E1/HR09、部署采集、Git写；不接管其他主线。详细输入输出/代码SHA见DELIVERY_MANIFEST.json。

## 2026-10-15 REPLAY-MEASURE-01 会话回放「测点距离」工具（SUBMITTED）

用户直派「给总控会话回放加一个测点距离的工具」。口径：升级 HR-04 既有的 `M` 三态标尺，**不新造一套**——原来它只把光标投到地面 `z=0` 两点量平面距离且是隐藏快捷键，现改为**取点云真点（3D）**并加可见「测距」按钮 + 画布点击取点（点到地面空处自动退化成原地面标尺），量身高/任意两点/地面距离走同一条路径。5 文件：`human_replay_lib.js` 新增纯函数 `measure_point_from(pick, ground)`（点云点→地面→null，+1 单测）；`replay.js` `measure_pick` 用既有 `pick_point_on_ray(…,0.5)` + `ray_ground_intersect` 取点、`measure_step(cx,cy)` 报 3D/水平/高差/两端坐标、距离标签改挂 3D 中点、新增 `bind_measure_click`（按下→抬起 >4px 的拖动不算取点；测距开启时点击不拖参照人形）、按钮绑定、换会话清尺；`index.html`/`human_track.html` 各加 `#measureBtn`（该 id 缺失先被既有 `human_track_static.test.js` R2 契约抓出）；`human_replay_lib.test.js` +1 用例。自验：`human_replay_lib` **46 passed**、`human_track_static` ALL PASS（修前 FAIL missing:measureBtn）、`panel`/`human_detect_lib` 11/`human_pipe_lib` 38/`session_selection` 12/`detect_overlay`/`rf_person`/`gt_lib` 29/`gt_live` 15/`gt_workbench_ops` 12/`registration`、`sessions_test` 7、console `console_html` 21 + `console_test` 7 全 exit 0；`gt_roundtrip` exit 1 为既有（缺 `cap_20261010_180751`，与本轮无关）。未改服务端/`panel.js`/数据/板端/算法/模型/GT。NOT_RUN：浏览器实录（M03/M05）、exe 内嵌副本重打（检查发现另一个并行写入者的 `PyInstaller Console.spec` 仍在跑，共用 `build/`+`dist/`，本轮不叠加第二次构建；本机桌面控制台本就靠 `dist/console_passthrough.ini` 把回放源指到本仓源码目录 → SOURCE_BYPASS，重启即生效，不需要重打）；独立复审 NOT_RUN；无 commit/push/部署/采集。见[唯一验收M01–M07](evidence/2026-10-15_replay_measure_r1/ACCEPTANCE_V1.md)/[改动与限制](evidence/2026-10-15_replay_measure_r1/README.md)/[回传](returns/REPLAY-MEASURE-01.md)。技能 ponytail（skill 工具，full）。

## 2026-10-15 HFUS-INDOOR-AI-TEST-01 独立公开数据实验计划（SUBMITTED，未实施）

用户要求完整开发计划、分阶段AI提示词、开发后OpenCode审查及再制定下一阶段计划。当前[计划包索引](evidence/2026-10-15_hfus_indoor_ai_plan_r1/CURRENT.md)/[完整计划V2](evidence/2026-10-15_hfus_indoor_ai_plan_r1/DEVELOPMENT_PLAN_V2.md)/[唯一拟实施验收A01–A16 V2](evidence/2026-10-15_hfus_indoor_ai_plan_r1/ACCEPTANCE_V2.md)/[AI阶段提示词](evidence/2026-10-15_hfus_indoor_ai_plan_r1/AI_STAGE_PROMPTS_V2.md)/[必读实施补充](evidence/2026-10-15_hfus_indoor_ai_plan_r1/IMPLEMENTATION_ADDENDUM_V1.md)/[回传](returns/HFUS-INDOOR-AI-TEST-01.md)。OpenCode指定Go Flash只读计划审查R1 PLAN_REVISE→R2 PLAN_PASS，无P0/P1；四项P3按来源分母/track成员SHA/旋转辅助指标门/匹配平局规则已纳入实施补充。当前仅计划交付，无新训练、检测指标或Demo；A01–A16实施NOT_RUN，非开发后验收。路线：真实点云GT首屏→几何基线→可信分组/监督→CPU新RF与PointNet→完整评价和错误Demo→开发后OpenCode审查/返工→按真实结果制定下一阶段计划，不自动实施下一阶段。独立sidequest，不解锁HFUS E1/本地逐点GT门，不覆盖旧权重/R1/生产，不采集部署/Git写；不接管其他主线。

## 2026-10-15 HFUS-LEARN-DEV-03 E0本机交付（SUBMITTED；学习目标BLOCKED）

用户实际派发v3并要求收尾，当前仅E0。[唯一L01–L18验收v3](evidence/2026-10-15_hfus_learn_stage_plan_r1/ACCEPTANCE_V3.md)/[结果](evidence/2026-10-15_hfus_learn_dev_r2/RESULTS.md)/[报告](evidence/2026-10-15_hfus_learn_dev_r2/FINAL_REPORT.md)/[回传](returns/HFUS-LEARN-DEV-03.md)。18原始源SHA重核，1934动作+90空场的4几何流两次新目录重算，82984数组/8096JSON无数值差异；G1退步不晋级，旧R1默认/页面字节/模型/GT/数据/并行用户差异保留。同应用版本路由/474队列/标注/原28B查询及原console入口交付；可信K0、282核心与66第二人工未做，E1未授权，36学习作业BLOCKED/15学习与压力流NOT_RUN，无主学习权重/语义准确率。源码与另名候选EXE scoped学习页检查exit0、浏览器PASS；完整console启动均FAIL（real_fall replay did not start），交互EXE NOT_RUN，候选壳版本与当前并行归档布局分列，不覆盖旧EXE。OpenCode最终AI只读R3 READONLY_NO_NEW_DEFECT，非独立实验/人审；逐条PASS/FAIL/BLOCKED见结果，工单非ACCEPTED。数据只读，无训练/下载/HR09/采集部署/驱动网络/Git写；此条不接管并行HC或其他主线。

## 2026-10-15 HC-JOINT-LOCAL-01 R8 相机预览同步落盘（camera.mjpeg + 逐帧索引）

用户连问「这些数据都看不了吗 / 视频看不了 / 视频文件帮我拉下来」并选择「给联合录制加相机写盘」。只读核对：三个联合会话（`joint_cap_20261015_111738/142227/142730`）`camera.mjpeg` 恒 0B；板端 `http://192.168.31.58:8081` 只有 `/stream`（实时 MJPEG）、`/snapshot`、`/status`，其余路由 404，**无录像/历史** → 那两次录制的相机画面从未被保存（现行错峰模式相机仅预览不写盘）。实现（PC 侧 4 文件，零新依赖）：`Recorder._camera_preview_only` 录制中把预览帧逐条写进会话 `camera.mjpeg` 并记 `camera_frames.jsonl`（offset/length/主机接收时刻，非硬件同步仅作索引）；停板后 `stop_event.set()`+`join` 先关文件再组装；`joint.json` 增 `camera_frames`；新增 `GET /api/camera?sid=`（流式回放，sid 白名单，越权→404）；联合页新增「相机录制回看」逐帧播放/拖动面板，文案与 README 同步。自验：`joint_capture_test` **10 PASS**（+2）、`console_html` **17**、`console_test` **7** 全 exit 0，联合页 JS 语法检查过。NOT_RUN：真机端到端（重打+重启+设备）、`human_replay` 回放器内嵌同屏显示；回看只对最近一次联合会话，相机与雷达无硬件同步。**EXE 未由本轮重打**，但 R7 并行流 14:50/14:57 两次重打已把本改动带入冻结 Console.exe（R7 的 FILE_SHAS/TESTS 早于本改动，已过期，需重生成）。见[唯一v1](evidence/2026-10-15_hc_joint_local_r8/ACCEPTANCE_V1.md)/[证据与限制](evidence/2026-10-15_hc_joint_local_r8/README.md)/[回传](returns/HC-JOINT-LOCAL-01.md)。SUBMITTED未ACCEPTED，独审NOT_RUN；未改板端/驱动/fetch/数据格式/模型/GT/`human_replay`，无 commit/push/部署/采集。技能 ponytail（skill 工具，full）。

## 2026-10-15 CONSOLE-GROUP-DB-01 R2 首页「归档」区（现在用不到的算法页收起）

用户续派「现在用不到的算法可以归档」：口径为**首页收纳**——7 项研究/算法页（算法验证/人体识别/人检锁定/骨架与倒地检测/真人倒地回放/小目标跟踪/逐源标注与学习对照）加 `archived` 标记，收进启动页最下面「归档」区，默认折叠、点标题展开收起，页面/URL/代码/exe 内嵌副本一个不少、零删除；`APPS` 索引与联合录制 `?sid` 契约不变。`console_html` **20**（+1 归档用例，分栏用例改口径）/`console_test` 7/`joint_capture` 10/`sessions` 7 全 exit 0；重打 `Console.exe` 193,818,509B/`6C9C65E4…`、`LiDAR_Console.zip` 151,052,851B/`25ACD3EC…` 并重启，冻结壳页 17,290B 含归档区（`archived:true`×7）。真机点标题与「真归档」（移出 exe/仓库）NOT_RUN；归档默认集合为判断项，增删一处 `archived:true` 即可。见[唯一v1](evidence/2026-10-15_hc_console_groups_db_r2/ACCEPTANCE_V1.md)/[证据](evidence/2026-10-15_hc_console_groups_db_r2/README.md)/[回传](returns/CONSOLE-GROUP-DB-01.md)。SUBMITTED未ACCEPTED；零删除、无 commit/push/部署/采集。

## 2026-10-15 CONSOLE-GROUP-DB-01 总控制台首页分栏归类 + 会话数据库模块（含分级删除）

用户直派「把这些模块收纳归类，再加入一个数据库模块支持删除功能」；两处决定经用户选择：数据库=会话库总表+分级删除，归类=分栏分组标题。`console.html` APPS 加 `group` 并按 `GROUPS`（采集录制/回放与标注/检测与研究/板端与平台/数据管理）分栏渲染 + 新增「会话数据库」卡片（`APPS[0]` 仍是会话回放，联合录制 `?sid` 契约不变）；`human_replay_lib.py` 新增只读 `GET /api/manifest`（本机逐文件 name+bytes+sha256 + 板端登记行，sid 白名单）；新页 `sessions_db.html`（总表+总览+清单/删本机/删板端/删两侧）。删除纪律沿用 2026-10-14：先清单→弹窗写明→人工确认→才 `POST /api/delete`（既有接口未改）。`console_html` 19 / `console_test` 7 / `sessions` 7 / `joint_capture` 10 / `fetch_lib` 13 全 exit 0；真数据+真板只读端到端：数据库页 200、`/api/manifest` 出 points.bin 237,644,764B 且 sha256 与独立计算逐位一致；重打 `Console.exe` 193,819,286B/`33D53CF5…`、`LiDAR_Console.zip` 151,051,879B/`E2D0BD89…` 并重启，冻结壳页含分栏与数据库卡片、冻结回放服务清单接口可用。真机点击与**真实删除**未跑（现场零删除）；不含 `data/leveled|registration|downloads`；独审 NOT_RUN。见[唯一v1](evidence/2026-10-15_hc_console_groups_db_r1/ACCEPTANCE_V1.md)/[证据](evidence/2026-10-15_hc_console_groups_db_r1/README.md)/[回传](returns/CONSOLE-GROUP-DB-01.md)。SUBMITTED未ACCEPTED；未改板端/fetch/joint_capture/模型/GT，无 commit/push/部署/采集。技能 ponytail（skill 工具，full）。

## 2026-10-15 HC-JOINT-LOCAL-01 R7 联合录制雷达被拉两遍（同数据两名）根因修复

用户直派「雷达数据会被拉两遍但是名字不一样」并贴出面板两行（同帧同长）。根因即 R6 记录级 A6：联合拉回落 `output_root/joint_<sid>/`，板端登记与回页面板都按 `local.get(sid)` 找本机副本 → 板端行判「本地无」→ 点行 `/api/sync` 再拉一份 `captures/remote/<sid>/`（现场 142730 两份 237,644,764B、111738 两份 255,522,036B；真板 `download_requested=true` 指认第二份来自面板点击）。修复：会话目录名 = 板端 sid（与面板同键，sync 短路天然命中）+ sid 白名单守卫 + 文案/README/示例同步，`human_replay` 零改动。面板对照（隔离临时根 + 真板只读 GET）改名前两行、改名后一行 `local=true`；`joint_capture_test` 8 / `console_html` 17 / `console_test` 7 全 exit 0。EXE/ZIP 已重打（`Console.exe` 193,812,397B / `LiDAR_Console.zip` 151,042,810B，冻结 `--check-joint-capture` exit 0）并 15:02 重启总控制台：运行中 exe 内 R7+R8 代码行为可观测（`/api/camera` 会话专属 404 vs 通用 `not found`）。真机改后新录一段 NOT_RUN（现场验收）、现场 3 组重名副本 BLOCKED 待用户确认处置。见[唯一v1](evidence/2026-10-15_hc_joint_local_r7/ACCEPTANCE_V1.md)/[根因与限制](evidence/2026-10-15_hc_joint_local_r7/README.md)/[回传](returns/HC-JOINT-LOCAL-01.md)。SUBMITTED未ACCEPTED，独审NOT_RUN；未改板端/驱动/fetch/数据格式/模型/GT，无 commit/push/部署/采集。技能 ponytail（skill 工具，full）。

## 2026-10-15 HFUS-LEARN-PLAN-03 学习前端大阶段计划（仅计划，SUBMITTED）

用户要求制定下一大阶段及AI开发提示词并交OpenCode审查。本轮仅计划/18源预检/只读审查，无开发训练。当前[计划V3](evidence/2026-10-15_hfus_learn_stage_plan_r1/DEVELOPMENT_PLAN_V3.md)/[唯一拟实施L01–L18验收V3](evidence/2026-10-15_hfus_learn_stage_plan_r1/ACCEPTANCE_V3.md)/[开发提示词V3](evidence/2026-10-15_hfus_learn_stage_plan_r1/AI_DEVELOPMENT_PROMPT_V3.md)/[最终审查与SHA](evidence/2026-10-15_hfus_learn_stage_plan_r1/PLAN_REVIEW.md)/[回传](returns/HFUS-LEARN-PLAN-03.md)。OpenCode R1 PLAN_REVISE→R2/V3最终PLAN_PASS，非ACCEPTED/非训练授权。10工作包含474队列项（282人工+192建议）、三族学习/场景实例/结构与因果时序、36作业上限30h/资源门、全1934+90对照与同应用版本页面。OOF与最终比较分表，旧N/Q/默认R1/GT/模型/数据/用户差异保留；未来须用户实际派发才做E0，E1须另外明确有界训练授权和可信标签门，不自动ML/HR09/下载安装/设备采集部署/Git写。本条不接管其他主线。

## 2026-10-15 HFUS-DEEP-RD-02 学习/距离图新路线研究（SUBMITTED）

用户本轮要求深化聚类/机器学习/二维深度图并尝试。本轮仅新离线研究原型，唯一[Q01–Q07验收v1](evidence/2026-10-15_hfus_deep_routes_r1/ACCEPTANCE_V1.md)/[结果](evidence/2026-10-15_hfus_deep_routes_r1/RESULTS.md)/[报告](evidence/2026-10-15_hfus_deep_routes_r1/FINAL_REPORT.md)/[回传](returns/HFUS-DEEP-RD-02.md)。18原SHA重核；148固定诊断帧、四链592组帧、三类三分辨率投影及轴深度CSR、冻结小模型CPU推理580次核对完成；共同分母/裁外/稀疏性/方向合成边界另表。几何/人体收益未获足够证据，不从窗口晋级；学习语义/实例与3D—距离图互补是待验证方向。源码单writer停写，AI只读两轮审查非独立实验；旧N表/默认R1/模型/原数据/用户差异保留，无新服务/训练/新大模型下载/HR09/设备采集部署/Git写。语义/关节与高级模型推理、板端/物理/泛化NOT_RUN/BLOCKED，不接管其他主线。

## 2026-10-15 HFUS-NEXT-DEV-01 本机离线全量开发交付（SUBMITTED）

当前授权仅用户HFUS-NEXT-DEV-01本机离线范围；唯一[验收v2](evidence/2026-10-14_hfus_next_development_plan_r1/ACCEPTANCE_V2.md)不改。当前[RESULTS](evidence/2026-10-15_hfus_next_dev_r1/RESULTS.md)/[报告](evidence/2026-10-15_hfus_next_dev_r1/FINAL_REPORT.md)/[回传](returns/HFUS-NEXT-DEV-01.md)。1934动作+90新留出全原字节、A/B/B_tau/C/D和时序单因素、原页/源字节/缺源/UNKNOWN已交付；新空场残余-89.83%，动作前景+69.27%，三条件图均非退化FAIL，NO_GEOMETRIC_WINNER。事件r2两受控慢降仅后验几何候选，非真实跌倒TP。独立AI只读全表/定向复审留证，原R1默认/旧输出/用户差异保留；N08语义与关节、旧原空场/CAL、反射证据BLOCKED，N09完整EXE启动real_fall失败且新功能NOT_RUN，N11板端/物理/部署/泛化/默认晋级NOT_RUN。单writer已停源码写入；无数据写/清理、Git写、训练/HR-09、设备采集部署、驱动网络改动，不接管其他工单。

## 2026-10-14 HFUS-NEXT-PLAN-01 算法借鉴与下一阶段计划（仅计划）

用户要求借鉴算法/架构、比较效果并制定下一阶段计划。本轮九会话18原文件SHA/帧数/28B尺寸预检PASS，八动作1934帧+新空场272帧，两背景artifact可读。当前[计划v2](evidence/2026-10-14_hfus_next_development_plan_r1/DEVELOPMENT_PLAN_V2.md)/[唯一验收v2](evidence/2026-10-14_hfus_next_development_plan_r1/ACCEPTANCE_V2.md)/[计划审核](evidence/2026-10-14_hfus_next_development_plan_r1/PLAN_REVIEW.md)/[回传](returns/HFUS-NEXT-PLAN-01.md)。V1 PLAN_REVISE→V2 PLAN_PASS，仅设计SUBMITTED；实现NOT_RUN、语义/关节GT BLOCKED。背景A/B/B_tau、条件图C/D、因果骨架/事件、固定960/974会话组和U/K/X语义分母；本工单算法单writer，其他线路只读并行。本条不接管旧工单，不启动实现/训练/HR-09/默认晋级或设备采集部署/Git写，原数据和旧产物只读保留，旧131958仍缺失。

## 2026-10-14 HC-DOWNLOAD-LIMIT-01 板端直下限速 70000→800000

用户口述"改限速"（源于"本机从 3588 拉数据是不是也非常快"）。实测板端 HC 网页直下 374.2 MB 需 42.8 s（8.75 MB/s）而链路裸 TCP 849 Mbps、ssh 86.8 MB/s；根因是 `capture_server.py` 文件路由的 `download_limit_kbit` 限速器——板端 `capture.yaml` 是 2026-10-02 旧版**缺该键**，落回代码默认 `70000`（70 Mbps，百兆时代给实时预览留余量用），数值与实测一字不差。板端加 `download_limit_kbit: 800000`（备份 `capture.yaml.bak-20261014`）并按 `/home/wel/BOOTSTRAP.md` §6 原命令重启容器内服务（PID 3578→26094，日志已备份）；仓库 `src/human_capture/config/capture.yaml` 同步，`pc_apps/human_replay/config.py`/`fetch.py` 仅改注释旧值。结果 3.77 s / 99.6 MB/s（11.4×），落地 sha256 与本机副本一致，45+13 项测试 PASS；取 800000 而非 0 是为给并存实时流（bridge ~93 Mbit + 预览 ~17 Mbit）留 ~200 Mbit 余量（0 实测 118 MB/s）。DL01–DL05 PASS；真实 `fetch.py --sid` 端到端、并发丢帧、实际回滚 NOT_RUN。未改板端源码/会话数据，未 commit/push。见[验收v1](evidence/2026-10-14_hc_download_limit_r1/ACCEPTANCE_V1.md)/[测量](evidence/2026-10-14_hc_download_limit_r1/BENCHMARK.json)/[回传](returns/HC-DOWNLOAD-LIMIT-01.md)。

## 2026-10-14 HFUS-SCENE-SOURCE-EMPTY-03 原始动作恢复与新空场诊断

八段动作原文件1934帧重新回放等价PASS；新空场cap_20261014_221808另建诊断背景，91 FIT/91 CAL/90 HOLDOUT，残余110492→11240点且0新增簇，容差仍约5.5cm。46动作帧候选点保留98.51%–100%，非人体召回；新背景全量因果与语义审核NOT_RUN，不晋级默认。页面原字节恢复状态/真实源行查询及旧空场缺失分支Edge PASS。旧cap131958两份原文件仍缺失；历史输出不覆盖。当前[验收v1](evidence/2026-10-14_hfus_scene_source_empty_r1/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hfus_scene_source_empty_r1/FINAL_REPORT.md)，SUBMITTED。无Git写、训练、采集、部署，后续仅只读原数据。

## 2026-10-14 REPLAY-LIST-INTEGRITY-01 会话回放列表数据完整性

用户直派：把会话回放里消失的数据删掉，以后只展示 3588 和本机真有数据的会话。实测板端 36 行登记里只有 10 行两端有文件（26 行是 FIFO 墓碑：22 行 `purged` + 4 行 `transferred` 但文件也没了）。`human_replay_lib.py` 新增 `_board_files_present`（HEAD meta/points，不下正文；板不可达不判缺失）并在 `/api/sessions` 过滤两端都无数据的行 + 返回 `hidden` 计数，`_local_sessions` 增加 stride 尺寸一致性检查（半写/截断不算本机有）；`panel.js` 状态行显示「已隐藏 N 条无数据登记」。按用户指示用既有 `DELETE /api/v1/sessions/<sid>` 清掉那 26 行墓碑（删前整份行数据+探针证据存 `captures/deleted_board_registry_20261014.json`，每行 `removed: []` 证明未删任何文件），板端登记 36 → 10 行；本机有副本的 8 行墓碑保留。验证：真板列表 10 行 `hidden:{0,0}`、`sessions_test.py` 5 项（含新 `IntegrityFilterTest`）、`panel.test.js`、`human_replay_lib.test.js` 45 项、`console_test.py` 7 项 PASS，全量 92 项仅既有 `leveling_auto_test` 缺旧数据 1 ERROR。未改板端源码/EXE/数据文件；重启总控制台生效（源码旁路）。见[证据](evidence/2026-10-14_replay_list_integrity_r1/README.md)。

## 2026-10-14 DATA-ROOT-JUNCTION-01 数据目录与 AI 工作区分离

用户直派：总控制台引用的数据和下载的数据要放单独的项目数据文件夹，与 AI 搞得数据分开防止误删。数据本体迁至 `D:\Code\ldiar\data\`（`sessions`/`leveled`/`registration`/`downloads`），仓库内 `captures\remote|leveled|registration` 改为指向它的目录联接，代码与 EXE 零改动、对外路径不变；`radar_sessions_8pack_2026-10-13` 8 段（16 文件 2,657,818,909 字节逐文件核对一致）已解压进 `sessions/`，压缩包按用户要求删除并释放 2.29 GB。console 7 项、human_replay sessions 4 项测试 PASS，冻结 EXE `--check-startup` replay/fall 起且 junction 读写实测通过；`真人倒地回放` 仍因原始 `cap_20261013_094333`/`131958` 缺失 NOT_RUN，legacy 九会话原始数据同样缺失（leveled 是配平变换后点云，不能替代）。`.gitignore` 加 `/data/`、AGENTS.md 加数据保护条。见[证据](evidence/2026-10-14_data_root_junction_r1/README.md)/[STATE](evidence/2026-10-14_data_root_junction_r1/STATE.json)，技能ponytail `C:/Users/30680/.config/opencode/skills/ponytail`。无 Git 写、无板端/部署/采集/生产改动。

## 2026-10-14 HFUS-SCENE-STATIC-02 活动区外锚点与全部新增簇

用户要求继续。原同页新增scene_static：活动区外参考锚点、双姿态背景过滤、全视野新增簇/PCA/高度/尺寸/源行、多色同屏与冻结观测；中央候选姿态限定，未知簇不套人体节点。原录制缺失，首次原始诊断失败保留；显式baseline_02 XYZ账本代理1966帧回归，原字节不报PASS、不重造录制。1934动作帧有中央候选，32空场目标/新增簇0；源行互斥、XYZ、背景/新增/小簇守恒及活动区锚点输入0自验PASS，Edge同页/UI返工PASS。当前[唯一v1](evidence/2026-10-14_hfus_scene_static_r4/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hfus_scene_static_r4/FINAL_REPORT.md)，SUBMITTED；18个meta/points字节及新CAL重标BLOCKED，完整人体/家具语义UNKNOWN，物理/独审NOT_RUN，不晋级R1默认。原core/actions/config、GT、模型和历史输出保持。localhost:8954同服务，未停8944等服务；无训练/采集/部署/Git写。实际技能路径见报告，不接管其他主线工单。

## 2026-10-14 HF-MAINLINE-POINTS-01 实施交付（原始源当前缺失，复跑BLOCKED）

用户明确授权计划v3实施、实验、原页面、1966帧回归、返工和OpenCode只读审核，覆盖下方旧“仅计划授权”。Codex单算法writer，加载ponytail与scientific-toolkit-skill。首轮6×1966及护栏2×1966源行/因果前缀验证完成；护栏最大中心偏移0.093991m、无新增轴缺测，但粗槽跳变仍退化，299975点次均UNKNOWN，无可信完整人体/纯度收益，不晋级R1默认。80帧明确REUSED_REGRESSION。最终浏览器检查发现captures/remote为空，18个主链meta/points文件当前缺失，原录制复跑及opaque查询BLOCKED，冻结页面/全量账本仍可用；不归因、不猜测替换。当前[唯一验收v2](../human_fall/evidence/2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V2.md)/[报告](../human_fall/evidence/2026-10-14_hf_mainline_points_r1/FINAL_REPORT_V2.md)/[交付索引](../human_fall/evidence/2026-10-14_hf_mainline_points_r1/CURRENT_DELIVERY_INDEX.md)，SUBMITTED，未ACCEPTED。页面http://[::1]:8944/（IPv4同端口另有PLANE服务，不停止其进程）。无训练、采集、部署、提交推送、旧GT或生产修改；物理/完整人体/晋级BLOCKED，独审结论独立登记。

## 2026-10-14 HFUS-SCENE-CHANGE-01 冻结场景新增点与抖动过滤

用户确认 D:/Code/ldiar 人体融合页，要求提取新进入点集并考虑传感器小幅抖动。原同一 pointset/r01 页面新增 scene_change 对照：局部背景平面、静态锚点小幅刚体补偿、双姿态冻结背景解释、当前三维候选；R1聚类参数保持。1934动作帧全部有目标候选，32空场留帧无目标；前景4945525→4791433，下降3.116%，不冒称家具污染率。1966帧源行/XYZ/粗节点/已匹配背景不因补偿晋升核验PASS，Edge九会话/跳帧/源行/切回旧方案PASS。首轮单姿态背景晋升及浏览器折叠文本读取失败保留。当前[唯一验收v1](evidence/2026-10-14_hfus_scene_change_r2/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hfus_scene_change_r2/FINAL_REPORT.md)，SUBMITTED；人体/家具完整身份UNKNOWN，物理/设备/独审NOT_RUN，不晋级R1默认或接管旧计划门。原核心/GT/录制/模型/历史输出保持，无训练/采集/部署/Git写。实际ponytail及scientific-toolkit-skill路径见报告。

## 2026-10-14 HF-MAINLINE-POINTS-01 下一阶段计划与OpenCode审核（仅计划授权）

用户明确要求多轮分析制定计划并交OpenCode审核，本轮未授权实现。Codex完成三轮分析，当前唯一[计划v3](../human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V3.md)及[上下文留出清单](../human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/CONTEXT_HOLDOUT_V2.json)；OpenCode CLI请求模型opencode-go/deepseek-v4.1-flash、plan agent、只读审核，v1 PLAN_REVISE → v2 PLAN_PASS → [v3最终PLAN_PASS](../human_fall/evidence/2026-10-14_hf_mainline_points_plan_r1/OPENCODE_REVIEW_V3.md)。原计划/原报告/失败日志保留。方向为上游逐点删点定位→有证据的保留规则→原8944页面固定候选→1934+32全帧回归；JS/Python口径、GT/proxy及家具未知分开。实施验收PR01–10/PR07a–c NOT_RUN，PR11/12 BLOCKED，R1默认保持；未修改算法/GT/源录制/服务/生产，未训练/采集/部署/提交推送/confirmed。实际ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。首轮外部读取权限受限、启动快照停滞及参数失败如实保留，后续仅本次CLI关闭snapshot并允许外部只读；无全局配置改动。保护范围首尾核验见READONLY_FINAL_CHECK，不冒称整树冻结。本条仅登记计划，不接管旧R3或M3′实施状态。

## 2026-10-14 HFUS-POINTSET-ACTIONS-02 R3 人体点集修复与粗骨架可观测性（当前入口）

用户明确授权完成本机离线研究/实现/1934+32全帧/8944同页浏览器验收，当前SUBMITTED，R3功能自验完成；R301核心保护范围PASS；首次383、后续5418其他路径缺失，用户已确认同期有其他清理/迁移，不宣称整树冻结，非ACCEPTED。Codex唯一writer，实际加载ponytail、scientific-toolkit-skill。A邻接图、B背景风险排除、C过去帧一致性及ABC消融，固定R1锚点与独立反馈tracker分开。R1默认保持，R2保留，新点仅当前FG原ROI、源行XYZ与UNKNOWN，13槽仅当前点支持；符号返工另2×1966帧，翻转9→4但新f124退化保留。身份/解剖精度UNKNOWN、晋级BLOCKED；独审/设备/物理NOT_RUN。原GT/录制/生产/旧输出不改，无采集/部署/训练/提交推送/confirmed。见[唯一v1](evidence/2026-10-14_hfus_pointset_actions_r3/ACCEPTANCE_V1.md)、[实验前诊断](evidence/2026-10-14_hfus_pointset_actions_r3/DIAGNOSIS_BEFORE_EXPERIMENT.md)。[FINAL_REPORT](evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md)。下方历史条目保留，不扩当前范围。

## 2026-10-14 HFUS-POINTSET-ACTIONS-01 R2 点集诊断/局部恢复/因果体轴（当前唯一入口）

用户授权继续本机离线研发，先检查人体完整性/背景混入，再做局部恢复与骨架。Codex唯一writer，实际读取ponytail、scientific-toolkit-skill；原pointset/r01页面，默认R1保持，新增action_research_r2五种实验对照。全1934+32帧重现、6方案11796帧源成员/当前节点支撑核验；轴实验缺测79→38，局部恢复有119/140/232新困难，均不晋级默认。人体完整率/家具污染率/解剖精度UNKNOWN；AI观察单独记录非人工GT，无训练/采集/部署/confirmed/Git写。实际Edge原页/控制台iframe与原EXE启动通过，原EXE/快捷方式不替换。当前[唯一v2](evidence/2026-10-14_hfus_pointset_actions_r2/ACCEPTANCE_V2.md)/[报告](evidence/2026-10-14_hfus_pointset_actions_r2/FINAL_REPORT.md)/[交付](evidence/2026-10-14_hfus_pointset_actions_r2/CURRENT_DELIVERY_INDEX.md)，SUBMITTED非ACCEPTED，独审/设备/物理NOT_RUN。旧v1/原数据/GT/模型/core/输出与历史证据只读保留。下方均历史，不扩本轮范围。

## 2026-10-14 HFUS-POINTSET-ACTIONS-01 八段中央人体与控制台（当前用户新授权）

用户指定复用pointset/r01和S1建模，助手自动研究中央人体，无用户审核前置，完成接入总控制台并总结优化。Codex唯一writer；[唯一v1](evidence/2026-10-14_hfus_pointset_actions_r1/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hfus_pointset_actions_r1/FINAL_REPORT.md)/[交付](evidence/2026-10-14_hfus_pointset_actions_r1/CURRENT_DELIVERY_INDEX.md)/[回传](returns/HFUS-POINTSET-ACTIONS-01.md)。旧core/旧output/原GT/模型不改，新增actions.py/config_actions.yaml/action_output；原页双数据集、默认中央候选，控制台新EXE Console_Pointset和桌面快捷方式，旧EXE/运行窗口保持。1934动作帧均有目标，32空场留帧0目标，两受控躺下候选15.135s/17.934s，79帧体轴歧义骨架UNKNOWN；源成员/节点全帧核验PASS。原空场三维距离口径、八段131958独立诊断背景与S1空间ROI区分，数值gate不是物理资格。软件自验/真实浏览器/冻结EXE启动PASS，未人工GT/解剖标定，真实跌倒准确率与物理/独审NOT_RUN，不ACCEPTED。无采集/部署/训练/Git写。下方停止集成为旧范围，本轮由用户具体离线控制台授权覆盖。

## 2026-10-14 HF-DATA-01 关联审阅修复（保留pointset r01）

当前HF-REAL三工单复用已完成pointset r01；8会话BOUND部分标签、S9 INVALID_BINDING、小ROI不扩展。原页增加PROPOSED最小队列/深链/当前选簇与GT上界区分，读/写实际源SHA和保存回调绑定修复。未训练/改旧GT/采集/部署/Git写。见[当前交付](../human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/CURRENT_DELIVERY_INDEX.md)与[人工队列](../human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/REVIEW_QUEUE.json)。原8941运行进程未重启，使用当前server.py --port 8942可看修复后入口；同一源码，无pointset r02。SUBMITTED/REVIEWED_WITH_FINDINGS，语义GT/生产BLOCKED，非ACCEPTED。下方既有未提交产物/入口保持。

## 2026-10-13 HFUS-POINTSET-01 S1空场与九会话三维点集合（当前独立入口）

用户明确统一标注/小活动区/冻结空场背景/独立聚类评分/考虑运动粘连/三维点集合/九会话动作框骨架；确认先做现有9段。Codex唯一writer，新隔离源sidequests/human_fusion_lab_next/pointset/r01。2605帧全跑，S1 FIT/CAL/HOLDOUT分开，101留帧0满足门限候选，直接XYZ PointNet+新XYZ-RF影子对照，自动/人工参照分开，部位选点格式与监督训练器。当前[回放8941](http://127.0.0.1:8941/)、[唯一v1](evidence/2026-10-13_hfus_pointset_01_r1/ACCEPTANCE_V1.md)、[报告](evidence/2026-10-13_hfus_pointset_01_r1/FINAL_REPORT.md)、[九会话目录](evidence/2026-10-13_hfus_pointset_01_r1/ACTION_CATALOG.md)、[回传](returns/HFUS-POINTSET-01.md)。SUBMITTED未ACCEPTED；纯人体/部位/关节精度及S9有效GT BLOCKED，小ROI不覆盖S8需核对；软件/浏览器自验PASS不是语义准确率。旧输入/GT/模型/生产只读，未启动原ML/HR-09或接管D05/HF-REAL，无部署采集Git写；独审/设备NOT_RUN。实际技能ponytail与scikit-learn，后续历史授权不扩大本轮范围。

## 2026-10-13 HC-JOINT-LOCAL-01 R2 相机超时返工（当前独立入口）

用户两次真实录制在4.312/5.219秒报timed out。本轮定位相机最后接收后约3秒触发读超时，新增本机相机有界重连和camera_events.jsonl，短暂断流雷达继续、持续12秒无帧仍报明确相机失败。断段完成状态completed_with_gaps，不当连续录制；初连失败/本机写失败不走网络重试。元数据完成写盘后才发布终态。9项联合测试、7项控制台、12项JS自验PASS；真实30秒899相机帧/139雷达帧未超时，但雷达已收区间缺号126，完整性仍未通过。见[R2验收v1](evidence/2026-10-13_hc_joint_local_r2/ACCEPTANCE_V1.md)、[报告](evidence/2026-10-13_hc_joint_local_r2/REPORT.md)、[回传](returns/HC-JOINT-LOCAL-01.md)。用户已关闭总控制台以替换EXE。板端相机源码/systemd只读检查，无服务配置/部署/驱动变更，旧会话和R1证据不改。SUBMITTED未ACCEPTED，独审NOT_RUN，不提交推送。

## 2026-10-13 HC-JOINT-LOCAL-01 总控制台本机双流录制（当前独立入口）

用户明确要求“在总控制台加一个usb和雷达同时录制的功能并且数据直接在本机不要放在3588”。Codex唯一writer，在pc_apps/console新增联合录制页和本机服务，复用既有8081 MJPEG与8765 Foxglove完整/innolidar_points；不调用板端录制接口、不创建板端数据文件。默认Windows本机captures/remote/cap_*_joint_*，可选择本机绝对路径；两路就绪再统一开始，手动/自动/关闭窗口停止并保存。保留MJPEG、完整原始雷达消息、28B兼容点云及逐帧接收时间索引。接收时间不是硬件同步；真实短录制发现雷达接收跨度与设备跨度不一致，时空标定及长期完整性未验收。见[唯一验收v1](evidence/2026-10-13_hc_joint_local_r1/ACCEPTANCE_V1.md)、[报告](evidence/2026-10-13_hc_joint_local_r1/REPORT.md)、[回传](returns/HC-JOINT-LOCAL-01.md)。SUBMITTED未ACCEPTED，独审NOT_RUN；不改板端服务/驱动/算法/模型/GT/旧会话，不commit/push。

## 2026-10-13 CAM-HOT R1 相机助手视觉场景建模与 f10 独立模态验证（当前独立入口）

用户明确"你可以让usb摄像头拍个照片借助你的视觉能力辅助判断并且进行场景建模"。利用板上既有 `systemd cam-mjpeg` 服务（2026-10-12 上线）的 `/stream` 路由抓 201 帧 (13.9 MB)。三帧 (CAM_F0000/0100/0200.jpg) 实时相机显示：中景人物左手提裙摆/袋，对应 r02 lidar f10 target 819 点（PERSON_LEFT_ARM_OBJECT）—— f10 大 bbox 的左下细长簇首次得到另一模态确认不是家具。scene_model.py 生成 9 个 camera/lidar anchors 与走廊几何（估计宽 1.7 m、左墙 y=1.0 / 右墙 y=2.7、尽头小桌凳 x=16-20 m 超出 IFW192S 15 m 量程），见 [场景模型](evidence/2026-10-13_cam_hot_r1/SCENE_MODEL.png)。相机与 lidar 093958 等历史 session 不同步，本单不 forge 相机证据；HF-REAL-02 RS04 FAIL 的关闭由指定独审在证据里决定，本单不代为收口。[证据目录](evidence/2026-10-13_cam_hot_r1/README.md)，[回传](returns/CAM-HOT.md)。 服务端口 8081 状态保持不变；未动 r01-r03 源码生产模型 GT captures；独审 / GT / 设备 / 部署 / 生产 NOT_RUN； 不 commit/push。

## 2026-10-12 HR-SKELETON-DEMO-01 真实点云粗骨架预览（当前独立入口）

当前交付：[可操作预览](http://127.0.0.1:8927/)，[报告](evidence/2026-10-12_hr_skeleton_demo_01_r1/FINAL_REPORT.md)，SD01–SD06工具自验PASS，SD07精度BLOCKED/设备NOT_RUN，SUBMITTED未ACCEPTED。

用户明确要求现在实现骨架标定给其查看。当前唯一验收 [SD v2](evidence/2026-10-12_hr_skeleton_demo_01_r1/ACCEPTANCE_V2.md)（v1失败保留）；隔离新源 sidequests/human_fusion_lab_next/skeleton_demo/r02/（r01保留），新证据同名r1，回传 returns/HR-SKELETON-DEMO-01.md。Codex唯一writer，实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。复用只读检测账与normalize/observe，对真实候选/已有人工人体点集分别作明确未标定的预览；参照模式不作为自动效果；不伪造人工可见性、不放行旧SKO/正式W04-W05，不启D06/D07/ML，不改生产/模型/GT/captures/旧证据，不部署采集或Git写。真人关节精度BLOCKED，设备NOT_RUN。下方历史入口不能扩大本次范围。

## 2026-10-12 HFUS-D05-R06 持续离线返工（当前唯一入口）

用户持续离线授权；唯一验收[R06 v1](evidence/2026-10-12_hfus_d05_r6/ACCEPTANCE_V1.md)，新源sidequests/human_fusion_lab_next/d05/r06/、新证据[R06](evidence/2026-10-12_hfus_d05_r6/)。主控唯一writer，原两代理/指定OpenCode只读。R05已完整[交付](evidence/2026-10-12_hfus_d05_r5/CURRENT_DELIVERY_INDEX.md)/[报告](evidence/2026-10-12_hfus_d05_r5/FINAL_REPORT.md)/[状态](evidence/2026-10-12_hfus_d05_r5/ACCEPTANCE_FINAL.json)，H4 FAIL不晋级，实际补审02 exit0/export0；[Demo8917](http://127.0.0.1:8917/)保留。R06只检验原半径外合法bank锚点修正，GT-free，无split/classifier/tracker联动改动；R06是D05返工编号，不启HFUS-D06/D07/ML/生产/GT模型变更，不部署采集或Git写。新轮未实跑；外部评测竞争时性能BLOCKED。实际九会话当前points.bin均由原loader按28B点记录读取，历史格式说明不可用来改冻输入；以下都是历史入口。

## 2026-10-12 HFUS-D05-R05 持续离线返工（当前入口）

用户持续离线授权及“继续”，主控唯一writer，两代理/OpenCode只读。唯一验收 [R05 v1](evidence/2026-10-12_hfus_d05_r5/ACCEPTANCE_V1.md)，新源码 `sidequests/human_fusion_lab_next/d05/r05/`，新证据 [R05](evidence/2026-10-12_hfus_d05_r5/)，D05 return追加。当前原bank已排除retained直接刷新，先纠正归因，再只比较合法bank锚点来自当前FG证明候选的单因素；不同时改tracker/分类/分离。R04审查包保留为control与当前可操作Demo，旧记录不覆盖。不启D06/D07/ML，不改生产/GT/模型/captures，不部署采集、驱动网络或Git写。算法/GT/生产未ACCEPTED，以下入口为历史。

## 2026-10-12 HFUS-D05 离线返工最终交付 V2（历史交付入口）

仅HUMAN-FUSION隔离离线范围，原D05及R02/R03/R04唯一ACCEPTANCE_V1不变。当前：[交付入口V2](evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX_V2.md)、[完整结果V2](evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT_V2.md)、[逐ID状态](evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_FINAL_V2.json)、[追加回传](returns/HFUS-D05.md)、[当前三窗Demo](http://127.0.0.1:8915/)。九会话合计2605帧，独审02真实exit0/export0完成；算法FAIL、GT/生产BLOCKED、未ACCEPTED。人工最小包仍V2，S9 INVALID_BINDING。旧报告/8914/失败记录均保留，以下入口为历史。

## 2026-10-12 HFUS-D05-R04 当前离线交付与持续返工授权

用户当前离线授权；唯一验收 [R04 v1](evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_V1.md)。当前操作入口 [CURRENT_DELIVERY_INDEX](evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX.md)，Demo v2 http://127.0.0.1:8915/ ，[最终报告](evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT.md)、[追加回传](returns/HFUS-D05.md)、[人工最小包V2](evidence/2026-10-12_hfus_d05_r4/MINIMAL_HUMAN_REVIEW_PACKAGE_V2.json)。R02/R03各按原冻结表保留FAIL/BLOCKED，R04等价性能优化全9场纯p95 PASS；算法目标仍FAIL，GT/生产BLOCKED，板端NOT_RUN，未ACCEPTED。主控唯一writer，独审只读，不动生产/模型/GT/旧证据，不部署采集/Git写/驱动网络/ML，不启D06/D07。下方旧入口仅历史。

## 2026-10-12 HFUS-D05-R04 当前持续离线返工授权

用户持续离线授权，Codex唯一writer。当前唯一验收 [R04 v1](evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_V1.md)，新代码 `sidequests/human_fusion_lab_next/d05/r04/`，证据 [R04](evidence/2026-10-12_hfus_d05_r4/)，D05 return追加。R03分类出现近距回退，不晋级；R04只做A06等价计算短路，R02/R03各按原表完整收口。冻结资产只读，不启D06/D07/ML，不改生产，不部署采集或Git写。以下入口为历史。

## 2026-10-12 HFUS-D05-R03 当前持续离线返工授权

用户当前直接授权的下一轮分类单因素返工，Codex唯一writer。唯一验收 [R03 v1](evidence/2026-10-12_hfus_d05_r3/ACCEPTANCE_V1.md)，新代码 `sidequests/human_fusion_lab_next/d05/r03/`，证据 [R03](evidence/2026-10-12_hfus_d05_r3/)，D05 return追加。R02按其冻结表收口，以下授权为历史。保留模型/GT/captures/原证据，不动生产，不部署采集，不启D06/D07/ML，不做Git写操作。算法和GT仍未ACCEPTED。

## 2026-10-11 HFUS-D05-R02 当前持续离线返工授权

用户明确授权先核查D05再逐轮离线返工；Codex唯一writer，两代理及OpenCode只读。当前唯一验收 [R02 v1](evidence/2026-10-11_hfus_d05_r2/ACCEPTANCE_V1.md)，新代码 `sidequests/human_fusion_lab_next/d05/r02/`，新证据 [R02](evidence/2026-10-11_hfus_d05_r2/)，回传追加 [HFUS-D05](returns/HFUS-D05.md)。保留D04 frozen与D05旧失败；不启动D06/D07，不动生产/模型/GT/captures/历史证据，不部署采集/ML激活/Git写操作。工程、算法、GT、生产分别裁定，未ACCEPTED。下面旧入口只作历史。

## 2026-10-11 HFUS-D01～D03 当前离线研发授权

用户明确启动三个子代理并行开发并持续集成/验证/OpenCode独审。本轮按[统一计划v2](HUMAN_FUSION_UNIFIED_PLAN.md)实施，主控已冻结独立开发验收：[D01 v1](HFUS_D01_ACCEPTANCE_V1.md)、[D02 v1](HFUS_D02_ACCEPTANCE_V1.md)、[D03 v1](HFUS_D03_ACCEPTANCE_V1.md)、[集成 v1](HFUS_INTEGRATION_ACCEPTANCE_V1.md)。唯一writer所有权：A=`sidequests/human_fusion_lab_next/contracts/`和`eval/`；B=`review/`；C=`background/`及其隔离引擎副本；主控=`integration/`、统一入口及共享索引。各自证据/return独占；冻结接口变更必须升版通知。

仅真实数据纯离线新代码/文档/证据。captures、原GT、历史证据、旧源码/模型只读；已有`human_fusion_lab_next/next/review/`纳入旧资产保护。本轮零部署/采集/生产/驱动/网络/模型替换/ML激活/提交推送，不使用历史授权。D04/D05依第一轮门判定、启动前另建版本验收与独立目录；D06主控一个实际组合，D07无人工区域证据只准备待审并BLOCKED。人工缺失不阻工程，语义保持BLOCKED/UNKNOWN。基线[BASELINE_BEFORE](evidence/2026-10-11_hfus_integration_r1/BASELINE_BEFORE.json)含12474文件、ignored/untracked、无读取错误或漂移。下方为历史入口，不授权新实施。

## 2026-10-11 HUMAN-FUSION-UNIFIED-PLAN 当前规划与审核授权

用户本轮明确“归一开发进度，根据总结制定修改优化开发的计划算法架构，多轮仔细制定完善，然后 opencode 审核”。Codex唯一文档writer，三轮事实/架构/反例归并；[统一计划](HUMAN_FUSION_UNIFIED_PLAN.md)、[唯一规划验收v1](HUMAN_FUSION_UNIFIED_PLAN_ACCEPTANCE.md)、[工单](tickets/HUMAN-FUSION-UNIFIED-PLAN.md)、[回传](returns/HUMAN-FUSION-UNIFIED-PLAN.md)、[证据](evidence/2026-10-11_human_fusion_unified_plan_r1/ROUND_01_RECONCILIATION.md)。OpenCode指定Go Flash只读审核，当前无生产writer。仅规划，不启动HFUS-D01～D07实施；保持旧生产/研究源、模型、GT、captures、旧证据只读，无部署/采集/提交推送/网络驱动变更/ML激活。三轮总结的B背景点率不作检测全链通过，S9草稿/预测/几何proxy不当真值。下方为历史入口，不授权新执行。

当前收口：**PLAN_READY / SUBMITTED，统一计划v2**。完整指定OpenCode只读审查真实exit0/READY，无阻断缺陷；多行CLI派审截断已实证纠正，旧不完整日志保留。见[最终收口](evidence/2026-10-11_human_fusion_unified_plan_r1/CLOSEOUT.md)/[完整独审](evidence/2026-10-11_human_fusion_unified_plan_r1/OPENCODE_REVIEW_03.md)。规划P01～P09已按职责闭合，DEV01与设备D01 NOT_RUN，DEV02/PHY01 BLOCKED；非算法或系统ACCEPTED。源码/模型/GT/captures未变，既有Chrome运行日志增长另列，未宣称整树SHA全冻结。

## 2026-10-11 HUMAN-FUSION-DEMO-V2 历史离线授权

用户直接纠偏：首交真实 Demo V2，再离线识别修复，再骨架可观测性。Codex 唯一 writer，基于 sidequests/human_fusion_lab Demo V1 新增 V2；[唯一验收表 v1](HUMAN_FUSION_DEMO_V2_ACCEPTANCE.md)、[回传](returns/HUMAN-FUSION-DEMO-V2.md)、[证据](evidence/2026-10-11_human_fusion_demo_v2_r1/)。主线/V1/R9及旧证据只读。用户尚未确认离线检测、骨架及姿态效果前，禁止板端部署、生产替换、现场发布。历史授权不能覆盖本轮禁止；不提交推送，不采集，不激活ML。

## 2026-10-11 HUMAN-R4-CANDIDATE-AUDIT 当前阶段

用户明确“继续啊下一个阶段的开发计划制定并且执行”。Codex唯一writer，按最近人体融合线完成本地离线候选归因开发：[当前计划](HUMAN_FUSION_NEXT_STAGE_PLAN.md)、[唯一验收v1](HUMAN_R4_CANDIDATE_AUDIT_ACCEPTANCE.md)、[回传](returns/HUMAN-R4-CANDIDATE-AUDIT.md)、[观察](evidence/2026-10-11_human_r4_candidate_audit_r1/REPORT.md)、[发现与后续](evidence/2026-10-11_human_r4_candidate_audit_r1/FINDINGS.md)。三会话v1/v2/v3九次全帧2400tick，core7套/FUSION16/GT契约/新映射检查通过，指定Go Flash只读独审无可复现功能缺陷；SUBMITTED/停写，未ACCEPTED。S6未标167帧UNKNOWN，传播观测不当独立样本，非空uncertain_intervals行为NOT_RUN。继承外部R3 Map实现，另[当前性能复验](evidence/2026-10-11_human_fusion_perf_r1/REPORT.md)/[唯一表](HUMAN_FUSION_PERF_R1_ACCEPTANCE.md)六会话两模型12/12通过，本轮未改engine或模型。R3文档仅作事实线索，本轮GT资格只再审S1/S3-near/S6；历史R2失败不回填。新增归因工具已处理GT compact→raw及A+B评分联合点集，已有engine公开索引缺口仍待后续工单。无训练/采集/部署/生产切换/commit/push/ML激活；模型与生产推广BLOCKED。

## 2026-10-10 HUMAN-UNIFY-FUSION-R1 / R2 离线收口

用户交接及后续确认授权F3/F4；Codex唯一writer，仅离线训练/评估。已SUBMITTED/停写，未ACCEPTED：[唯一验收表v1](HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md)、[最终报告](evidence/2026-10-10_human_unify_fusion_r2/FINAL_REPORT.md)、[回传](returns/HUMAN-UNIFY-FUSION-R1.md)。72完整运行及18组全帧同源对拍完成，指定Go Flash只读独审exit0。五判定：FUNCTIONAL PASS；GT_EVALUATION BLOCKED（当前7/9稳定GT，S1移走/S9测试污染与错误绑定）；PERFORMANCE FAIL（S3-far FUSION两版P95=53.46/53.40ms）；MODEL_PROMOTION BLOCKED（候选运动track召回回退，保留v1）；PRODUCTION_RELEASE BLOCKED。原模型/51维特征/生产算法SHA保持；外部human_replay_lib.py及GT改动保留，全树冻结S02 BLOCKED。无commit/push/deploy/采集/驱动/网络/ML激活。下方条目保持历史事实，不扩大本轮资格。

## 2026-10-10 本地分组提交审计

用户明确“分析一下哪些可以提交先提交了”。本轮仅收录已验证的 HTTP 下载/同步/改名与 Console 会话入口/独占端口软件修改；混合文件按功能拆分，其余算法、GT、研究与派生数据原样保留。[唯一验收表 v1](COMMIT_AUDIT_20261010_ACCEPTANCE.md)、[回传](returns/COMMIT-AUDIT-20261010.md)、[证据与暂留原因](evidence/2026-10-10_commit_audit_r1/README.md)。两组候选 Git 树的隔离回归均通过；不 push，不改变原工单资格；本轮设备/物理/部署/采集/候选 EXE 构建与启动 NOT_RUN。相关旧发布证据按原文归档，仅为历史记录。

## 2026-10-10 HUMAN-UNIFY-R1 返工当前授权

用户明确“帮我返工”：Codex唯一writer，修复[独立审核R01–R07](evidence/2026-10-10_human_unify_review_r1/CODEX_REVIEW.md)及直接相关的软件契约；[唯一验收表v1](HUMAN_UNIFY_R1_ACCEPTANCE.md)，[回传](returns/HUMAN-UNIFY-R1.md)，[当前收口](evidence/2026-10-10_human_unify_rework_r2/CLOSEOUT.md)。R01–R08功能修复两次指定Go Flash只读独审PASS；96测试、9会话1196帧对拍和最终45次来源矩阵完成，状态SUBMITTED/停写，未ACCEPTED。当前RF版本两次性能8/9 FAIL；范围外生产rf_person.js并发改写导致S02原全树冻结BLOCKED，变更保留且最终证据另按当前SHA重验。仅human_core离线实现及本工单文档，无本轮human_replay写入/commit/push/部署/采集/驱动/网络/模型切换；算法GT/生产资格BLOCKED。用户将自行重录九类会话，未当作已采集/GT。下方其他工单状态保留。

## 2026-10-10 RF 离线优化当前授权

2026-10-10 用户直派（会话入口集成与 EXE 更新，R2）：已备份并集成入口补丁，dist/Console.exe 与 ZIP 已真实重建更新；修复 Windows 共享端口混用旧服务问题，保留原服务。唯一当前验收表 [SESSION_SYNC_RELEASE_ACCEPTANCE.md](SESSION_SYNC_RELEASE_ACCEPTANCE.md)，回传 [returns/SESSION-SYNC-RELEASE.md](returns/SESSION-SYNC-RELEASE.md)，证据 [evidence/2026-10-10_session_sync_release_r2](evidence/2026-10-10_session_sync_release_r2)。状态 SUBMITTED；本机入口/发布自验通过，测试配平质量 failed: floor_not_found，不等于现场精度验收。

用户本轮明确暂停 HUMAN-FUSION-OFFLINE-R1，先执行 [RF-OPTIMIZATION-R1](tickets/RF-OPTIMIZATION-R1.md) 的 R1/R2；[唯一验收表 v1](RF_OPTIMIZATION_R1_ACCEPTANCE.md)。Codex 唯一 writer，仅新 evidence/workspace 离线研究，OpenCode Go Flash 只读独审。现有弱标签不构成新人/新家具泛化证据；R3/R4、生产、设备/物理/采集/部署均未启动，不激活 ML/HR-09。

当前[收口](evidence/2026-10-10_rf_optimization_r1/21_CLOSEOUT.md)：三路对照及两次实际独审完成，加固后4检查PASS/当前软件无FAIL；可用性与可靠困难样本/跨人跨景资格BLOCKED，未ACCEPTED。R3/R4保持NOT_RUN。[回传](returns/RF-OPTIMIZATION-R1.md)已追加复审结果，不覆盖旧证据。

# human_capture — 人体数据采集 / 回放 / 标注支线

> 新支线，独立于 HF/GL 工单体系。文档组织照搬 HF 的 milestone/ticket/证据习惯，
> 但本文是本方唯一计划入口。
>
> 创建：2026-10-02（Asia/Shanghai）。设计冻结：2026-10-02（用户两轮拍板后）。

2026-10-07 当前主线（R39-CLOSEOUT）：用户明确授权 W03 阶段A–F收口审计/诊断与统计返工；[当前工单](tickets/HR-W03-R39-CLOSEOUT.md)已自验 **SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**；[最终收口报告](evidence/2026-10-07_hrw03_r39_closeout/08_final_closeout.md)。31点=30 workspace crop+1 reference，语义UNKNOWN31；confirmation机械归因完成，非静态155行真人GT仍缺。gate保持49.652981%<50%，旧artifact历史DEGRADED；最小统计修复改变全文件SHA后当前loader STALE且SAFE=P。唯一验收表仍为 [R3.7 06_test_matrix.md v1](evidence/2026-10-07_hrw03_r37_productionization/06_test_matrix.md) 的T37/T38，T38-05/06、S4/S7 FAIL。W04–W09及registration R3.9 production未授权、未启动。下一步人工GT与gate支撑/契约审查，见[计划当前状态更新](HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md)及[逐点审阅页](evidence/2026-10-07_hrw03_r39_closeout/09_point_review.html)。以下同日R3.8及更早条目保留为历史。

2026-10-09 用户直派（exe 板端地址随新网络更新）：板子迁至新网络固定 `192.168.31.58` 后，`Console.exe` 两处板端地址由 `192.168.3.125` 更新为 `192.168.31.58`：`console.html`「板端 WebUI」卡片（:8090）与内嵌 `human_replay/config.py` 的 `BOARD_URL`（:8766）；`console_html.test.js` 断言同步。console node 10/python 4、node 回放各套全绿；human_replay python 46 项 45 OK、1 ERROR 为 `leveling_auto_test` 缺本机数据（环境缺失，与本改动无关）。`Console.exe` 与 `LiDAR_Console.zip` 已重建，内嵌副本离线抽取核验通过。证据：[2026-10-09_console_board_ip_update](evidence/2026-10-09_console_board_ip_update/README.md)。

2026-10-08 用户授权（采集 + 生产接入）：① 生产接入按 [HR-RET-V2 工单](tickets/HR-RET-V2.md) 启动，唯一验收表 v1 [HRRETV2_ACCEPTANCE.md](HRRETV2_ACCEPTANCE.md)；increment 1 已交付并自验 **PASS**——`human_pipe_lib.js` 新增融合删除能力函数 `extract_foreground_fused`（默认不被任何现有路径调用，P 路径逐位不变；37/37 + 45/45 + panel 全过）：[evidence/2026-10-08_hrretv2_r1](evidence/2026-10-08_hrretv2_r1/README.md)；increment 2（消费侧旗标/加载路径/浏览器节点验证）与独立复审待做。② 采集按 [CAPTURE_PROTOCOL_DRAFT.md](CAPTURE_PROTOCOL_DRAFT.md) 执行，但板端 2026-10-08 探测**不可达**（ping 100% 丢失、8766 超时）→ **BLOCKED**，待板端在线。③ 离线链路 P1（S-A+ 独立复核）/P2（融合 v2 A/B+端到端 11/11 PASS）/P3（采集协议）均完成，见 [HUMAN_RECOGNITION_REVIEW_AND_PLAN.md](HUMAN_RECOGNITION_REVIEW_AND_PLAN.md)。W03 自身状态不变（仍 REWORK_REQUIRED）；W04–W09 未启动。

2026-10-07（晚）用户直派（补充记录，不改变上方 W03 状态）：四段新录制会话（cap_20261007_215540/215607/215623/215643，同一人于 ≈(2.1,−0.5)、距 2.2m 站立/举手）已完成离线配平（auto；3 段 recommended=tls，215607 TLS−RANSAC d 差 3.69cm>3cm 按规范不推荐）并完成现行管线 P 路径逐帧人体对照 probe：[evidence/2026-10-07_new_sessions_person_probe_r1](evidence/2026-10-07_new_sessions_person_probe_r1/README.md)。结论：静立人被离线全帧静态图自建模并删除 ~97–98%（前景仅 14–57 点/帧，成簇也基本 NON_HUMAN、无 confirmed、无人/物粘连），"静立吞人"已知边界定量复现，非新 bug。随后按「静止模板」直派：空场会话 cap_20261007_233658 配平（job 3c793d7bda0f4ced86b20ac8076e7b0e，recommended=tls）+ 四段配准（3/4 WARN/DEGRADED，215607 因配平 conflict 被 LEVELING_SHA_MISMATCH 拒绝）+ 参考层保留率阶梯：参考层保留静立人 **97.4–98.0%**，叠加在线层后仍仅 **1.2–2.1%**（并集语义），空场自身 P 复验 0 candidate/0 confirmed；开发计划 [STILL_PERSON_RETENTION_PLAN.md](STILL_PERSON_RETENTION_PLAN.md)（阶段 0 完成；阶段 1 融合优先级规则草案 v1：[FUSION_PRIORITY_RULE_DRAFT.md](FUSION_PRIORITY_RULE_DRAFT.md)，实施需另行授权；人体语义分类层草案 v1：[HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md](HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md)，S-A 离线原型已跑：[evidence/2026-10-08_human_semantic_sa_r1](evidence/2026-10-08_human_semantic_sa_r1/README.md)（7 样本全过、空场 0 HUMAN，未接管线）；审查/分析/计划：[HUMAN_RECOGNITION_REVIEW_AND_PLAN.md](HUMAN_RECOGNITION_REVIEW_AND_PLAN.md)；S-A+ 独立复核：[evidence/2026-10-08_human_semantic_sa_r2](evidence/2026-10-08_human_semantic_sa_r2/README.md)（数据驱动留出 0 假 HUMAN，修复稀疏竖条假阳性）；采集协议草案：[CAPTURE_PROTOCOL_DRAFT.md](CAPTURE_PROTOCOL_DRAFT.md)；P2 融合 v2 离线 A/B+端到端：[evidence/2026-10-08_fusion_v2_ab_r1](evidence/2026-10-08_fusion_v2_ab_r1/README.md)（11/11 PASS：v2 人保留 99.9–100%、每帧候选、确认 2/3 段；WD01 不回归、代价公开））。该轮为诊断轮；10-08 用户授权采集与生产接入，进展见上条。W03 状态/W04–W09 边界不变。

2026-10-07 当前主线：[R3.8 离线 writer/shadow 工单](tickets/HR-W03-R38.md)已自验提交/停写，gate=DEGRADED、T38-05/06 与 S4/S7 FAIL，未 ACCEPTED；[最终结果与停止点](evidence/2026-10-07_hrw03_r38/10_final_submission.md)。唯一验收表为 R3.7 `06_test_matrix.md` v1 的 T37/T38；R3.9 production 仍未授权。用户另要求规划人体识别，已登记 [下一阶段计划与当前效果](HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md)；W03 未冻结，W04–W09 为 PLAN_RECORDED。下方 R3.1/R3.2“下一步”为历史进度。

2026-10-07（深夜）控制台回放直连板端（用户直派）：`human_replay` 会话面板点未下载的板端行 = 自动 `/api/sync` 下载、完成后自动载入回放（不再「同步选中 → 等 → 再点行」两步）；板端已 `transferred` 但本机没有的会话（本机删过再要/别的 PC 拉过）由 `fetch.transfer_one` 只读复制，不再被 `transferred→transferring` 非法迁移挡成 409 失败。新增会话改名 `POST /api/rename`：只写本地 `<sid>/meta.json` 的 `name` 字段（sid/目录/板端登记都不动，空名=恢复默认），列表优先显示 name、hover 见完整 sid。测试：human_replay python 46、human_capture 45、panel O1–O5、node 各套、console 10+4 全绿；Console.exe 与 `LiDAR_Console.zip` 已重建（内嵌副本 `/api/rename` 探针 400 通过）。证据：[2026-10-07_console_board_load_rename](evidence/2026-10-07_console_board_load_rename/README.md)。

2026-10-07（晚）PC 回传数据面换轨（用户直派修复 exe）：`fetch.py`/`config.py` 去掉 `ssh/scp`——`ldiar-wel` 别名+私钥只在本机 `~/.ssh/config`，别人电脑解压 zip 后拉不了会话的根因；改走 capture_server 新增 `GET /api/v1/sessions/<sid>/files/<meta.json|points.bin>` HTTP 直下（板端 `download_limit_kbit` 默认 70000 Kbit/s 限速，`webui/human_capture` 同页加 ↓meta/↓points 下载链接，免 SSH 手工放进 Console 的 `captures/remote/<sid>/`）。`fetch.py` 任何失败必退回 `ready`，不再可能卡死 `transferring`。Console.exe 已重建（`pc_apps/console/dist/LiDAR_Console.zip`）；板端已部署并重启（旧 4 个卡 `transferring` 会话退回 `ready`，部署实录/回滚见 [evidence/2026-10-07_files_download_deploy](evidence/2026-10-07_files_download_deploy/README.md)）。测试：`fetch_lib_test.py` 11 项、human_capture 45 项、node 各套全绿；真机 HTTP 端到端拉取 digest 通过。

2026-10-06（三轮）用户判定 **W03-R3.2 跨会话 match audit = PASS**（归因修正：alignment 已证明重要——ICP 消掉 WD01 原始漏匹配 ~94%（0.854→0.991）；全文残余 ≠ matcher error，须在 known-static correspondence set 上归因）。`09_r32_summary.md` 已按评审修订（修订记录在文内）。**R3.3 controlled AB（离线，生产零改动）完成**：AABB（点到占用格盒距离 <0.12）有独立于 ICP 的收益——known-static ICP Δ+0.032、WD02 ICP Δ+0.051、WD01 ICP 0.994→1.000；干净人体 retention ≥97.7%；纯 containment 弱于 center；HP02 NOT_RUN。生产接入仍 **NOT AUTHORIZED**。[r5 证据](evidence/2026-10-06_hrw03_r5/14_r33_summary.md)；[R3.2 修订](evidence/2026-10-06_hrw03_r4/09_r32_summary.md)。

2026-10-06（二轮）用户判定 **W03-R3.0 Static Leakage Audit = PASS（根因定位）**、同意停止 R2.6b 调参；WD01/WD02 金标锁定、新增 HP01–HP03 正样本门，[W03-R3 验收规范](W03_R3_ACCEPTANCE.md) 生效（**从 R3 起生产行为验收以 console leveled 管线为唯一权威口径，raw 仅诊断**）。判定记录：[11_user_verdict](evidence/2026-10-06_hrw03_r3/11_user_verdict.md)。**R3.1 reference builder 已交付**（离线 additive，未接 production）：[r4 证据](evidence/2026-10-06_hrw03_r4/04_summary.md)（203349 leveled：参考体素 5286、阈值 0.5 回收稀疏面 1632、同会话自吸收 0.9987、digest 复现一致；35 单测过）。下一步：R3.2 跨会话 leveled match audit（223757 vs 203349 reference）；未过 audit 不接 production。

2026-10-06 用户登记《W01–W09 最终算法架构计划书》：[计划书](W01_W09_FINAL_ALGORITHM_PLAN.md)（仅记录 PLAN_RECORDED，不构成实施授权；W03 未冻结）。当前 W03-R2 动态背景链证据：[2026-10-06_hrw03_r1](evidence/2026-10-06_hrw03_r1/README.md)。

## 0. 目的与边界

在板端远程控制采集 `/innolidar_points`（+IMU/设备状态）数据段，自动回传 PC，
在 PC 端 WebUI 中回放、剪辑，并用建模软件式交互对 3D 点云做**人工标注**，
标注以 `source:"human"` 写入数据产物，供下游 AI 一眼区分。

**边界（不做）：**

- 不动驱动 `inno_lidar_node`、HF 节点、8090 实时预览页、foxglove_bridge 配置（只读消费）。
- 不发布任何控制指令；全链路只读或本地文件操作。
- 不引入 MCAP（2026-10-02 用户拍板）——数据落地为自有 JSON 元数据 + 原始 float32 二进制点。
- 非目标：跨帧插值标注、旋转框（v1 仅轴对齐 yaw 预留）、自动标注模型。

## 1. 总体架构

```
            RK3588 板 (192.168.3.125)                    Windows PC (192.168.3.8)
┌─────────────────────────────────────────────┐   ┌──────────────────────────────────┐
│ 雷达 → inno_lidar_node → /innolidar_points   │   │ pc_apps/human_replay/             │
│                            │(board loopback)│   │  ├─ fetch.py      ←──轮询拉取      │
│            ┌───────────────┴───────┐        │   │  │   sessions → scp → 回报已下载   │
│            ▼                        ▼        │   │  ├─ load_session.py ← AI/Python 读 │
│   record_session.py(现成)     capture_server │   │  │      demo/校验库                │
│   (rosbag record → .bag)     :8766 REST      │   │  └─ index.html 回放/剪辑/标注     │
│            │                        │        │   │      (Three.js r127)              │
│            ▼                        │        │   │                                 │
│   bag2session.py (新, 纯 py)        │        │   │ 数据落盘:                        │
│   .bag → meta.json + points.bin    │        │   │  D:\Code\ldiar\captures\remote\   │
│            │                        │        │   │     cap_*/meta.json              │
│            ▼                        ▼        │   │     cap_*/points.bin             │
│   captures_remote/ (板端暂存) ←── sessions.json│  │                                  │
│   FIFO 留10份 / <5GB 强清                    │   │                                  │
└─────────────────────────────────────────────┘   └──────────────────────────────────┘
        ▲                                                    │
        └───────── 控制面 HTTP :8766（KB 级）─────────────────┘
                  数据面：仅下载时走 eth1，scp -l 限速 ~70Mbit
```

**控制面 vs 数据面分离**：8766 REST 只传请求和 KB 级状态；点云文件只在
下载时走 eth1 百兆（限速给实时预览留 30%）。录制过程本身零网络。

**为什么 PC 侧拉取**：PC 无 sshd，板→PC 推不动；PC 有免密到板的 key，
拉取天然成立。fetch.py 轮询 + 手动立即按钮。

## 2. 数据格式（两侧共同契约，version=1）

每个会话一个目录 `cap_YYYYMMDD_HHMMSS/`：

### meta.json

```json
{
  "format": "human_capture_session",
  "format_version": 1,
  "session_id": "cap_20261002_143012",
  "created_iso": "2026-10-02T14:30:12+08:00",
  "sensor": {"model": "IFW192S", "frame_id": "innolidar"},
  "time_domain": "device_stamp_s_unanchored",
  "duration_sec": 28.4,
  "frame_rate_hz_measured": 9.68,
  "topics": ["/innolidar_points", "/inno_imu", "/device_status"],
  "point_layout": {"fields": ["x", "y", "z", "intensity"],
                   "dtype": "<f4", "stride_points": 4},
  "point_file": "points.bin",
  "frames": [
    {"seq": 1, "stamp_sec": 12345, "stamp_nanosec": 678900000,
     "offset_points": 0, "count_points": 81234, "src_bag_time_sec": 0.0}
  ],
  "human_annotations": [
    {"id": "ann_001", "source": "human", "label": "person",
     "frame_seq": 154,
     "stamp_sec": 12360, "stamp_nanosec": 120000000,
     "box": {"center": [1.6, 0.1, 0.9], "size": [0.6, 1.1, 1.8], "yaw": 0.0},
     "created_iso": "2026-10-02T14:35:22+08:00", "tool": "human_replay/0.1",
     "frame_valid": true}
  ],
  "extraction": {"tool": "bag2session/0.1", "point_step_bytes": 16,
                 "field_map": "x,y,z,intensity@0,4,8,12",
                 "dropped_frames": 0, "source_bag_sha256": "…"}
}
```

### points.bin

原始 float32 小端连续流，行主序 `[x,y,z,i]`×N。`frames[i]` 的
`offset_points/count_points` 是**点索引**（字节偏移 = ×16）。
双端零解析：Python/`numpy.memmap`、JS/`Float32Array` 切片。

### AI 读法（pc_apps/human_replay/load_session.py 即此参考实现）

```python
import json, numpy as np
meta = json.load(open("cap_xxx/meta.json"))
pts = np.memmap("cap_xxx/points.bin", dtype="<f4")
f = meta["frames"][154]
cloud = pts[f["offset_points"]*4:(f["offset_points"]+f["count_points"])*4].reshape(-1, 4)
boxes = [a for a in meta["human_annotations"]
         if a["frame_valid"] and a["frame_seq"] == f["seq"]]
```

**契约要点**：

- `seq` 用驱动 ROS header **seq 原始值**（回放丢帧诊断）；`frame_valid=false`
  的标注（剪辑切半/戳空帧）AI 侧必须跳过。
- 时间域标 `device_stamp_s_unanchored`（雷达上电秒，跨年已知问题），
  与 HF manifest 同源声明。
- 人工标注唯一判定字段 = `source:"human"`。AI 侧过滤条件就这一个。

## 3. milestone 表

| ID | 内容 | 验收要点 |
|----|------|----------|
| **HC-01** | capture_server 骨架：:8766 REST、/healthz、/api/v1/status、sessions CRUD、sessions.json 原子写 | curl 200、JSON 契约、并发写不烂 |
| **HC-02** | 录制生命周期：**调现成 record_session.py**、超时长/低盘自动停、FIFO 留 10 已下载优先删、非干扰实测 | 启/停/双自动停/FIFO/sessions 状态机 + 共存证据 |
| **HC-03** | bag2session：.bag → meta.json+points.bin，sha256，抽帧记账 | 与 `rosbag info` 对账、meta 通过 load_session 校验 |
| **HC-04** | 板端控制页 webui/human_capture/：实时预览嵌入 + 录制控制台 + 会话列表 + 下载触发 | 浏览器全流程可点通 |
| **HR-01** | PC fetch.py：轮询 ready→限速 scp→回报 transferred；断点续传 | 板端 ready 文件自动出现在 PC captures/remote/ |
| **HR-02** | 回放器：.bin+meta 加载、Three.js 渲染、播放/逐帧/时间轴 | 打开即播，帧率与 meta 一致 |
| **HR-03** | 剪辑：区间 → 新子会话目录（同格式，points 切片不重编码） | 剪辑产物可被 load_session 正常读 |
| **HR-04** | 编辑器导航层：双相机(环绕/飞行)、四视图、网格/三轴/原点、坐标读数、参照物、标尺 | 键位表逐条过、读数对得上 |
| **HR-05** | 标注编辑：顶视画框、gizmo 移动/旋转/缩放、轴约束/捕捉、数值面板双向、撤销/复制、落盘 | 标注→存→重开→原位；AI 侧能按 seq 取框 |

## 4. 冻结设计决策（用户拍板记录，2026-10-02）

| # | 决策 | 结论 |
|---|------|------|
| D1 | PC 落盘路径 | `D:\Code\ldiar\captures\remote\` |
| D2 | 控制端鉴权 | 不要（局域网），后续加 token 属增量 |
| D3 | 板端产物格式 | ~~bag→mcap~~ 撤销 → **bag→meta.json+points.bin**（JSON 存不住点云本体，1.6GB/60s，二进制约其一半且零解析） |
| D4 | 回传方向 | PC 侧拉取（PC 无 sshd） |
| D5 | AI 消费者 | Python 脚本读 → `load_session.py` 为契约参考实现 |
| D6 | 板端回滚 | FIFO 留 10 / 盘 <5GB 强清最老，已下载优先删 |
| D7 | gizmo 键位 | Unity 式 **W/R/T** = 移动/旋转/缩放；飞行升降 **Z/C**；相机归位 **Home** |
| D8 | 左键冲突解 | 模式键 **B**（框选）/ **V**（查看），HUD 常显 |
| D9 | 标注法 | top-down 俯视正交画框 + z 自动（2%/98% 分位）+ 手动微调；旋转框/插值留 v2 |
| D10 | 音源现成复用 | **HC-02 录音机 = human_fall_detection/scripts/record_session.py**，不新造 |

## 5. 键位与交互总表（HR-04/05 的共同契约）

### 相机

| 输入 | 动作 |
|------|------|
| 模式切换 | **B** 框选 / **V** 查看（左键行为切换） |
| 查看模式 左键拖 | 环绕旋转 |
| 中键拖 / 滚轮 | 平移 / 缩放 |
| **F** | 环绕 ⇄ 飞行模式 |
| 飞行：按住右键拖 + **W A S D** + **Z/C** 升降 + Shift×5 | 自由飞行 |
| **7 / 1 / 3 / 0** | 顶视正交 / 前视 / 侧视 / 透视 |
| **Home** | 相机归位 |

### 标注操作

| 输入 | 动作 |
|------|------|
| **W / R / T** | gizmo 移动 / 旋转 / 缩放 |
| 按住 **X / Y / Z** 或 Shift+轴 | 轴约束（Shift+Z = 仅地面平移） |
| 按住 **Ctrl** | 捕捉：移 0.1m / 旋 5° / 缩 0.05m |
| **Ctrl+Z / Ctrl+C / Ctrl+V** | 撤销(20层) / 复制框 / 粘贴到当前帧 |
| **Enter / Del / Esc** | 定稿 / 删除 / 取消选择 |
| **空格 / ←→(Shift=±10)** | 播放暂停 / 步进 |
| **P** | 拾取最近点，状态栏显精确 (x,y,z,i) |

### 辅助显示开关（工具栏）

地面网格 1m（开）/ 细格 0.1m（关）/ XYZ 三轴（开）/ 雷达原点（开）/
1.8m 站立人形（可拖摆位）/ 1.8m 横放人形 / 2.1m 门框 / 两点标尺（开/关 + 数据持久化于 meta.view_state，草稿）。

## 6. 与运行系统的共存预算（HC-02 实测项）

| 资源 | 风险 | 措施 |
|------|------|------|
| 话题订阅 | 新增 rosbag 第 3 订阅者 | roscpp 慢订阅者只自身丢帧，不拖累 HF/bridge |
| CPU | 抽取转 bin 烧 1-2 核 ~30s | `nice 10` 起 bag2session；录制期 CPU 有富余 |
| 磁盘持续写 12MB/s | **最大风险**：板卡写速不达标→bag 静默缺帧 | record_session 缓冲 1GB；HC-02 实测掉帧率留证据；不达标降级录 `/dev/shm`(≤2min) |
| eth1 百兆 | 下载挤实时预览 | `scp -l ≈70Mbit` 限速，录时不传 |
| 驱动/HF/bridge | — | 全程只读，代码无触碰路径 |

## 7. 目录与产物

```
src/human_capture/                 # ROS1 包（HC-01..04，板上）
  core/__init__.py  session_store.py  recorder.py  bag2session.py
  scripts/capture_server.py  bag2session_cli.py
  config/capture.yaml
  launch/human_capture.launch
  tests/test_hc01_health.py  ...
webui/human_capture/              # 板端控制页（HC-04）
  index.html  capture.js  capture_lib.js  capture_lib.test.js
pc_apps/human_replay/            # PC 端（HR-01..05）
  fetch.py  load_session.py
  index.html  replay.js  trim.js  annotate.js  editor_*.js
  human_replay_lib.js  human_replay_lib.test.js
  vendor/three.min.js  vendor/OrbitControls.js  vendor/TransformControls.js
docs/human_capture/tickets/HC-01.md  ...      # 每单：范围、不做什么、验收表、return 模板
docs/human_capture/evidence/YYYY-MM-DD_<id>/  # 每单证据目录
```

依赖原则延续项目基线：板端 **stdlib + numpy + 系统已有的 rosbag CLI**；
PC 端 **stdlib + numpy + 浏览器 + Three.js r127**（与 human_fall_preview
同源取 r127 稳定系列，min 三件套 vendor 进仓，运行时零外网）。

## 8. 会话状态机（HC-01..04 共同养活）

`recording → extracting → ready → transferring → transferred → (FIFO) purged`
异常支：任何一步 `failed(reason)`；`deleting/purged` 仅 FIFO 清理用。
PC fetch 只对 `ready` 动手；成功后置 `transferred` 回报板端。

票/证据每个 milestone 一份，ticket 写明「不做什么」防范围漂移。


## 2026-10-08 新工单登记（仅制定，待用户转发开工）

用户本聊天要求制定可交给Codex执行的工单：[HR-SEM-SHADOW](tickets/HR-SEM-SHADOW.md)，唯一验收表 [HR_SEM_SHADOW_ACCEPTANCE.md v1](HR_SEM_SHADOW_ACCEPTANCE.md)。状态 DRAFT_READY_FOR_DISPATCH；本轮只交付文档。用户转发明确开工后仅执行冻结语义原型的真实整簇/全帧PC离线旁路、负例与按帧票审计、GT审阅材料及接入设计；生产语义切换、配准改动、artifact签发/重签/安装、旗标、部署采集均不在范围。W03与HR-RET-V2原授权/状态/唯一表不变。


## 2026-10-08 下一阶段骨架离线计划登记（仅计划，未开工）

用户本聊天要求“制定下一个阶段计划”，已制定 [下一阶段离线粗骨架计划 v1](HUMAN_SKELETON_OFFLINE_PLAN.md)、[HR-SKELETON-OFFLINE 工单](tickets/HR-SKELETON-OFFLINE.md)及其唯一验收表 [HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](HR_SKELETON_OFFLINE_ACCEPTANCE.md)。状态DRAFT_READY_FOR_DISPATCH，SKO-01～18全部NOT_RUN。本轮仅规划；后续用户明确开工后才做人工确认人体簇→可逆标准化→5–7粗结构节点→独立时序→离线复审。

最新SEM R2已修复SEM-12工具绑定，但SEM-05～08、10与WD02仍BLOCKED，[R2报告](evidence/2026-10-08_hrsemshadow_r2/REVIEW_R2.md)；真实身份GT缺失、05/08结构上界不足95%。本计划是受控离线可行性，不等于正式W04/W05放行，不改W03/SEM/RET-V2历史状态，不重开已关闭HR-07/08、不激活HR-09/ML，不部署采集或修改生产。
