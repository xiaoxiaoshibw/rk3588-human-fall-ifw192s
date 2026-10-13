# C1.5 动态人体识别真值验证与生产准入前审计 — 最终报告

> 日期 2026-10-10（Asia/Shanghai）。执行: Codex 主控；OpenCode `opencode-go/deepseek-v4.1-flash` 只读独立复审。
> 边界: 冻结 C1-R2；生产算法零改动 (5 锚点 SHA 未触)；不重新训练、不调生产阈值、不部署 RK3588、不伪造 GT。
> 证据根: `docs/human_capture/evidence/2026-10-10_c15_gt_validation/`（新建独立目录）。

## 0. 执行边界声明
| 约束 | 遵守证据 |
|---|---|
| 生产算法零改动 | 全程只读 `pc_apps/human_replay/*`；唯一临时拷贝 `b2a_shadow_probe_v2.js` 用完即删；`git status` 无生产新改 |
| 不重训模型 | 仅复用 `rf_person_v1.json` 推理探针 |
| 不调生产阈值 | 硬门/RF 阈值在探针副本内, 与 C1 一致, 未回写生产 |
| 不部署 | 未触板端 |
| 不伪造 GT | 坐标不可靠的 GT 明确降级/剔除 (143945 CONTESTED 不计 recall) |

## 1. 目标 1+2: R2 复审结论复核 + 历史证据覆盖审计

**OpenCode 独立复核 (真实跑通, 本轮已替代两次卡死调用)**: 读源码/Grep/重算 SHA 后判定 — R2 复审 4 项发现在**根 `workspace/` 主副本已闭合**, 但 **`r2/workspace/` 下两个被 R2 manifest 锁定的脚本副本仍是旧 bug**:
- `r2/workspace/c1_label_audit.py:108` 仍 `pass: True` 恒真 (z_band), 主版已修真比对。
- `r2/workspace/c1_rf_v2.py:193-204` 仍 51-vstack-53 维度碰撞 + `Xcomb2` 死代码, 主版已修零填充真消融。
- 两副本 SHA (`df9265ae…` / `590a3f84…`) 均被锁进 `SHA_MANIFEST_R2.sha256`。
- manifest FAILED 数已如实更正为 4 (主报告 §7)；`SHA_MANIFEST_R2.sha256` 零自引用成立。

**裁定: 部分闭合 / 锁定残留** — R2 报告结论本身可采信 (其基于根版 GOOD 副本), 但 R2 manifest 固化了两个带 bug 的 `r2/workspace/` 副本, 独立性/可复现性受损。**建议后续修订 R2 manifest 标注副本差异** (需用户授权, 本轮只发现不修改)。

## 2. 目标 3: 现有真实动态人体会话盘点 (新发现)

全库 28 段物理会话实测 (运动分诊探针 + vision 人工判读):
| 会话 | 帧 | C1.5 判定 | 是否曾进 C1 |
|---|---|---|---|
| `cap_20261007_143945` | 108 | 真人慢走+停留 (运动候选), 但 GT 坐标多标注员互斥 → **CONTESTED** | 否 (新发现) |
| `cap_20261007_154007` | 83 | 真人走-停-走多段, y≈2.2 横线, GT 自洽 → **可用动态 GT** | 否 (新发现) |
| `cap_20261008_114340` | 281 | 静态真人站立 (span 0.29m 呼吸) | 否 (新发现) |
| `cap_20261008_114254` | 271 | 静态真人站立 (0.22m) | 否 (新发现) |
| `cap_20261009_113611` | 203 | 空场 (FP 基准) | 部分 |
| 11 段 2026-10-09 | 915+ | auto 标 stand, 零人确 | 是 (C1 全部) |

**缺口**: 明确转身、遮挡后重现、>2.5m 远距 GT、多人交叉、坐/蹲/弯腰/躺/跌倒、变速走。

## 3. 目标 4: 人工 GT 标注规范 (区分自动 vs 人工)

已交付 `workspace/GT_SPEC.md` v1: 标签四层分级 (runtime / `confidence:"auto"` / `source:"human"` / AI-assist+人确)、真人 3 独立判据、场景/运动分类、gt_v1.json 契约、治理。
**C1.5 实证根因**: 现有渲染**无坐标轴数字**, 多标注员"数格"给互斥坐标 → 坐标级 GT 不可用, 仅分类级可提取。已交付带刻度渲染器 `workspace/render_axis.py` 修复。

## 4. 目标 5+6+7+8: 指标实测 (生产 FIX-R1 探针 tracks.jsonl, 档 0.55; associate ≡ detect_overlay.js)

原始指标: `workspace/metrics_final.json`（逐会话 + A/B + 段级 Wilson）。

