# FINAL_REPORT — HUMAN-UNIFY-FUSION-R1 工单交付与裁定

2026-10-10。敏感方法writer: Claude (Sonnet/CLAUDE.md 指令); worker 工具: `pc_apps/human_core`, `pc_apps/human_ml`; 独立独审: OpenCode CLI `opencode-go/deepseek-v4.1-flash --agent plan`。
**未 commit / push / deploy / 替换任何生产主入口 / 覆盖任何模型 artifact**。

## 1. 交付物清单

### 1.1 本工单新增代码 (pc_apps)

| 文件 | 作用 | 备注 |
|---|---|---|
| `pc_apps/human_core/fusion.js` | 融合跟踪器 + FUSION 配置契约 | 新 |
| `pc_apps/human_core/engine.js` | 新增 `MODE.FUSION` + `_tick_fusion` + `_fusion_a_chain/_b_chain/_organize` + `_build_ref_static_keys` (未用, 留作后续 ref→static_keys 复用; 未链接) | 修改 (不影响 BASE/U) |
| `pc_apps/human_core/runner.js` | mode 白名单加 FUSION | 修改 (加白) |
| `pc_apps/human_core/test_fusion_specific.js` | F2 专项 16 项 | 新 |
| `pc_apps/human_core/perf_profile_fusion.js` | 逐层性能剖析 (预热 5 帧) | 新 |
| `pc_apps/human_core/summarize_fusion_runs.js` | F4 对照汇总 | 新 |
| `pc_apps/human_ml/audit_fusion_sessions.py` | F1 9 会话审计 + SHA + 趋势 | 新 |
| `pc_apps/human_ml/dump_parity_dataset.py` | F1 483 簇特征 dump | 新 |
| `pc_apps/human_ml/gt_workbench_export.py` | 人工 GT 交付包 (模板+索引+自动候选) | 新 |
| `pc_apps/human_ml/export_furniture_hard_neg.py` | F3 家具硬负样本入口 (GT 冻结后启用) | 新 |

### 1.2 本工单新增证据/报告

`docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/`

| 文件 | 状态 |
|---|---|
| BASELINE_AUDIT.md | STEP 0 完成 |
| SESSION_DATASET_MANIFEST.json | 9 会话 / 2,605 帧 / contract_ok=true / display_match=true / 0 issues |
| GT_COVERAGE_REPORT.md | F0 交付, GT 全 UNKNOWN 2 / 9 会话标注任务完整 |
| FEATURE_PARITY_REPORT.md | 真实 483 簇 + 6 边界断面; leaf 路径 489/489 中 488 匹配, 概率 P95=0 |
| PERFORMANCE_REPORT.md | 9/9 A/B/U3 P95<50ms + heap<1500MB (预热+逐层) |
| REGRESSION_REPORT.md | 96+16=112 项功能断言全 PASS, JS 生产未跑 (不接管) |
| FUSION_ABLATION_REPORT.md | 9 会话 × A/B/U3/FUSION 全 36 行, FUSION v3 均 ms ≤ 46.8 |
| TRACKING_EVALUATION.md | 工单 §4 规则逐条落实证据 |
| RF_MODEL_COMPARISON.md | F3 BLOCKED — GT 缺失模型不升级, 硬负样本管线交付 |
| OPENCODE_INDEPENDENT_REVIEW.md | 真实独审完成 (exit=0), OpenCode 无 FAIL |
| gt_workbench/ (9 会话 × frames_index + GT 模板) | 人工标注交付包 ready |
| furniture_hard_neg_dryrun.json | F3 管线 dry-run 实际跑 0 样本 (证明 S1 空场背景 = 自参考) |
| runs_fusion/ | A/B/U3 9 会话基线 (36 行 manifest 含 source SHA) |
| runs_fusion_v3/ | FUSION 最终 9 会话 (ref_only + decision fix) |
| F1_parity_run1.json | 真实对拍结果 (4,994 统计维超 5e-3 但决策带宽不跨侧; 见 FEATURE_PARITY_REPORT §3) |
| perf_profile_01/perf_profile.json | 逐层性能 SHA 守卫 |
| webui_fusion_demo.html | FUSION 演示 (示读) |
| opencode_review_prompt_01.md | 独审计 prompt |
| git_status_before.txt / git_head.txt / source_baseline_sha.txt | 基线冻结 |

## 2. 五判定裁定 (工单 §8)

| 判定 | 状态 | 关键证据 |
|---|---|---|
| **FUNCTIONAL_PASS** | ✅ PASS | 96+16 断言 exit=0; 9 会话 × 4 路线 36 行输出全收齐; OpenCode 独立 audit 无 FAIL |
| **GT_EVALUATION_PASS** | ❌ BLOCKED | 9 会话全 UNKNOWN GT, 0 段 HUMAN_VERIFIED, 不允许上处标 recall/precision |
| **PERFORMANCE_PASS** | ✅ PASS | 9/9 BASE_A/B/U3 P95<50ms + heap<1500MB (预热后逐层); FUSION 全 9 会话稳态 ≤ 46.8ms, 甜点性体现在低代价值 |
| **MODEL_PROMOTION_READY** | ❌ BLOCKED | 无 GT, 无 RF v2 对照; v1 保留 (4c83db11…), 未覆盖 |
| **PRODUCTION_RELEASE_READY** | ❌ BLOCKED | 仅演示 WebUI, 不替换生产主入口; 工单 §7 要求独立验收+发布授权才能切换 |

