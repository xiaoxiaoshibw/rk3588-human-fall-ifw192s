# CL2-11 最终报告 — 121647 TLS 物理补证与可辨识性审计

2026-10-10 Asia/Shanghai。Claude（Kimi K2.6）主控，OpenCode CLI `opencode-go/deepseek-v4.1-flash`
独立只读审计。本轮**未修改 TLS 算法 / 门控 / 生产代码 / 历史证据 / GT / 50mm P95**。唯一验收表
[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1。**CL2-11 调查工作 = PASS_WITH_FINDINGS；
121647 有效 TLS / 修复条件仍 BLOCKED**（与 CL2-10 对齐：单一状态口径下整体 BLOCKED）。

## 1. 结论一句话

现有资料**不能**区分 A(真地面非平面)/B(测距系统偏差)/C(多表面混入)/D(提取链错误)，真实
物理根因维持 **UNKNOWN**；本轮交付**最小独立物理补证计划**（未执行），**不启动算法修复。**

## 2. 五项最终裁定（各自独立，不混用）

| 裁定 | 状态 | 依据（详见 [02](02_EVIDENCE_IDENTIFIABILITY.md) §7 + [03](03_HYPOTHESIS_MATRIX.md)） |
|---|---|---|
| **DATA_AVAILABLE** | **PASS** | S01 板端 bag（SHA 经 meta 绑定）、S02 bin（本地 SHA 验证）、S03 meta、S04 domain、S05 report 全部实际复位并 SHA 对齐；S06 09A 设计文档实际存在 |
| **DATA_BOUND** | **PASS** | sid→job→meta.bin_sha256→domain.source_rows→plane 全链绑定；318 帧 offsets 连续、seq 连续、dropped=0；ROI 名义盒与 09A 预注册精确一致 |
| **INDEPENDENT_GT** | **FAIL** | 所有已到手的资料要么同一传感器同一测量（S01/S02/S03/S04/S10），要么 TLS 同源产物（S05），要么**未执行的设计方案**（S06），要么**MISSING**（S07 照片/S09 PCAP/厂商协议） |
| **IDENTIFIABLE** | **UNKNOWN** | 一维口径下 A/B/C 在数学上不可分辨（f(x)=g(x)+b(x,c) 欠定 + ring↔display-x 混淆量化）；y 内残差结构与 cell×ring 双向分解是**本轮未做**的潜在判别量（审计指出）；即便做了，把估计出的 β(ring) 命名为传感器偏差还是真实几何投影仍需 E3 |
| **READY_FOR_REPAIR** | **BLOCKED** | 缺 INDEPENDENT_GT 与 IDENTIFIABLE；CL2-10 的反事实（等权/局部平面）只测机制，不是 GT；CL2-09A/10 已要求补证，本轮给出可执行的最小计划 [05](05_MINIMUM_PHYSICAL_EVIDENCE_PLAN.md)，未授权下不启动修复 |

**不越级**：五项独立(各自单一标签)，CL2-11 的库存/清点 PASS 不会被误判为 121647 TLS 通过。

## 3. 关键新增量化（本轮 STEP3，全部描述性，未改门控/未改拟合）

基于 S04 domain 行绑定 + S02 bin + S05 TLS 平面，全部点保留：

- frame72 ROI2 300/300 点 ring 标签有效，FIT ROI2 63959/63959 有效（无 ring==0 的记录）；
- signed mean 随 ring 单调：FIT ring22 −0.073 → FIT ring41 +0.061，跨 19 环，平均步进 ≈**0.0071 m/ring**（**审计修正**，曾误记 0.013）；
- display‑x 平均映射跨 19 环步进 ≈**0.0126 m/ring**（曾误记为“signed mean 步进 0.013”）；
- 相邻 ring 的 display‑x 正规化重叠中位 ≈**64%**（曾误记 30–50%），重叠区残差平滑过渡；
- frame72 fixed‑ring 内 resid‑on‑display‑y slope 在 −0.10..+0.10 m/m 不规则混号（audit 触发的**新增描述**），说明残差场不是“每环常量偏差”这一最简 B 子型能单独生成的；
- range 仅 1.5–1.75 m 窗，无法判别“随距离”；
- `holdout ROI2 = 891 = 300+294+297`，`channel_diagnostics = 64850 = FIT 63959 + 891`（**审计修正**，曾错误表述为“63959 与 channel diagnostics count 一致”）。

证据文件（本目录）：`cl2_11_verify_counts.json`。跨目录写入的两个 probe（审计 finding #6，见下）
**：`cl2_11_ring_probe.json` / `cl2_11_ring_xy_probe.json` 现在**位于 CL2-10 封号目录**（`docs/sidequests/evidence/2026-10-09_cl2_10_r1/`)，属本轮**边界瑕疵**：本轮 audit 的真实产物误入 CL2-10 的目录空间。
处置：不再对 CL2-10 目录增删任何字节（避免再改起止状态）；07 manifest 跨目录登记两个文件的 SHA；
CL2-10 的封号完整性以其 `05_evidence_manifest.json` 为准（这两个文件不在其中，不影响）。

## 4. 独立审计（OpenCode 实际 CLI）

