# FINAL_REPORT — HFUS-RD-01 总报告（交付 9）

任务：九会话辨识实验 + 四模型路线决策 · 日期 2026-10-12 · Repo HEAD
`026e06303f60ed1bbe4ddc4d037836db68da6d27`（dirty 保留原状，无提交、
无推送、无部署、无板端动作、无 GT 写）。

## 1. 任务 §12 执行规则合规对账

| 规则 | 执行 |
|---|---|
| 直接开展审计/调研/实验/报告，不停询问授权 | ✓ 本轮 21 个交付物已一气落盘 |
| 不把规划完成当研究完成 | ✓ D1/D2/D3/D4 全真实验跑通；PointNet CPU 真实练 15 epoch |
| 隔离 sidequest 目录写代码/测试/可视化 | ✓ `sidequests/HFUS-RD-01/{tools,demo,docs,work}` |
| 不修改/部署/打包生产检测链 | ✓ 生产 `human_replay/*`, `human_core/*` 零 diff |
| 不覆盖/自动造 GT | ✓ gt_store 零 diff |
| 无法满足前置条件明确标记不做虚假 PASS | ✓ 全部暂不可证事件 BLOCKED，见 §7 |
| 不以纯静态代码阅读代替真实会话运行 | ✓ 九会话 × 2605 帧 ledger 全部流过；9 变体聚类 × 2605 帧全部自算 |
| 不以 OpenCode 不可用为停全部研究的理由 | ✓ 本轮未依赖 |

## 2. 交付清单（全部已落盘）

| 交付物 | 位置 |
|---|---|
| 1 RESEARCH_SURVEY.md | `sidequests/HFUS-RD-01/docs/RESEARCH_SURVEY.md` |
| 2 DATA_AUDIT.md | 同上 |
| 3 LAYER_ATTRIBUTION.md | 同上 |
| 4 CLUSTER_ABLATION.md | 同上 |
| 5 CLASSIFIER_ABLATION.md | 同上 |
| 6 METRICS.json | `docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/METRICS.json` |
| 7 CASEBOOK.md | `sidequests/HFUS-RD-01/docs/CASEBOOK.md` |
| 8 ARCHITECTURE_DECISION.md | 同上 |
| 9 FINAL_REPORT.md | 本文件 |
| 演示器 | `sidequests/HFUS-RD-01/demo/{demo_server.py,demo_compare.html}` |
| 实验代码 | `sidequests/HFUS-RD-01/tools/` (`common.py`,
  `d1_attribution.py`, `d1_fusion_ablation.py`, `d1_track_events.py`,
  `d2_cluster_ablation.py`, `d2_finish.py`, `stage2_features.py`,
  `build_d3_dataset.py`, `d3_classifiers.py`, `d4_randlanet_probe.py`,
  `make_metrics.py`, `rf_extract_node.js`, `smoke_bridge.py`) |
| 证据 JSON | `docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/`
  (`D1_LAYER_SUMMARY.json`, `D1_FUSION_ABLATION.json`,
   `D1_TRACK_EVENTS.json`, `D2_CLUSTER_ABLATION.json`,
   `D3_CLASSIFIER_ABLATION.json`, `D4_RANDLANET_FEAS.json`,
   `METRICS.json`) |

## 3. 一轮实测结果汇总

### 3.1 九会话 × 主链（D05 R04 fast）

- **点级 GT 保留**：79.4%（979,285 已 reviewed 人点 across 7 会话）；
  S5-turn 最劣 31.1%、S3-near 43.1%、S7-far5m 83.7%；S8-still 实际
  98.0% （D05 旧解读"S8 严重"被本轮翻案为"其失不在 BG"）。
- **对象级召回（reviewed 510 实例）**：提案覆盖 cov≥0.5 = 94.9%；
  接受后仍 = 94.9%；**RF 独立误拒 0**。
- **FP/小时（候选级上界）**：7.0×10⁴–13.5×10⁴；S1 家具会话 RF
  `prob≥0.55` frac=58.2%，p50=0.87 → RF51 在家具上完全无判别。
- **跟踪 确认延迟**：稳态 2 帧（S3-near/S3-far）；难点 19–52 帧
  （S5-turn/S6-occl/S7-far5m）。

### 3.2 聚类/背景六变体（reviewed 411 对象，排除 S9）

| 变体 | 对象级召回 | FP 簇 | 帧均 ms |
|---|---:|---:|---:|
| C0_XY_PROD | 0.839 | 5,885 | 1.3 |
| C1_EUCLID3D | 0.830 | 10,125 | 5.5 |
| C2_DBSCAN | 0.839 | 20,928 | 41.3 |
| C3_XY_SPLIT | 0.839 | 9,992 | 462.9 |
| **C4_DUAL_SRC (valid 全点 r=0.35 min=15)** | **1.000** | 13,908 | 130.2 |
| C5_CONS_BG | 0.567 | 5,421 | 2.0 |

（明细见 CLUSTER_ABLATION.md）

### 3.3 分类器五变体（train fold n=645，pos=259；val 全正无外推）

| 模型 | AUPRC train | F1@0.5 train |
|---|---:|---:|
| M0_RF51 | 0.986 | 0.573 |
| M1_RF69 | 1.000 | 1.000 |
| M2_XGB69 | 0.995 | 0.992 |
| M3_PointNet | 0.996 | 0.933 |
| M4_PointNetPP | 0.999 | 0.992 |

（**严格声明**：val 全正 91/91 → val AUPRC=None；深度与树模型均在 train
饱和或接近；不外推生产精度。详见 CLASSIFIER_ABLATION.md §7–8。）

### 3.4 RandLA-Net 逐点分割（D4）