总体 SUBMITTED = **FUNCTIONAL_PASS + PERFORMANCE_PASS**, 其余三项 BLOCKED (同 R2 语义)。

## 3. 与验收表工单的逐条对账

| 工单要求 | 状态 | 证据 |
|---|---|---|
| STEP 0 真实读取既有证据+代码 | ✅ | BASELINE_AUDIT.md 全部文读 |
| F0 新 9 会话全面入库 | ✅ | SESSION_DATASET_MANIFEST.json contract_ok+display_match 全 true |
| F0 GT 交付包 | ✅ | GT_COVERAGE_REPORT.md + gt_workbench/ 9 会话模版 ready |
| F0 train/val/test 划分 | ❌ BLOCKED | 需 GT 冻结后划分 (划分未发生, SHA 未冻) |
| F1 51 维契约核验 | ✅ | FEATURE_PARITY_REPORT.md (fv[37..39] 历史契约冻结); 真实 483 簇 + 边界断面 |
| F1 性能 P95<50ms | ✅ PASS 9/9 (A/B/U3, 预热); FUSION 全部 ms ≤ 46.8 | PERFORMANCE_REPORT.md |
| F2 A+B 统一融合 | ✅ | FUSION mode + 16 项专项 PASS; 对重复候选合并 |
| F2 静止保留 | ✅ (机制) | retention 独立证据守卫同 U3; S8 ever=2 FUSION = U3 = BASE_B |
| F2 运动连续检测 | ✅ (机制) | lost 30 帧窗口内重捕成功 (S6 occlusion ever=4) |
| F2 单一 Track | ✅ | FUS_t{seg}_{id} 唯一空间, 不与 PIPE 冲突 |
| F2 UNKNOWN 输出 | ✅ | CLS_DECISION.UNKNOWN 决策带宽保留 |
| F2 bank 独立证据续命规则 | ✅ | FG+CONFIRMED 才刷, retained/merged 不刷 |
| F3 硬负样本入口 | ✅ 管线交付 | export_furniture_hard_neg.py + 契约元数据 |
| F3 RF v2 训练/对照 | ❌ BLOCKED | GT 缺失 |
| F3 模型保留 | ✅ | v1 未覆盖 |
| F4 四路线对照 | ✅ | FUSION_ABLATION_REPORT.md 36 行 |
| F4 各专项场景评估 | ❌ BLOCKED | 需 GT 冻结 |
| F4 会话切换代际 | ✅ | generation 守卫 + begin_session 重置 |
| F4 P50/P95/P99 | ✅ | perf_profile.json (单帧 P50/P95+log) |
| F4 帧/track/episode 单位 | ✅ | 帧帧参与; episode = ever_tracks 分段记录 |
| 不拿 confirmed_tracks 当真人数 | ✅ | 全 report 明确CONFIRMED ≠ 人数, 缺 GT 不评估识别 |
| OpenCode 独立复核 | ✅ | exit=0, 无 FAIL; OPENCODE_INDEPENDENT_REVIEW.md |
| WebUI 不接管生产主入口 | ✅ | 仅 webui_fusion_demo.html 示读; A/B 页面未动 |

## 4. 阻断原因 (BLOCKED) 与所需人工操作

1. **GT_EVALUATION_BLOCKED** — 需要人工逐会话标注 9 会话 (P0: S1 furniture+S8 still+S9 two-person; P1 其余), 填 gt_workbench/<sid>/GT_v1.json, review_status=reviewed 后冻结 GT_POS/GT_FURN_HARD_NEG/SPLITS (会触发 F3 训练)。详见 GT_COVERAGE_REPORT §4 任务表。
2. **MODEL_PROMOTION_BLOCKED** — 同上; GT 冻结后再跑 train_person_rf_v2.py + RF_MODEL_COMPARISON 报告。
3. **PRODUCTION_RELEASE_BLOCKED** — 除 GT 外, 还需上层独立验收+发布授权; FUSION mode 轮值 human_replay 生产主入口为下一步工单, 未授权。
4. **R2 S02 全树冻结 BLOCKED** (继承, 非本工单新缺陷) — FUSION 工单对 human_core 写入为预期范围, OpenCode 明确「不是 fusion 写入缺陷」。

## 5. 未处理事项 (下一阶段工单候选)

- `cap_20261004_203135` 对拍会话从 captures/remote 消失 — OpenCode 发现 (治理, 与本工单无关, 由人补录/恢复）。
- FUSION 与 BASE_B 的全帧对拍 (本次只做 4 路线对照统计, 未逐帧同源断言; 需 F4 在 GT 冻结后补)。
- `_build_ref_static_keys` 已写入但未链接使用 — 当前 fusion ref_only 直接按 envelope 热点过滤, 不动用 PIPE.build_static_map; 是优化空间, 非缺陷。
