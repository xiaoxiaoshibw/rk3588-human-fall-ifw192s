I'll start by reading the required guard files in parallel.

Continuing the audit-summary tail plus the core evidence files.

Now the numeric bundles, catalog, and directory structure.

Let me read the remaining evidence: README, cross-check outputs, channel diagnostics, reproduction, and the baseline guards tail.

Reading the preserved preparation-failure records to complete T100/T111 review.

# CL2-10 独立只读审计报告

审计对象：`D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/`（CL2-10｜121647 有效 TLS 残差归因 v1）
审计模式：只读，未执行任何脚本、未重算 SHA、未运行测试与数值管线。
证据根绝对前缀：`D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/`（下称 `E/`）

---

## 0. 方法与诚实边界

- 我已通读：`PONYTAIL_SKILL.md`、`00_SCOPE_AND_ACCEPTANCE.md`、`00_EXPERIMENT_PLAN.md`、`01_root_cause.md`、`04_audit_summary.json`、`04_source_summary.json`、`diagnostics.py`、`cross_checks.py`、`test_diagnostics.py`、`03_regression_results.txt`、`candidate/leveling_quality.py`、`candidate/leveling_estimators/tls.py`、`inputs/cap_20261009_121647/report.json`、`01_gate_cross_checks.json`、`01_channel_diagnostics.json`、`prepare.py`、`README.md`、`03_search_*.json`、`00_prepare_*`。
- 按需读取：`04_audit_numeric_bundle.json`（分段）、`00_input_catalog.json`、`00_baseline.json`（分段，超大）。
- **UNKNOWN 声明**：所有 SHA/字节级一致性、46 测试的真实退出、时序、以及 `01_reproduction.json` 的逐帧梯度统计，我**没有亲自执行或重算**，只能复核其记录值之间的内部一致性。凡标 `[UNKNOWN]` 者即为此意，绝不伪造执行。
- 该目录为前置 guard：最终 `05_evidence_manifest.json`、return 追加、独立审阅尚未封存（被本会话权限白名单证实：白名单只含既有文件，无 `05_*`、`FINAL_REPORT.md`、`04_independent_review.md`），与用户所述“目前仅前置 guard”一致。

---

## 1. 独立分析性复算（不执行，仅算术核对）

| 复核项 | 记录值 | 我的算术核对 | 结论 |
|---|---|---|---|
| 帧72 ROI2 P95 拒绝 | 50.291869 mm（report line 318 / 04_audit_summary） | n=300，rank=0.95·299=284.05，`ordered[284]·0.95+ordered[285]·0.05`=`50.227390722·0.95+51.516963488·0.05`=50.2919 | 一致；且两端邻值均>50 → 非浮点擦线误判，作者 line 36 陈述成立 |
| 帧72 ROI2 尾点 | 正7/负9=16，5cm内284 | 284+16=300 | 一致 |
| 原 TLS 门 | `GL_HOLDOUT_QUALITY` | `cross_checks.py:23-28` 复算顺序与 report `reject_reasons` 完全一致 | 一致 |
| 加权不可低于原全域最优 | `diagnostics.py:186` 断言 | D_ROI_EQUAL full RMS 22.541 > 基 22.383；D_FRAME_EQUAL 22.3833313952 ≥ 22.3833313928 | 数学上必然成立，未伪装成“真实几何改善” |
| 独立 SVD | 目标 8.88e-16，全 11 段 ≤1.55e-15 | 阈值 1e-12（`cross_checks`/`leveling_quality:101-102`） | 余量 ~10³，非擦线 |
| ROI 等权“隐藏144” | D_ROI_EQUAL `holdout_failed_regions=[["144","2"]]`，144/2=51.1645 | 51.1645>50 → 仍失败 | **作者主动记录了 144 失败，未隐藏** |

---

## 2. 逐条评审

### T100 资产/清单/基线分离/SHA 冻结
**PASS（记录级）**。`04_source_summary.json:57-78` 记 4 份历史 manifest（85/97/164/126）逐 SHA 验证；`prepare.py:48-57,74-96` 对所有输入/报告/域/源做 `sha()` 断言后才复制；`04_audit_summary.json:1327-1421` 起止 code_sha 完全一致且 `code_unchanged:true`；`protected_assets_verified:578, changed:{}`。执行 runtime（09C）与主树生产（selector 92d2ed）分离，未集成 09B/09C，与结论一致。
**证据边界**：4 份 manifest 位于 `E/` 之外（`.codex/worktrees`、`cl2_09b/09c`），我**无法在本白名单内独立重算**其 SHA → 该 4 项 `[UNKNOWN]`（接受为记录）。