- 九会话非人点 `reviewed_nonperson_points = 0`；点级监督 **不可获得**。
- 每帧 GT 人点只占 0.09%–2.46%，即 97–99.9% 点无 label。
- cKDTree K=16 在 16k/40k 点 CPU 实测 104ms/392ms — 网络本体不是
  CPU 瓶颈。
- **verdict = DATA_BLOCKED**，须先补逐点负例标注清单（见 §6）。

### 3.5 融合/决策四变体（D1 消融）

- V0/V1/V2/V3 的 reviewed 对象召回**完全相同** → **软化身份硬门不能
  提升召回，只会升 FP**。不推任何软门替换。

## 4. 推荐架构（详见 ARCHITECTURE_DECISION.md）

**唯一首选** = `C4 (RAW 上欧氏 r=0.35 min=15) 提案 + M1_RF69 + sigmoid
校准 + 现有 3 票窗跟踪`。**备选** `M0_RF51 + Platt sigmoid`（工程
0 风险但只修负例，不修 BG）。**不推荐** PointNet++/RandLA-Net/
Cylinder3D/SPVCNN/PVKD/S3DIS 预训练权重。

## 5. 复算命令

```powershell
# Win Git Bash（仓库根）
python sidequests/HFUS-RD-01/tools/d1_attribution.py
python sidequests/HFUS-RD-01/tools/stage2_features.py
python sidequests/HFUS-RD-01/tools/build_d3_dataset.py
python sidequests/HFUS-RD-01/tools/d3_classifiers.py rf
python sidequests/HFUS-RD-01/tools/d3_classifiers.py xgb
python sidequests/HFUS-RD-01/tools/d3_classifiers.py pn
python sidequests/HFUS-RD-01/tools/d3_classifiers.py m3
python sidequests/HFUS-RD-01/tools/d3_classifiers.py m4
python sidequests/HFUS-RD-01/tools/d3_classifiers.py finish
python sidequests/HFUS-RD-01/tools/d2_cluster_ablation.py    # 可加 --sid
python sidequests/HFUS-RD-01/tools/d2_finish.py
python sidequests/HFUS-RD-01/tools/d4_randlanet_probe.py
python sidequests/HFUS-RD-01/tools/d1_fusion_ablation.py
python sidequests/HFUS-RD-01/tools/d1_track_events.py
python sidequests/HFUS-RD-01/tools/make_metrics.py
# 可视化
python sidequests/HFUS-RD-01/demo/demo_server.py     # :8930
```

## 6. 最小人工标注清单（使生产接入判定有依据）

1. **S1 家具 GT** — 100 个 mainline 候选标 P/N（五类型分层）；→
   S1 从 "按定义负" 升级为 reviewed 负。
2. **S4/S8 UNK 候选** — 300 个；→ val 负例池可建。
3. **S9 session_sha256 修复** + 双人标注；→ S9 从 exploration 升级。
4. **D4 逐点** — 全身人 每会话 ≥5 帧；S1 家具帧 500+ 散点；空地
   500 散点。
5. **S8 ≥20s 静止窗** — 当前最长 1.76s；新采集（用户授权板端采集
   后）或放弃该指标。

## 7. 独立分类裁定

| 维度 | verdict | 备注 |
|---|---|---|
| 工程接通 | **PASS (SUBMITTED)** | 所有实验可复跑；演示器 endpoint smoke PASS |
| 算法效果 | **UNKNOWN**（部分 PASS、部分证据不足） | C4 提案层 / RF51 负例整洁率低 / V0-V3 等价 三结论 PASS；分类器选择、空场 FP/h、板端性能 均 BLOCKED |
| GT 资格 | **BLOCKED** | 无 reviewed 负、S9 binding 缺、S8 长静无、S4/S8 UNK 未审 |
| 生产接入 | **BLOCKED** | 三向阻断（证据不齐 + C4 板端未测 + 无部署授权） |

**状态: SUBMITTED（不自签 ACCEPTED）**，等用户承接
ARCHITECTURE_DECISION §6 的 P0 授权。

## 8. 已知问题 / 诚实披露

- **Cover 是不是真的好？** C4 召回 1.000 是在 "reviewed GT 对象" 上；
  mainline 7805 个 UNK 候选中可能有其余"应该是人"的对象未被 GT 标，
  这不是 C4 的虚假高分。
- **会话间独立性**：九会话同 疵 → 会话级不是真独立样本；主要结论
  （C4 提案层方向、RF 校准需求）在 7 会话一致，但**不表示跨场景能
  泛化**。
- **Wilson 置信区间**：510 对象级 实例在高召回估下 95% CI 宽度 ~±2pp，
  即 C4 的 1.000 真值可能∈[0.985,1.000]；**不能证明真 100%**。
- **PointNet/PointNetPP 的可检属性**：mini SSG 与 M2 同输入，但模型
  结构更复杂；**未证明"深度优于树"** ，只证明"深度 在此数据下能
  与树打平"。
- **数据形态限制**： val fold 全正造成任何阈值选择在数学上无意义；
  生产决策需重建 fold 后重跑。

## 9. 执行边界验证

- 未 `git commit/push/reset/checkout/clean`。
- 生产 `pc_apps/human_replay`, `pc_apps/human_core`, `pc_apps/human_ml`,
  `webui/` 无改动（新增文件全部在 `sidequests/HFUS-RD-01/` 与
  `docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/`）。
- `captures/`, `pc_apps/human_replay/gt_store/` 零写。
- 未板端部署、未启动采集、未驱动网络改动。
- `sidequests/human_fusion_lab_next/d05/demo_d05.html` 不动（D05 已有
  演示器保留）。
