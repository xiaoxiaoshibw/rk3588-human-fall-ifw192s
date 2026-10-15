# HF-MAINLINE-POINTS-01 · 人体候选点保留链开发计划 v1

日期：2026-10-14。目标仓库：D:/Code/ldiar；本聊天工作区为 D:/Code/radar。作者：Codex；已读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

当前授权仅为多轮分析、制定开发计划并交给 OpenCode 审核；实现、实验运行、页面改造均为下一轮拟执行范围，不把计划审核当作实现授权。计划状态 DRAFT_FOR_REVIEW；实现验收全部 NOT_RUN，生产晋级 BLOCKED。

## 1. 成品目标与边界

交付一个在原 pointset/r01 页面可连续回放的离线候选版本：在固定真实片段中解释人体候选在哪一环丢失，并在有证据的环节改善点集保留，同时控制家具、地面混入和目标漂移。R1保留默认，R2/R3及失败输出只读保留。优先点集效果，粗骨架仅辅助观察。

不训练、不采集、不部署、不提交推送、不启动设备操作、不更改旧GT/原录制/生产算法或正式配准门，不开启 confirmed 跌倒。UNKNOWN身份不升级为人体GT；13槽不称解剖关节。人工审核不是离线研究的启动条件，但完整纯度、物理资格及最终身份验收不能由AI替代。

## 2. 三轮分析后的路线判断

### 第一轮：事实、根因与范围

- M3′共享选区/公共清洁域未获得合格leveling，094333↔131958仍无新VALID。不能强制TLS、放宽门限或由fit_p90单项决定整体资格。该分支保持阻断，不作为所有隔离研究的前置条件。
- R3仅恢复已经通过背景过滤的当前前景点，无法救回上游背景删除点。轴缺测79→9是几何收益，不是人体完整率；符号返工9→4次但新增f124退化、最大粗槽跳变约1.191m仍保留。
- A01对KS1的归因不能直接采纳：r04/background_ab.js明确将地面下限设为−0.25m，A/B/C均关闭生产0.10m裁剪；旧低位失败不能据此归因KS1。215540旧统计也预扣z<0.10点。现有帧级JSON无法反推丢弃点的逐点原因。
- 两条链分别研究：JS human_pipe_lib的占据体素背景、清理、选簇；Python pointset的3D最近背景距离、DBSCAN、ROI排名及因果选簇。不能把JS结论直接移植到Python，或将10帧因果临时图称为全录制生产P的等价版本。
- source transform、reference transform、scene identity与registration validity分别记录。数值可计算不等于背景具有物理资格。

### 第二轮：实验设计与因果鉴别

先完成逐点删除账本与基线重现，再做单因素及组合消融。当前点是否被几何规则删除、是否真为人体是两个问题。仅在诊断集合确定条件；冻结后跑验证集合，不利用空场留出反调阈值。

主线采用Python八动作+空场数据和原页面；JS作为已有部分标注数据的删点归因对照，不启动另一套产品或统一核心重构。已有模型输出可展示旧基线，但新规则不训练模型，也不读取身份标签选择目标。

### 第三轮：风险、验收与失败出口

增加当前源点可能只是吸收家具或地面。真实收益必须同时给出已有绑定标签上的局部保留、已知家具混入、UNKNOWN数量、空场目标与几何风险。没有全量GT时完整人体召回/纯度仍为null/UNKNOWN。

重复使用过的1934动作+32空场只能称已开发数据上的回归，不能称新独立泛化验收；另冻结未用于本轮选择条件的动作上下文作为本轮验证，并披露历史已见。单次失败允许诊断返工，保留原版本；一旦读取验证结果后返工，新版本需要新冻结和明确标注验证重用，不能声称未见测试。

## 3. 复用入口与写入范围

