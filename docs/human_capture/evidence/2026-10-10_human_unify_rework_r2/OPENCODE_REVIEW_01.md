I'll load the required skill and start reading the authoritative docs for this review.

# HUMAN-UNIFY-R1 R2 返工 · 独立只读复审报告

复审者：opencode（`opencode-go/deepseek-v4.1-flash`，plan agent，default DB，未换模型/认证）
日期：2026-10-10（Asia/Shanghai）；基线 HEAD `777296d`（与 `head.txt` 一致），branch `master`
适用技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（`ponytail` skill 已加载，full）
本轮**未修改任何源码/数据/配置/文档/证据，未 commit/push/部署/采集/网络/设备**，仅只读与既有测试。

结论（一句话）：**在 human_core 范围内 R01–R08 软件修复经独立复现成立，无软件 FAIL；可提交下一轮验收。但本轮结果矩阵的可复现性因一个范围外文件 `pc_apps/human_replay/rf_person.js` 在当前工作树被并发改写而不再与当前实现对应，S02 结束冻结 `BLOCKED`。算法资格/生产资格 `BLOCKED`，D01 `NOT_RUN`。**

## 读取与执行记录

实际读取：`docs/human_capture/README.md`、`HUMAN_UNIFY_R1_ACCEPTANCE.md`、`returns/HUMAN-UNIFY-R1.md`、`evidence/2026-10-10_human_unify_review_r1/CODEX_REVIEW.md`、`evidence/2026-10-10_human_unify_rework_r2/*`（SUBMISSION、AB_RESULTS、matrix_summary、parity_01/02、perf_01、production_js_01、submitted_source_sha、all_sha_before、preservation_01、opencode_probe/review 脚本与日志）、`pc_apps/human_core/{engine,runner,data_loader,leveling,schema,test_rework,test_baseline_parity,test_replay_contract}.js`、生产 `pc_apps/human_replay/{detect_overlay.js,human_pipe_lib.js,rf_person.js}`。

实际命令与退出码：
- `node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js` → 7/7 套件、94 断言全过，**exit 0**
- `node --max-old-space-size=2048 pc_apps/human_core/test_baseline_parity.js`（未加 `--out`）→ 9 会话逐帧 A/B 对拍 `PASS`，**exit 0**
- 生产 JS 独立复跑：`detect_overlay.test.js`(41) / `human_pipe_lib.test.js`(38) / `rf_person.test.js`(6) 全 `EXIT=0`
- `certutil -hashfile`：human_core 16 文件 SHA 与 `submitted_source_sha.json` **16/16 完全一致**
- `node -e` 复算：45 份 JSON+45 CSV 自身 SHA 全匹配 manifest，`hash_issues=[]`，5980 帧次

## 逐 ID 结论

