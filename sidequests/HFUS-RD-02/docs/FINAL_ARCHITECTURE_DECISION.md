# FINAL_ARCHITECTURE_DECISION — HFUS-RD-02 总决策

日期 2026-10-12 · HEAD `026e06303f60ed1bbe4ddc4d037836db68da6d27`（dirty 保持，
无提交/推送/部署/采集/GT 写）· 全离线 · 证据目录
`docs/sidequests/evidence/2026-10-12_HFUS_RD_02_r1/`

## 0. 本轮推翻了 RD-01 的什么（最重要）

| RD-01 结论 | 本轮证据 | 处置 |
|---|---|---|
| "C4 提案层 100% 召回" | W3C：92% 的 GT 命中簇是 ≥2000 点房间级大团；ledger 实测这类候选生产接受率 **0/258** | **降级为纸面召回**，不可生产 |
| "RF51 对家具完全没判别力（p50=0.87 塌陷）" | W1B：该 p50 来自**与生产不一致的 JS 复刻**（接受率 100% vs 生产 58.2%）；生产真分上人 p5=0.9672 > 家具 p99=0.9658 | **推翻**，判别力存在 |
| "M1_RF69 train AUPRC=1.000，扩维有价值" | 特征来自复刻（污染）；且 M3 仅 18 维也 1.000 → 会话指纹 | **作废**，增益不可证 |
| "分类器不是瓶颈，C4+RF69+sigmoid 为首选" | 真瓶颈是**阈值未校准**（0.55 vs ~0.9666）+ 拆簇工序缺失 | **改写路线** |
| "无 reviewed 负例" | 本轮建了 125 条分层队列 + 审核台，但**人工未审** → 仍为 0 | 维持 BLOCKED |

## 1. 任务结尾五问的直接回答

### Q1. 传统聚类应该保留哪部分？

**保留"候选生成"职责，但必须去掉"C4 一步到位的 100% 召回"叙事。**
证据：C4H/C4AH 证明了 RAW 上做欧氏提案是**正确方向且能便宜**（P95 13ms），
但 W3C 证明**单靠 C4 产出的东西生产接不住**。具体保留：

- ✅ **C4 的 RAW/valid 全点输入**（不经过 BG 预筛）——BG 截断人点的事实
  （S5-turn BG 仅保 31%）由 C5_CONS_BG 反向证明。
- ✅ **cell 化欧氏连通 + scipy.csgraph**（等价 + 2.4×，零风险）。
- ✅ **ROI 局部化**（z 带 + XY 半径，P95 -60%）——但登记其副作用：
  rescue_ready 从 8% 降到 5%（切地板把 GT 更推入墙团）。
- ❌ 不保留：**min_pts 门当作最终筛选**（它让 92% 的召回落在生产必拒的
  大团上）；**"对象级召回 100%" 作为验收指标**（它奖励误吞整屋）。
- ❌ 不保留：C4B（双重开销）、C4D（自适应 r 回退）、C4F（体素丢结构）、
  C4E（静区复用降纯度）。

### Q2. C4 如何兼顾高召回和速度？

**速度已解决，召回的定义需要重写。**

| 方案 | P95 (ms) | 7 会话召回@cov0.5 | rescue_ready |
|---|---:|---:|---:|
| C4_FROZEN | 88.7 | 1.000 | 8% |
| **C4AH**（推荐） | **13.2** | **1.000** | 5% |
| C4G2（拆大团） | 136.8 | 1.000（4 会话）/ 0.909–0.943（3 会话） | — |

**6.7× 提速**由 ROI（削输入点数）+ csgraph（消 Python UF 热点）正交叠加得出。
**召回口径重写为**：`每 GT 对象存在一个 60–1999 点的候选覆盖 ≥50%`
——这是生产能打分的形态。按此口径，C4 的"100%"降至 **8%（41/510））**。

### Q3. RF69 是否真的优于 RF51？

**不可答——但方向上"不值得追"。** 三层理由：

1. **输入污染**：RF69 的 69 维特征来自 JS 复刻，而复刻与生产打分不一致
   （W1B：S1 接受率 1.000 vs 0.582）。任何基于该特征的比较都无效。
2. **满分归因**：M3（仅 18 维扩展）同样 AUPRC=1.000 → 满分有会话指纹
   成分，不是判别力。
3. **真分基线的实际形态**：生产 RF51 真分在 S1 型场景上判别力已足
   （人 p5=0.9672 > 家具 p99=0.9658），但**该分界不跨场景**（见下）。

**⚠️ 关键限制（MODEL_COMPARISON §5.1）**：阈值 0.9666 在 S1 上把家具
FP 从 118 降到 0，但在 **S8-still 拒绝 100% 候选、S6-occlusion 拒绝
94.5%** —— 而这两场景共有 **124 个 GT 人对象**。**"调阈值即可" 只在
S1 型场景成立，静立/遮挡的人会被一起杀掉。** 分场景校准未验证（NOT_RUN）。

→ 若要重测 RF69，须先（a）确认生产采样协议并复刻一致特征，
（b）拿到人工负例，（c）评估其**跨场景**而非单场景的分数稳定性。

### Q4. PointNet++ 是否真正改善困难样本？

**未实施，且本轮证据不支持投入。** 理由：
- RD-01 的 mini-SSG（M4）结论"与 M2 平打"，本轮无新数据改变它。
- 本轮 M5（轻量 PointNet，512 点）已在同数据上跑通：AUPRC=1.000，
  但**同样受复刻特征缺陷影响**，且**比 RF 贵 10–20ms/候选**。
