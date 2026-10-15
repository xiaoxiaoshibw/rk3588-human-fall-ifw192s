# B01 收口路径独立审计 · 2026-10-14

## ① 身份独立性声明

本审计由独立审计员（B 组，Kimi k3）执行，与作者链（Codex/kimi 助手/Claude）无关。全程只读：未修改任何生产代码、测试、配置、GT、WORKFLOW.md、README.md、REVIEW_LOG.md 或任何既有证据文件；仅新建本目录与本报告。对文档自报状态一律不信任，关键事实（控制台实际接入版本、adoption 字段、点数/比例、gate 数值）均对照实际文件/代码核实。本报告不构成对任何工单的 ACCEPTED 判定。

## ② 证据清单（实际读取）

| 类型 | 路径 |
|---|---|
| 权威入口 | docs/human_fall/WORKFLOW.md、docs/human_capture/README.md、docs/human_fall/REVIEW_LOG.md（顶部） |
| 工单 1 | docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/{ACCEPTANCE_V1.md, FINAL_REPORT.md, CURRENT_DELIVERY_INDEX.md, INDEPENDENT_REVIEW.md, REVIEW_QUEUE.json} |
| 工单 2 | docs/human_fall/evidence/2026-10-13_hf_real_0{1,2,3}_r1/{ACCEPTANCE_V1.md, FINAL_REPORT.md}；returns/HF-REAL-0{1,2,3}.md |
| 工单 3 | docs/human_fall/evidence/2026-10-13_hf_console_01_r1/{ACCEPTANCE_V1.md, FINAL_REPORT.md} |
| 工单 4 | docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1/{ACCEPTANCE_V1.md, ACCEPTANCE_FINAL.json, FINAL_REPORT.md} |
| 工单 5 | docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1/ACCEPTANCE_V1.md；.../2026-10-14_hfus_pointset_actions_r2/{ACCEPTANCE_V2.md, EXPERIMENT_COMPARISON.json, FINAL_REPORT.md}；returns/HFUS-POINTSET-ACTIONS-01.md |
| 工单 6 | docs/human_capture/evidence/2026-10-13_hc_joint_local_r{1,2}/{ACCEPTANCE_V1.md, REPORT.md}；returns/HC-JOINT-LOCAL-01.md |
| 工单 7 | docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/08_final_closeout.md |
| 代码事实 | pc_apps/console/console_gui.py、console.html、git diff/log、sidequests/human_fusion_lab_next/real_fall/{r02,r03,r04}、pointset/r01 |

## ③ K1 逐工单表（状态字面值 / 未通过验收 ID 与出处 / 卡点分类 / 翻盘动作）

