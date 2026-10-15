# OpenCode 只读计划审核结论

## 0. 身份与读取清单

- **实际模型/会话身份**：本会话为 opencode CLI，运行时配置模型 `opencode-go/deepseek-v4.1-flash`（提供方/底层权重无法由我独立核验，标记为 UNKNOWN；此处按 harness 声明记录，不作为权威身份）。角色：独立只读计划审核者，未写任何仓库文件、未运行算法/测试/服务/命令、未联网、未调子代理。
- **技能路径**：审核指令要求读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。该路径 **三次读取均被 CLI 权限拒绝**（attempted：`.codex\skills\ponytail\SKILL.md`、`.claude\skills\ponytail\SKILL.md`、`.config\opencode\skills\ponytail\SKILL.md`，均返回 external_directory deny）。因此 **未能读取 ponytail SKILL.md 正文**；计划作者与 R3 报告自述已读取该路径，但我无法独立核对内容。此为审核限制，如实记录。
- **实际读取清单（均只读）**：`AGENTS.md`(根，上下文提供)、`docs/human_fall/WORKFLOW.md`、`docs/human_capture/README.md`、`docs/human_fall/HF_MAINLINE_POINT_RETENTION_PLAN_20261014_V1.md`(被审计划全文)、`docs/human_fall/evidence/2026-10-14_hf_mainline_leveling_r1/FINAL_REPORT.md`、`docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md`、`docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/FINAL_REPORT.md`、`docs/human_fall/evidence/2026-10-14_audit_r1/C01_claude_code_kimi_k3.md`、`sidequests/human_fusion_lab_next/pointset/r01/{research_actions.py,actions.py,core.py,config.yaml,config_actions.yaml}`、`.../action_output/{RUN_MANIFEST.json,catalog.json}`、`sidequests/human_fusion_lab_next/real_fall/r04/{background_ab.js,score_background_ab.py,close_data_bg.py}`、`pc_apps/human_replay/human_pipe_lib.js`、`pointset/r01/server.py`/`check_r3_browser.py` 等（grep/glob 只读）。
- **无法核验项**：跨仓依赖 `D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01` 是否存在（外部目录读取被拒；glob 未返回);ponytail 正文。

## 总体裁决：**PLAN_REVISE**

计划整体方向正确、与已读源码事实高度一致（KS1 归因纠正、R3 边界、Python −0.25 域、数值≠物理资格、拒绝采纳 C01 的 leveling 因果断言均经我独立对源码核实为真）。但**验收表 PR07 的可操作化存在自相矛盾/分母混用**，且**独立验证集与跨仓阻断边界描述不足**，会导致实施后无法按表收口或产生口径争议。故给 PLAN_REVISE（非 BLOCKED：计划已内置诚实失败出口，不会死锁；也非 PASS）。

---

## P1 必要发现（影响能否收口/口径正确性）

### P1-1 PR07 条件跨数据集混用 + 家具项 NOT_EVALUATED 自相矛盾
- **位置**：计划 `L116`(PR07 行)、`L123`(PR07 说明)、`L58`(JS对照分支)。
- **证据**：
  - `score_background_ab.py:15` 硬编码会话 `['cap_20261013_094333','cap_20261010_180557']`；`L66` 对 180557 标 `BOUND_PARTIAL_PERSON_LABELS`，对 094333 标 `HF_REAL_UNREVIEWED_PROXY_ONLY`。
  - `hf_real_close_data_bg_r1/FINAL_REPORT.md:45`：“S1没有人体分母”；`:73`：“HF094333全部人体GT分母0，仅旧target proxy”；`:71`：“0已标非人不代表0家具污染”。