| 对象 | 复用路径与用途 |
|---|---|
| Python源点加载/选簇 | sidequests/human_fusion_lab_next/pointset/r01/actions.py：load、choose；core.py：cluster、roi_mask |
| Python五层/域掩码 | research_actions.py：frame_points、masks及*_sources.npz；现有距离/范围边界须精确重现 |
| R3下游对照 | research_r3.py、experiment_r3.py、axis_sign_r3.py及冻结配置；先固定原R1锚点隔离因素，再独立feedback |
| JS删除链 | pc_apps/human_replay/human_pipe_lib.js：denoise、build_static_map、build_reference_map、extract_foreground(_fused)、cleanup_isolated_fg、cluster_voxels、pipeline_frame |
| JS既有隔离对照 | real_fall/r04/background_ab.js、score_background_ab.py及HF-BG-01绑定标签/分母 |
| 原页面 | pointset/r01/server.py、app.js、index.html；端口8944，仅localhost，后续授权范围内新增实验菜单 |
| 隔离实现（拟新增） | pointset/r01/research_retention.py及config_research_retention.json；复用加载与聚类，不复制整个r01，不新建r02页面 |
| 实验结果（拟新增） | pointset/r01/action_research_retention/<run_id>/；输出独占创建，已存在拒绝覆盖 |

旧core/actions/配置、生产JS、captures、旧结果和GT不改。JS若需stage instrumentation，使用只读加载函数加隔离薄适配器，不复制整套生产模块；先证明适配器与原函数的成员输出相同。不能用XYZ匹配替代源行身份（重复坐标须保留不同源记录）。页面修改与服务重启仅在实施阶段，需核对当前writer/运行实例，保存原字节和差异。

Python RUN_MANIFEST存在跨仓依赖：D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01。必须核对该目录background.npz、八动作registration文件及哈希；不以当前cwd自动改路径，不重写原配置。依赖缺失则仅阻断该数据分支，记录迁移路径与原SHA，不重新猜变换。

## 4. 数据与冻结

主回归：action_output/catalog.json列出的八段083254/083218/083120/083044/082906/082829/082717/082623，共1934帧；131958空场32个frame mod3=2留帧。精确sid、帧列表、meta/points SHA以catalog和RUN_MANIFEST为准，执行前再次实时核验。

诊断优先：082623 f119/f124/f192/f231/f232、082717 f140/f263、082906 f94及各±3帧；八会话起止/最小高度/过渡片段按已有R2诊断列表冻结。不凭session活动名称自动生成节点、身份或事件。

JS对照：S8 cap_20261010_180557↔175227的523帧与101空场留帧、094333↔131958的164帧与32留帧分别计算，部分标签仅在哈希/源行/帧绑定成立后用于评分。215540仅同源P诊断：缺233658参考，不替换成131958；S9 INVALID_BINDING、093958 DATA_BAD及缺原数据会话排除评分，单列BLOCKED。

参考FIT/CALIBRATION/HOLDOUT划分沿旧manifest；FIT建图，CALIBRATION只用于原容差标定，HOLDOUT不建图、不调参。空场不使用自身HOLDOUT点自建参考，不以空场0目标声称其他场景安全。

实施阶段P0生成SOURCE_BINDINGS、FROZEN_CASES、FROZEN_EXPERIMENT、保护范围清单，记录代码/配置/输出SHA、branch/HEAD、实际环境及命令。全树git状态（含untracked）保存到文件；核心源码/配置/标签/输入及跨仓依赖首尾哈希。同期其他清理/迁移单列，不把范围保全冒称整树冻结。

## 5. 开发顺序与实验矩阵

### P0：绑定与基线重现

精确重现Python R1目标成员、背景掩码、R3现有对照；JS分别重现全录制回顾P、过去最多10帧P、冻结参考B及现有C诊断。全录制P明确NONCAUSAL，不能进入候选因果链。以源行集合相等为准，数量相等不足以证明重现。基线漂移先定位，不继续比较失配结果。

### P1：全链逐点删除账本

每条28B源记录有(sid, fi, local_index, global_row, offset_bytes)身份；保留raw XYZ、变换XYZ、时间、强度/opaque字段引用和变换/背景版本。对所有源记录记first_terminal_reason；另记overlapping_predicates，禁止把多个原因计数相加当总删除量。