| # | 工单 | 当前状态字面值（出处） | 仍未通过的验收 ID（出处） | 卡点分类 | K2 最小翻盘动作 |
|---|---|---|---|---|---|
| 1a | HF-CLOSE-01 | SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED（ACCEPTANCE_V1.md 尾段） | CL01 部分 FAIL：console 仍 r02「完整入口 FAIL」；CL02/CL03：r04 全表未通过（ACCEPTANCE_V1.md 表行；INDEPENDENT_REVIEW.md ST01 行） | [软件可复审]×console 入口；[需独审结论]×r04 全表 | 有：把 console fall 入口统一切到当前授权源（工作树已是 pointset/r01，见 K3），重打 EXE/ZIP 并 `--check-startup` 复验——消掉 ST01/CL01 的 console 缺口。r04 全表无法廉价翻盘 |
| 1b | HF-DATA-01 | SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED（同上） | DT01：S9 BLOCKED；DT03：人工审核 BLOCKED（ACCEPTANCE_V1.md；REVIEW_QUEUE.json human_review_completed=false） | [需人工GT]×31 POINT+155 ROW+9 窗口+164 帧；[需用户决策]×S9 强绑或放弃 | 有（仅 DT03）：队列里 S8→HF231 帧里先做 31 POINT/155 ROW 两小项的人工点击（工具已修、浏览器复验过）；S9 与 GT 资格无廉价动作 |
| 1c | HF-BG-01 | SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED（同上） | BG02 FAIL：v2 静立 C=54069/57045=94.783%<95%、近地 C=4/1163；BG01：生产现行 P 完整等价 A/B BLOCKED；BG03：新 registration REJECTED、W03 gate BLOCKED（ACCEPTANCE_V1.md；FINAL_REPORT 数值表） | [需人工GT]×家具/低位身份；[需独审结论]×等价 A/B 流程资格；[需设备物理]×W03 gate 与 VALID | 无廉价动作。最便宜的半步是复用本轮诊断 A/B 在已有 S8 人工窗口结果上重算 B/C 保留率，把 BG02 从「缺 GT 的 FAIL」收敛成「带 GT 的 PASS/FAIL」 |
| 2a | HF-REAL-01 | SUBMITTED 未 ACCEPTED（WORKFLOW 2026-10-13 条目；REVIEW_LOG） | RF02：093958 FAIL→已被 HF-REAL-03 判 DATA_BAD（不再补救）；RF08：独审 NOT_RUN、真人 GT/泛化 BLOCKED | [需独审结论]（已部分满足：10-14 独审覆盖 r04 但未单独审 r01）；[需人工GT] | 有：接受 093958=DATA_BAD 定性为 RF02 的最终答案（HF-REAL-03 证据足够），剩余 GT/泛化转 BLOCKED 挂账——工单语义层面可判 STOPPED但不 ACCEPTED；要 ACCEPTED 无廉价动作 |
| 2b | HF-REAL-02 | SUBMITTED 未 ACCEPTED（同上） | RS04 FAIL（f10 家具残留）——HF-REAL-03 用 v3 证伪「盒内有家具」、但明确「RS04 关闭由指定独审决定」；RS05 完整解剖骨架 BLOCKED；f47/109/118 轴歧义 BLOCKED | [需独审结论]×RS04；[需人工GT]×RS05 | 有（RS04）：指定一轮只读独审，依据 r03 的 404/404 落人区证据与 10-14 独审「不关闭」附记，正式裁定 RS04（本审计倾向「不可判为 PASS、可判为重定性」，理由见 K3）。属一次评审动作而非研发动作 |
| 2c | HF-REAL-03 | SUBMITTED 未 ACCEPTED（同上） | RS-C FAIL（视觉盒被证伪——这是任务本身的正确结果）；RS-F BLOCKED（215623/215643/233658 原始点本机/板端均无）；RS-H BLOCKED/NOT_RUN（独审、GT、设备） | [需独审结论]；[需人工GT]；数据缺失不可补 | 有（RS-C/RS-D/RS-E 的判定采纳）：独审确认三个结论性判定（盒证伪、093958 DATA_BAD、P 臂吞人 97.6%）即可把该单定性为「排查完成、结论文档化」——这三个判定是它的真实贡献。GT/泛化无廉价动作 |
| 3 | HF-CONSOLE-01 | SUBMITTED 未 ACCEPTED（ACCEPTANCE_V1.md；FINAL_REPORT CI01–05 PASS/CI06 BLOCKED） | CI06：算法精度 BLOCKED、独审/设备/物理 NOT_RUN；且其交付的 fall 入口（real_fall/r02）已被后续 HFUS-POINTSET-ACTIONS-01 取代（工作树 console_gui.py 指向 pointset/r01）——本单功能层面「已完成即过时」 | [需独审结论]；[需用户决策]×是否承认被覆盖 | 有：把本单定性为「被 HFUS-POINTSET-ACTIONS-01 的集成覆盖、功能由新入口继承」并登记；CI06 的算法精度本来就与入口无关，无廉价动作但也不需要 |
| 4 | HFUS-POINTSET-01 | SUBMITTED_NOT_ACCEPTED（ACCEPTANCE_FINAL.json） | GT01 BLOCKED；DEV01 NOT_RUN；PS05 BLOCKED（无解剖标注）；PS06 纯人体/关节精度 BLOCKED；PS07 S8 ROI 坐标人工核对 pending；independent_review=NOT_RUN | [需人工GT]×纯人体/部位；[需独审结论]；[需设备物理] | 有（PS07）：S8 ROI 坐标人工核对是 31 POINT 队列的旁支，一次人工动作可闭合。其余取决于 GT 与独审 |
| 5 | HFUS-POINTSET-ACTIONS-01 R1→R2 | R2 SUBMITTED 非 ACCEPTED（FINAL_REPORT.md 尾段）；R2 未在 WORKFLOW/README 顶部登记（见 K6） | R203/R204/R205 自验 PASS 但 adoption=EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE（EXPERIMENT_COMPARISON.json，五个方案逐字核实）；中央点集完整率/家具污染率/身份关联/方向/解剖误差全 UNKNOWN（FINAL_REPORT R2） | [需人工GT]×f192、119/140/232、38 歧义帧端部身份；[需独审结论] | 有（任务边界）：R206「同页旧/新切换、旧默认不变」已实现——承认实验期已结束、结论已写成文档（FINAL_REPORT R2 + FINAL_PRESERVATION），不再追加实验轮。GT 与独审另列 |
| 6 | HC-JOINT-LOCAL-01 R1+R2 | R2 SUBMITTED 未 ACCEPTED（ACCEPTANCE_V1.md V2 表 6 行自验 PASS；REPORT 尾部） | 雷达已收区间缺号 126（REPORT R2 实测：899 相机/139 雷达帧）；真实断流重接仅合成验证；时空标定 NOT_RUN；独审 NOT_RUN | [需设备物理]×长时断流/吞吐；[需独审结论]；缺号 126 是一次实测的完整性未过，属 [软件可复审]+[需设备物理] 混合 | 有（缺号 126）：一次长时（≥30 min）真实双流录制复测即可判定是偶发还是系统缺陷——这是最便宜能把「完整性未过」转成可判的动作。独审另派 |
| 7 | HR-W03 R39-CLOSEOUT | REWORK_REQUIRED · SUBMITTED 未 ACCEPTED（08_final_closeout.md §1、§6 表） | T38-05 FAIL（shadow exit1）；T38-06 FAIL；S4/S7 FAIL；gate 49.652981%<50%（§4）；31 POINT 语义 UNKNOWN；T39 未授权；HP02 BLOCKED | [需人工GT]×31 POINT+155 ROW；[需用户决策]×gate 放宽或换 pair；[需设备物理]为空 | 无廉价动作。gate 差 42 keep/70 raw，理论上只需换更接近的 reference 或人工确认 benign 边界——但这是用户才能拍的决策；GT 队列与工单 1b 共用 |
| 8 | 权威入口对照 | WORKFLOW 顶部 2026-10-14 HFUS-POINTSET-ACTIONS-01 条目 / README 顶部同日条目 | R2 只在 human_capture README 无顶部登记（见 K6） | [需用户决策]×登记 | 有：在 README 顶部补一行 R2 登记（一字不改语义） |