### T101 原 bin→ROI→FIT/holdout 重建 + 原 TLS/拒绝复现 + 全指标
**PASS**。`diagnostics.py:92-134` 从 raw `points.bin`（28B stride，little-endian f4，ring@16 u2，intensity@12 f4）重解，按 `report['config']['regions']` 半开盒重建 membership，并在 `:131-133` 断言 7 数组与 `domain.npz` **逐元素相等**、FIT/holdout 行**不交**。holdout indices 由帧数派生（`:99`）并与 report `holdout_ordinals [72,144,217]` 对齐（`:171`）。原始 TLS 法向/offset、全域/逐区/留出 signed mean/median/P95/P99/max/几何/Grad 均已落盘。
**UNKNOWN**：逐帧 X 梯度 (0.223612–0.280811，中位 0.252860) 与 corrX (0.602577–0.712822)（`01_root_cause.md:52`）我未在 `01_reproduction.json` 内逐帧重算。

### T102 A 几何/空间
**PASS（描述性）**。`01_gate_cross_checks.json:88-104`：λ2/λ3=0.372065·、切向展布 [1.877,2.469] m，0.01/0.1m 退化门未触；不删点/不换 ROI（`:114-118` 断言 ROI 互斥且来自原 config）。

### T103 B 姿态/坐标
**PASS（仅数学控制）**。`diagnostics.py:202-208` 对点+同平面配做 4 组 ±1°+平移 [.1,-.2,.3]，实测 ≤8.9e-16（运动学上恒等式，见 §3.7）。`report.profile` 与 `leveling_quality.PROFILE` 均 `physical_verified:false, extrinsics_verified:false`，未把外参/1.14m 当 GT。

### T104 C 模型失配
**PASS（诊断级）**，但见 §4 的加强性反驳。四 ROI FIT-only 局部平面预测固定 holdout，目标三留出 P95 → 38.30/36.49/36.35 mm，且 `eligibility=DIAGNOSTIC_ONLY: four distinct planes cannot constitute one rigid TLS transform`（`04_audit_summary.json:327`）。`test_diagnostics.py:34-44` 强制“四平面≠单一刚体解”。数值模型解释与物理表面身份分离（E1/E2/E3 分层）。

### T105 D 噪声/密度/通道
**PASS**。所有点保留（无权重点被删，`diagnostics.py:37` 断言仅正权重）。ROI 等权 72→49.77 但 144→51.16（仍拒）；帧等权 72 仍 50.292（仍拒）。`01_channel_diagnostics.json` 记录 ring 分组、5cm 格多 ring 覆盖、强度-残差相关，并显式标 `causal_status: confounded`，未做通道/强度/尾部削减。

### T106 E 实现/统计
**PASS**。独立 centered SVD 最大 FIT 残差差 ≤1.55e-15；`scalar_check`（math.fsum + 排序线性插值）与 `Q.statistics` 的 np.percentile 在 12 区一致（`cross_checks.py:31-35` 断言 <1e-12）。原 compare/门控/输出口径未改（`cross_checks.py` 重建 reasons 并断言等于 report）。

### T107 最小 shadow 修复
**PASS-BLOCKED**。`candidate/` 仅存放复用 09C 冻结源码，无任何 CL2-10 修正；无有效 TLS 导出；T107 修复资格 BLOCKED 结论与证据一致（`01_root_cause.md:81-89`）。

### T108 目标+全部既有 TLS-valid 复现/独立对照
**PASS（复现）/证据边界缺口**。11 段（1 目标+10 valid）原域逐门复现，114754 仍 valid 但 `NO_RECOMMENDATION`（`03_regression_results.txt:95-105`）。“修复后泛化”正确标 NOT_RUN。
**缺口**：`prepare.py:67-68` 的 wanted 集合来自外部 `cl2_07/03_normal_comparison.json`（不在本包内）；我无法确认“既有 TLS-valid 会话全集”未被裁剪 → 集合完整性 `[UNKNOWN]`（见 §5.2）。