阶段至少覆盖：INVALID/NONFINITE/ZERO、RANGE、HEIGHT_LOW/HIGH、BACKGROUND_MATCH、ISOLATED_CLEANUP（JS适用）、VOXEL_NOISE/MIN_CLUSTER、ROI或候选资格拒绝、UNSELECTED_CLUSTER、RECOVERY_ACCEPT/REJECT及当前TARGET。未经过的阶段记NOT_REACHED，链中不存在的阶段记NOT_APPLICABLE；ROI排名不是裁剪时不得伪称ROI删点。

按原顺序归因，背景距离/命中体素与参考支持、在线占据证据、簇ID、拒绝理由、过去引用年龄随候选保存。对高度先删除的点可计算背景反事实证据，字段标COUNTERFACTUAL，不能混作实际first reason。原始记录=互斥终态总和，valid/各阶段成员集合闭合。

全帧用压缩整数stage码/源行数组及帧摘要；困难帧保存详细数值JSON。逐帧读取和写出，限制缓存/历史，不构建全录制逐点JSON内存。格式、代码字典、units与完整成员导出随manifest，UI抽样不用于计量。

### P2：先鉴别，再修有证据的环节

| 实验 | 固定项 | 唯一变量与解释 |
|---|---|---|
| E0 Python R1 | 原R/T、注册、3D背景、tau、ROI、cluster、choose | 现行−0.25m域基线 |
| E1 JS高度鉴别 | 同源输入、背景模式、聚类、选簇 | 0.10m与−0.25m对照；分别报告建图高度与提取高度开关，拆分二者，不称降低高度即薄地面分割 |
| E2 JS背景鉴别 | 完全相同源域/高度/选簇 | 回顾全P、因果10帧P、冻结B、现有C分列；原0.12m与Python约54.924mm不混用 |
| E3 Python背景删除候选 | 原E0点、tau、ROI、其他门及R1当前锚点 | 只从当前真实background_removed点产生隔离UNKNOWN候选池，分别研究当前局部连接/参考支撑风险/过去有界证据 |
| E4 下游与反馈 | 冻结E3条件 | 先不接R3看foreground→cluster→selection损失；再接固定R3与独立tracker反馈，隔离上游、恢复及关联贡献 |

E3不能沿用R3仅允许FG的recover接口后冒称救回背景点；候选池与原前景来源分别存储，不改旧R3契约。诊断比较：局部连接单因素、参考风险单因素、因果证据单因素及必要组合。只实现诊断支持的组合，不预设所有方法都有效，不规定“必须恢复X点”。贴地、稳定、近背景均是风险proxy，不能单独判家具或人体。起始无可靠目标时允许MISSING/UNKNOWN，不用GT种子或未来强观测回填。

所有新增点来自当前frame，保留原ROI；不跨帧累计身体点、不恢复invalid/range外点、不合成点。历史只作有界证据，换ID、失锁、时间倒退、过长gap清空；继承参考不刷新独立证据寿命。新增阈值由诊断统计确定并冻结，集中新配置，正式背景/注册门不变。

### P3：原页面固定候选版本

复用8944原页；R1/R2/R3及新候选同帧切换与同步视角，分层显示原始、域外、背景删除、候选池、前景、未选、当前目标和新增风险。困难片段深链/连续播放、源点点击、完整成员导出；明确显示参考资格、身份UNKNOWN和显示采样数。

先交付一个最佳证据支持的固定候选，保留消融以便复查，不用更多菜单数量替代产品效果。若没有可接受收益，页面交付删点诊断模式和失败候选，不包装成优化成功。实际浏览器查看困难帧邻域及长片段，多视角播放、seek/reset/gap不污染状态；保留截图与原日志。

### P4：全帧回归、失败返工与收口

冻结后主数据1934+32全帧；JS所需数据分支独立回归，不拼接分母。固定R1锚点与独立feedback分别报告。覆盖所有新增目标缺失、已知家具混入、方向大跳、目标中心偏移和空场目标，最差帧/新退化不得被平均值掩盖。

不通过就定位首个退化环节，允许修改诊断支持的规则并新建run；至少完成诊断→候选→全帧→有依据返工或明确无收益裁决的闭环，不因一个方案失败提前停止，也不无限增加策略。返工若接触验证样本须披露，并保留该样本为回归，不再称未见验证。缺物理GT不阻止研究；源数据/绑定缺失只阻断对应分支。