卡点分类汇总：**需人工GT** = 6 单（1b/1c/2b/2c/4/5/7 的 GT 子集）；**需独审结论** = 8 单全部；**需设备物理** = 3 单（1c W03、6、以及所有「DEV01/部署」项）；**需用户决策** = 2 单（1b S9、7 gate+README 登记）；**软件可复审** = 1 单（1a console 入口）。

## ④ K3/K4 事实核验

### K3.1 控制台当前回放到底接的是 r02 还是 r04？

**两者都不是（在已提交的快照上）；工作树是 pointset/r01。**核实链：

1. **已提交的 HEAD 版**（git show 得的 `pc_apps/console/console_gui.py`）= line 51 `sidequests/human_fusion_lab_next/real_fall/r02`。这正是 2026-10-13 HF-CONSOLE-01 交付的版本，其 FINAL_REPORT/验收表也写「控制台从当前仓库定位 r02」。
2. **当前工作树未提交修改**（`git diff` 实测工作树 diff）：line 51 已改为 `sidequests/human_fusion_lab_next/pointset/r01`，console.html 卡片描述同步改为「八段动作 · 中央人体 / 点支撑骨架 / 倒地姿态候选」。这是 HFUS-POINTSET-ACTIONS-01 R1 的集成版本。
3. **r04 从未被接入 console**：`grep -n "r04" pc_apps/console/*` 无命中（r04 只被 2026-10-14 收口审计当作源码研究对象；CONSOLE-01 交付是 r02，ACTIONS-01 交付是 pointset/r01）。
4. **待审证据自报「console 仍 r02」是滞后陈述**：docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md 「当前 pc_apps/console/console_gui.py 第 51 行仍指向 r02」、CURRENT_DELIVERY_INDEX.md 「console 当前源码仍 r02」与实际工作树不符——该目录自述断言的是他自己没改动控制台，但同一日 ACTIONS-01 R1（更早提交的工单）已把工作树切到 pointset/r01。两份同日证据相互打架，属登记滞后而非作者造假。

