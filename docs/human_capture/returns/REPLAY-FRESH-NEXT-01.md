# REPLAY-FRESH-NEXT-01 回传

## 2026-10-16 R1 / Codex：传统人体与跌倒候选链

- 用户本轮实际授权：按计划开发，交OpenCode审核，借助视觉/算法继续传统聚类和架构更新，参考外部案例。
- 唯一当前验收：[v2 FN01–FN10 / AD01–AD08](../evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)，SHA256 `f666a4720002c1d5251475242a7ef2efdf6ccba73c3a38c6c140912ff6988eff`。
- 执行方式：Codex唯一生产writer；OpenCode CLI `opencode-go/deepseek-v4.1-flash`，`--standalone --agent plan`，权限只读。
- 状态：**SUBMITTED**；本机候选软件逐项自验；设备/物理/部署NOT_RUN，语义GT BLOCKED；未宣称ACCEPTED或真跌倒产品验收。
- 起始master / HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；故意脏树，已保存含untracked的BASELINE/STATUS；
  本项既有生产前态在before，最终SHA在SOURCE_FINAL，保护源与30份原输入不变；并行用户差异未清理/提交。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）；科学计算辅助技能：`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。

### 集中诊断与根因覆盖

| 缺陷/验收 | 根因与入口 | 修复/保留 |
|---|---|---|
| FN03/FN04 | R1把所有观测计入8容量，空场假0 | eligible才占容量，超载只冻结出生，既有唯一轨迹可续；撤回R1收益，保留R2 152/186失败 |
| FN02/AD04 | 贪心竞争、歧义和帧计数时序不足 | 小目标精确一对一分配、双向歧义拒接、真秒生命周期、实际id/obs/距离/dt/原因 |
| FN04/FN05 | 错参考下竖向静物穿过人形门 | 参考低支撑时新身份须独立位移，静止待核实；并非全局停用；错参考真人漏认边界保留 |
| AD03/AD05 | 站姿/低姿混用、单帧地面簇错误续接 | 站姿建身份、直立中间态/低姿只续接、垂直连续与横向宽约束；真实躺姿长度保留 |
| AD05/AD06 | 单帧躺姿/慢躺恢复被当事件 | 稳定躺姿、快速下降与持续证据分开；POSTURE_RETURNED与候选后RECOVERED分开；confirmed=false |
| FN08/AD07 | 主线方案与参考难对照、历史颜色挂接失败风险 | 单钩子、真实RGB/源行验证、开关/菜单/错误提示、当前帧部分GPU上传 |
| FN03 | 页面服务有自身配平、旧离线固定RT | API transform_id冻结，页面42→0与固定RT162→0独立对照 |

### 实际变更

| 文件 | 本轮用途 | 与前态区分/提交SHA |
|---|---|---|
| pc_apps/human_replay/traditional_perception.js | 新pure-JS候选聚类/人体/身份/姿态/事件模块 | 新文件；最终SOURCE_FINAL |
| traditional_perception.test.js / traditional_overlay.test.js | 19引擎场景组、实际源成员/RGB/生命周期测试 | 新文件；最后宽家具反例经隔离差分纠正 |
| fresh_overlay.js | 版本适配、真实源成员、HUD/事件/计时、当前帧GPU更新与reset统计 | 旧版计算分支保留；before差异+SOURCE_FINAL |
| fresh_view.js / fresh_view.test.js | XY默认、方案/参考选择、错误与本地目录防丢失 | 原版可选/关闭仍原着色；原测试SHA在BASELINE |
| index.html | 开关旁版本/参考、姿态与事件面板 | 既有工具保留 |
| replay.js | 记录manual/server载入来源，避免目录重载丢失 | 三处有界修改，其余沿用 |

源SHA/差异见[最终源](../evidence/2026-10-16_traditional_perception_dev_r1/SOURCE_FINAL.json)、CHANGESET_R3.diff及最后测试文件。
输入28B raw→同一R/T米制z-up；bag_time秒；无训练/模型切换/新依赖/板端变更。

### 逐条验收

所有软件项均synthetic/offline/本地浏览器；没有用mock替代设备。详情、命令与对应输出/source SHA见[RESULTS_FINAL](../evidence/2026-10-16_traditional_perception_dev_r1/RESULTS_FINAL.md)。

| ID | 状态 | 证据/边界 |
|---|---|---|
| FN01 | PASS | INPUT_MANIFEST/DEBUG_HOLDOUT/实际页面配平清单，非盲同日分组声明 |
| FN02 | PASS | audit_main_xy_r6源行/实际RGB/id/时间/参考/R/T/分支/拒接；无身份GT结论 |
| FN03 | PASS | 几何根因/2×2参考/实际配平，算法收益分列 |
| FN04 | PASS | 固定RT162→0≤32；页面42→0；overflow0，误认领区间与事件分列 |
| FN05 | PASS | 221808固定与自身配平均0/272，管线实际运行 |
| FN06 | BLOCKED | 主会话覆盖代理291→291、无新增失亮；可信人物GT缺失 |
| FN07 | BLOCKED | 完整逐会话对照已做，低姿起始两段少13/5帧；语义GT未有 |
| FN08 | PASS | 开关/版本/参考/代际/重置/单钩子和页面实测；本地目录切换有明确守卫 |
| FN09 | PASS | 19套回归exit0、Python45 tests；原30文件/保护源码SHA不变，失败完整留证 |
| FN10 | PASS | Go Flash实际只读R1 REVISE返工，R2/R3 REVIEW_PASS exit0；最后测试/报告补齐记录另列 |
| AD01 | PASS | 聚类/准入/关联/姿态/事件分离并接主线 |
| AD02 | PASS | PCL/Autoware/AB3DMOT官方案例借鉴，无模型/依赖移植 |
| AD03 | PASS | 原XY/3D全量对照，当前真实源成员，不造点；3D未获胜保留 |
| AD04 | PASS | 真秒、短遮挡/分裂/竞争/超载/相同时间/重置等19组回归 |
| AD05 | PASS | 候选/未知、站/低/躺/恢复与候选事件，初始躺不判发生跌倒 |
| AD06 | PASS | 合成对照及真实受控轨迹事件输出，不报真实跌倒TP或召回 |
| AD07 | PASS | 当前最终代码站/躺/起实图、空场对照、CPU与JS堆记录 |
| AD08 | NOT_RUN | GT结论BLOCKED；真实跌倒/跨场景/设备物理/EXE部署未验收 |

回归：regression_r6.json/log；生产冻结后只修测试反例，width_counterexample_r7.log 19组exit0。
原输入：INPUT_AFTER_R5.json，15会话30原文件逐字节/sha全匹配，5保护源匹配起始baseline。

### 未闭合与限制

- FN06/FN07需要独立人工人体/身份/姿态GT；两段低姿起始覆盖退步不能隐藏或直接解释为正确排静物。
- 错参考下新XY只163/295、静止真人可能延后/漏认；初始躺地、窄凳等相似几何仍未解决。
- 最大8目标；整段常驻JS堆约1.1GB；本机CPU测量不代表GPU/板端/连续播放墙钟。
- AD08真实跌倒/物理/设备/打包部署NOT_RUN，无当前明确设备指令；未触碰驱动/网络/采集/训练/GT/data/Git写。

### 独立复审包与下一步

[完整证据索引](../evidence/2026-10-16_traditional_perception_dev_r1/README.md)、[最终报告](../evidence/2026-10-16_traditional_perception_dev_r1/FINAL_REPORT.md)、REVIEW_FINAL.md、DELIVERY_MANIFEST.json。
后续先用既有工作台补退步/假目标真值，再做初始低姿与局部参考结构，随后降低整段内存；物理/设备另列。
本项不接管HF/GL、公开数据学习或并行HC工单，未宣称ACCEPTED。

### 最后复核补记（同日本轮）

OpenCode R4实际读取最终生产/测试/报告，确认宽家具差分反例与最终163数值两项P2均关闭，
`REVIEW_PASS`、exit0、REVIEW_COMPLETE，新实质缺陷无；未重跑实验/哈希/设备。
见REVIEW_FINAL.md与OPENCODE_R4_CURRENT.md/_status.json。生产自R3未变，R7仅测试反例修正。

---

## 追加：后续只读诊断与修复设计（diag r1，2026-10-16，不改变上方历史与验收状态）

### 本轮信息

- 工单 / 轮次 / 执行者 / 时间：REPLAY-FRESH-NEXT-01 后续诊断 diag r1 / OpenCode（opencode-go，只读诊断+修复设计）/ 2026-10-16
- 验收表路径 / 版本 / SHA：沿用 ACCEPTANCE_V2.md（未改）；本追加为诊断记录，FN06/FN07 BLOCKED、AD08 NOT_RUN 等状态一律不变
- 执行方式 / 实际会话与模型：用户口头授权「下一步排查尝试」；本机回放探针，生产代码零写入
- 状态：SUBMITTED（诊断与设计）；软件自验仅为探针数据，设备/物理未跑
- 起始branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；无 commit/push/reset/clean，数据/GT/板端/驱动网络未动
- ponytail SKILL.md实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail`（full）

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| P1 低姿起始13/5帧（FN07 边界） | `human_pipe_lib.js` L52 身高墙 0.90m × `traditional_perception.js` L10 出生门 1.15/1.4m 叠加；低姿只续接不创建；确认延迟 hits≥3/0.18s | 082829/082906 认领、页面高亮、身份生命周期 | 出生准入加「升起证据」provisional 旁路（FIX_PLAN_R1 Fix 1） | 低姿不直接建身份、初始躺不判发生跌倒 |
| P2 空场保护脆弱 | `verification_motion_m:0.04` 量质心位移，簇组成抖动（碎簇 n=80，0.05–0.10m）可冒充独立运动；`reference_trusted` 全局支撑率 0.9 一刀切 | 空场误认领、错参考确认、候选事件前置 | L204–205/L218 直进度+参考分级（Fix 2） | 歧义拒接、overflow 不输出假 0 |
| P3 窄凳混淆被指标掩盖 | h=0.57 窄凳 vs 起身 h=0.70 仅差 0.13m，纯高度分不开；正确参考→零运动确认；认领帧指标对目标级假目标不敏感 | 版本对照、冻结评估、回归 | evaluate.js/run_matrix 目标级聚合+反例回归（Fix 3） | 认领帧口径保留，目标级另列 |
| P4 3D f27–28 失亮 | 度量洪泛脚/地面间歇桥接，簇 zmin 跳 0.57–0.74 失触地与续接几何 | 3D 对照模式 | 不修（默认 XY，YAGNI） | 3D 保留对照 |
| P5 错参考 163/295 | P2 另一面：静止真人缺独立运动确认；背景变新鲜致观测 3.4 倍、门限拒接暴增、断裂重出生 | 错参考召回边界 | 随 Fix 2 分级改善 | 错参考边界如实保留 |