| ID | 结论 | 独立依据 |
|---|---|---|
| R01 | **PASS** | `test_baseline_parity.js` 9 会话逐帧对比 `_candidates`↔生产 `_test.find_clusters/_test.associate` 的簇数、每 raw 索引的 X/Y/Z/intensity、RF 概率、track `{id,x,y,z,r90,n,age,born,miss}`、确认集、HUD 确认 ID 集合、候选→track 绑定；`engine.js:140-171` 改用 `this.overlay._test.*`，不再用 `pipe.Tracker`；`.9m`/同帧近邻两簇/实例隔离见 `test_rework.js:12-13` |
| R02 | **PASS** | `engine.js:174-182,199-221` 用 `subset_indices` 保序映射回 raw 索引，强度取 `fg_final[pp*4+3]` 与 XYZ 同点；`test_rework.js:14-15` 前置 NaN 点后强度/索引回归 |
| R03 | **PASS** | `leveling.js:26-33` `resolve_contract` 统一「已配平/raw/显式 R/T」，`engine.js:96-101` 会话级坐标契约冲突即拒；CLI `--leveling identity` 实际生效（`test_rework.js:16-19`） |
| R04 | **PASS** | `engine.js:84-95` 换会话清 report/track/保留/背景并自增代际；`tick` 校验 `session_id`+`session_generation` 拒过时（`engine.js:114`）；跳帧显式重置（`engine.js:127-131`）；`test_replay_contract.js` 11 条实际断言 |
| R05 | **PASS** | `engine.js:52-55` 将实例级 cfg 写入本实例 `pipe.PIPE`；`load_production` 每次新建闭包 → 实例隔离；`test_rework.js:20-22` 验证 U6 寿命 30 生效、其他实例与真实生产模块仍 8、未知/未实现/非法配置拒绝 |
| R06 | **PASS** | `data_loader.js:34-41` 帧连续/整数/越界/时间回退校验，`131` 打开即校验整文件尺寸；`next()` 累积读 + short read 抛错 + `close`（`143-154`）；`test_rework.js:31-35` 覆盖截断/partial/close 幂等 |
| R07 | **PASS** | `engine.js:242-244` 输出 `n_accepted_cand/n_rejected_cand`，`current`(=lost0&confirmed) 与 `ever`(历史曾确认) 分离；`RUNNER prf.status=BLOCKED`（`runner.js:41`）；`AB_RESULTS.md` 头部与 `README.md:23` 明确「非真人/家具 GT」；无 `n_furn_*` 字段 |
| R08 | **PASS**（软件机制） | `engine.js:183-196,228-234` retained 去重（`seen`）、来源 FG/retained/merged、raw 索引可追溯、过期退出、仅 FG 确认才刷新锚点；`test_rework.js:24-25` 覆盖去重/来源/过期/不自续命 |
| S01 | **PASS（生成时）/ 记录例外** | 7/7 套件 + 6 套生产 JS `exit 0`；新 `runs_01` 45 JSON+45 CSV（5980 帧）自身 SHA 一致。**例外见下** |
| S02 | **BLOCKED** | `preservation_01.json`：`status=BLOCKED`，`outside_changes=[pc_apps/human_replay/rf_person.js 78c4ce66→f3e98453]`；审核期间该文件又被改写为 `21796a55`（`external_rf_01.js` 副本） |
| Q01 | **PASS** | `opencode_probe_01.txt` 真实 `PROBE_OK`/`REAL_EXIT=0`；`opencode_probe.py`/`run_opencode_review.py` 均用 `opencode-go/deepseek-v4.1-flash`+`--agent plan`；`opencode_review_01.jsonl` 为真实 opencode 会话日志 |
| D01 | **NOT_RUN** | 无设备/物理/部署/采集 |

## 唯一阻断性发现（范围外，需编排者处置）

`pc_apps/human_replay/rf_person.js` 与结果矩阵对应关系失效：
- 45 份运行 `run_meta.source_sha256['pc_apps/human_replay/rf_person.js']` = `78c4ce66…`（与 `all_sha_before.json` 起始快照一致）；**当前工作树该文件 = `21796a55…`**（`certutil` 复算），行内容为 PCA 幂迭代重写并令 `fv[37..39]=axis_z`（见 `external_rf_diff_01.txt`）。
- 该改动**在 human_core 返工范围之外**（`submitted_source_sha.json` 只含 16 个 human_core 文件，不含它），且发生在本轮证据生成之后（`perf_01.json` 17:31 → 该文件 17:36 改写），与本轮 writer 停止状态吻合，疑似并发任务，非本轮 human_core 缺陷。
- 后果：① S01「结果 manifest 的**实现 SHA 对应当前实现**」这一可复现性目前不成立（仅此一文件）；② S02 结束冻结 `BLOCKED`。**核心对拍不受影响**：我用当前 `rf_person.js` 复跑 `test_baseline_parity.js` 仍 9/9 PASS，`rf_person.test.js` 仍 EXIT 0。
- 处置建议：先稳定工作树、把 `rf_person.js` 变更归属到其自身工单并记录来源，再**重建 45 次运行与 S02 结束快照**，然后把结果重新交独立复审。此发现不判为 human_core 软件 FAIL。

## 判定与边界

- **本轮软件修复（human_core）可提交下一轮验收**：R01–R08 均有本轮可复现证据、无软件 FAIL、相关回归（含生产 JS）通过。
- **算法资格 BLOCKED**：45 次运行 GT 来源全为 `UNKNOWN/PSEUDO_LABEL`，`prf` 恒 `BLOCKED`，不据此声明真人 recall / 家具免疫；U2/U3 空场误报边界仍属待验证。
- **生产资格 BLOCKED、D01 NOT_RUN**。
- 不改动、不追改任何历史证据；本轮不作 commit/push/部署/采集/网络/设备动作。