**结论**：控制台**实际当前工作树接入 pointset/r01**（含 actions.py），不是 r02 也不是 r04；r04 只存在于研究证据目录，从未进入 console 入口。HF-CLOSE-01 声称的「console 缺口 = 仍 r02」是以它自己开工时刻快照为基准，untracked 修改早于它但未 commit。

### K3.2 RS04 按 HF-REAL-03 + 10-14 独审是否已具备关闭条件？

**不可判为 PASS，可判为「重定性为不需关闭的 FAIL」——即转为 BLOCKED 挂账；关闭本身不可判，缺的是一轮把该问题从「当前工单语义」里移除的用户裁决 + 在该裁决下的独审签字。**理由：

- HF-REAL-02 的 RS04 原定义是「同一初始化目标持续关联，显示真实 bbox/轨迹/失联 UNKNOWN，不靠骨架外观当人体证明」。f10 家具残留被原作者判 FAIL 是审慎自定。
- HF-REAL-03 的 RS-C 证据：v3 盒剔除 404 点全部落 HF-REAL-01 视觉人区、v2 target 在 f10 不含盒内点——推翻的是「f10 内有家具条带混入 target」这一个具体成因假设；并未证明「v2 target 在 f10=纯人体」（另一可能成因：人肩/裙带联通路径未被排除）。
- 10-14 独审（INDEPENDENT_REVIEW.md）明确：「404/404 视觉区重叠只是 ROI 事实，不是人体真值…RS04 原 FAIL 与身份 BLOCKED 保留，不关闭。」
- 三方共识：RS04 的 FAIL 不能被推翻、也不能被直接关闭。**把它从「阻挡收口」变「已定性挂账」，唯一需要的动作是用户裁决「RS04 改为『判定：成因假设被证伪但身份 GT 缺失，保留 UNKNOWN』」+ 一轮独审照顾改判。**在拿到该裁决前，RS04 的成本效益最高处理方式是**写进 UNKNOWN 清单、从 HF-REAL-02 的「未通过」移入「语义不可判」**——这是文档动作而非研发动作。

### K4.1 R2 是否已完成实验期？adoption 字段是什么？基线保留意味着什么后续动作？

**已完成实验期**。R2 FINAL_REPORT 末段写明「状态 SUBMITTED，自验完成，非 ACCEPTED」「五个新方案均为实验对照」「默认保留 R1」；EXPERIMENT_COMPARISON.json 实测：

- `default = "baseline"`
- `summary.point12.adoption = "EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE"`（其余 point20 / component20 / low20 / axis 同字面）
- `tracking_policy = "baseline causal track anchors held constant to isolate member recovery"`
- `holdout_not_tuned = true`

