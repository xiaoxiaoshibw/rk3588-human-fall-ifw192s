# HFUS-D05 回传（UNKNOWN/CLEANUP/时序重构——连续实施授权）

> 主控（Claude Code）接管用户 D05 连续实施授权后落笔。本回传只报告**实际跑出的软件结果与逐会话逐帧真实账**；不保 PASS，不包装失败。

| 项 | 值 |
|---|---|
| 工单 | HFUS-D05（用户授权正文见 `docs/human_capture/tickets/HFUS-D05.md`，当日登记） |
| 证据目录 | `docs/human_capture/evidence/2026-10-11_hfus_d05_r1/`（含 BASELINE_D05.md 预登记、BASELINE_SHAS.json SHA 冻结、baseline_probe/、runs/{a03,a06,b,c,abc}/、REGRESSION_FINAL.json） |
| D05 代码目录 | `sidequests/human_fusion_lab_next/d05/` |
| D05 demo | `sidequests/human_fusion_lab_next/d05/demo_d05.html` + `demo_server.py` + `BUILD_DEMO.md`（默认 :8908；D04 `demo_d04.html`/`demo_server.py` 完全不动，历史证据保留） |
| ponytail | 主控 + Agent A/B/C 均已加载 `C:\Users\30680\.claude\skills\ponytail\SKILL.md` 并在回传/代理回执中记录使用 |

## 授权接收与前置工作顺序

1. 授权接收 → 登记工单 → 预登记冻结（`BASELINE_D05.md` + SHA）→ 逐点阶段归因探针 → Agent A/B/C 并行交付（隔离工作区域、各自单文件）→ 主控统一接口/integration/真实评测/组合/Demo/回归/return。
2. **先实跑、后补文档；不为反复补写报告中断算法开发。**本回传所有数字都是从落盘 ledger/summary 抽取，不是合成示例。

## D05 §1「首先确认 D04 的根因」— 逐点阶段归因答案

探针（`eval/baseline.js`，元信息诊断、**不参与打分**）逐点回答：GT PERSON（`source=='human'`）在每个阶段的去向。

| sid | activity | GT 点数 | BG keep | cleanup keep | 成成分 | 主导丢失原因点级分账 |
|---|---|---:|---:|---:|---:|---|
| cap_20261010_175227 | S1-empty-with-furniture | 0（无 PERSON 真 GT 点） | — | — | — | — |
| cap_20261010_175429 | S3-walk-x-near | 286,822 | **43.1%** | 43.1% | 67.7% | no_reference_XY_support_UNKNOWN 149,937 / bg_voxel_match 4,253 |
| cap_20261010_175553 | S3-walk-y-far | 561,361 | **94.9%** | 94.9% | 96.5% | no_reference_XY_support_UNKNOWN 6,312 |
| cap_20261010_175804 | S4-walk-stop-walk | 13,327 | **43.1%** | 43.1% | 63.7% | no_reference_XY_support_UNKNOWN 7,194 |
| cap_20261010_175943 | S5-turn-in-place | 8,841 | **0.3%** | 0.3% | 0.3% | no_reference_XY_support_UNKNOWN 8,552 |
| cap_20261010_180235 | S6-occlusion | 27,268 | **80.7%** | 80.7% | 89.2% | no_reference_XY_support_UNKNOWN 3,141 |
| cap_20261010_180337 | S7-far-5m | 24,361 | **25.4%** | 25.4% | 74.7% | no_reference_XY_support_UNKNOWN 16,986 |
| cap_20261010_180557 | S8-still-retention-long | 57,045 | **69.3%** | 69.3% | 92.8% | no_reference_XY_support_UNKNOWN 16,356 |

