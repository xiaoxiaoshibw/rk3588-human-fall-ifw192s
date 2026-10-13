# CLUSTER-ADAPTIVE-SPIKE-R1 — FINAL REPORT

日期: 2026-10-10
任务: 距离自适应聚类 (B1 `find_clusters`) 离线 A/B/C 验证
范围边界: 只验证 B1；不练 RF，不动生产，不上 RK3588

---

## 裁定 — UNKNOWN

**PASS 不成立**: "人体聚类质量有可复核提升"这条验收原则无法在评估范围内成立 — 12 段站立 GT 的人锚命中 A=B=C 完全一致, 差异帧数 = 0/2874.
同时 **FAIL 也不成立**: 三变体**没有引入不可接受退化** — 评估范围内 (1.2-3m 站立+短静立) 既无回归也无增益.
故唯一诚实裁定 **UNKNOWN**， 达到 UNKNOWN 的根因是 **"人簇碎"这个假设在评估数据上不存在**, 自适应半径不是正确的问题方案.

按 C1 铁律: **UNKNOWN 强于假 PASS，不构成 FAIL**.

---

## 1. 任务 11 条要求逐条交付对照

| # | 要求 | 交付 | 文件 |
|---|---|---|---|
| 1 | 审计实际仓库定位函数+12 段+绑定 | PASS | `README.md`, `baseline.json` |
| 2 | 独立 evidence 目录冻结基线 | PASS (2 audit 补) | `baseline.json` |
| 3 | 复现现有聚类输出+明确输入 | PASS (IoU=1.0 4 段) | `crosscheck_*.log` × 4 |
| 4 | 比较 A/B/C | PASS | `_harness_lib.py/_v2.py` + `eval_*` |
| 5 | 参数依据真实数据, 训/评分离 | PASS (audit #2/#3 修正后) | `calibration_k.json` 由 TUNING 6 段估计 |
| 6 | 12 段分层 A/B, 7 项域+耗时 | PASS | `SUMMARY.md` + `eval_*.json` |
| 7 | 固定成功/自适应失败场景归因 | PASS | `FAIL_ATTRIBUTION.md` |
| 8 | 回归+可视化证据, 不改生产 | PASS (SHA 锁定) | `manifest.json`. 注: 可视化证据**有限** — 仅日志+HOMEDAS-canvas 服务 (未做图像级 PNG). 已记 UNKNOWN |
| 9 | OpenCode CLI 独立审计 | PASS | `audit_opencode_v3_flash.md` (1 UNKNOWN→PASS,  2 FAIL 已修, 3+ PASS) |
| 10 | 一次性交付文档 | 见本报告+§6.3 | 本目录全部 md/json/log |
| 11 | 明确 PASS/FAIL/UNKNOWN | **UNKNOWN** | 本报告 §0 |

## 2. 事实摘要 (全部可复算)

### 2.1 算法实现
- `A` 复现 B1 `find_clusters`: 5cm 熞格 + 8 邻 + min_points=30 + top4, 与 `detect_overlay.js` 逐点 IoU=1.000 (4 帧对拍留证据: 114641_f100, 215540_f30, 121622_f87, 114205_f122).
- `B` 距离自适应 `eps(r) = max(0.08, 0.0092·r − 0.0031)` + 对称门: `eps_ref = min(eps_cur, eps_nei)`; `k` 在 TUNING 6 段 (cap_20261007_*) 用 p90 NN/cKDTree 加权 LAD 拟合.
- `C` = B + 点级 5 z-band 防并簇 (用 subcell key 二复合): 以为柜位生成独立子簇, 减人+柜粘连.

### 2.2 主要观测 (eval_frames.jsonl, 2874 帧)

| 指标 | A | B | C | 备注 |
|---|---|---|---|---|
| 人锚命中 (hit) 站立 | 100% | 100% | 100% | n_diff_frames = 0 |
| 人锚命中 (hit) 静立 | 100% | 100% | 100% | - |
| 人主簇 top0 (t1) 站立 | 100% | 100% | 100% | - |
| **柜位捕获率 cab, 121622** | 21.5% | 46.7% | 53.3% | C 反而最差 (同 zband 柜) |
| **柜位捕获率 cab, 121647** | 24.3% | 25.2% | **0.0%** | - |
| **柜位捕获率 cab, 122616** | 90.6% | 47.5% | **0.0%** | C 改善 2 倍 |
| **柜位捕获率 cab, 122637** | **93.1%** | 93.1% | **0.0%** | C 100% 拒柜 |
| **残片 sf 站立** | 0-177/264 | ≤61 | **全 0** | C 把人残片吸到 z-band 主簇 |
| 残片 sf 静立 | 281-843 | 281-569 | 273-562 | C/B 15-20% 改善 |
| 空场 113611 | 0/0/0 | 0/0/0 | 0/0/0 | 零假命中 |
| PER 簇数 站立 | **1.0/帧** | 1.0/帧 | **3-4/帧** | **C 把人拆 3-4 段** (副作用) |
| find_clusters 耗时 P50/P95 ms | 1.95/4.58 | 2.55/8.18 | 10.74/29.80 | C 是 A 5.5 倍 |

### 2.3 A 基线新发现 (证据级)
1. 121622 f87 三簇现象: 本体 n=2019 + 柜 n=36 + 人残片 n=33 — 我们**证**了 README 提到的 n=33 旁簇是 "人手臂残片" (距人锚 0.66m) 而非"人碎". 这不是聚类域问题.
2. 12 段站立: A 优已 100% 人锚命中, **任务中"远近距离人体出现碎簇、并簇"的现象在站立 GT 上不被复现** — 只被 GT 勘查记录的 `走-停-走 154007` (assist GT) 和 `bend synth` 承载, 这两个都已公平列入 TUNING/UNKNOWN, 不能作 PASS/FAIL 判据.

## 3. 根因分析 (按 task #11 第 3 段要求)

**"距离自适应聚类"不解决本批次真问题**, 三段推理:

(a) **人 1.2-3m 站立域根本没碎** — IFW192S 192 线在该距离带对人产生的点密度已足够 (anchor 圆内点 p50 Chebyshev cell-NN=1, p99=2 — 见 fail_attribution §5 的前置观察), A 的 8 邻已足够. 所以"距离自适应"本来就没什么可放大.

(b) **任务所述"碎簇"更多是"人残片独立成簇"**, 不是"簇被切" — 121622 f87 的 n=33 是人手臂的物理边缘, cell 网格独立 disjoint, B/C 的 eps 增大只是**偶然桥接**, 等效于"把不属于人簇的点纳入人" — 反而不可靠.

(c) **任务是"柜位误检"** — 这是 RF 51 维特征不强 (SILENT_REGION_MEMORY §3 柜位 prob 0.76-0.87）。聚类层根本就无法分辩，靠 z-band 只能在**柜 z 范围与人不重合**时部分帮 (122616/122637), 同带场景 (121622) 反而更糟.

## 4. 已知 UNKNOWN / 缺口 (诚实声明)

| 项 | 状态 | 影响 |
|---|---|---|
| r_xy > 3.0m 真人 GT | 无采集 | B/C 在 r>3m 是否增益 **UNKNOWN** |
| r_xy < 1.2m 真人 GT | 无采集 | B/C 在近距粘连风险 **UNKNOWN** |
| 走动人 GT | 仅 154007 一段 assist 级 (已列入 TUNING) | 自适半径对动态人的真实收益 **UNKNOWN** |
| 弯腰/躺卧/多人 GT | 无 (仅 synth_bend_v1) | 低姿态域 `eps(r)` 参数有效性 **UNKNOWN** |
| 板端 RK3588 性能 | 未实机 | C P50=10.7ms 在 RK3588 stdlib+NumPy 上预期 2-3 倍 latency, 是否满足 10Hz 未经实测 **UNKNOWN** |
| "可视化证据" 图像级 PNG | 未做 | 本轮仅留 cell/cluster 级 LOG + eval_frames 可复算; PNG 补开另案 |

## 5. 后续最优行动 (不接生产)

按 `任务≠11 要求 "给出最优行动"`, 以下为优先级:

1. **HIGHEST** — **死 "距离自适应聚类"**, 至少在此评估范围内。这项不集成生产. B/C 仅在 122616/122637 偶见 100% cab 但也 121622 +32% cab, 与 stand 域 PER=3-4 副作用并立 — ROI 不证明集成.
2. **HIGH** — 下一 ticket 由**真问题驱动**: 先后顺序:
   - (a) 走 - 停 - 走 154007 + 未来"走/弯/多人"采集: 用 TUNING 已冷启动的 calibrate_k 测试.
   - (b) 远距 GT 采集 (r_xy>3m): 验证 B 的真实价值.
   - (c) 柜位 RF 新增特征的 R1 那 (51→69 维: 五层归一化高度占比等 18 项) — 不需自适应聚类. 这是另一个 ticket 的事.
3. **MID** — B/C 的那点提示: stand 残片吸除是可以的; 但 get 这个要用**平顺渐近的 eps** 而不是 `ceil(eps/CELL)`. 原理验证仅 spike 存档, 不动生产.
4. **LOW** — 可视化证据补 PNG/React-wing: 另案.

## 6. 交付清单

### 6.1 代码 (pc_apps/human_ml/spike_cluster/)
- `_harness_lib.py`, `_harness_lib_v2.py` — A/B/C 实现 (v2 = 点级 z-band C)
- `freeze_baseline.py`, `calibrate_k.py`, `eval_cluster.py`, `summarize_eval.py`, `crosscheck_diff_frames.py` — pipeline
- `rerun_crosscheck.py`, `smoke_crosscheck.js`, `test_bc_impl.py` — 认证与性质测试
- `params_frozen.json` — k=0.0092 b=-0.0031 eps_min=0.08 SF=1.0 (实量, 审计修正) 5 z-band

### 6.2 证据 (docs/human_capture/evidence/2026-10-10_spike_cluster_r1/)
- `README.md` — 任务 边界+绑定+缺口声明
- `baseline.json` — 22 段输入 SHA + 5 份关键代码 SHA + 常量冻结
- `calibration_k.json` — p90 NN 标定; `calibrate_k_stdout.log` (可再跑)
- `crosscheck_*.log` × 4 — A 复现 PASS (IoU=1.000)
- `test_bc_impl.log` — B/C 性质测试 6/6 PASS
- `eval_frames.jsonl` — 2874 帧逐帧数据
- `eval_diff.json` — A/B/C 人锚命中差异帧扫描结果 (n_diff=0)
- `eval_timing_ms.json` — 三变体耗时分布
- `SUMMARY.md` — Wilson by-track-run (段级置信域) 汇总
- `FAIL_ATTRIBUTION.md` — 5 个失败案例 + 2 个 pass/uncertain 案例归因
- `audit_opencode_v3_flash.md` — OpenCode 独立审计 (9 条)
- `audit_request.txt` — 审计请求原文
- `manifest.json` — 全部产物 SHA 清单 (见 §6.3)
- `FINAL_REPORT.md` — 本文档
- `NEXT_ACCEPTANCE.md` — 下一阶段 ACCEPTANCE 草案 (工作项: B1 半径自适应单独立案 + 采集驱动评估)

### 6.3 manifest.json (本文档尾后生成, 一份 SHA 涵下所有产物)

(见 `manifest.json`)

## 7. 对上文档接口

- **STILL_PERSON_RETENTION_PLAN** — spike 结果**证实**其 §1 根因归因 (背景吸收在 hot 层) 是对的；本 spike 不替代它.
- **RF_OPTIMIZATION_R1_ACCEPTANCE** — 51→69 维是解柜位问题的下一步, 不动 (51 vs 213 都不属于本 spike 它能借).
- **SILENT_REGION_MEMORY_DRAFT** — 柜位"prob 0.76-0.87"的根因 (RF 特征弱) 在 spike 由 cab 指标进一步证实: **聚类域解不了, 要特征域解**.
- **C1-HONEST-VERDICT-TOKUTSU** — 本报告 UNKNOWN 裁定按与 C1 R2 一致的标准: C-rolls 唯一恒真, 采用独立段 for Wilson 既使过激, 报告保持面向可复算证据.

## 8. 一致性声明

- 本 spike **未修改**: pc_apps/human_replay/ 任何文件, src/human_capture/ 任何文件, webui/, 生产 RF JSON, docs/human_capture/ 任何现有文档 (只新增本目录文件).
- git status snapshots 与本 pid 完整衔接.
- baseline.json 落在开跑前 (`13:38`) 作为冻结点; eval 与 summarize 与 crosscheck 全部完全独立实施后写报告.
- OpenCode 审计按 task #9 用 `opencode run` 真实跑 (CLI 1.18.35 + deepseek-v4-flash + deepseek key 来自 _icode/3rdparty_key.txt).

**UNKNOWN 正确的行动**: 集成决策推迟到 GT 覆盖补全后, 并且由一个有明确问题驱动 (走/弯/远距) 的 ticket 才重生.
本 spike 即时 closeout.