- CLI 1.18.35，session `ses_edbf2cff3ffeN9r8HZWon1Y2kd` 唯一；运行 exit **0**；终末 finish **stop**；
- 实际模型 `opencode-go/deepseek-v4.1-flash`（8/8 assistant 消息）；read 28 次，全程只读，
  external_directory 在运行期实际拒绝了对 codex worktree 的读取（据此把 S06/CLUSTER‑01 保留为
  UNKNOWN，**没有假装读过**）；
- 报告全文 [06_INDEPENDENT_REVIEW.md](06_INDEPENDENT_REVIEW.md)（11,418 字符，含 AUDIT_COMPLETE）；
- 策略与裁决 [06_INDEPENDENT_REVIEW_NOTES.md](06_INDEPENDENT_REVIEW_NOTES.md)：审计 6 个可判定 finding
  全部 ADOPT（#1/2/3/5/6/7），过强的“数学上不可分辨”论断弱化为“一维口径下不可分辨、二维分解未做”，
  但明确“二维分解也不会不用 E3 就把 β/h 命名成 g/b”；审计当时的若干 UNKNOWN（S06、CLUSTER‑01 追加、
  运行时 exit/export 尚不存在）**保留不越权**。审计总评“不应给无保留的 PASS”，本轮按
  **PASS_WITH_FINDINGS** 计。
- 权限实测差异（诚实）：CL2-10 是逐文件白名单，本轮是“read 全局 + 其余工具全 deny + external deny”。后者
  宽松一些，目的是审计员能检查 CLUSTER‑01/09A；**运行期证实 external deny 生效**。配置与有效 agent
  分别存档 `cl2_11_config.json` 与 `cl2_11_agent.json`。

## 5. 逐 ID 验收

| ID | 结果 | 证据与限制 |
|---|---|---|
| I100 | PASS | 真实读取了 CL2-10 FINAL_REPORT/01_root_cause/00_input_catalog、CLUSTER-01 return（codex worktree）、CL2-09A FINAL_REPORT/08_next_experiment；建立独立 evidence 目录 2026-10-10_cl2_11_r1 |
| I101 | PASS | 10 份资料逐条路径/SHA/时间/会话/绑定/TLS 同源/独立性/能证/不能证齐全；bag 板端独占、bin 为提取产物、09A 为未执行设计均如实标注 |
| I102 | PASS_WITH_FINDINGS | 假设—观测—判别矩阵 + E1/E2/E3 分级完成；§6 过强论断已被审计纠正并改写（不挡回 A 也不挡回 B），两项未尝试判别量（y-within-ring、cell×ring）正确登记为“未做” |
| I103 | PASS_WITH_FINDINGS | CL2-10 三项复算与原文完全一致；新增混淆量化 + 审计触发的 y 内结构 + 64850=63959+891 精确核对；两个数值引用错误已在本文档及 02/04 内更正；bag 复解码仍 NOT_RUN（板端独占） |
| I104 | PASS | [05](05_MINIMUM_PHYSICAL_EVIDENCE_PLAN.md) 仅设计：前置冻结、点位、量具、预注册、盲测、失败判据、最小采集量（A 包 31 读数、B 包 9 场景、C 包 1 次 bag 拉取比对）全部预注册；**不执行** |
| I105 | PASS | 真实 CLI + 实际模型 + exit0 + finish stop + read-only 权限运行期证实；全部原始 IO 留存 |
| I106 | PASS | 本轮 evidence manifest 逐 SHA（07_EVIDENCE_MANIFEST.json）；CLUSTER-01 return **append-only**（见 `return_append_record.json` + return 末尾 CL2-11 R9 段） |
| TLS01 | BLOCKED | 121647 有效 TLS 仍 BLOCKED，50mm P95 门一字未动，本轮离线任何 PASS 不自动解锁 |
| E01 | BLOCKED | 无生产接入/发布/部署/运行链路变更 |
| D01 | NOT_RUN | 无设备/物理干预/采集/B2/B3；STEP4 只编方案 |

## 6. 最小下一步（方案已给出，未执行）

见 [05](05_MINIMUM_PHYSICAL_EVIDENCE_PLAN.md)。优先级：

1. **包 A — 九点独立几何**：9 个预注册网格点 × 3 重复 + 4 基准点 = 31 读数，激光水准仪且不连 LIDAR
   （点位扩展自 09A 五点，全部开工前一次性写死）；满足前置才授权实施，否则 BLOCKED；
2. **包 B — 测距偏差独立标定**：9 场景刚性平板对照（**仅在包 A 指向 B 时启动**）；
3. **包 C — 提取链一次性结案**：从板端只读拉取 S01 bag，本地逐点验证 vs S02；1 次比对，
   封闭或确证 D 子型。
4. （本轮追加的**分析层**判别量，无需设备）：固定 ring 内 resid‑on‑y 分解 + 5cm cell×ring 双向
   最小二乘估计 h/β，仅作诊断，不生成修复候选、不改门、不宣称物理归属。

## 7. 边界与不变量（再次确认）

- 50 mm P95 / 支持率 / 几何 / RMS / 数值一致门 全部原值未动；
- 未新增任何 TLS 候选/估计器/权重实验；未导出任何“有效 TLS”；
- 未修改 CL2-10/09C/09B/09A/08 任何封号字节；CLUSTER-01 return 严格只追加；
- 未 commit/push/部署/接入生产；未触及 B2/B3；
- “CL2-11 PASS_WITH_FINDINGS” 只是**本轮调查工作**的验收，而**不是** 121647 有效 TLS 的解锁、
  生产接入条件或 B2/B3 的启动授权。