**adoption 字段的字面值 = EXPERIMENT_ONLY_NO_IDENTITY_EVIDENCE，五个方案全部一致**——即本轮所有候选方案都因为没有独立身份 GT 而不晋级为新默认。

**基线保留意味着什么后续动作**：
1. **控制台 EXE/快捷方式二进制不改**：R2 FINAL_REPORT 明确「未采用新默认，因此没有重打包或替换 EXE/快捷方式，二进制 SHA 与 R1 相同」——即 ACTIONS-01 的 R1 集成状态仍是唯一对外交付；
2. **页面保留实验开关**：用户可以切换看新方案，但「默认证据」停留在 R1 行为；
3. **后续研发的入口固定**：任何想动默认的第三轮工单必须绕过身份 GT 这一硬门——要么补 GT 要么用户裁决；在那之前，「基线保留」**意味着 R2 已终结，不再投入下一实验轮，除非 GT 先补**。
4. **R2 未登记**：ACCEPTANCE_V2.md 存在但 WORKFLOW.md / human_capture README.md 顶部都没有 R2 条目（见 K6）。

## ⑤ K5 推荐收口顺序（先关谁、依赖谁）

顺序按「最小代价先关掉、让下游解锁」排序；*依赖* 列给出先决动作。

| 序 | 工单 | 先做什么 | 依赖谁解开 |
|---|---|---|---|
| 1 | **HFUS-POINTSET-ACTIONS-01 R2 登记** | 在 human_capture README 顶部补一行 R2 条目 | 无——文档动作，解锁 K6 全部滞后 |
| 2 | **HF-CONSOLE-01** | 定性「被 ACTIONS-01 覆盖」、登记其交付物由新入口继承 | 序 1——登记后实现「R1 集成 = 唯一界面」的自洽 |
| 3 | **HF-DATA-01 的 DT03 子项**（31 POINT + 155 ROW 人工点击） | 一次性人工标注会议（队列工具已就绪） | 序 1（README 登记后所有 GT 队列可引用） |
| 4 | **HF-REAL-02 的 RS04 定性**（写进 UNKNOWN 挂账） | 用户裁决「成因假设被证伪 + 身份 GT 缺失，保留 UNKNOWN」，独审签字 | 无——纯文档动作 |
| 5 | **HF-REAL-03** | 把 RS-C/RS-D/RS-E 三个判定采纳为结论文档；RS-F 转 DATA_BLOCKED 挂账 | 序 4——RS04 定性后 HF-REAL-03 不再有未完成派发任务 |
| 6 | **HF-REAL-01** | 采纳 093958=DATA_BAD 作为 RF02 最终答案 | 序 5——依赖 HF-REAL-03 结论被认可 |
| 7 | **HFUS-POINTSET-01 的 PS07 子项**（S8 ROI 坐标核对） | 一次性人工复核 | 序 3 同一人工会议可顺带完成 |
| 8 | **HC-JOINT-LOCAL-01 R2** | 一次 ≥30 min 真实双流长录复测 + 一轮只读独审 | 序 3 之后的空档；独审独立 |
| 9 | **HR-W03 R39**（gate 49.65%） | 用户裁决 reference/换 pair/放宽 gate 三选一 | 序 3 的 GT 会议先解决 31 POINT |
| 10 | **HF-BG-01 / HF-CLOSE-01**（r04 收口 + console 统一） | 先把 console fall 入口正式切到 pointset/r01 并重打 EXE/ZIP，再复审 r04 全表 | 序 2+3+4 全解后才进入；独审资源最多 |
| 11 | **HFUS-POINTSET-ACTIONS-01 本体** | 不主动收口——已进入「等待身份 GT 前不再实验」状态，仅登记 | 序 3 GT 大规模铺开之前不要动 |

**应该现在停掉（不再投入）的工单**：HF-CONSOLE-01、HFUS-POINTSET-ACTIONS-01 R2 之后的继续实验、HF-REAL-03（三个判定已采纳即完）、以及任何「绕过 GT 门继续做局部恢复/骨架精度」的同族研发。它们要么已被覆盖、要么硬卡 GT、要么已得出所有能得出的结论。