| 场景 | v1 无硬门 | v2 硬门 n_pts≥500 | 判定 |
|---|---|---|---|
| **动态 154007** 真人区 confirmed recall | **0.349** (29/83) | **0.000** | FN 高 + **硬门误杀真人** |
| 静态 114340 still-retention | 0.993 | 0.993 (ID churn 136→58) | 好; 门稳 ID |
| 静态 114254 still-retention | 0.993 | 0.993 (churn 90→0) | 好 |
| 空场 113611 FP (confirmed) | **0 / 203 帧** | — | 强截证, 单会话 |

**支撑细节 (已存疑复核)**:
- v1 confirmed cy 分布跨 -0.19..2.42 (y≈2.2 真人区有 107 事件)。
- v2 confirmed cy 全部 ≤0.74, **真人区 (y>1.7) 0 事件**。
- 154007 **72.9% 簇 n<500 被硬门拒** → 该会话真人走/停点云大部分 <500 点, 硬门系统性误杀。
- **目标 6 静止保留**: 静态会话 still-retention 99.26-99.29% 达标 (Wilson n=2 下界 0.34, 样本小)。
- **目标 7 少点误杀**: **确证** — 硬门对动态/少点人体误杀 (recall 0.349→0), 与 R2 静态结论相反。

## 5. 目标 8: 统计口径

- 独立样本 = 会话, 帧不作独立样本。
- still-retention n=2 Wilson95=[0.34,1]; 动态有效样本 n=1 → **无法算 Wilson, 单点观察**, 143945 CONTESTED 剔除。
- 诚实标注: 动态 recall 是 1 会话 1 口径的单点, **统计上不足以支撑生产主张**。

## 6. 目标 9: C2 readiness 裁定

### **C2 readiness = NO (NOT READY)**, 依据 (主拒绝理由):
1. **硬门 n_pts≥500 在动态/少点人体上误杀确证** (154007 recall 0.349→0, 72.9% 真人簇被门拒)。C1 采纳的 C2 候选机制在动态域失效 — 必须重新设计预过滤 (不能静态阈值一刀切)。
2. **动态有效 GT 统计样本不足** (n=1, 无 Wilson; 143945 contested; 远距/遮挡/多人/低姿态无 GT)。
3. **RF 对动态人低频确认** (v1 动态 confirmed recall 仅 0.349, 真人簇 prob 多 0.82-0.85 低于家具 0.89-0.95) — 检测层动态召回本身弱, 与 C1 静态 98-99% 反差大。
4. **GT 标注基础设施缺陷** (无坐标刻度渲染) 需先修, 否则无法产生坐标级人工金标。
**生产接入维持 BLOCKED** (未获独立授权)。

### C2 最小门槛 (冻结, 需另行授权):
- ① 弃用或改造 n_pts≥500 硬门 → 动态安全的预过滤 (如时序簇质量 + 非单帧点数)。
- ② ≥2 独立动态会话 source:human GT (含 walk + still), 坐标经带刻度渲染 + track 锚定双源核对。
- ③ RF 动态召回归因 (为何真人 prob 低于家具) — 可能需特征/样本补, 但不重训。
- ④ 部署带刻度渲染 + 单标注员逐帧重标 2 段动态会话 → 坐标级 GT。
- ⑤ 远距/遮挡/多人 GT 至少各 1 段。

## 7. 交付物清单
| 项 | 路径 |
|---|---|
| 本报告 | `2026-10-10_c15_gt_validation/FINAL_REPORT.md` |
| GT 规范 | `workspace/GT_SPEC.md` |
| 采集/标注方案 | `workspace/C15_CAPTURE_ANNOTATION_PLAN.md` |
| 原始指标 (逐会话+A/B+Wilson) | `workspace/metrics_final.json` |
| 生产探针 track 证据 | `workspace/probe_v1/*.tracks.jsonl`, `workspace/probe_v2/*` |
| 人工判读渲染 (含刻度版) | `workspace/renders_axis/`, `workspace/renders_dense/` |
| GT 标签 (vision-assist, assist 级) | `workspace/gt_labels/*.json` |
| OpenCode R2 独立复核 prompt | `workspace/C15_REVIEW_PROMPT_R2.md` |
| 工具脚本 | `workspace/c15_motion_triage.js` `render_axis.py` `aggregate_c15_track_metrics.py` `finalize_c15_metrics.py` |
| SHA 锁定 | `2026-10-10_c15_gt_validation/SHA_MANIFEST_C15.sha256` |

## 8. 诚实边界
- 动态 recall 基于 1 个自洽动态会话 + person-region (cy∈[1.7,3.0]) 锚定口径, 非坐标级逐点 GT。
- 143945 因多标注员坐标互斥剔除, 未生产假 recall 数字。
- GT 为 vision-assist 级, 未达双人复核 source:human 金标。
- 未测 >2.5m 远距/多人/跌倒 (无数据)。