修复方法、验收口径与实施顺序见 [FIX_PLAN_R1.md](../evidence/2026-10-16_traditional_perception_diag_r1/FIX_PLAN_R1.md)。
关键禁止项：不得以调低出生/身高门限为修复（probe_false_r1 已复现窄凳 79/90/122 帧假认领）。

### 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| evidence/2026-10-16_traditional_perception_diag_r1/probe_matrix.js、probe_false_r1.js | 新增只读探针（复用 evaluate.js 回放逻辑，内嵌 base 复现 R6 断言） | 新增诊断文件 | 生产源未变（SOURCE_FINAL.json） |
| 同目录 probe_matrix_r1.json、probe_false_r1.json | 参数矩阵与目标级生命周期输出 | 同上 | |
| 同目录 PROBE_REPORT_R1.md、FIX_PLAN_R1.md | 诊断报告与修复设计 | 同上 | |
| pc_apps/human_replay/* 等生产源 | 零修改 | | |

### 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| 探针检查：base 复现 R6 82/67/291/0/0 | offline | node probe_matrix.js 内嵌断言 | PASS exit0 | probe_matrix_r1.json |
| P1 根因：窗口 13/13+5/5 可找回、同身份 f70–f182 | offline | probe_matrix_r1 / probe_false_r1 | PASS | 同上 |
| P2 反例：111738 birth07→179、nomotion→181 | offline | probe_false_r1 | PASS | probe_false_r1.json |
| P3 反例：窄凳 (4.89,2.99) 三段 79/90/122 帧假认领 | offline | probe_false_r1 | PASS | probe_false_r1.json |
| FN01–FN10 / AD01–AD08 | — | 本轮不重跑不改状态 | 沿用 dev_r1（BLOCKED/NOT_RUN 不变） | 见 RESULTS_FINAL.md |

### 未闭合与限制

- 全部为本机回放代理指标，无人体/身份/姿态 GT，不宣称真实人体 P/R/F1 或真实跌倒结论。
- 修复仅为设计未实施；实施与阈值工作点须先做顺序 1 标注，不拿同日留出调参。
- 设备/物理/EXE 部署仍 NOT_RUN/BLOCKED，无当前设备指令。

### 交给Codex独立复审

- 现行验收表与本轮变更记录：ACCEPTANCE_V2.md 未变；本追加+diag r1 五文件。
- 根因诊断/完整入口检查证据：PROBE_REPORT_R1.md → FIX_PLAN_R1.md → 两个 probe json（探针 base 断言 exit0）。
- 源码差异与SHA证据：生产零变更；新增仅 evidence 目录。
- 原始日志索引：diag r1 目录；历史 dev_r1 证据全部保留未改。
- 当前工单下一步：顺序 1 标注（两段退步+假目标 P/N/U 与身份/姿态真值）→ Fix 3 指标 → Fix 1+2 → 冻结对照定默认版本。

---

## 追加2：设计核对返工（diag r1 → FIX_PLAN_R2，2026-10-16）

独立只读设计核对提出四点，已在 [FIX_PLAN_R2.md](../evidence/2026-10-16_traditional_perception_diag_r1/FIX_PLAN_R2.md) 返工闭合（R1 保留为历史，R2 为现行设计）：

1. **在线/回填/确认延迟三分口径**：provisional 不染色、实时不补染；Fix 1 的 13/13、5/5 承诺仅限离线回填覆盖，在线覆盖与确认延迟分别报告实测值。
2. **直进度降级为待验证特征**：不承诺空场归零；Fix 2 验收改为"不劣于 base（111738 0/186、221808 0/272）"+ 三特征 ablation，判不过回退结构域证据。
3. **静止真人矛盾解除**：`motion_evidence = xy_motion ∨ shape_motion`；升起/结构域证据可独立转正（零 XY 位移站起也能确认）；错参考下始终静止无形变者保持延后/漏认的诚实边界。
4. **顺序统一 + 目标级冻结定义**：以本回传口径为准——**GT 标注 → Fix 3 → Fix 1+2 → 冻结对照**（废止 FIX_PLAN_R1 的"指标先行"表述）；目标匹配/身份切换/假目标/provisional 计数定义冻结于 R2 §4，算法轨迹不得直接当真值。

状态不变：本轮只读设计核对，未重跑探针、未改生产代码与验收状态；**修复效果 NOT_RUN，语义 GT BLOCKED**。
ponytail：`C:/Users/30680/.config/opencode/skills/ponytail`（full）。


## 2026-10-16 REPLAY-FRESH-NEXT-01 dev_r2 实施回传

### 本轮信息

- 工单/轮次/执行者：REPLAY-FRESH-NEXT-01 / dev_r2 / Codex唯一生产writer。
- 状态：**SUBMITTED；真实目标级评分/语义GT BLOCKED**。逐条为本机自验；软件检查不等于工单ACCEPTED。
- 唯一验收：`docs/human_capture/evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md`，v2，SHA256 `f666a4720002c1d5251475242a7ef2efdf6ccba73c3a38c6c140912ff6988eff`；现行设计diag_r1/FIX_PLAN_R2.md。
- 当前证据目录：`docs/human_capture/evidence/2026-10-16_traditional_perception_dev_r2/`；入口CURRENT.md。
- 起始branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；BASELINE.json含13,029项工作树SHA/缺失和全部未跟踪状态，数据不作workspace处理。
- 实际技能读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。复用既有runner/探针，新增逻辑均有可跑检查；无新增依赖。
- 执行方式：本机Node/Python，Python测试继续`-B -W error`；Codex具体模型ID不可得。OpenCode CLI命令指定`opencode-go/deepseek-v4.1-flash`、plan只读；实际日志及退出码保留，不冒充人审。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| Fix3/FN02/09 | 认领帧数掩盖同时存在的假轨迹 | evaluate→目标匹配→覆盖/IDSW/假目标 | score.js；真实source行members；合成0.5边界/冲突/中断检查 | 无GT全BLOCKED；normalized adapter不替代外部约定 |
| Fix1/FN06/07 | 分类与出生双层身高门截断低姿起始 | Engine出生→关联→确认→claims | structure/provisional、独立shape转正、backfill审计；原阈值不改 | 在线仍有确认延迟；完整回填仅离线审计，页面仅当帧claims |
| Fix2/FN03/04 | 累计质心位移把簇组成抖动当运动 | 差参考出生→运动验证→确认 | xy_motion_mode0/1/2/3、净位移/路径、多窗采样边界 | 三候选均不保证排除抖动；诊断降门后的79/90/122及birth07失败保留 |
| D1/AD04/05 | 起身变稀疏后不再过旁路结构门，候选长期不转正 | provisional→严格站姿o.birth→shape→confirmed | 出生结构资格+当前严格站姿可提供升起证据；两例修前失败、修后通过 | 不降低身高/点数全局阈值；无升起的静态候选仍未知，出生互斥保持 |
| D2/FN09/10 | 复审期间版本细化，早期证据非最终源码 | 源码→矩阵/消融→复审 | SOURCE_FINAL_R4/SOURCE_R4.diff及dev2c/delivery代统一 | dev2/dev2b/旧SOURCE全部保留为历史，不拼接结果 |
| D3/AD07 | 完整出生→确认回填需要保存成员 | pending缓存→离线回填 | 记录边界，未扩展内存专项 | 连续可见且永不转正者缓存无独立上限；长会话内存NOT_RUN |


### 实际变更

| 文件 | 本轮用途 | 与起始差异区分 | 源码SHA256 |
|---|---|---|---|
| `pc_apps/human_replay/traditional_perception.js` | 结构旁路/确认/三口径审计/运动候选 | 本轮前副本before_*及R3差异可核对 | `2f2faa1a193d63b53f81cadec3177378aa2d5e41f087eca81b972a9767055f4e` |
| `pc_apps/human_replay/traditional_perception.test.js` | 4指定反例+多窗正例+2稀疏/占位反例+容量边界；27组 | 本轮前副本before_*及R3差异可核对 | `b2d0edf6cf76cc544eee39165e57a7ba00606d944be9acc128d1398038dfcef3` |

证据工具：score.js/score.test.js、evaluate.js、run_matrix/run_regression、探针副本及消融/汇总/保护检查。
输入为原28B源、冻结REF_RT配平、bag_time_sec真秒，坐标米；源行保持原帧局部索引。
板端代码未改。回放默认入口仍XY；Engine原直接调用默认参数未作全局切换；3D仅对照。

### 逐条验收

| ID | 本轮自验 | 证据与边界 |
|---|---|---|
| FN01 | PASS | 30原文件SHA复核相等；24组继续使用r1冻结会话/参考/REF_RT，非新盲测 |
| FN02 | PASS | dev2c逐帧tracks/branches/events/observations/members/source映射/参考变换可追溯；算法id不冒充身份GT |
| FN03 | PASS | 原探针副本复核+24消融；质心/直进度/多窗仍可认领抖动，失败完整保留 |
| FN04 | PASS | 固定221808参考、固定REF_RT：111738两版本0/186、overflow0；相对冻结原版162≤32；本轮未重跑legacy |
| FN05 | PASS | 221808两版本0/272；当前引擎与既有overlay软件回归通过；本轮真实浏览器实录NOT_RUN |
| FN06 | BLOCKED | 主会话XY291/295保持；可信目标级GT/接口未交付，语义门不解锁 |
| FN07 | BLOCKED | 24组实跑；低姿在线84/69仍比原版95/72少11/3；回填分列；GT未知不改判 |
| FN08 | PASS | fresh_overlay/fresh_view/换会话/坐标/单钩子等软件回归通过；页面源码保持，浏览器交互本轮NOT_RUN |
| FN09 | PASS | SOURCE_FINAL_R4/SOURCE_R4.diff、19套exit0、30输入/347保护SHA、两轮复审、回传与历史失败齐 |
| FN10 | PASS | 本轮OpenCode只读R1 REVISE→R2 REVIEW_PASS，原文/JSONL/退出码保留；不是独立实验或人工GT |
| AD01 | PASS | 原拆分链保持，新增结构候选/独立转正与离线审计；页面仍仅消费claims |
| AD02 | NOT_RUN | 本轮按冻结设计实施，未新增/重新核验外部案例；r1来源证据只读保留 |
| AD03 | PASS | 24组XY/3D；原source点索引映射验证，3D不升级默认、无地面桥接专项 |
| AD04 | PASS | 27引擎组含真秒/重复/逆序/reset/遮挡/互斥/不规则时间窗/稀疏起身；真实身份GT未知 |
| AD05 | PASS | confirmed-only姿态/候选事件、初始低姿不报跌倒；shape独立于XY；静态无形变仍未知 |
| AD06 | PASS | 27组中合成快降/慢躺/蹲坐/恢复/离场；真实会话候选事件仍导出；真实跌倒TP/召回BLOCKED |
| AD07 | NOT_RUN | 本轮未做浏览器站倒起截图与页面CPU/JS堆重测；评测器CPU/RSS不当浏览器/设备性能 |
| AD08 | NOT_RUN | 真实GT指标BLOCKED；跨场景/设备/物理/EXE/部署均未运行 |


### 实测、命令与日志

- `python -B -W error .../run_regression.py regression_release`：18JS+human_capture Python45，全19套exit0；引擎27组。日志regression_release.*。
- `node .../score.test.js`：exit0，scoring_review_r2.log；缺GT/不完整/U、0.5匹配、IDSW、MISMATCH、假轨迹79/90/122计数、回填冲突、provisional率/延迟。
- `python -B -W error .../run_matrix.py dev2c`：24组exit0、overflow全0；逐组源码SHA与当前R4一致，inputs与r1冻结相同。
- `node .../summarize_delivery.js`：exit0；METRICS_TABLES_DELIVERY_V2.md、TARGET_METRICS_DELIVERY.json、THREE_METRICS_DELIVERY.json；完整24组在线/离线目标级栏BLOCKED。
- 两原探针副本`node .../probe_false_r1.js`、`node .../probe_matrix.js`均exit0，结果在本轮新目录；diag_r1未写。修订后相同24任务`motion_ablation_delivery.js`再次exit0；ABLATION_DELIVERY.md。
- `node .../check_counterexamples.js`：exit0，默认XY在历史79/90/122窄凳位置均0 confirmed认领轨迹，仅几何复现代理；真实“无GT匹配confirmed轨迹数”仍BLOCKED。
- `python -B -W error .../verify_sources.py _R4`：exit0；347个保护文件及30原始文件SHA全相等，PROTECTION_R4.json。
- OpenCode R1 REVISE→R2 REVIEW_PASS，两个exit0且REVIEW_COMPLETE；OPENCODE_R1/R2.md/jsonl/status及REVIEW_RESPONSE_R1/R2.md。R2复审后只新增容量边界测试，生产SHA保持；R4快照包含最终27组测试。

### 三口径与未闭合

- XY 082829两个退步窗口共13帧：online_cov **2/13**、backfill_cov **13/13**、confirm_latency **3.007031s / 29帧**；082906五帧窗口：**2/5、5/5、1.650004s / 16帧**。不把回填当在线收益。
- 正确参考主会话XY仍291/295；两空场仍0/186、0/272。082829/082906全段在线84/69，较旧原版95/72仍少11/3帧，未称语义修复完成。
- 错参考主会话XY从163降为137帧（3D137→141）；该代理退步保留FAIL，不以无GT强判为正确排除。默认仍XY，3D不升级。
- 质心/直进度在诊断birth07仍可认领1/5/6/9；多窗仍可认领5/9。诊断birth05窄凳79/90/122仍存在。禁止由此降低生产出生/分类门；不宣称运动特征能空场归零。
- 未找到本轮外部GT接口约定及标注文件，已请求路径；不生成/修改GT。消费适配与真实目标覆盖/假目标/IDSW/MISMATCH为BLOCKED。FN06/FN07解除必须遵从原验收表明文，AI标注产物也不能自动冒充独立语义GT。
- ≥9 eligible（包括provisional）时冻结新出生，已有confirmed可继续；滚动半秒升幅不足0.3m或缺测跨窗可能漏认，均保留未知。长会话pending缓存边界保留；本轮未做浏览器实录/页面性能、独立外部案例重查、真实跌倒、跨场景、设备/物理/EXE/部署。无commit/push/reset/clean、采集、板端/驱动/网络/模型/训练或数据写。

### 交给Codex独立复审

当前索引CURRENT.md；唯一表及逐项状态见RESULTS_DELIVERY.md；根因/入口见本回传及REVIEW_RESPONSE_R1.md；源码R4差异/SHA、原始日志、保护清单均在本轮目录。
下一步是消费用户提供的外部接口/GT产物完成真实目标级评价，并由指定验收者判定；本轮不自动解锁其他工单。

## 2026-10-16 REPLAY-FRESH-NEXT-01 后续 GT 标注轮（gt r1，diag r1 之后）

### 本轮信息

- 工单 / 轮次 / 执行者 / 时间：REPLAY-FRESH-NEXT-01 后续 GT 标注（人/家具/背景/未知 + 身份 + 姿态真值）/ gt r1 / OpenCode（只读诊断 + 标注执行者，**非生产代码 writer**，开发归 Codex）/ 2026-10-16。
- 验收表路径 / 版本 / SHA（提交时记录）：当前唯一验收表 [dev_r1 ACCEPTANCE_V2](../evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md)（FN01–FN10/AD01–08）不变，本轮未新建验收表；工单四条交付物按 GT-D1…D4 自验。ACCEPTANCE_V2.md SHA256 见本轮 MANIFEST_R1.json 附注（同批计算）。
- 执行方式 / 实际会话与模型：OpenCode agent 会话，模型 `opencode-go/mimo-v2.6-pro`（工单称 mimo-v2.6-pro）；本机 PC：probe（Node 复用 diag r1 探针加载）+ 8901 回放页/工作台 API。**AI 视觉标注，非人工 GT**。
- 状态：SUBMITTED（GT 标注交付，待人工抽检）；软件自验逐条见下；设备/物理/EXE/部署 NOT_RUN；FN06/FN07 **维持 BLOCKED**（不因本标注自动解除，除非验收表明文）。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置SHA证据：HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树按基线即脏（既有 M/?? 条目为他人/历史改动，本轮零生产代码改动，未动 SOURCE_FINAL.json 冻结源）；本轮写入仅=新证据目录 + gt_store 四会话 draft（仅经 /api/gt/save）+ 本回传追加。全部交付件 SHA256 见 [MANIFEST_R1.json](../evidence/2026-10-16_traditional_perception_gt_r1/MANIFEST_R1.json)。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具，full）。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| FN07「真人丢失 vs 静物排除」 | 双层身高墙（pipe 0.90 × birth 1.15/1.4）+ 确认延迟（diag r1 P1），低姿真人在墙下不可出生 | 082829 f86–94/f97–100、082906 f103–107 共 18 帧 base 认领 0/13、0/5；GT 定性：18 帧逐帧均为人 P1（同一连续簇，低姿→起身→1.81/1.82m 站立）→ **真人丢失** | 不修（本轮不改生产）；GT 供 Codex Fix 1/3 锚定 | 窄凳 (4.89,2.99)、111738 四杆状物判非人静物（家具/背景）→ base 0 认领=正确排除；birth05/birth07 放宽后的 79/90/122 与 179/186 认领=假目标 |
| C 窄凳假目标（P3） | h0.57 与起身 h0.70 纯高度分不开 + 参考可信零运动即确认 | 三段会话各染 79/90/122 帧 | GT 定性 F1_bench 家具（假目标反例真值） | 跨三会话位置形状稳定、质量集中 0.1–0.3m；**遮挡事实**：082829 f94+/082906 f102+ 被站立人同方位角遮挡无回波（f104 特写空白），f100 可见→非消失 |
| D 杆状物假目标（P2） | verification_motion 量质心位移，簇组成抖动冒充运动 | 111738 birth07 179/186、轨迹 1/5/6/9 | GT 定性 R1/R2 家具、R3/R4 背景（均非人，R1/R2/R4 类内置信 medium） | 四区 h>1.5m、max_motion≤0.026m、f2→f150 高度稳定、无躯干质量带；R1/R2 f10–15 并簇、f20 起并入大结构→抽样判 f2 |

### 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `docs/human_capture/evidence/2026-10-16_traditional_perception_gt_r1/`（新目录） | 全部 GT 证据与交付件（探针/特征/95 截图/判定表/标注/导出件/API 日志/manifest） | 纯新增，未动 dev_r1、diag r1 任何文件 | 见 MANIFEST_R1.json |
| `pc_apps/human_replay/gt_store/<4 sid>/draft.json` | 工作台标注（经 `/api/gt/save`，source=model/unreviewed） | 仅新增 082829/082906/082623/111738 四会话 draft，无既有 draft 被覆盖（保存前校验） | 服务端 sha256 见 gt_api_log_r1.json export 行 |
| `docs/human_capture/returns/REPLAY-FRESH-NEXT-01.md` | 本回传（只追加） | 未改历史回传 | — |
| 生产代码（pc_apps/、webui/、src/） | **零改动** | 未改算法/工作台格式/GT 旧资产/板端 | 与 SOURCE_FINAL.json 冻结源一致 |

步骤与证据：① 静态场景建模+背景剔除——`probe_gt_r1.js` 直接复用 diag r1 probe_matrix/probe_false 的加载与簇特征输出（load/frame/zhist、build_reference(221808)→fresh_update→Engine(base)），不新写引擎，输出 `gt_cluster_features_r1.json`（082829 f70–110 全量、082906 f95–115 全量、082623 f115/120/200、111738 f50/100/150）与 `_r1b`（111738 f2–f30 早期帧，两杆簇 f10 起并簇），每观测含 n/height/宽/径/10cm 高度带/出生门理由 + denoise↔raw↔compact-local 三索引空间（映射带值级自检）；② 视觉核验——8901 回放页（人物高亮默认关）逐关键帧截图 95 张入 `shots/`，每张前后校验 HUD 帧号与高亮态（HUD「帧 N+1」= f<N>），C/D 另补程序化相机中距/近距特写（同页 controls 调视角，非生产改动）；③ 判定按工单三规则+U 政策（无证据不判，本轮 0 无证据判定点、0 U 帧）；④ 落标注——`build_annotation_r1.js`（复用 gt_lib.make_object/encode_indices，带截图+簇特征双证据存在性自检）→ `workbench_submit_r1.py` 走 save→freeze→export，`annotation_gt_r1.json` 74 条伴生表（人 P1×62、F1_bench×6、杆状物×6，含身份/姿态真值/provisional_stage/依据引用）。

### 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| GT-D1 annotation_gt_r1.json + 工作台导出件 + SHA 入 manifest | offline | `node build_annotation_r1.js` exit0；`python workbench_submit_r1.py` exit0 | PASS | annotation_gt_r1.json `d98912a3…`、workbench_exports/*_draft.json ×4（3b8c7adf/6bbc5924/0739fb0c/a3f28b44），MANIFEST_R1.json |
| GT-D2 窗口逐帧判定表 + C/D 表 + FN07 回答 | offline | JUDGMENTS_R1.md §1–§5 | PASS | 082829 f86–94(9)+f97–100(4)、082906 f103–107(5) 逐帧人/P1/姿态；C×6、D×6 |
| GT-D3 标注来源声明 | offline | JUDGMENTS_R1.md §6 | PASS | AI 视觉标注（OpenCode/mimo-v2.6-pro）；人工抽检栏留空；FN06/FN07 不自动解 BLOCKED |
| GT-D4 returns 追加（只追加） | offline | 本文件 | PASS | 未改历史回传 |
| M1 双证据（截图+簇特征同帧号） | offline | build_annotation_r1.js assertShot/簇特征映射自检 | PASS | 74/74 标注双证据齐；95 截图 vs 特征帧号对齐；无证据帧不判（0 违例） |
| M2 方法顺序（建模→视觉→判定→落标注） | offline | probe_gt_r1.js → shots/ → JUDGMENTS → API | PASS | 未跳过建模；判定引用簇特征+截图双证 |
| M3 工作台契约与红线 | offline | gt_api_log_r1.json | PASS | save 200×4；freeze 400×4（"冻结前需对象全部 reviewed"，AI 不冒充人工、无 GT_V* 冻结版）；export 200×4；captures/、data/ 只读；无 commit/push/reset/clean |
| FN06 | device/语义 | 验收表原文：可信人物GT窗口缺失→语义项 BLOCKED | **BLOCKED（维持）** | 本标注为 AI 标注非人工 GT，不自动解除 |
| FN07 | offline/语义 | 验收表原文：未知GT不强标，失败留存 | **BLOCKED（维持）** | 本轮 GT 已回答"真人丢失 vs 静物排除"（18 帧真人丢失），但状态解除须验收表明文 |
| AD08 / 设备 / 物理 / EXE | device | — | NOT_RUN | 本轮无设备/物理/部署动作 |

### 未闭合与限制

- 本标注为 **AI 视觉标注 + 簇特征互证**，非人工 GT；不构成人体 P/R/F1、真实跌倒或设备结论；FN06/FN07 维持 BLOCKED，解除须验收表明文 + 人工抽检。
- 工作台未出 GT_V* 冻结版：source=model/unreviewed 待人工在工作台 reviewed 后 freeze（闸门拒绝已留痕，防 AI 冒充人工）。
- R1-person-rise 的"单调上升"按连续簇语义应用：082829 f89–94、082906 f97–98 身高回落为同一连续簇内俯身波动（逐帧身高序列如实保留），身份不断裂——该解释如与验收口径不符，按验收口径重裁。
- 类内细分（家具 vs 背景）为次级判断（class_confidence=medium），人/非人判定 high；范围外（082623 人体、111738 其他簇、A/B 范围外帧）本轮未标注。
- 截图用页面原始着色（人物高亮默认关）；C/D 特写因暗点在默认 LUT 下近黑改用 lut2 档（工作台自有着色选项，非人物高亮）；桌面窗口中途不可见一次（工具拒截图），经用户恢复后补齐，无缺帧。
- 未做：人工抽检、板端/设备/物理/EXE/部署、跨场景、真实跌倒；无 Git 写、无训练、无采集；gt_store 仅四会话 draft 新增。

### 交给Codex独立复审

- 现行验收表与本轮变更记录：ACCEPTANCE_V2.md（未改）；本轮变更 = 新证据目录 + gt_store 四 draft + 本追加。
- 根因诊断/完整入口检查证据：JUDGMENTS_R1.md §5（FN07）、§3（窄凳遮挡事实）、§4（杆状物并簇时序）；diag r1 PROBE_REPORT/FIX_PLAN_R2 只读引用。
- 源码差异与SHA证据：生产零改动；MANIFEST_R1.json（全部交付件）、gt_api_log_r1.json（API 留痕）、SOURCE_FINAL.json 冻结源未动。
- 原始日志索引：gt_cluster_features_r1(_r1b).json、shots/ 95 张、gt_api_log_r1.json、workbench_exports/。
- 当前工单下一步：Codex 按 FIX_PLAN_R2 顺序 2（Fix 3 目标级指标，锚定本 GT）→ Fix 1+2；人工抽检后在工作台 reviewed→freeze 出 GT_V*；FN06/FN07 由验收者按验收表裁定。


## 2026-10-16 dev_r2 GT消费补充 R1（AI未审核/部分范围）

### 本轮信息

- 工单REPLAY-FRESH-NEXT-01，Codex消费实现，状态SUBMITTED；FN06/FN07维持BLOCKED，不是工单ACCEPTED。
- 依据用户补充的gt r1交付，消费原标注，不生产/修改GT。唯一验收仍为dev_r1/ACCEPTANCE_V2.md，SHA256 `f666a4720002c1d5251475242a7ef2efdf6ccba73c3a38c6c140912ff6988eff`；FIX_PLAN_R2不变。
- 起始branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`。BASELINE.json记录含未跟踪的工作树状态、GT全部文件SHA、生产源码/测试SHA、回传原前缀SHA。
- ponytail实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，本会话此前已读full，持续使用。
- 执行：本机Node/Python stdlib，工具检查Python `-B -W error`。GT作者为OpenCode AI/model/unreviewed（mimo-v2.6-pro）；人工抽检为空、无冻结版。本轮未启动标注CLI或GT API。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 入口/消费者/转换 | 实施位置 | 保留行为 |
|---|---|---|---|---|
| Fix3/FN02/FN09 | 三索引域不同，直接以工作台compact当原始点序会错配 | annotation→导出对象→特征簇→source行→score | gt_consume_r1/adapter.js；74条原帧raw↔compact值级契约核查 | GT只读，normalized对象只在内存中，不落GT产物 |
| FN06/FN07 | GT是AI未审核、只标部分帧/目标，无U不等于完备 | complete=false→冻结评分器→全会话null；匹配明细→条件范围表 | CURRENT_AI_SCORES.json / REPORT.md | 不将未标帧当负样本，不把条件评价升级成人审P/R或正式验收 |
| FN03假目标归因 | GT杆样本与旧birth07误认领轨迹1/5/6/9缺点集对应 | 六控制回放→标注N掩码匹配→来源缺口 | CONTROL_AI_SCORES.json / POLE_SCOPE_GAP.json | 不修改GT类别/身份、不跨帧补标；这些假轨迹的全生命周期语义归因仍BLOCKED |
| FN07原失败核验 | 认领帧代理可能掩盖目标是否匹配 | 精确旧base原字节回放→当前同source对比 | evaluate_control.js；6个隔离进程/执行元数据 | 不替换生产文件，原base仅加空backfill字段作评测兼容；放宽门只在诊断进程内存 |

### 实际变更与入口

仅新增 `docs/human_capture/evidence/2026-10-16_traditional_perception_dev_r2/gt_consume_r1/` 的消费工具、6控制回放、24组评分与报告，以及本回传/当前索引的追加记录。
生产源码/测试、既有score/evaluate脚本和GT源均未改；当前生产SHA仍 `2f2faa1a193d63b53f81cadec3177378aa2d5e41f087eca81b972a9767055f4e`，27组引擎测试快照不变。
gt r1清单113文件、3历史引用、4会话原始meta/points SHA全通过，annotation SHA为 `d98912a3932ca3870a5a69f0feead4b30290909bb626593e0c9fe539f4c93d1b`。

### 逐条验收（本补充执行记录，不覆盖前轮已执行事实）

| 验收ID | 本补充状态 | 证据与边界 |
|---|---|---|
| FN01 | PASS | 4消费会话原始SHA、GT清单/引用、原始帧号/时间与索引核对；其它会话沿用此前冻结记录 |
| FN02 | PASS | 74标注object_id/身份/类别/时间/点集/来源一致，原始source行匹配可追溯 |
| FN03 | PASS（软件诊断） | 窄凳抽样点集反例成立；111738杆样本不覆盖误认领1/5/6/9，相关真实归因BLOCKED |
| FN04 | NOT_RUN | 未重跑默认完整矩阵推理；仅消费既有24冻结输出及6诊断控制，先前软件自验记录保留 |
| FN05 | NOT_RUN | 本补充不做221808页面着色实录；先前软件自验不改 |
| FN06 | BLOCKED | 082623本批仅窄凳样本，无主会话人体正标；且无人工审核/冻结 |
| FN07 | BLOCKED | 两窗口AI条件点集评价完成，不能替代可信完整GT；既有在线失亮和新3D范围漏匹配保留 |
| FN08 | NOT_RUN | 未改页面，不重复浏览器/换会话操作 |
| FN09 | PASS | 新输入/输出、命令/日志、来源声明、保护SHA和追加回传齐 |
| FN10 | NOT_RUN（本消费工具） | 不把先前生产代码REVIEW_PASS当新增消费工具独审；生产源码未再变 |
| AD01 | NOT_RUN | 无新架构实施；原架构软件检查沿用前轮 |
| AD02 | NOT_RUN | 无外部案例重查 |
| AD03 | PASS（消费对照） | 已有24组XY/3D输出按同GT source掩码复评，索引不造点 |
| AD04 | NOT_RUN（引擎重测） | 引擎/27用例未变；新增adapter IDSW段/缺标/索引坏值检查PASS |
| AD05 | NOT_RUN | 姿态词表仅保留，不新增映射准确率或改事件逻辑 |
| AD06 | NOT_RUN | 不补真实跌倒语义结果 |
| AD07 | NOT_RUN | GT截图只读引用，未做新浏览器截图/性能测量 |
| AD08 | NOT_RUN | 人审/完整目标/泛化语义仍BLOCKED；设备/物理/EXE/部署未运行 |

### 实测与可跑检查

- `node .../gt_consume_r1/adapter.test.js`、`node .../score.test.js`：exit0；索引映射/无效点/坏索引、部分GT全会话null、条件IDSW段与负类0.5边界检查。
- `python -B -W error .../gt_consume_r1/run_controls.py`：6控制exit0，CONTROLS_EXIT.json / *.execution.json。原base复现82/67认领帧；窗口点集匹配0/13、0/5。
- `node .../gt_consume_r1/consume.js current`：24组评分exit0，其中12组有本批标签范围，其余未标；全部全会话目标指标BLOCKED。
- `node .../gt_consume_r1/consume.js controls`及`check_results.js`：exit0；CURRENT_AI_SCORES/CONTROL_AI_SCORES、INDEX_MAPPING_CHECK、POLE_SCOPE_GAP。
- XY已标人体范围：082829在线12/41、离线41/41；082906在线10/21、离线21/21。小窗口在线2/13、2/5，离线13/13、5/5；provisional各1/1转正，延迟3.007031s/29f、1.650004s/16f。条件IDSW与MISMATCH均0，不外推。
- 3D已标完整范围离线39/41、20/21，缺082829 f70/71、082906 f114；小窗口仍13/13、5/5，不以局部成功冒充整段成功。
- 默认在6个窄凳N样本无confirmed轨迹匹配；birth05诊断三会话各匹配一条（#1/#1/#3）。只报告抽样非人关联，不填全会话假轨迹总数。
- birth07实际认领1/5/6/9，但四杆的六个N样本都无≥0.5关联；不能从GT报告的叙述替代点集匹配结论，未对未知帧/其它簇补标签。

### 未闭合与交给独立复审

报告/24组条件表：`gt_consume_r1/REPORT.md`。AI范围内评价可复算，正式FN06/FN07仍BLOCKED；全生命周期假目标总数、实际误确认轨迹的P/N/U、未标会话/主体、真正独立人审仍不足。
GT全部源文件与生产/测试SHA未变，见PROTECTION_AFTER.json；原回传前缀保持，未写data/captures/GT，无commit/push/reset/clean、模型/训练/网络/驱动/板端/采集部署。
本补充工具独立复审NOT_RUN；可按原唯一验收v2审查新adapter、条件范围界限及POLE_SCOPE_GAP，不自动启动新标注或下一工单。

---

## 2026-10-16 REPLAY-FRESH-NEXT-01 fix3 r1 实施回传（Fix 3 目标级评分，锚定 gt r1 GT）

### 本轮信息

- 工单/轮次/执行者/时间：REPLAY-FRESH-NEXT-01 / fix3 r1 / OpenCode（opencode-go/mimo-v2.6-pro，本轮唯一生产 writer，用户"继续开发传统聚类"直派）/ 2026-10-16。
- 验收表路径/版本/SHA：唯一表 `docs/human_capture/evidence/2026-10-16_traditional_perception_dev_r1/ACCEPTANCE_V2.md`（FN01–FN10/AD01–AD08，v2）**未改**；现行设计 `2026-10-16_traditional_perception_diag_r1/FIX_PLAN_R2.md` §4 顺序 2。
- 当前证据目录：`docs/human_capture/evidence/2026-10-16_traditional_perception_fix3_r1/`；入口 README.md → RESULTS.md → TARGET_LEVEL_TABLES.md。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；工作树按基线即脏（既有 M/?? 为他人/历史改动）。本轮写入仅=新证据目录 + 本回传追加 + human_capture README 顶部登记；**生产代码零改动**（traditional_perception.js `2f2faa1a…`、human_pipe_lib.js `8b50a221…`、fresh_map_lib.js `6bc0e2de…` 与 dev_r2 R4 记录一致），gt_store draft / captures / gt_r1 证据只读未改。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具，full）。复用 dev_r2/score.js backfill 与 run_regression.py；新逻辑均有可跑检查；无新增依赖。
- 状态：**SUBMITTED**；AI 标注锚定的本机代理评价，不构成人工 GT/真实跌倒/设备结论；FN06/FN07 维持 **BLOCKED**，AD08 NOT_RUN。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| Fix3/FN02/09 | 评分缺真实 GT 输入：dev_r2 仅有 normalized adapter 软件自验，无 draft→源行索引适配 | gt_store draft、evaluate.js claims/members（源行域）、目标级评价 | `gt_target_score.js`：compact-local→原始行号双重值级自检（draft 解码==features idx_compact_local；points.bin 独立重算==features idx_raw_frame），74/74 对象全过；SID/meta/points SHA 强校验 | 完整人工 GT 路径仍走 dev_r2/score.js；GT 文件只读 |
| FN07（窗口语义） | 低姿起始在线不点亮与"静物正确排除"混淆 | FN07 退步窗口、页面认领口径 | §4 冻结定义落地：P 覆盖按 GT 目标逐帧聚合、在线/回填/延迟三分口径 | 在线不补染；假目标总数 BLOCKED；未知不推断 |
| 阳性对照 | 评分器需在已知反例上证明假目标捕获 | 窄凳 79/90/122、杆状物 179/186（probe_false_r1） | `evaluate_diag.js`（诊断降门副本）+ §5 表 | 诊断组不代表默认参数；失败如实保留 |

### 实际变更（均在新证据目录；生产零改动）

| 文件 | 用途 |
|---|---|
| `gt_target_score.js` / `gt_target_score.test.js` | GT 适配器+稀疏 GT 评分器（§4 冻结口径）+ 15 组断言 |
| `run_fix3.js` | 8 组评分批跑、汇总表、首尾保护清单 |
| `evaluate_diag.js` + `opt_birth05/07.json` | probe_false_r1 已知反例配置复现（诊断专用） |
| `GT_<sid>.json`×4 / `SCORE_*.json`×8 / `TARGET_LEVEL_TABLES.md` / `TARGET_LEVEL_METRICS.json` | 适配与评分产出 |
| `regression_fix3.json/.log` / `PROTECTION.json` / `MANIFEST.json` / `RESULTS.md` / `README.md` | 回归、保护、SHA、逐项自验、索引 |

### 逐条验收（对照 ACCEPTANCE_V2；沿用=未触碰保留前记录，详见 RESULTS.md）

| ID | 本轮 | 证据/边界 |
|---|---|---|
| FN01 | PASS（沿用+核对） | PROTECTION.json：5 会话 meta/points、4 draft、gt_r1 3 证据、3 生产源首尾 SHA 相等 |
| FN02 | PASS（增强） | SCORE_*.json 逐帧 matches/mismatches/u_hits/unannotated、GT 索引=原始源行可追溯 |
| FN03 | 部分 PASS/部分 UNKNOWN | 窄凳假目标 GT 锚定阳性对照 79/90/122 精确复现；杆状物 f2/f100 不可判（f2 无 confirmed 认领、f100 与 B1/B2 零重叠）→ UNKNOWN 保留 |
| FN04 | PASS（沿用+GT锚定） | 111738 固定 221808 默认 dev2c 0 认领帧；4 个 N 目标 0 被认领 |
| FN05 | PASS（沿用） | 221808 空场 0/272（dev_r2 记录）；空场无标注不改判 |
| FN06 | **BLOCKED（维持）** | 真值=AI 视觉标注（model/unreviewed）非人工 GT |
| FN07 | **BLOCKED（维持）** | GT 锚定窗口对照已交付：082829 缺失 f70–98（29 帧）、082906 缺失 f95–105（11 帧）逐帧为 P1 真值（low/rising）；三口径与 dev_r2 逐项一致（2/13、13/13、3.007031s/29帧；2/5、5/5、1.650004s/16帧）；解除须验收表明文+人工抽检 |
| FN08 | NOT_RUN（沿用） | 零页面改动 |
| FN09 | PASS | 19 套回归 exit0 0 失败 + 新测试 exit0 + PROTECTION equal + 生产 SHA 不变 |
| FN10 | NOT_RUN | 本轮新工具未独立只读复审；dev_r2 FN10 记录保留不覆盖 |
| AD01–AD03 | PASS（沿用） | 链路拆分/案例借鉴/XY-3D 对照未动 |
| AD04–AD06 | PASS（增强） | IDSW/真秒/回填口径入评分器并单测；GT 姿态真值入窗口表；假目标对照入 §5；真实跌倒 TP/召回仍 BLOCKED |
| AD07 | NOT_RUN（沿用） | 无浏览器/页面性能 |
| AD08 | NOT_RUN | 无设备/物理/EXE/泛化动作 |

### 实测命令与退出码

`node gt_target_score.test.js` exit0；`node evaluate_diag.js …` ×4 exit0（claimed 174/159/291/179）；`node run_fix3.js` exit0（8 组、PROTECTION equal=true）；`python run_regression.py regression_fix3` exit0（19 套 0 失败）。默认 4 组复用 dev2c 预测，内嵌源SHA==当前生产源校验通过后才评分；输入/输出均新文件（wx）。

### 未闭合与限制

- 假目标**总数**保持 BLOCKED（表中仅"范围内已判定"计数）；082623 人体无标注→覆盖/假目标不可判；杆状物假目标须补标注帧（新标注轮另派）。
- IDSW 分段沿用 score.js 既定口径（间隔≥3帧开新段），与 §4"≥3帧覆盖中断"边界差一读法已录 RESULTS，未改口径。
- AI 标注非人工 GT；FN06/FN07 维持 BLOCKED；无数据/GT/板端/驱动网络/模型写、无采集/训练/部署/Git 写。
- 未做：人工抽检、独立只读复审（FN10）、浏览器/性能（AD07）、设备/物理/EXE（AD08）、Fix 1+2 与冻结对照（FIX_PLAN_R2 顺序 3/4）。

### 交给 Codex 独立复审

现行验收表 ACCEPTANCE_V2（未变）+ 本轮变更新证据目录 34 文件（MANIFEST.json 全量 SHA）；根因/口径见 RESULTS.md；评分定义=FIX_PLAN_R2 §4 冻结+稀疏策略；下一步按顺序 3：Fix 1+2（结构旁路/运动特征），后冻结对照定默认版本。
