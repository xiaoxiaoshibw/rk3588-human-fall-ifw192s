# HFUS-RD-02 — 高召回人体候选优化与困难负例分类实验（回传）

- 日期：2026-10-12（Asia/Shanghai）
- HEAD：`026e06303f60ed1bbe4ddc4d037836db68da6d27`（dirty 保持原状）
- Writer：Claude Code 主控（唯一写入者）
- ponytail 使用路径：本会话 `Skill(ponytail)` → `C:\Users\30680\.claude\skills\ponytail\SKILL.md`（全文已读，见下"复用声明"）
- 状态：**SUBMITTED**（不自签 ACCEPTED）

## 复用声明（ponytail 阶梯）

- **第 2 级（复用现有）**：加载层全部复用 `sidequests/HFUS-RD-01/tools/common.py`
  （已实证索引域契约）；XY 体素粗聚复用 `d2_cluster_ablation.xy_voxel_clusters`
  （生产同源）；渲染模式复用 RD-01 `demo_compare.html` 的 Canvas 手法而非代码。
- **第 3 级（stdlib）**：审核服务用 `http.server` + `socketserver`，无新依赖。
- **未做的事**：未新建标注框架（复用其模式）、未引入 ML 框架（除已有的
  sklearn/xgboost/torch）、未重写 PointNet（复用 RD-01 结构）。

## 交付物

| 工作 | 报告 | 证据 JSON | 代码 |
|---|---|---|---|
| 一 审计 | `sidequests/HFUS-RD-02/docs/GT_AUDIT_AND_REVIEW.md` | `W1_AUDIT.json`, `W1B_PROB_CONSISTENCY.json` | `w1_audit.py`, `w1b_prob_consistency.py`, `w1b_append_rootcause.py`, `probe_prob_divergence.py` |
| 二 负例 | 同目录 `HARD_NEGATIVE_STUDY.md` | `W2_REVIEW_STATUS.json` | `w2_build_queue.py`, `w2_finalize.py`, `review_ui/{review_server.py,review.html}` |
| 三 C4 优化 | 同目录 `C4_OPTIMIZATION.md` | `W3_C4_OPT.json`, `W3_EXTRA.json`, `W3C_GTHIT_SIZE.json` | `w3_c4_opt.py`, `w3c_gthit_size.py` |
| 四 分类器 | 同目录 `MODEL_COMPARISON.md` | `W4_MODEL_COMPARE.json`, `W4_CALIBRATION_SWEEP.json` | `w4_fair_compare.py`, `w4b_true_prod_baseline.py`, `w4c_calibration_sweep.py` |
| 五 决策 | 同目录 `FINAL_ARCHITECTURE_DECISION.md` | — | — |

全部证据目录：`docs/sidequests/evidence/2026-10-12_HFUS_RD_02_r1/`

## 关键结果（逐条对应任务要求）

### 工作一（审计 RD-01）
| 核查项 | 结果 |
|---|---|
| 510 分母 | ✅ 复算一致（GT_V1 reviewed PERSON 对象，S9 外） |
| C4 100% 是否只对满足条件的子集 | ✅ **是**——分母 411 全为 ≥30 点对象；且 W3C 证 92% 的召回打在 ≥2000 点大团上 |
| S1 58.2% 来源/独立对象/审核状态 | ✅ 复现 0.5823；来源=mainline BG 下游 XY 体素候选；**无任何人工审核** |
| RF69 全正 val 为何不能作证据 | ✅ 且**比 RD-01 自陈更严重**：train 负例 100% 来自 S1、正例 100% 来自 S3-near |
| S5/S8 背景保留率定义一致性 | ✅ 同口径复现（31.09% / 97.96%），差异是真实场景差异 |
| C4 混簇/静态大物 | ✅ 静态大物占 C4 候选 30–45%；混簇仅 S9 可判（16/18），单人会话结构性不可判 |
| **未将 RD-01 架构当已验证** | ✅ 本轮推翻其 4 项结论（见 FINAL_ARCHITECTURE_DECISION §0） |

### 工作二（人工负例）
- ✅ 队列 125 条（分层：A10/B30/C50/D15 + S3N 困难负例 20），冻结（seed=20261012），
  每条绑定 `pointset_sha256`
- ✅ 审核台 `:8932` 实测（GET/POST 端点通；标签 append-only）
- ✅ 导出链路 `w2_finalize.py` 端到端验证（0→1→0 往返）
- ⛔ **人工审核 = 0 条 → 依任务要求明确阻断分类器收益结论**（HARD_NEGATIVE_STUDY §7）

### 工作三（C4 优化）
| 要求 | 结果 |
|---|---|
| 局部 ROI / 空间索引 | ✅ C4A：P95 88.7→35.2ms |
| 高效 3D 邻域搜索 | ✅ C4H（csgraph）：逐帧集合级**等价**（15/15）+ 2.4× |
| XY 粗聚 + 3D 细分 | ❌ C4B：双重开销，净负 |
| RAW/FG 双来源 | ⚠️ C4C：纯度 2.7×，召回零增益 |
| 自适应邻域 | ❌ C4D：召回 -5~-9pp |
| 减跨帧重复 | ⚠️ C4E：最快但纯度最低 |
| **背景误吞/混簇/碎片/家具误候选** | ✅ W3C 量化：92% 召回靠生产必拒大团 |
| **不牺牲真实召回** | ✅ 推荐组合 C4AH：P95 13.2ms，7 会话召回 1.000 |

### 工作四（分类器）
- ✅ 帧级 OOS 划分（S1/S3-near 奇偶 + S3-far 整会话）
- ✅ RF51/XGBoost/PointNet 实现并跑通；RF69 + 消融
- ⛔ PointNet++ **未实施**（理由：RD-01 已平打；复刻缺陷使比较无效；YAGNI）
- ✅ **独立校准集（含正负）已满足** → 阈值 0.9666：家具 FP 118→**0**，近距人召回 1.000
- ⛔ 分类器"换模型提升"**BLOCKED**（复刻特征污染 + 人工负例 0）

## 本轮新发现的缺陷（登记，不修生产）

1. **RD-01 JS 复刻与生产打分不一致**（W1B）：`rf_extract_node.js` 用全量点，
   生产在抽特征前采样（`model_calls` 特征首维 `[5018, 10]`）→ 接受率
   100% vs 58.2/79.0/79.5%。影响 RD-01 的 CLASSIFIER_ABLATION 与
   LAYER_ATTRIBUTION §3 全部结论。
2. **C4 的 100% 召回不可生产**（W3C）：92% 命中生产必拒的大团。
3. **生产阈值 0.55 未校准**（W4C）：真分下 S1 型场景工作点在 0.90–0.9666
   ——**但该阈值不可跨场景**：S8-still 拒 100%、S6-occlusion 拒 94.5%
   候选（两场景共 124 个 GT 人对象）。分场景校准 NOT_RUN。

## UNKNOWN / BLOCKED / NOT_RUN（如实）

- **BLOCKED**：分类器收益结论（人工负例 0）、多人检测资格（S9 无效）、
  生产采样协议（属 HF/GL 侧）、reviewed 负例训练集
- **NOT_RUN**：板端性能、PointNet++、分距离 P/R、S4/S8 UNK 帧负例
- **UNKNOWN**：125 条队列全部保持 UNKNOWN（未审核）
- 未 commit/push/deploy/采集/驱动/网络/GT 写

## 复算

见 `FINAL_ARCHITECTURE_DECISION.md` §5（10 条命令，全部可跑）。
