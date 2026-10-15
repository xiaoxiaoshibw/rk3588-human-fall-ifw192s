I'll start by exploring the evidence directory and key files.

已按只读约束完成定向复核。以下结论直接输出，可由调用者原样保存。

---

# HF-MAINLINE-POINTS-01 独审发现修复后的定向复核结论

审核身份：opencode（agent=plan），模型 `opencode-go/deepseek-v4.1-flash`，只读。未写文件、未执行命令/测试、未启动服务、未读 points.bin、未调用其他代理。本次仅针对审核02五项做定向复核，未重复旧未改算法全轮审核。

## 实际读取与技能路径

技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（已读，full 强度）。
入口：会话注入 `D:/Code/ldiar/AGENTS.md`、`docs/human_fall/WORKFLOW.md`（顶部当前入口 2026-10-14 HF-MAINLINE-POINTS-01）。

本目录实际打开：`OPENCODE_REVIEW_02.md`、`REVIEW_RESPONSE_V2.md`、`ACCEPTANCE_V2.md`、`FINAL_REPORT_V2.md`、`CURRENT_DELIVERY_INDEX.md`、`ACCEPTANCE_V1.md`（对照用）、`FEEDBACK_DIVERGENCE.json`、`S8_HUMAN_REFERENCE_BINDING.json`（头部 1–60、尾部 3740–3786）、`VERIFICATION_TIMELINE.json`、`FINAL_INPUT_BINDING_CHECK.json`（头部）、`FINAL_SOURCE_AVAILABILITY.json`、`SOURCE_BINDINGS.json`、`DEPENDENCY_BINDINGS.json`、`BROWSER_FINAL_SOURCE_V2.json`、`BROWSER_FINAL_ADDITIONAL.json`、`BROWSER_FINAL_SOURCE.json`（0 字节）、`OPENCODE_REVIEW_01.md`（0 字节）、`tools/hf_mainline_points/resolve_review.py`。

## 总体裁决

**REVIEW_WITH_FINDINGS**（非 ACCEPTED）。五点必要修复均已按"补证/限定表述"落地，未发现算法或冻结配置被改动，未发现新的阻断性软件缺陷；但仍存少量低烈度残余观察及不可消除限制，故不报 REVIEW_PASS。

## 原五项逐条

**P2-1（feedback 非独立对照）— CLOSED_AS_DOCUMENTED。**
`FEEDBACK_DIVERGENCE.json`：frames=1966、anchor 分歧 0、member 分歧 0、status=`DEGENERATE_COINCIDENT_ARM`、meaning 明示"零分歧退化臂，非独立前景证据"。生成逻辑见 `resolve_review.py:18-22`。表/报告同步限定：`ACCEPTANCE_V2.md` PR09 及 `FINAL_REPORT_V2.md:19,27` 改为"单独运行 feedback（本数据零分歧退化臂）"。原表述"独立 feedback"已消除。

**P2-2（后验护栏/复用回归）— CLOSED_AS_DOCUMENTED。**
`ACCEPTANCE_V2.md` PR04 标注"后验拟合式护栏；REUSED_REGRESSION"、PR05 标注"后验护栏内/复用回归"。与审核02最小修复要求一致；`REVIEW_RESPONSE_V2.md` 明确 0.85/0.12m/30° 来自旧 R3/R2 常数而非本轮诊断统计。

**P2-3（PR05/PR07a 时序不可复跑）— CLOSED_AS_DOCUMENTED。**
`VERIFICATION_TIMELINE.json`：missing_check=2026-10-14T12:25:18Z；run_01/run_02 `ALL_FRAME_VERIFICATION.json` 各绑 SHA、observed_mtime（10:23:52Z / 10:11:17Z，均早于缺源检测）及"mtime 非可信独立时间戳"说明；current_rerun=BLOCKED。`ACCEPTANCE_V2.md` PR05/PR07a 已补"当前复跑BLOCKED"。

**P3-1（S8 人体分母溯源）— CLOSED_AS_DOCUMENTED。**
`S8_HUMAN_REFERENCE_BINDING.json` 绑定 reviewed_GT SHA（89da673…）、GT 源 meta/points SHA、523 帧 derived_output_sha256 与 reference_source_indices_sha256、逐帧对象 ID/PERSON/帧号/解压数量、denominator=57045、labeled=53、human_reference.npz SHA，并显式保留 `current_mapping_recheck=BLOCKED`（原始 raw 缺失，不伪造 raw→compact 重放）。

**P3-2（空工件引用）— CLOSED_AS_DOCUMENTED。**
`BROWSER_FINAL_SOURCE.json`、`OPENCODE_REVIEW_01.md` 均确为 0 字节且保留未删；`CURRENT_DELIVERY_INDEX.md:11,16` 明确标为失败工件、不作成功证据；实际点击源改引 `BROWSER_FINAL_SOURCE_V2.json` / `BROWSER_FINAL_ADDITIONAL.json`（含真实 click、opaque=null、MISSING_ORIGINAL_SOURCE）。

## 必要新缺陷精确定位（低烈度残余，非阻断）

- `resolve_review.py:18` 锚点分歧用 `np.setdiff1d`（集合语义、去重）比较，较逐帧成员比较（`:19` 精确 `array_equal`）弱；"锚点分歧0"目前是集合级结论，非多重集/顺序级。
- `VERIFICATION_TIMELINE.json` 仅绑 run_01/run_02 `ALL_FRAME_VERIFICATION.json`；`ACCEPTANCE_V2.md` PR07a 另引的"80 帧具名子表"未单独绑时间戳（由同轮 run 覆盖，属极小缺口）。
- `ACCEPTANCE_V2.md` 相对 `ACCEPTANCE_V1.md` 无任何状态升级（PR01 仍 FAIL、PR02/08/11/12 仍 BLOCKED、PR04/05/09 均弱化），无"PASS 冒充"风险。

## 不可消除限制（单列，不作 PASS）

- 无人体/物理 GT：身份 UNKNOWN，完整人体召回、纯度、解剖精度、跨人跨景泛化均 null（PR11 BLOCKED）。
- 原始 capture 快照当前缺失：`FINAL_INPUT_BINDING_CHECK.json` 所列路径 `exists` 全为 false（经 grep 无 `"exists": true`），主链 18 文件见 `FINAL_SOURCE_AVAILABILITY.json`，复跑 BLOCKED；作者未归因、未替代。
- 跨仓依赖 `DEPENDENCY_BINDINGS.json` 11 项 expected==actual 仍相等（与作者表述一致）。
- 整树非原子冻结（12 变化/33 缺失未逐文件归因），并行外部页面改动不由本轮认领。
- 本回复的溯源证据均由作者脚本自产，独立性仅由本次只读复核提供；S8 raw→compact 映射重放 BLOCKED。

## 关于范围与未改动声明

`resolve_review.py` 的写入集合仅为本 evidence 目录 JSON/表/报告、`WORKFLOW.md`、`docs/human_capture/README.md`、returns 与 REVIEW_LOG，未触及 `research_retention*.py` 或冻结 config；与"本轮仅补证和限制表述、算法/冻结配置未改"一致。作者总体保守（SUBMITTED、R1 默认、不晋级、不声称人体收益），未见夸大。

结论由调用者原样保存；本审核不代作者关闭物理/完整人体/生产门，不代作者写结论。