## 6. 唯一实施验收表（v1；本轮全部NOT_RUN）

| ID | 实施通过条件 | 当前 |
|---|---|---|
| PR01 | 实时数据/依赖绑定、保护清单、全树状态与范围首尾SHA可核；漂移如实分列 | NOT_RUN |
| PR02 | 原链成员逐点重现，JS各上下文和Python口径分开，baseline差异为零或解释后重新冻结 | NOT_RUN |
| PR03 | 所有源行互斥终态闭合；重复XYZ不合并；实际与反事实原因分开 | NOT_RUN |
| PR04 | 完成高度/背景单因素鉴别及诊断支持的候选消融，原门未放宽，无HOLDOUT反调 | NOT_RUN |
| PR05 | 1966帧主回归，新增成员全部当前源点；有界因果前缀独立重放相等，GT不进入推理 | NOT_RUN |
| PR06 | 源点风险与效果报告齐全：按会话/姿态上下文/最差帧统计保留、家具、UNKNOWN、漂移/缺失；有明确收益或失败裁决 | NOT_RUN |
| PR07 | 冻结的候选提请效果验收需32空场0目标/0新增事件、原1934帧无新目标缺失、已有绑定人体标签保留不低于对应旧基线、已知家具目标成员不增加；不满足保留为失败实验，不放宽门 | NOT_RUN |
| PR08 | 原页真实浏览器多视角与连续回放/seek/reset/源点击/导出/非法输入通过；R1仍默认，完整成员与显示采样分开 | NOT_RUN |
| PR09 | 固定锚点与独立feedback分开；方向翻转/粗槽跳变/原9帧缺测及新退化完整报告；不以节点数作准确度 | NOT_RUN |
| PR10 | 当前源码/配置/输入SHA、命令、指标、失败、复跑入口、FINAL_REPORT、回传和独审记录齐全 | NOT_RUN |
| PR11 | 完整人体召回/家具纯度/解剖精度/泛化：需独立身份GT与物理资格；缺失时null/UNKNOWN，不以PR01–10替代 | BLOCKED |
| PR12 | 生产晋级/confirmed/设备部署/物理验收：本轮范围外 | BLOCKED |

PR07是候选提请门而非身份准确度证明；没有已知家具标注的会话填NOT_EVALUATED，不能将其当0或全安全。收益至少在冻结诊断中的一个实际丢点环节有可追踪的局部改善，同时完整列出其他退化；若无身份GT仅称几何保留改善。PR06可以以诚实的失败裁决完成报告，但PR07不因此变PASS，整体仍SUBMITTED未ACCEPTED。

## 7. 实施验证与交付

新增有意义的契约检查：终态守恒、重复XYZ源行、invalid/opaque不变、实际/反事实阶段语义、当前源支撑、前缀截断、超龄/换ID/gap清空、标签仅评分、FIT/HOLDOUT隔离、输出拒绝覆盖。Python -B -W error；复用pointset相关unit tests、JS human_pipe_lib/registration相关检查和原console入口回归，不跑无关设备套件。真实浏览器检查遵循PR08。

交付：绑定manifest、冻结案例/配置、逐点stage数组及codebook、逐帧摘要、消融/前后/最差帧清单、运行命令与性能实测（Windows，仅本机口径）、页面固定候选、FINAL_REPORT及唯一表逐ID状态。评审者只读审核，作者修正文档另存v2，原v1/原评审日志保留，不伪称OpenCode认可改后版本。

## 8. 依据

- docs/human_fall/evidence/2026-10-14_hf_mainline_leveling_r1/FINAL_REPORT.md
- docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md
- docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md
- docs/human_fall/evidence/2026-10-14_audit_r1/C01_claude_code_kimi_k3.md（采纳已核源码事实，未采纳其未经证实的leveling因果断言）
- docs/human_fall/WORKFLOW.md、docs/human_capture/README.md、AGENTS.md及上述实际源码。
