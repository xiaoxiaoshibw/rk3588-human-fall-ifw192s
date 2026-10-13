# 主控接管日志（Claude Code 临时主控，2026-10-11 晚）

授权：用户「HUMAN-FUSION — Claude Code 临时主控接管与连续开发」消息。Codex ClientRequest 爆满无法完成最终收尾；本主控接手**验证、回传、独立审核**，不重跑可复用工程。

## 接管基线
- HEAD = 026e06303f60ed1bbe4ddc4d037836db68da6d27（master，无推进）
- 时间：接管检查 ~2026-10-11 21:01；Codex 主控范围最新写入 20:56；之后无新写入证据
- 并发：Codex 本轮已终端报错（ClientRequest 403 user_rate_limit，见 codex 日志 `C:\Users\30680\.codex\log\*.log`）；我端旧 D02-REVIEW writer 已于 ~20:40 SUBMITTED（returns/HFUS-D02-REVIEW.md）；用户按移交指令可视为唯一活人，持续漂移监控见本表下方
- worktree：另有 4 个外部 worktree（含 cl2-06-isolated-r1、traditional-clustering、cl208audit、ldiar_console_build），均不在本主控写入域，本轮不触碰
- 全树冻结状态：沿用 `EXTERNAL_DRIFT_01.md` 结论 = BLOCKED（整树一致性不宣称 PASS；逐域以下方快照为准）

## 接管快照（域级）
- 快照文件：`TAKEOVER_SHA_2026-10-11.txt`（2400 个文件，0 读取错误，排除 __pycache__/.git）
- 快照自身 SHA256：`28f53b028b1bf0651d42209138bf09ba93d5eb3955815fd52951988165912012`
- 覆盖域：`sidequests/human_fusion_lab_next/**`、`evidence/2026-10-11_hfus_d01_r1|d02_r1|d03_r1/**`
- 复核方式：结尾验收时重算同域 SHA 逐文件比对；同步监控新文件（域内新增=我主控产物，其余新增按漂移登记）
- GT/captures/模型/旧 lab results：读操作以各 FINAL_MANIFEST/INPUT_LOCK 记录的 SHA 为准，不整树哈希（体积声外）

## 接管时实际状态（证据已逐域读取）
- D01：三器件/运行产物齐（RUN_ATTEMPTS、POINTNET_PARITY status=PASS、baseline_final 三会话、FIXED_JS 859 候选、LEDGER_EVENTS）；见 `2026-10-11_hfus_d01_r1/`
- D02：主控 side（browser_01..03、coverage_package_01、package_01）齐；BROWSER_01_FAILURE 保留；browser_03 含真实 Chrome 渲染 PNG；另有外部 Claude writer 的 next/review 2309 条包 + returns/HFUS-D02-REVIEW.md SUBMITTED
- D03：九会话 A/B ledger、双 LINE_SUMMARY、双 REGRESSION_COMPARISON、EVENTS(_V2)、FLOW×6、FINAL_MANIFEST(_V2)、RUN_RETURN_PLACEHOLDER、CHECK_01.log（BG_B_CHECK_PASS）、final_02（venv 现场）
- 集成：INPUT_LOCK、ASSET_CHECK_01（漂移登记）、CONTRACT_CHECK_01（exit 0）、BG_COVERAGE_PREREGISTRATION、OPERATION_MATRIX、DISPATCH_MANIFEST
- 返回值缺口：HFUS-D01.md / HFUS-D02.md（主控 B 侧）/ HFUS-D03.md / HFUS-INTEGRATION.md 均未建立 —— 本主控补齐主控侧四份（D02 另有外部 writer return 保留，不覆盖）

## 暴露会话清单（主控）
- 读取内容：9 会话 meta/points（只读）、GT（只读）、lab/results/models（只读 SHA 引用）、D01/D03 产物（只读）
- 主控写入仅限：`sidequests/human_fusion_lab_next/integration/**`、`evidence/2026-10-11_hfus_integration_r1/**`、`returns/HFUS-D01|D02|D03|INTEGRATION.md`（Codex 放弃的 name claim 由本主控继承）