### T109 09B/09C/耗时/边界回归
**PASS（记录级）**。46 = 35（09B 冻结：selector 10+detector 3+sheet 12+roi 6+leveling 4）+6（09C 差分）+5（诊断）；`test_selector` 覆盖假拒绝/不足/条件失败，`test_equivalence` 覆盖共线/无解/大集/重复。100 格单次 4.038/7.183s 与配对中位 2.77/3.01s 均保留；`03_search_paired.json` 同源逐字节一致、精确相同。未做性能开发。

### T110 真实 OpenCode CLI 审计
**PARTIAL/UNKNOWN**。用户声明先前 CLI 因 shell 引号 exit 2、未进模型、失败 IO 保留，本质会话为新实际会话——我在白名单内**无法核验** argv/model/session/export/raw IO。`run_opencode.py` 存在但内容未读，`03_regression_command.json` 的 argv 已含。此项须待最终 manifest 封存时以原始 CLI 记录闭合，现不得声称 PASS。

### T111 新 evidence/manifest 逐 SHA/保护资产/return 仅追加
**PARTIAL（正确的前置状态）**。`prepare.py:112-118` 保存 `return_before.bin` 并对旧 return 做前缀断言（仅追加语义）；`:119-126` 冻结 guards/inventory。`05_evidence_manifest.json` 等尚未生成，符合“独审后封存”。未封存前不得宣称本轮全部闭合。

### TLS01 / E01 / D01
- **TLS01 BLOCKED**：50mm P95 门不变，离线 PASS 亦不解锁 → 一致。
- **E01 BLOCKED**：无生产/链路接入/发布。
- **D01 NOT_RUN**：无设备/物理干预/采集/B2/B3。

---

## 3. 主动反驳（用户点名的九项）

1. **因果过强** — 未发现过度因果。`01_root_cause` 把结论限制在“数学拒绝机制可复现 + 给定模型下的数值贡献”，物理根因 UNKNOWN（`:3,50`）。C 的“确认…数值贡献”是模型级陈述，可接受。**No FAIL**。
2. **FIT/holdout 泄漏** — 未发现。holdout 由帧序派生且与 report 对齐；`diagnostics.py:133` 断言行集不交；估计器只接收 `points`（FIT）；局部平面只在 `points[codes==i]`（FIT）拟合。**No FAIL（强项）**。
3. **局部多平面冒称刚体 TLS** — 未发现。`eligibility` 明标 DIAGNOSTIC_ONLY，`test_diagnostics.py:34-44` 反例强制“四平面 offset 差>0.1 且非单一 R,t”。**No FAIL**。
4. **阈值/样本/ROI 隐改** — 未发现。ROI 直接读 `report['config']['regions']`，profile 与 report 一致，无 Z/强度/ring/尾点过滤；FIT 行数与 report 一致（136942）。**No FAIL**。
5. **目标过拟合** — 未发现。固定三留出、无按 SID/帧的权重网格、无门改动（`00_EXPERIMENT_PLAN.md:17`）。**No FAIL**。
6. **ROI 等权隐藏 144 失败** — **反例不成立**：作者不仅未隐藏，反而落盘 `holdout_failed_regions=[["144","2"]]` 且 51.16>50。**No FAIL**。
7. **刚体控制误当真实外参正确** — 未发现，但该控制近乎同义反复（见 §4.2）。**No FAIL（弱证据，非错）**。
8. **跨 capture 误当 GT** — 未发现。plan 与 root cause 均明确“可能同一现场、非独立物理 GT”。**No FAIL**。
9. **已有成功回归遗漏** — **无法完全排除**：valid 集合由外部文件定义，包内不可枚举全集。列为唯一未闭合的证据边界（§5.2）。**非已证 FAIL，但未 PASS**。

**结论：在我可核范围内未发现逻辑 FAIL；作者结论整体应维持 BLOCKED。**

---

## 4. 额外反证/加强点（进一步支持 BLOCKED，非逻辑错误）

### 4.1 “局部几何”相对的是未验证的 ROI 身份（循环性）
`inputs/cap_20261009_121647/report.json:157-159`：`ground_confirmed:false`、`ground_identification:"algorithm_candidate"`、`uses_manual_reference:false`，四 ROI 盒来自 `lowest_floor_sheet_v2` 候选。因此 C 的“局部平面贴合”是在**未被证实为真实地面的四个算法选区**上测得的；它不能升级为表面身份/几何证据。`01_root_cause` 已说“无法确认真表面还是混合回波”，但**未显式指出 ROI 盒本身即候选**。建议补一句最小说明（见 §5.1）。