授权 §1 各检查项真实答复：
- **UNKNOWN 区域为何删掉大量疑似人体点** — 是。`no_reference_XY_support_UNKNOWN` 占近端/转身/远端 5m 全部损失的 43–99.7%（仅 GT 人点账，不含背景）。
- **CLEANUP 是否误删孤立但属于人体的有效点** — **否**。cleanup keep = BG keep 全部一致，cleanup**零额外删点**（投产 cleanup_isolated_fg 本身就不删有 XY 拓扑连接的人点；「要重新设计 cleanup」是 D04 的误判）。
- **背景模板是否把静止人体吸收到背景** — 不是主链。FUSION 是 ref_only，背景在 `begin_session` 一次性冻结，运行期不吸收；180557 S8 69.3% 保留下仍少 TP 是 UNKNOWN 支撑半径问题而非背景吸收。
- **远距离稀疏人体为何无法形成候选** — 25.4% 的 S7 / 0.3% 的 S5 保留不足以满足「0.4m XY 支撑」刚性 OR 判，剩下那点进不了 `human_n_min=60`；并不是「无法形成候选」而是「根本没机会评」。
- **现有 split hook 为何零触发** — D04 已确证九会话真实账本里**没有**满足「radius/height 出窗」的异质簇；候选不是局部混合的，而是被先杀点。
- **真实 GT vs 自动标签** — 只把 GT `source=='human'` 记账入账；点集归属始终以 GT 为准，未人工审核一律 UNKNOWN。

## 三条可替换算法（并行交付，各单文件、隔离区域）

| 钩子 | 交付者 | 语义 | 自检 |
|---|---|---|---|
| `d05/hook_unknown.js` | Agent A | UNKNOWN 自适应邻域重判 r=0.3/0.6；z≤0.1 不救；ref 列质心+局部密度双门；带 `ponytail:` 注释的网格桶 O(N rejected × N candidate) 优化 | `HOOK_UNKNOWN_SELFTEST_PASS` |
| `d05/hook_cleanup.js` | Agent B | 候选感知 CLEANUP（connect / vertical-span / 家具 guard 三谓词）；保持「cleanup 输出必须是输入子序列」硬契约（原位插入救援点） | `HOOK_CLEANUP_SELFTEST_PASS`（3 场景） |
| `d05/hook_temporal.js` | Agent C | 时序前景恢复：跟踪段状态观察器 + begin_session 复位（杜绝跨会话污染）；still 人锚点注入 + 短期提升 retention max_lost；`_temporal_stats.recovered_pts` 镜派归因 | `HOOK_TEMPORAL_SELFTEST_PASS` |

工作组织与授权 §5 一致：三代理**隔离交付互不覆盖文件**；主控负责接口统一/真评/组合/Demo/回归/return。

## §3 真实评测（九会话，正式打分只算 8 会话 GT-bound 会话；S9 永远 exploration-only）

GT 参会规则（预登记冻结）：`eligible && review_status=='reviewed' && session_sha256 同时有 meta+points && 与输入 SHA 双等`。九会话全跑，**S9 (cap_20261010_180751) GT 绑定缺 meta 键 → 永远 EXPLORATION、不进任何正式判定**。base = D04 已定 frozen ledger（不重跑）。

`unsupported_UNKNOWN_points` 逐变体总数（整个九会话账本总和）：

```
 base  1,671,909
 a03   1,671,909   (与 base 完全一致)
 a06     420,546   (-1,251,363 / -74.9%)
 b     1,671,909   (与 base 完全一致)
 c     1,671,909   (与 base 完全一致)
 abc     420,546   (与 a06 相同 = A06 独带 UNKNOWN 账)
```

**单变体 vs base,legacy confirmed TP/FP（正式 8 会话）**：

| sid | base lc TP/FP | A03 | A06 (ΔTP,ΔFP) | B | C (ΔTP,ΔFP) | ABC (ΔTP,ΔFP) |
|---|---|---|---|---|---|---|
| 175227 家具 | 0/347 | 0/347 | +0 / **+1** | 0/347 | +0 / **−19** | +0 / **−19** |
| 175429 near | 213/625 | ≡base | **+42 / −84** | +1/0 | +6 / +39 | +39 / −34 |
| 175553 far | 95/104 | ≡base | +1/+1 | ≡base | ≡base | +1/+4 |
| 175804 行走停顿 | 9/17 | ≡base | +1/+4 | ≡base | ≡base | +1/+2 |
| 175943 原地转 | 0/6 | ≡base | **+4/+0** | ≡base | ≡base | **+5/−1** |
| 180235 遮挡 S6 | 65/93 | ≡base | −1/+1 | +0/−1 | −5/−2 | −5/+0 |
| 180337 5m 远 | 11/9 | ≡base | +0/+1 | +0/+1 | +0/−2 | ≡base |
| 180557 静保 | 51/115 | ≡base | ≡base | ≡base | +0/−3 | +0/−3 |

### 真实成功帧（帧级,逐变体落盘的 evidence）