- **影响**：PR07 把「原1934帧无新目标缺失」(Python 八动作分支) 与「已有绑定人体标签保留」(仅 JS/S8 `cap_20261010_180557` 的 53 帧部分标签) 串成一个 PASS，**分子分母来自不同数据集**；而「已知家具目标成员不增加」在缺负例 GT 的会话中按 `L123` 应记 NOT_EVALUATED，NOT_EVALUATED **不能**作为 PASS 条件，于是 PR07 实际上**永远无法整项 PASS**（与 L123 允许“失败裁决”并存但表述矛盾）。
- **最小修订**：拆成 `PR07a`（Python：32 空场 0 目标/0 新事件 + 1934 帧无新目标缺失）与 `PR07b`（JS/S8：人体标签保留 ≥ 对应旧基线）；家具子项显式定义为「非阻断信息项」，无标签会话固定 NOT_EVALUATED，不计入 PASS/FAIL 判定；并注明 094333 分支仅 proxy/几何诊断、不含人体分母。

### P1-2 独立验证集未具名，且全部数据已在 R1–R3 被使用
- **位置**：计划 `L33`（“另冻结未用于本轮选择条件的动作上下文作为本轮验证”）、`L60`、PR05 `L114`。
- **证据**：R3 报告自述“全1934动作帧＋32空场”、“原6方案11796帧”；`research_actions.py:154` 断言 `len(allstats)==1966`。八动作+空场在 R1/R2/R3 已反复用于阈值与方案选择。
- **影响**：“本轮验证”未指明具体帧/会话；由于全 1966 帧均已被历史选择条件触及，所谓验证实为**同数据内的上下文留出**，不能支撑“未见测试”。不具名会让 PR05/PR11 的口径无法复核，也易在返工时无意读取验证样本（计划 L104 只要求“披露”，未要求先冻结）。
- **最小修订**：在 P0 之前**具名冻结**验证上下文（列出具体 sid/fi 集），承诺不进入任何阈值/组合选择；明确标注为 context-holdout、非新数据泛化，PR11 泛化维持 BLOCKED。

---

## P2 发现（显著但可用文字修订收敛）

### P2-1 跨仓依赖的阻断爆炸半径被低估
- **位置**：计划 `L50`（“依赖缺失则仅阻断该数据分支”）。
- **证据**：`actions.py:79-84`（`bg=prior/'background.npz'` 并 `assert sha(bg)==...`）、`actions.py:116-117`；`action_output/RUN_MANIFEST.json` 中 `background_experiment:"D:/Code/radar/Plan/evidence/indoor-empty/20261014-low-pose-r01"`；`close_data_bg.py:209` 亦引用 `D:/Code/radar/radar_capture_data`。
- **影响**：该外部目录缺失时，**整条 Python 动作链（E0/E3/E4 及 1934 帧逐点账本）全部阻断**，并非“一个小分支”；仅 JS 臂 E1/E2 可独立。当前措辞会让人误判可交付面。
- **最小修订**：明确“该数据分支 = Python 动作链全部”，并列出缺失时仍可完成的 JS 臂；同时要求在 P0 就完成该目录 background.npz/background.json/manifest.json 及八 `*_registration.json` 的哈希核对（计划仅提 background.npz 与 registration）。

### P2-2 复用的评分子与 HF-REAL-04/S1 产物强耦合，不能直接服务动作链
- **位置**：计划 `L43`（复用 `score_background_ab.py`）。
- **证据**：`score_background_ab.py:15`（硬编码两 sid）、`:23-25`（读 `docs/human_fall/evidence/2026-10-13_hf_real_04_r1`）、`:30,36-40`（读 `PS/'output'` 即 S1 输出）;`close_data_bg.py:15,137,155` 同用 `PS/'output'`。
- **影响**：它评的是 094333/180557 + S1 输出，**不是**八动作 action_output；直接复用会错挂目录/会话，PR02/P06 的“复用”不成立。
- **最小修订**：注明复用需参数化 sid/数据集与路径，或明确仅用于 JS/S8 分支、动作链另建隔离评分器。

### P2-3 094333↔131958 分支被列为“部分标签可评分”，但 094333 无人体分母
- **位置**：计划 `L58`。
- **证据**：`hf_real_close_data_bg_r1/FINAL_REPORT.md:73`（094333 人体 GT 分母 0，仅旧 target proxy）。
- **影响**：该分支只能做 target-proxy/几何对照，不能报“人体标签保留”。
- **最小修订**：将该分支标注为 `PROXY_ONLY_DIAGNOSTIC`，与 S8 的人体标签分支分开。