- RD-01 的 D4 结论"RandLA-Net DATA_BLOCKED（reviewed 非人点 = 0）"
  本轮**仍然成立**——W2 的人工负例还未产出。
- **YAGNI**：在生产采样协议与人工负例两项到位前，点云深度网络是
  在坏数据上做昂贵实验。

### Q5. 是否已具备进入下一阶段多人检测的条件？

**不具备。** 四条件中只满足 0 项：

| 条件 | 状态 | 依据 |
|---|---|---|
| 候选层能产出生产可打分的候选 | ⛔ 5–8% | W3C（拆簇工序缺失） |
| reviewed 人工负例 | ⛔ 0 条 | W2（队列就绪，人工未审） |
| 多人/混簇样本与判定 | ⛔ | S9 INVALID_BINDING，永久排除 |
| 生产采样协议确认 | ⛔ | W1B 只登记未复刻 |

**S9 的 mixed=16/18 帧**是本轮唯一多人混簇信号，但该会话绑定无效 →
连"多人时 C4 会混簇"都只是**探索观察**，不是证据。

## 2. 修订后的推荐路线（取代 RD-01 §PRIMARY）

```
RAW 点云
   │
   ├─ C4AH 提案（ROI 裁剪 + cell欧氏 r=0.35 min=15 + csgraph）  13ms ✓
   │
   ├─ 【新增·缺失工序】大团拆分：≥800点簇 → r=0.22~0.25 二次细分
   │     目标：把 rescue_ready 从 5-8% 抬到 ≥60%
   │     代价（实测）：候选 ×3.8，需在拆后碎片 ≥60 点上收口
   │
   ├─ 【新增·校准】RF 真分阈值 0.55 → 场景分档（NOT 全局单值）
   │     ⚠️ 单一阈值已被证否：0.9666 在 S1 上 FP 118→0，但在 S8 拒 100%、
   │     S6 拒 94.5% 候选（两场景 124 个 GT 人）→ 必须分场景/分档校准，
   │     本轮未验证任何分档方案（NOT_RUN）
   │
   └─ 现有 3 票窗跟踪（不动——本轮无跟踪层证据）
```

**与 RD-01 路线的三处实质差异**：
1. **删除 RF69/扩维**（输入不可信且收益空间小）。
2. **新增"拆大团"为显式工序**（RD-01 的 C4 直接输出，未意识到
   92% 打在必拒大团上）。
3. **主改阈值而非换模型**（成本 0，收益 118→0 FP）。

## 3. 三个独立维度的裁定

| 维度 | verdict | 依据 |
|---|---|---|
| **工程接通** | **PASS (SUBMITTED)** | 8 份证据 JSON 可复跑；审核台端点实测；C4H 逐帧等价证明；脚本全绿；零生产改动 |
| **算法效果** | **FAIL / 部分 UNKNOWN** | C4 提速 PASS（6.7×，等价）；**C4 召回 PASS 但不可用**（W3C）；阈值校准 PASS（OOS 正负集）；分类器收益 **BLOCKED**（复刻污染 + 无人工负例） |
| **GT 资格** | **BLOCKED** | reviewed 负例 0；S9 无效；W2 队列待人工 |
| **生产接入** | **BLOCKED** | 算法不齐 + 板端 NOT_RUN + 无部署授权 + 无 commit 授权 |

## 4. 本轮交付物索引

| 交付 | 位置 |
|---|---|
| GT_AUDIT_AND_REVIEW.md | `sidequests/HFUS-RD-02/docs/` |
| C4_OPTIMIZATION.md | 同上 |
| HARD_NEGATIVE_STUDY.md | 同上 |
| MODEL_COMPARISON.md | 同上 |
| FINAL_ARCHITECTURE_DECISION.md | 本文件 |
| 证据（8 份 JSON） | `docs/sidequests/evidence/2026-10-12_HFUS_RD_02_r1/` |
| 实验代码（8 脚本） | `sidequests/HFUS-RD-02/tools/` |
| 审核台 | `sidequests/HFUS-RD-02/review_ui/`（:8932） |

## 5. 复算命令

```bash
python sidequests/HFUS-RD-02/tools/w1_audit.py          # 工作一
python sidequests/HFUS-RD-02/tools/w1b_prob_consistency.py
python sidequests/HFUS-RD-02/tools/w2_build_queue.py    # 工作二
python sidequests/HFUS-RD-02/review_ui/review_server.py # 人工审核（浏览器）
python sidequests/HFUS-RD-02/tools/w2_finalize.py
python sidequests/HFUS-RD-02/tools/w3_c4_opt.py         # 工作三（全量 ~25min）
python sidequests/HFUS-RD-02/tools/w3c_gthit_size.py
python sidequests/HFUS-RD-02/tools/w4_fair_compare.py   # 工作四
python sidequests/HFUS-RD-02/tools/w4b_true_prod_baseline.py
python sidequests/HFUS-RD-02/tools/w4c_calibration_sweep.py
```

## 6. 执行边界验证

- 未 `git commit/push/reset/checkout/clean`；未部署；未板端操作。
- 生产树零改动：`pc_apps/**`、`webui/**`、`captures/**`、
  `pc_apps/human_replay/gt_store/**` 全部只读。
- 新文件全部在 `sidequests/HFUS-RD-02/` 与
  `docs/sidequests/evidence/2026-10-12_HFUS_RD_02_r1/`。
- `sidequests/HFUS-RD-01/` 只读（import 其 tools，未改一字）。
- 未设备/物理/部署/采集结论；一切此类项 NOT_RUN。