A06 相对 base 至少多接 1 个 accepted 人候选的帧（ac > bc，ac = 变体候选 prob≥0.35 or decision HUMAN/CONFIRMED）：

- 175227: +20 帧（fb 4/9/12/46/50/...）
- 175429 near: +20 帧（fb 21/51/75/83/84/...）
- 175553 far: +47 帧（fb 19/27/43/47/63/...）
- 175804: +62 帧（fb 1/5/10/23/24/...）
- **175943 原地转: +141 帧（fb 9/12/13/14/25/...）** ← 真实从「近零接受」→「多数帧有接受」
- 180235: +16 帧（fb 52/86/90/104/106/...）
- 180337: +15 帧（fb 36/38/59/76/150/...）
- 180557: +0 帧（保留已满载 base 上界）

### 真实失败帧（变体仍不优）

- **S6 遮挡**：A06 65→64 TP（−1），C 60（−5），ABC 60（−5）。在 A06 收到 11 accepted 帧的同时，S6 的「在who处」中间人被砍落到 base 之下，说明 A06 救了 11 个 accepted 但也把某关键确认主票打断；仍 FAIL。
- **家具 FP**：A06 家具 0→1（+1），仍在预登记 ≤+50 预算内，但方向不对；A03/B 不改善；C/ABC −19 是真改善（C 的 retention 被家具 guard 拒绝时不再重复申报家具）。
- **静保（180557）**：任何变体均 0 提升；A06 不收人，因为静人的 UNKNOWN 原因不是稀疏边缘而是老语义 elsewhere。
- **S4 行走停顿**：A06 +1 TP/+4 FP，净 FP 增。
- **性能**：base p95 52.6–73.4ms；A03 82–138ms；A06 90–338ms（180337 337.94 是单次抖动峰值）；B/C/ABC 全局 55–207ms。**全变体 p95 超 50ms gate → 性能 FAIL**，与 D04 相同门槛下。

## §2「允许借鉴论文/开源算法」

本轮回路从 D04 失败者清单出发,以证据驱动的「重判+救援+时序」三运营商组合(论文思想: DBSCAN 邻域格、SOR cleanup、短期 occupancy evidence)。**没有简单搬用某个现有库**——适配的是本厂「ref 列质心 XY 支撑 OR 判」这个特定被杀住的源头。

## §4 Demo 升级（用户必要条件）

D05 Demo 已交付 `sidequests/human_fusion_lab_next/d05/demo_d05.html` + `demo_server.py`（默认 :8908）+ `BUILD_DEMO.md`：

1. **九会话切换/播放/暂停/逐帧/拖动/重置** — 继承 D04 底座
2. **三窗同步**: 左=原始点云 + GT 人(红)/家具(粉) + D05 变体候选(橙)；中=D04 baseline（紫） + D05 accepted 绿覆盖；右=three.js 真实 3D 点云（鼠标拖转/滚轮缩放，真实可观察点云几何）
3. **被删的点显示**：中窗紫者=base 候选、绿者=base 中仍被变体接受的；右窗橙色=D05 变体 accepted；**青色=A06/ABC 相对 base 新增 accepted 点 = 「人真被恢复」的点**
4. **候选 ID/人分/每层点数** — ledStats 面板逐帧账 + 3D 显示
5. **一键跳转**: 近距离丢失 / 远距离丢失 / 静止人体 / 家具误检 / A06 相对 base 新增 accepted（自动找 fb 4/9/12/... 首帧）
6. **人体真被恢复还是仍被删除** — 青色点云直接看到
7. **A/B/C 方案同帧切换** — 变体下拉可换 a03/a06/b/c/abc/base，同原始帧对比
8. **保留 D04 demo** — `d04/demo_d04.html` 与 D04 侧 `demo_server.py` 完全未改、历史证据保留

**别的 user 必要条件兜底**: 人工复核 DRAFT 导出功能保留（新文件 `D05_<variant>_MANUAL_DRAFT_f<idx>.json`，不覆盖 D04 老下载）。

## §6 交付与边界

### 交付物清单