## OpenCode 审核计划
- 沿用统一计划v2 §7：opencode-go/deepseek-v4.1-flash、probe（约定 PROBE_OK，工具数=0）+ 短 carrier + 只读权限注入；三阶段审核意见存本目录并反处理记录进 INTEGRATION return
- 注意 IP 白名单：历史上 opencode-go 订阅超时曾返回 403 "Go 订阅未生效"；独立审核走通是 INTEGRATION-06 的硬门，若缺 provider 资格 → INTEGRATION-06 BLOCKED、集成仅按主控自验+外部 reviewer 证据结算，不会假装 PASS

## 接管后修正（2026-10-11 补）
- **重要纠正（D03-02 注意）**：sub_d03_verify 发现 D03 方向 A/B 复跑**语义层数值完全一致**（18/18 `semEqAfterSanitize=true`）但**字节层不一致**。根因：官方原始 A/B ledger 与 SUMMARY 由 `run_b.js` 老一版 SHA=`303acea5...` 写出（untracked、HEAD 无记录），现行工作树 `run_b.js` SHA=`646aae91...` 在 ledger row 增 4 键（schema_version/evaluation_version/segment/timestamp_s）与 `<mode>_SUMMARY.sessions[i]` 增 6 键（input_sha256/gt_manifest_sha256/gt_binding_valid/gt_sha256/model_sha256/config）。**这是对 D03-02「归因控制」的二阶风险**：工程留档缺失，算法本身不漂。**子建议**：当前 untracked run_b.js 应入版基线案（突出实际 source SHA 夹住影响范围）。
- 本接管**不是** "Codex 范围最新写入 20:56 之后无新写入"：四个 verify subagent 在 21:05~21:10 落盘一批 sub_d0{1,2,3}_verify/ 产物（已知、授权接管内）。除了该目录，其它范围内文件树未检测新写。原话改为「除授权子代理产物外无未知写入」。
- D01 RUN_ATTEMPTS 中提到的 「baseline_final 新轮重跑」已由 sub_d01_verify/all_run 复跑完成：六会话 × 两种 inputMode SUMMARY 与原 baseline_final 完全一致（near strict observed_confirmed tp=161、S6 tp=45 等严格匹配），near 与 S6 的 D01 jsonl 与 D03 A ledger 逐帧完全一致（metric/cand/legacy mismatches 全空）——这是 D03-02「归因控制」最强证据之一。resume 后 S7/S8/S9 也已落盘（S9 因 GT_V2 binding aaaa 占位 → gt_valid=false 全 INVALID_BINDING 但引擎走通）。
- 冷点已灭：S7/S8/S9 已落盘 resume_run；f128/f187/f188 A 侧分层 flow 已由 collection workflow 完整提取（详见 HFUS-D03.md 难帧表） ；next/review manifest 对照与 D02 回传完成。
- **重要纠正**：sub_d02_verify 早期回报的「bad_asset SHA 不一致 → D02-01/D02-05 FAIL」是误读。`check_browser.js` 是**故意的负测试**：注入 4 字节 bad.bin → load() 因 SHA mismatch 抛「SHA不匹配」是 PASS 信号。我再用 Python 对 package_01 1650 文件 + coverage_package_01 123 文件逐 SHA 校验 manifest.files：**0 mismatch**。D02-01 绑定与导出、D02-05 复核入口的 PASS 成立。
- **重要纠正 2**：D02-02 覆盖包的**独立口径**实际上 FAIL——`coverage_package_01` 只覆盖 175943(16) + 180337(25) 两会话 41 帧，**没有任何** S6 难帧、S4/S8 ≥20s 窗、S1 也不在其内。不过 `package_01/split_manifest.json` 中 selected_frames 已涵盖 D02-02 全部点名帧组（S6 f128..188 邻帧、S4/S8 194 帧、S5/S7 43 帧、S1 14 帧、S9 40 帧）。**结论**：D02-02 在 package_01 口径下算 PASS；coverage_package_01 单独 FAIL。这个二值区分已写入 HFUS-D02.md 表。