### 4.2 刚体控制是恒等式，几乎不具区分力
对正交 S 与 q=S·p+δ，residual(q, S·n, offset−(S·n)·δ) 恒等于 residual(p,n,offset)。故 ≤8.9e-16 只排除“变换代数实现 bug”，对数据/物理零信息。作者定位其为例行控制，未越界，但不应当作 B 假设的实质证据。

### 4.3 “独立 SVD”共享同一 FIT 集与锚点
`svd()` 与 `tls()` 用同一批 FIT 点、同一 anchor，仅换求解路径（centered SVD vs covariance eigh）。它是**独立求解器**而非独立数据；其价值仅证 TLS 求解/单位化无 bug，不能外推为现场真值。

### 4.4 candidate/frozen `floor_sheet.py` 不一致（provenance 措辞风险）
`04_source_summary.json`：`candidate/floor_sheet.py=d0b3e3…`，`frozen/floor_sheet.py=dd1b58…`，`baseline/floor_sheet.py=066a81…` **三者互异**；而目标 `report.json:168` 的 `code_hashes.floor_sheet.py=dd1b58…`（即 **frozen** 版）。`01_root_cause.md:9` 称“执行用…09C SHA d0b3e3…”，`diagnostics.py:13` 的 `sys.path` 亦以 `candidate` 优先。二者混读易被误解为“报告由当前 candidate 生成”。
- **不是数值 FAIL**：诊断链只 import `leveling_quality`+`leveling_estimators`（三处 SHA 与 report 完全一致：`leveling.py=b00cac`、`leveling_quality=3940c5`、`tls=800b7a`），**从不运行 floor_sheet**，故 TLS/拒绝复现与 selector 版本无关。
- 但 T100“执行基线分离/源 SHA 冻结”的叙述应避免把 selector d0b3e3 与报告生成器 dd1b58 混同。

### 4.5 性能时序方差大，无统计界
单次 4.038/7.183s vs 配对中位 2.77/3.01s；`03_search_*.json` 明示“no statistical latency limit”。不可据此宣称复杂度回退或板端准入。合理。

---

## 5. 最小修复建议（仅针对文档/证据边界，非代码根因）

### 5.1 一行级
- `01_root_cause.md`：在 C 段落补“四 ROI 为 `ground_identification=algorithm_candidate`，非物理 GT；局部平面贴合不构成表面身份证据”。
- `01_root_cause.md:9` / `README.md:5`：明确“报告 `code_hashes.floor_sheet=dd1b58`（frozen），本轮诊断执行路径不经 selector；`d0b3e3` 仅用于 09C 搜索对照”。

### 5.2 T108 完整性闭合
- 在最终 manifest 中纳入 `cl2_07/03_normal_comparison.json` 的 SHA 与“候选 capture 全集/筛选规则”，或列出 `captures/remote` 的全部 sid 与剔除理由，使读者可确认 10 个 valid 会话无遗漏。

---

## 6. 总裁定

| 项 | 裁定 |
|---|---|
| T100–T106、T109 | PASS（记录级；外部 manifest/T110 原始 IO 为 `[UNKNOWN]`） |
| T107 | PASS-BLOCKED（无 CL2-10 修复，candidate=09C 冻结源） |
| T108 | 复现 PASS；valid 会话全集完整性 `[UNKNOWN]` |
| T110 | PARTIAL/`[UNKNOWN]`（须待 CLI 原始记录封存） |
| T111 | PARTIAL（正确处于前置 guard，尚未封存） |
| TLS01 | **BLOCKED** |
| E01 | **BLOCKED** |
| D01 | **NOT_RUN** |

**整体仍应 BLOCKED。** 理由：无真实物理根因证据（缺源 bag/独立表面 GT）、无满足原单平面+原门+全留出改善的候选、物理外参未验证。数值机制复现与 E2 反事实成立，但不足以解锁修复。

**算法修复资格：不具备。** 仅可继续离线补证（先按 09A 预注册完成原现场独立身份/相对高度核验、取得原 bag 逐行独立解码），在此之前不得进入任何 shadow 修复或生产集成；LOCAL_PLANES/重权重数值改善**均不构成** raw TLS 修复或许可。

**未发现应判 FAIL 的逻辑缺陷。** 唯一动作项为 §4.4/§5.1 的 provenance 措辞澄清与 §5.2 的 T108 完整性闭合（文档/清单级，非算法）。

AUDIT_COMPLETE