- **算法**: `d05/hook_unknown.js` / `hook_cleanup.js` / `hook_temporal.js`（各自 `ponytail:` 标记限制）
- **runner**: `d05/run_d05.js`（base 引用 D04；S9 永远 exploration；refuse-overwrite 的保护性 ledger 写入避免重跑污染）
- **归因探针**: `eval/baseline.js`（元信息诊断，不评晋级）
- **回归**: `d05/make_regression.js` → `docs/human_capture/evidence/2026-10-11_hfus_d05_r1/REGRESSION_FINAL.json`
- **Demo**: `d05/demo_d05.html` + `demo_server.py` + `BUILD_DEMO.md`（AUTO 模式与手工三目录模式均可）
- **证据**: 本目录全部 + `runs/{a03,a06,b,c,abc}/` 九会话 ×5 + baseline_probe + RUN_D05_STATUS.md（阶段快照）

### 边界守护

- 未 commit/push；未动生产主链；未部署板端；未动 captures/GT/D04 证据；D04 `demo_d04.html`/`demo_server.py` sha 不变（D05 侧另起 d05/ 与独立 8908 端口）
- S9 永远 exploration-only；never scored
- 不把 FAIL 包装成 PASS — C/ABC 对 S6 明确 FAIL、180557 没进展、p95 仍大于 50ms gate 已明示

## 下一阶段所需的**最小人工标注清单**

1. **S1 家具侧 FP 定性**: 由 demo_d05 选 175227 侧约 20 帧内的 A06 误接受家具簇,导出 `D05_a06_MANUAL_DRAFT_f<idx>.json` ~5 帧 → 人工复核 LABEL+FURNITURE 负例入库（D04-06 负例为 0,仍 BLOCKED 用）。对应预登记「家具误检变化」 root-cause 靠近点。
2. **S6 遮挡**: 至少 f52/86/90/104/106 + f128/187/188 共 8 帧,对 A06 多 accepted + base FN 的那几个 track 做 GT 传播到 track.id 级人工 qualified（未 qualified 前 S6 无资格作为晋级输入）。
3. **S9 (180751)**: `session_sha256.meta` 缺失修复 + 人工 reviewed 晋级；当前永远 INVALID_BINDING。
4. **静保 (180557) 重点**: 3 帧（在 demo 里跳「静止人体」首帧）+ A06 candidate 增加为 0 的事后人工位置核验 — 验证是否真为「静人已完整可接受、只是没多接」的问题还是metric定义错位。

## 工程 / 算法 / GT / 生产 四项独立裁定

