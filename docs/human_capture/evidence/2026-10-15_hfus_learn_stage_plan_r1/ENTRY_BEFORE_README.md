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