## ⑥ K6 发现的登记矛盾

1. **HFUS-POINTSET-ACTIONS-01 R2 未登记**：docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/ACCEPTANCE_V2.md、FINAL_REPORT.md、EXPERIMENT_COMPARISON.json 全部已存在；docs/human_fall/WORKFLOW.md 顶部只有 ACTIONS-01 R1 条目、docs/human_capture/README.md 顶部也只有 R1 条目——**R2 完成的事实未在任何权威入口顶部登记**。
2. **HF-CLOSE-01 自报「console 第 51 行仍指向 r02」与实际工作树不符**：FINAL_REPORT.md 与 CURRENT_DELIVERY_INDEX.md 都断言 r02，但工作树实际已是 pointset/r01（某 ACTIONS-01 工单已切）、且 git 未提交。两份 2026-10-14 同日证据相互矛盾；应以工作树为准，CLOSE-DATA-BG 那个断言是以其自身开工时刻快照为基准的过期陈述。
3. **HF-CONSOLE-01 与 HFUS-POINTSET-ACTIONS-01 交付同一卡片**：console.html 只留一个「骨架与倒地检测」卡且 URL 来自 `_start_fall_server()`；CONSOLE-01 交付时指向 real_fall/r02、ACTIONS-01 交付时改为 pointset/r01——后单覆盖前单，但两单的 FINAL_REPORT 都没有标记「本单被同仓后单覆盖」，REVIEW_LOG 也无对应收回条目。
4. **REVIEW_QUEUE.json 的 31 POINT / 155 ROW 标「PROPOSED」状态**：human_review_completed=false 与 README/WORKFLOW 中「HF-DATA-01 SUBMITTED/REVIEWED_WITH_FINDINGS」一致，但 README 顶部 2026-10-14 HF-DATA-01 条目没写「下一步人工队列入口在该 JSON」——读者不知道入口在哪。
5. **HF-REAL-01/02/03 三单 returns 全部在位**（docs/human_fall/returns/HF-REAL-0{1,2,3}.md）且 REVIEW_LOG 顶部有对应提交记录；这一点登记无矛盾。
6. **HC-JOINT-LOCAL-01 R2 在 human_capture README 顶部已登记**（2026-10-13 条目）；与 R2 子目录的证据自洽，无矛盾。
7. **HR-W03 R39 在 README 顶部「当前主线」条目仍在**：「2026-10-07 当前主线（R39-CLOSEOUT）…REWORK_REQUIRED」与 08_final_closeout.md 一致——但它仍是 10-07 的旧日期，**10 月 14 日仍是「当前主线」会让读者以为它取代 10-13/10-14 的新工单**；建议顶部补一行「R39 仍为最新但未收口，下接 10-13/10-14 各工单」。
8. **HFUS-POINTSET-01 ACCEPTANCE_FINAL.json 自报 S8 ROI 核对 pending 与 WORKFLOW/README 一致**，无矛盾。

## ⑦ UNKNOWN 清单（本审计无法判定的项）

- RS04 关闭/不关闭的最终裁决（需用户拍板 + 独审签字）。
- S9 GT bindings 是否可恢复（需用户提供可信原始点或人工重审）。
- W03 gate 49.652981% 差 42 keep/70 raw 是否 benign（需用户裁决放宽/换 pair）。
- 155 ROW / 31 POINT 的真实人/物/混合语义（需人工会议）。
- HC-JOINT 雷达缺号 126 是偶发还是系统缺陷（需长录复测）。
- 完整解剖骨架/关节精度（全部工单，共同 GT 门未过）。
- 独审在所有工单的角色定位（除 10-14 已完成的 HF-CLOSE/DATA/BG 独审外，其他 7 单均 NOT_RUN）。
- 设备/物理/板端部署（全部工单统一 NOT_RUN）。