| 维度 | verdict | 依据 |
|---|---|---|
| **工程接通** | **PASS（SUBMITTED）** | 预登记冻结存在、六变体九会话全跑完且 ledger 全落 SHA、`run_d05.js` refuse-overwrite 保护、demo_d05 三模式启动 (AUTO/file://) + API/summaries/证 MANIFEST 验证、回归 REGRESSION_FINAL.json 齐、D04/D05 demo 并存互不污染。所有工程检查实际跑通（非假设）。 |
| **算法效果** | **FAIL（部分改善）** | 仅 **A06** 有真实、单方向改善：near +42 TP/−84 FP；turn-in-place 0→4 TP；乒乓帧级 +141 帧。但 S6 −1..−5、静保 0 改善、S4 +4 FP、家具 +1、p95 90–338ms 超 gate；A03/B 零效果；C 单变体在 S6 −5 TP 下不能独用。任意一单项 FAIL 则全 FAIL。明说不包装。 |
| **GT 资格** | **BLOCKED（保持 D02-06）** | S9永远 INVALID_BINDING (缺 meta SHA key)；ROUND 家具负例仍 0；S6 track-qualified 需人工；本轮 D05 没破人工资格。 |
| **生产接入** | **BLOCKED** | 算法 FAIL + GT 资格 BLOCKED + 未授权部署；「我的验收以能直观看到人体识别效果为必要条件」由 demo_d05.html 提供，但**用户最终视觉验收决定权仍在用户**。 |

**状态: SUBMITTED（工程 PASS / 算法 FAIL-部分（仅 A06 真实改善并需保留）/ GT 资格 BLOCKED / 生产 BLOCKED）**。

## 推荐下步 (不自动开工; 等用户授权)

- **A06 晋级至正式研究轨道**（生产接入仍 BLOCKED）：它是当前唯一方向正确、不掩饰的修补。D06 潜在工作: 在保留 A06 的前提下只驾驶 S6 FP 家具误检增加 + S4 +4 FP 的成本,看是否能用 strict track qualification 控制 SWAP；如用户授权可转 D06/D07。
- **A03/B 方向正式归档**: 明确无效,不再为此两轴检索调参（已真实零效）。
- **C 单变体先不晋级**: S3/S6 上 TP 退;留作 A06+C 的组合参考并作为「still人恢复」的未来次要构建块。


## 2026-10-12 Codex R02/R03/R04 离线返工完整回传（SUBMITTED，自验非ACCEPTED）

- 唯一writer Codex；两代理和OpenCode只读。ponytail实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 验收表与SHA：{"R02": {"path": "docs\\human_capture\\evidence\\2026-10-11_hfus_d05_r2\\ACCEPTANCE_V1.md", "sha256": "64f900237f0246d0441786bde8ed785dd2d40cb1c170f17dda6a9d7883658ec7"}, "R03": {"path": "docs\\human_capture\\evidence\\2026-10-12_hfus_d05_r3\\ACCEPTANCE_V1.md", "sha256": "82f0a976cd38c4dd9a269db4696bc19969c1642d71eb842c2ed599881d336aed"}, "R04": {"path": "docs\\human_capture\\evidence\\2026-10-12_hfus_d05_r4\\ACCEPTANCE_V1.md", "sha256": "063241df66a3e6ad618c85a4e79a99dbd6182e9381270e090d19650e4c40194a"}}
- 起始master/026e06303f60ed1bbe4ddc4d037836db68da6d27，dirty保留；全树SHA15217→15402（非原子），原资产无变化，外部scheduled_tasks.lock消失单列；后续本轮增量另留SHA。零Git写/部署/采集/驱动网络/生产改动/ML激活。

实际代码仅新增d05/r02,r03,r04，模型/GT/输入原字节冻结。R02 H1密集核心互斥守恒，严格观测base→当前near111→184、far14→67、走停走3→10、turn0→4、occl7→10、5m5→7、still51→51。原f238已有高分混簇，A06真人coverage/purity改善，不能称无候选。R03宽水平分类规则家具诊断1/351→0/48，但near184→179，因前序分类拒绝改变bank资格，使f220–224丢retained补充，FAIL不晋级。R04只消除A06恒真邻居计算，全9会话2605新帧点/组件/候选/分数/轨迹/strict/legacy精确parity；纯算法p95 far44.836/5m47.170ms，九场均<50，p99 far50.294ms保留，Windows不冒充板端。

| 验收ID | 自验 | 根因/证据/限制 |
|---|---|---|
| R02-01 | PASS | 全树起止SHA，外部lock消失/非原子扫描单列 |
| R02-02 | PASS | D05六套实物/历史缺件审计 |
| R02-03 | PASS | 完整逐层ledger与失败原因 |
| R02-04 | PASS | 净恢复/accepted/human-supported分列 |
| R02-05 | PASS | 冻结GT-free H1守恒互斥 |
| R02-06 | BLOCKED | strict收益子条件PASS；家具独立资格不足；legacy回退保留 |
| R02-07 | BLOCKED | 软件契约PASS；连续未标/退出资格不足 |
| R02-08 | FAIL | 原viewer race保留；最终R04 v2修复另验 |
| R02-09 | FAIL | far55.693/5m170.302ms原门失败保留 |
| R02-10 | PASS | 指定OpenCode最终01实际0/model/brief；缺陷处理另补审 |
| R02-11 | PASS | 实物/SHA/索引/人工包/本次追加return |
| R03-01 | PASS | 起止范围/源SHA和处理中增长补账 |
| R03-02 | PASS | 真实147固定候选反事实/原69D/raw/effective |
| R03-03 | PASS | 原模型不变，9会话完整实际exit0 |
| R03-04 | FAIL | near184→179；家具诊断改善不抵消回退 |
| R03-05 | BLOCKED | bank反馈实证；连续身份/负例/退出资格不足 |
| R03-06 | PASS | 当前R04 v2含R03真实失败对照；原分数/判定理由/同步/SHA |
| R03-07 | FAIL | far/5m/S9纯perf超原50ms门 |
| R03-08 | PASS | 指定最终01实际exit0，缺陷处理补审 |
| R03-09 | PASS | 全账/回退窗口/源SHA/人工包/return |
| R04-01 | PASS | before/end加增量SHA；不宣称全树冻结 |
| R04-02 | PASS | 等价短路/120反例exit0；注册配置范围 |
| R04-03 | PASS | 实际9×2605完整新账，所有点/状态精确parity |
| R04-04 | PASS | 纯算法9场p95<50ms；p99far50.294保留；板端NOT_RUN |
| R04-05 | PASS | v2实际完整DOM/9会话/全部控件/SHA/截图，空导出失败保留 |
| R04-06 | PASS | 指定独审01实际流程PASS；工程缺件已修，补审另附 |
| R04-07 | PASS | 源SHA/实账/案例/人工包/追加return，四类独立裁定 |

完整源SHA/配置/加载模型：各SUMMARY SOURCES与R04 TOOLING_SOURCES_V3；消费资产baseline/runtime/post SHA绑定36输入/GT/manifest与AUDIT。逐帧R02/R03 FAILURE_LEDGER、FRAME_COMPARISON、R04真实新ledger和FRAME_PARITY；完整CASE_INDEX带±5上下文。D04候选/terminal完整对拍，新base补充stages用于显示，非旧D04原生stage账。最终Demo v2当前8915，真实完整浏览器DOM账V3和FULL_VERIFICATION，旧V1 race/空导出失败保留。

独审实际指定opencode-go/deepseek-v4.1-flash，OPENCODE_FINAL_01 exit0/export0，完整brief/技能/实际模型/只读工具验证PASS；P1空浏览器账已真实重做落盘，导航改当前唯一入口，R03分析运行中增长与最终SHA/纯perf串行另说明，最终补审结果稍后追加。不改旧review、旧return或旧评分账。

未闭合：far32/occl61/turn2FN，高分家具和银行自维持仍在；far legacy FP协议105→188，occl legacy TP65→64，完整账保留、不用平均隐藏。缺独立已审负例/连续未标身份/退出参照，S9仍INVALID_BINDING。工程交付可审查；算法FAIL；GT BLOCKED；生产BLOCKED，设备/物理/部署/采集NOT_RUN。未自行ACCEPTED。

人工包仅待审，MINIMAL_HUMAN_REVIEW_PACKAGE_V2给具体frames与独立negative分组需求，不写回GT或训练。下一轮依据：银行自支持资格与far单核混簇，不盲调H2、不泛降门；新假设须另预登记，当前不自动开D06/D07。完整[FINAL_REPORT](../evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT.md)、[当前操作入口](../evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX.md)。


### 2026-10-12 R02/R03/R04 最终补审与措辞纠正（追加，不改旧账）

前述“9×2605”明确纠正：九会话合计2605帧，逐会话304/258/464/239/202/238/251/523/126；五套base/A06/split/gate/fast完整实跑共13025 ledger行。没有23445帧的单轮实验；PARITY_SUMMARY及各SUMMARY/ledger计数未改。最终报告材料V2与ACCEPTANCE_FINAL_V2只纠正记录，原唯一ACCEPTANCE_V1标准与原FAIL/BLOCKED保留。

OPENCODE_FINAL_02实际PID27084，420.659s，child/wrapper/export均exit0；实际opencode-go/deepseek-v4.1-flash，完整brief/ponytail读取、载体核验、只读grep/read、REVIEW_COMPLETE，见真实STATUS/EXPORT/md。独审核验九会话19条DOM、三窗SHA/索引时间一致；P1-1/P1-2/P2-4闭合，P2-3未完成新分析增长与非原子范围已披露，不阻断当前工程交付。独审未自行重跑浏览器或大ledger，不替代人工接受。

当前唯一入口：[R04交付V2](../evidence/2026-10-12_hfus_d05_r4/CURRENT_DELIVERY_INDEX_V2.md)、[最终报告V2](../evidence/2026-10-12_hfus_d05_r4/FINAL_REPORT_V2.md)、[逐ID自验](../evidence/2026-10-12_hfus_d05_r4/ACCEPTANCE_FINAL_V2.json)、[当前Demo](http://127.0.0.1:8915/)。Demo v2/source工具实际SHA仍TOOLING_SOURCES_V3，各实跑加载源仍各SUMMARY。两个新收口脚本只写材料，不入算法；最终新增/变更材料SHA与实际加载源复核另见FINAL_INCREMENTAL_BOUNDARY。初次fill数值但尚未触发change的补充浏览器行明确未完成，真正gate/fast f220及键盘221另有加载DOM；不冒充成功动作。

逐ID状态维持报告表：R02-01..05 PASS、06/07 BLOCKED、08/09 FAIL、10/11 PASS；R03-01..03 PASS、04 FAIL、05 BLOCKED、06 PASS、07 FAIL、08/09 PASS；R04-01..07 PASS（R04-03是9会话合计2605帧，R04-06补审02已实际完成）。工程PASS指当前材料完整可审；算法FAIL，far32/turn2/occl61FN及家具高分自维持未解决，H2 near184→179拒绝晋级；GT与生产BLOCKED，S9 INVALID_BINDING，设备/部署/采集/物理NOT_RUN。未ACCEPTED。

唯一writer主控；实际skill C:/Users/30680/.codex/skills/ponytail/SKILL.md；master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27。没有commit/push/reset/checkout/clean/部署/采集/驱动网络或原模型GT修改；旧失败与评分保留。下一方向为银行自支持/单核混簇的证据驱动单因素登记，本次不把未运行建议当交付成果。


### 2026-10-12 HFUS-D05-R05 完整离线返工回传

实际ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md；Codex唯一writer，代理与指定OpenCode只读。master HEAD026e06303f60ed1bbe4ddc4d037836db68da6d27；15463初始SHA，结束全树及增量非原子，42外部新增与当前HFUS-RD-01进程单列，不干预，不声称全树冻结。旧资产模型/GT/captures/生产只读，没有Git写、部署采集/网络驱动或ML启用。

纠正旧回传“银行自维持”推断：retained/MERGED不能直接刷新原银行；家具是独立FG高分误接受播种→有限延续→过期→再入。PA多候选同内部track导致EMA偏移实证，原票不改。H4仅更新合法bank.xy为FG候选中心。完整control/anchor各九会话TOTAL2605帧/5210新账，真实exit0；control精确R04。42收益24回退，far67→84但27赢10输，near184→185但220–224五次全部TP→FN，因此H4拒绝晋级。walk10/turn4/occl10/5m7/still51不变；家具已标错误接受不变，纯FG chair高分仍未解决。

R05-01/02/03/07/08/09 PASS；R05-04/05/06 FAIL；05真实ID/退出另BLOCKED；06实际pure控制8/9、新版6/9超50ms，主控内部串行不证明全机无竞争，环境资格另BLOCKED。旧R04性能PASS保留不能替代本轮失败。三次工具失败枚举/UNKNOWN NULL/SHA项数均保持源/exit/log，新v2双方完整重算。TTL raw限制v2派生复核。Demo v1与跨tab错误保留，当前v2真26观察23加载九会话/三窗/控件/SHA，pending排除console[]。

指定独审最终补审02实际PID22712，child/export0、实际opencode-go/deepseek-v4.1-flash、完整brief/ponytail/载体/只读核验PASS，缺陷处理另附。不替代人工ACCEPTED。工程材料PASS；算法FAIL；GT/生产BLOCKED；设备/物理/部署/采集NOT_RUN。

[交付入口](../evidence/2026-10-12_hfus_d05_r5/CURRENT_DELIVERY_INDEX.md)、[完整报告](../evidence/2026-10-12_hfus_d05_r5/FINAL_REPORT.md)、[逐ID状态](../evidence/2026-10-12_hfus_d05_r5/ACCEPTANCE_FINAL.json)、[Demo](http://127.0.0.1:8917/)。源SHA TOOLING_SOURCES_V5/各SUMMARY；逐帧analysis_v2与连续案例/银行账/最小人工包/结束增量皆在R05目录。下一轮HFUS-D05-R06只是离线返工编号，不启动HFUS-D06/D07；仅检验超出原.4恢复圆才修正，有far41反例，尚无新结果。

R05结束增量实核：15662枚举/53新或变更SHA，70加载源与ToolingV5 SHA全部匹配，errors/drift空；HFUS-RD-01范围外变更/新增及其pycache缺失单列，不干预、不声称全树冻结。R06写前baseline是单独下一阶段新增，不算R05实验。最终证据自身/追加return SHA另FINAL_ARTIFACT_SHA。字段等价限定PARITY_SUMMARY_V2，人工包MINIMAL_HUMAN_REVIEW_V2，补审P3处理REVIEW_FINAL_SUPPLEMENT；原文件保留。