---

## P3 发现（澄清/一致性）

- **P3-1** 计划 `L54,L60` 以 131958 为空场参考，但 `config.yaml:3` 为 `background_session: cap_20261010_175227`；实际参考来自跨仓 manifest 的 `reference`（`actions.py:121`）。建议显式声明 config 的 175227 为历史字段/JS 参考，避免读者混用。
- **P3-2** JS 与 Python 输入窗不同（`human_pipe_lib.js:27-28` range 0.35–25.0 / `config.yaml:8-9` range 0.2–15.0），计划未把 range 列入“固定/差异变量”清单；虽已声明“两链分别研究”，仍建议在矩阵固定项中点明。
- **P3-3** E1 高度鉴别（`L84`）：JS 的 `ground_keep_below_m` 同时控制建图与提取（`human_pipe_lib.js:162,281`；`background_ab.js:70`）。计划要求“拆分建图高度/提取高度”正确，但应明写**降低建图高度会引入地板吸收**（`human_pipe_lib.js:148-149` 注释），否则“降高度更好”会被误读为薄地面分割收益。
- **P3-4** E3（`L90`）“参考支撑风险”：Python 背景判定本为最近距 `dist<=tau`（`actions.py:137`），对 background_removed 点“参考支撑”恒真；需把“参考支撑”定义为超出同一距离的独立性证据，否则该子项无鉴别力。

---

## 无需修订的已核项（我独立对源码/证据确认）

- KS1 误归因纠正属实：`background_ab.js:70` 设 `ground_keep_below_m=-.25`，B 臂 `build_reference_map` 用 `{drop_ground:false}`（`:37`），A/B/C 确实关闭生产 0.10 裁剪；`probe_215540.js` 预扣 z<0.10（C01 `L55,64` 一致）。
- R3 边界属实：R3 仅恢复当前 FG 真实源行、不恢复背景删除点（R3 报告“恢复策略”段），计划忠实。
- Python E0 基线 −0.25 正确：`config.yaml:10 z_min_m:-0.25`。
- 源行身份与重复 XYZ 要求正确：现有 `research_actions.py:106,112` 已断言源行集合相等，计划 PR03 与之同向。
- 配准“数值≠物理资格”表述正确，与 leveling FINAL_REPORT 的 `BLOCKED_LEVELING_QUALITY`、`background_ab.js:74` 的 provisional alignment 一致。
- 拒绝采纳 C01 的 leveling 因果断言正确：leveling FINAL_REPORT `L41` 指出 C01 “3*tan(2.86°)=0.149874m”算术不成立，计划 `L136` 明确未采纳。
- 页面端口 8944 与当前 R3 页面一致（`check_r3_browser.py:25` 等）。
- 输出独占/拒绝覆盖（计划 `L46`）与现有 `dump` 用 `open(...,'x')`（`actions.py:30`）一致。
- 计划范围声明准确：`L5` 明示“仅多轮分析+制定计划交审核，实现/实验/页面改造为下一轮”，未越权。

---

## 实现仍 NOT_RUN 的边界

- PR01–PR12 **全部为计划内条目、当前全部 NOT_RUN**；PR11（完整人体召回/家具纯度/解剖精度/泛化）与 PR12（生产晋级/confirmed/设备部署/物理验收）为 BLOCKED。
- 设备、物理、部署、采集、训练、提交推送、GT、板端、网络/驱动变更均 **NOT_RUN/未授权**。
- 本审核仅为计划裁决：**无权将任何工单标 ACCEPTED，也无权批准生产晋级**；PLAN_REVISE 不构成对作者自述或任何历史结论的确认。
- 审查限制：ponytail 正文未读到（权限拒绝），跨仓目录存在性未验证（外部读取拒绝），未运行任何算法/测试。
