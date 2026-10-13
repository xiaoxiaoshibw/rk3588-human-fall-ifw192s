I'll begin by reading the current round's six artifacts, then the historical evidence.

Now the historical evidence and the probe JSONs.

Let me read the remaining referenced artifacts to verify claims independently.

The directory has additional I105/I106 artifacts. Let me read them and the returns area.

Notable: `cl2_11_raw.stdout` appears to be a live transcript of this very audit session. Let me check the returns area and the CL2-09A design file to verify S06 and I106.

`external_directory` is denied, so the codex-worktree CL2-09A files and the CLUSTER-01 return target are unreadable to me. Let me inspect the in-repo evidence tree.

Let me confirm whether `cl2_11_raw.stdout` is a live capture of this session by re-reading it.

# CL2-11 独立只读审计报告

**模型**：opencode-go/deepseek-v4.1-flash｜**权限**：仅 read（shell/write/task/network 无）｜**性质**：只读、零执行
**审计对象**：`docs/sidequests/evidence/2026-10-10_cl2_11_r1/` 六份产物 + I105/I106 工件，及 CL2-10 冻结证据。

## 0. 我实际做了什么（边界声明）

我**只调用 read**，读了本轮 6 份产物、本轮目录（发现 6 个 `cl2_11_*` 工件）、CL2-10 的 `FINAL_REPORT.md / 01_root_cause.md / cl2_11_ring_probe.json / cl2_11_ring_xy_probe.json / 01_channel_diagnostics.json / 00_input_catalog.json / 00_SCOPE_AND_ACCEPTANCE.md`、`returns/CL2-09C.md`、`REVIEW.md`。

**主动尝试但被拒**：
- `C:/Users/.../codex/worktrees/.../2026-10-09_cl2_09a_r1/08_next_experiment.md` 与 `FINAL_REPORT.md` → `external_directory` deny，**未读到**。
- 因此 **S06（09A 五点、其 SHA）、CLUSTER-01 return 的实际追加内容**，我都**无法核验 → UNKNOWN**。

**我未执行任何脚本、未重算任何 SHA、未跑任何测试**。下文出现的求和（如 631+891+287+106）是我**从读出字段手算**的核对，非工具执行；凡涉及"文件级 SHA 是否真的被重算"一律标 **UNKNOWN**。

**一个重要发现**：`cl2_11_raw.stdout` 里记录的正是**本次会话自己**的 read 调用（sessionID `ses_edbf2cff3ffeN9r8HZWon1Y2kd`、含我刚发生的 read），说明它是**本审计的运行期实时捕获**，不是一份已封存的完整审计日志。故 I105 的"exit/模型导出"在包内**尚不存在**。

---

## 1. 逐项反驳（对应你要求的 8 个问题）

### ① 证据来源是否可靠？是否同源冒充独立 GT？

**未发现同源冒充独立 GT。** 01_INVENTORY 的区分是**诚实**的：
- S01 bag `board_side_only=true, local_copy_exists=false`，SHA 注明来自 `meta.json` 记录而非本地重算（`sha_source` 明写）；
- S02 bin `is_independent_measurement=false`、`produced_by_same_tls_estimation=false`（提取产物，非独立）；
- S05 report `produced_by_same_tls_estimation=true, is_independent_measurement=false`（**关键诚实点**：TLS 输出不独立）；
- S06 09A **明写"设计方案、从未执行、不含实测值、不能作 GT"**；
- S07 照片 / S09 PCAP `found=false`；S10 probe/ai_labels 标为"严格同源派生"。
- S05 自述 `ground_identification=algorithm_candidate`、`ground_confirmed=false`，未被当作 GT 使用。

**轻微瑕疵（非阻塞）**：S01 字段 `is_independent_measurement=true` 只看字面易误导（它只"独立于 TLS 估计"，**不是独立表面 GT**）；其 note 与 §7 INDEPENDENT_GT=FAIL 已把它拉回，但字段命名建议改为 `independent_of_tls=true`。

### ② 是否存在循环论证（用 TLS 输出证明 TLS 解释 / 用 f(x) 归因 g 或 b）？

**结论：没有犯此循环。** 02 §6、03 汇总都显式声明"E2 反事实只测机制，不能把 f(x) 归因给 g 或 b"，并拒绝把局部平面拟合当真实几何。方向正确。

**潜在残留（非阻塞）**：残差 f(x) 是相对 **S05（TLS 输出）法向/offset** 计算的。作者用"刚体不变性 ≤8.9e-16 m"证明"残差不是坐标系选择造的"，但那是"到固定平面的距离"不变性，**不等于拟合平面无偏**。作者其实在 §2 已用"数学表示正确 ≠ 物理安装角正确"提醒，故不构成循环；建议再显式写一句"残差场是相对 TLS 平面的性质，其沿 x 形状本身不构成地面几何真值"。

### ③ 物理假设是否真正可辨识？02 §6 的欠定论证是否成立？有无被忽略的可分离锚点？

**这是本次审计最重要的发现：§6 的欠定论证方向正确，但结论"数学上不可分辨"被写得**过强**，且**忽略了一个潜在可分离锚点**。**

- §6 的论证只覆盖**沿 x 的分量**（ring 与 display-x 强相关 → g(x)+b(x)=f(x) 不可拆）。这一层**成立**。
- **但它忽略了两个可利用结构**：
  1. **y 维度**：由 `01_channel_diagnostics` 可见，每个 ring 在 ROI2 内 display-y 跨约 0.24 m（如 ring27 的 y 从 −0.2499 到 −0.0063），而 x 只跨约 0.07 m。**固定 ring 内的残差随 y 的变化**无法由"逐环测距偏差"解释（b 只随 c=ring 变），这是 g 的 y 依赖的**潜在分离通道**——文档未做。
  2. **每 5cm 格多 ring 结构**：CL2-10 明说 `fraction_points_in_multiring_cells=1.0`（每格 5–7 个 ring），且相邻 ring 的 display-x 有重叠 → 观测方程 r≈h(cell)+β(ring) 的**cell–ring 二部图连通**，理论上可把"格效应"与"环效应"**分离到一个全局常数**（这正是"多环重叠观测同一点"的经典可分结构）。作者只用"重叠区残差平滑过渡"定性否掉了**阶跃式**逐环偏差，但**平滑变化的**逐环偏差仍可与平滑地面共存。
- **不过**，即使分离出 h 与 β，把哪个**命名为"真地面 g"、哪个命名为"传感器偏差 b"仍需外部假设**（g 在 5cm 内是否可视为常数、floor 是否有与扫描带对齐的纹理）。因此物理因果仍未闭合——**但"数学上不可分辨"这句话本身不成立**，正确表述应是"**在已执行的分析口径下未辨识，且 cell/ring 二维分解是未尝试的潜在判别量**"。

**裁定：§6 属"过强论断/论证不完整"，是一个真实的逻辑瑕疵（见下文 I102），但不翻盘总体 BLOCKED 结论。**

### ④ ring↔display-x 混淆量化是否足以挡回"逐环偏差不成立/地面非平面不成立"这种强论断？

- **值得肯定**：文档**没有**下"逐环偏差不成立"或"地面非平面不成立"的强论断，反而用混淆**同时**挡回 A 与 B 的强论断，方向正确。
- **但量化本身证据不足**：`cl2_11_ring_xy_probe.json` 只存了每 ring 的 **count / signed_mean / display_x 的 min·mean·max**，**没有分布**。因此"相邻重叠 30–50%"**无法从存档复算**——它是断言而非可追溯量。而且我按 FIT 的 min/max 粗估 ring32∩ring33 重叠比可达 ~60–75%（frame72 域亦 >50%），与"30–50%"不符的可能存在；**该百分比应视为 UNVERIFIED**。
- **数值混淆（可判定 FAIL）**：02/04 反复写"signed mean…平均步进 ≈0.013 m/ring，共 0.134 m"。事实：signed mean 从 ring22 −0.07306 到 ring41 +0.06138 共 **0.1344 m**，跨 **19** 环 → 步进 **≈0.0071 m/ring**；**0.013 m/ring 是 display-x 的步进**（0.24035/19≈0.01265）。0.013×19≈0.247≠0.134，**该句内部自相矛盾**，属把 display-x 步进错标为 signed-mean 步进。
- **覆盖区数值**：02 的 0.003/−0.001/+0.006 与 frame72（300 点）一致（ring32=+0.00291、ring33=−0.00067、ring34=+0.00551），但该表同时混用了 FIT 域的 count（如"FIT 833"）——见 ⑦。

**裁定：量化方向可用于避免强论断，但 (a) 关键"重叠%"未存档，(b) 0.013/0.134 自相矛盾，(c) 更根本的 cell/ring 或 y 内分离通道未做 → 不足以支撑"完全混淆/数学不可分辨"的强表述。**

### ⑤ 训练/验证泄漏：FIT 与 frame72 留出是否互斥？本轮是否偷用 FIT 点证留出结论？

- CL2-10 与 CL2-11 均声明"源行/FIT/留出互斥"；`cl2_11_ring_probe.json` 明确**分列** `by_ring`（frame72 300 点）与 `fit_roi62k_recheck`（FIT 63959）。
- 我手算交叉验证：`01_channel_diagnostics` 各 ROI count = 45748/64850/20715/7544，减去 `01_root_cause` 的 FIT（45117/63959/20428/7438）得 holdout 631/891/287/106，**合计 1915**，与 CL2-10"三个留出共 1915 点"一致 → **count 与 FIT 口径互斥成立**。
- 未见"用 FIT 点证 frame72 留出结论"的实质泄漏。**主要问题只是 02 §3 的表格把 FIT 域与 frame72 域的数字混排且逐行不标域名**（可追溯性瑕疵）。
- **裁定：无实质泄漏，PASS（附可追溯性建议）。**

### ⑥ 是否违反 CL2-10 停止边界？是否新增 TLS 候选/改门控/改算法/设备操作？

- **算法/门控/候选**：未新增。04 §4.6"未生成任何 TLS 候选"，50 mm 门未动，05 只写方案。
- **设备/采集**：无（05 §5.10 明列不执行）。
- **但有一处记录边界冲突（可判定）**：`cl2_11_ring_probe.json`、`cl2_11_ring_xy_probe.json` 被写入 **`2026-10-09_cl2_10_r1/`**（CL2-10 的旧轮目录），而 00 表第 23 行自定"**本轮只新增自己的 evidence 目录，不回填旧记录**"，仓库规则亦为"每轮一个 `<date>_<item>_r<N>` 目录、never backfill past records"。04 §4.3 的辩解"写到 **CL2-11 investigation 名下**的既有目录"**与目录名不符**（该目录是 CL2-10 名下）。
- **裁定：未见改算法/门控/设备越界；但存在"把本轮产物写进旧轮目录"的记录卫生/边界瑕疵。** 若确有用户显式授权，应 (a) 明确披露授权出处，(b) 在 CL2-11 目录留副本/清单，(c) manifest 里标注"跨目录写入"。

### ⑦ 数值一致性（你点名的口径）

| 项目 | 本轮声明 | 独立核对来源 | 结果 |
|---|---|---|---|
| frame72 signed mean | −0.00079674 m | `cl2_11_ring_probe.json.signed_residual_overall.mean_m=−0.0007967392724574577` | **一致** |
| frame72 RMS | 0.02741799 m | `rms_m=0.02741798759071692`；CL2-10 RMS=27.417988mm | **一致** |
| frame72 P95(abs) | 0.05029187 m | `p95_abs_m=0.05029186936019117`；CL2-10 P95=50.291869360mm | **一致** |
| frame72 中位 | (−0.00122994) | `median_m=−0.0012299369294443974`；CL2-10 −1.229937mm | **一致**（未在你清单但同源佐证） |
| FIT ROI2 count 63959 | "与CL2-10 channel diagnostics count 一致" | `01_root_cause` FIT 表 ROI2=63959 ✓；但 `01_channel_diagnostics` ROI"2"的 `count=64850` | **数字 63959 正确；"与 channel diagnostics count 一致"的引用错误** |

- **关键纠错**：`01_channel_diagnostics.json` 的 ROI2 `count=64850`（我手算各 ring 计数和亦=64850），而 FIT ROI2=63959，差 891 = ROI2 三帧留出（300+…）。因此 04 §4.1"63959 点，与 CL2-10 channel diagnostics count 一致"是**把 FIT 数误配上 channel-diagnostics 的全量数**。属**引用/归属级错误**，非数据造假。
- **另一处**：02 §3"ring 23 | 4(FIT 833)"——FIT 的 ring23 应是 **822**（`fit_roi62k_recheck`），833 是 channel-diagnostics（FIT+holdout）值；且该行 signed mean −0.0475 是 **frame72** 值。混域。
- **结论**：你点名的三项复算值与 CL2-10 原文**完全一致**；但**"FIT ROI2 63959 与 channel diagnostics 一致"的说法不成立**（应为 64850），且 0.013 步进自相矛盾。

### ⑧ 五项最终裁定是否越级？

02 §7 明确"**即使 STEP0/STEP1 全 PASS，也不代表 121647 的 TLS 已通过**"，**未把 INVENTORY PASS 当 TLS PASS**。方向正确。

**但违反"不得混用"的形式要求**：00 表要求五项"各自独立报告 PASS/FAIL/BLOCKED/UNKNOWN，不得混用"，而 §7 写成 `IDENTIFIABLE = FAIL（即 UNKNOWN）`、`READY_FOR_REPAIR = FAIL / BLOCKED`——**FAIL 与 UNKNOWN、FAIL 与 BLOCKED 被混写**。应择一（建议 IDENTIFIABLE=UNKNOWN、READY_FOR_REPAIR=BLOCKED）。属**形式逻辑瑕疵**。

我**独立复核**五项规定：DATA_AVAILABLE=PASS（S01–S05 存在，合理）；DATA_BOUND=PASS（含 S01 bag 仅由 meta 记 SHA 绑定、非本地重算的限定）；INDEPENDENT_GT=FAIL（确无独立物理 GT）；IDENTIFIABLE=UNKNOWN；READY_FOR_REPAIR=BLOCKED。**无实质越级。**

---

## 2. 逐 ID 裁定

| ID | 裁定 | 依据与限制 |
|---|---|---|
| **I100** | **PASS（限定）** | 独立 evidence 目录已建（`2026-10-10_cl2_11_r1/`）；`01.STEP0_baseline` 列出所读 CL2-10/09A 冻结件。**子项"Git/工作树/保护资产起止的实读 SHA"我无 shell 无法核验 → UNKNOWN**（不记为 FAIL）。 |
| **I101** | **PASS** | 10 份 S01–S10 逐条给出路径/SHA/时间/会话/是否同 TLS 产/是否独立测量/能证/不能证；对 bag 板端独占、bin 提取产物、09A 仅设计、照片与 PCAP 缺失**如实标注**。限定：S06（及 09A）文件在 codex worktree，**我无法读、其 SHA 未亲验 → UNKNOWN**。 |
| **I102** | **PASS（含逻辑瑕疵）** | 02/03 完成假设—观测—判别矩阵与 E1/E2/E3 分级，⑤判不可辨识，未把局部平面当 GT。**逻辑瑕疵（非致命）**：02 §6 的"数学不可分辨"过强，忽略 y-within-ring 与 cell↔ring 二部可分结构；证据不足：'重叠 30–50%'未存档、不可复算。 |
| **I103** | **PASS（主体）＋子项 FAIL** | 04 全程描述性、未造 TLS 候选、NOT_RUN 项诚实标记；frame72 三项统计与 CL2-10 完全一致。**具体逻辑/引用 FAIL**：(a) §4.1"63959 与 channel diagnostics count 一致"错误（实际 64850）；(b) §4.3"0.013 m/ring 的 signed-mean 步进"错误（signed-mean 步进≈0.0071，0.013 是 display-x）。**限定**：bin SHA"启动时断言"是否真重算，我无法从产物确认 → UNKNOWN。 |
| **I104** | **PASS** | 05 为**仅设计未执行**的最小补证方案，含前置条件、判伪/失败判据、预注册、最小采集量与依据，并再三声明不连板/不改标定/不动 50 mm 门。 |
| **I105** | **PASS（限定）** | 只读审计**确已真实进行**（即本会话）：`cl2_11_config.json` 全局 deny 仅 read 允许、`cl2_11_agent.json.tools` 明确 `read:true` 其余 bash/write/edit/task/webfetch/websearch/skill 全 `false`；我本人被 `external_directory` 拒绝，**操作层面证实只读与外部目录封锁**。**限定/UNKNOWN**：`cl2_11_raw.stdout` 是**本次会话的实时捕获**（可见我自己的 read），**exit code 与模型导出在包内尚不存在 → UNKNOWN**，不得据此写"exit0/export0"。 |
| **I106** | **BLOCKED / UNKNOWN** | evidence 目录存在，但**目录内无任何逐 SHA manifest 文件**（I106 明确要求"manifest 逐 SHA"）→ 交付未完成或未入该目录。CLUSTER-01 return 目标在 codex worktree（我 external deny 读不到）→ **追加是否发生/仅追加不能核验**。另：**probe JSON 被写入 CL2-10 旧轮目录**，与 00 行 23"不回填旧记录"冲突（见 ⑥）。 |
| **TLS01** | **BLOCKED** | 121647 有效 TLS 仍 BLOCKED、50 mm P95 门未动、离线 PASS 不自动解锁——本轮未见任何解锁动作。 |
| **E01** | **BLOCKED** | 无生产接入/发布/部署动作。 |
| **D01** | **NOT_RUN** | 无设备/物理干预/采集/B2/B3；05 仅方案。 |

---

## 3. 具体逻辑 FAIL、证据不足项、非阻塞建议

**具体逻辑/事实 FAIL（可判定）**
1. **I103/04 §4.1**："FIT ROI2 63959 与 CL2-10 channel diagnostics count 一致" —— 实际 channel-diagnostics ROI2 = **64850**（我手算 ring 和亦得 64850；64850−63959=891=ROI2 留出）。引用错误。
2. **I102/03、I103/04**："平均步进 ≈0.013 m/ring（signed mean），共 0.134 m" —— 0.013 是 **display-x** 步进；signed-mean 步进 ≈ **0.0071**；0.013×19≈0.247≠0.134，**句内自相矛盾**。
3. **I102/02 §3**："ring 23 | 4(FIT 833)" —— FIT ring23=**822**，833 是含留出的 channel-diagnostics 值；且 −0.0475 属 frame72 域。混域。
4. **I102/02 §6**："A/B/C 平缓子型在**数学上**不可分辨" —— 论证不完整（未处理 y-within-ring、cell↔ring 二分），属**过强论断**。
5. **五项混写**：`FAIL（即 UNKNOWN）`、`FAIL / BLOCKED` 违反"不得混用"。
6. **记录边界**：本轮产物写入 `2026-10-09_cl2_10_r1/`，与自定边界冲突；辩解措辞"CL2-11 名下目录"与目录名不符。

**证据不足项（应保持 UNKNOWN，勿记为 FAIL）**
- S06/09A 文件与其声明 SHA（我在 external 目录，读不到）。
- CLUSTER-01 return 是否仅追加（同上）。
- I105 的 exit code / 模型导出（包内仅实时 stdout）。
- bin SHA 本轮是否**真的被重算**（仅有"断言"声明）。
- "相邻 ring 重叠 30–50%"的量化（存档仅 min/mean/max，无法复算）。
- 09A 的"25 格跨帧相关 0.988""合并趋势 P95 29.3mm"（源在不可读 worktree）。

**非阻塞建议**
1. 把"不可分辨"改述为"**在已执行口径下未辨识**"，并**补做**：固定 ring 内残差对 y 的回归；5cm 格内 cell×ring 双向分解（检验残差形状落在环效应还是格效应，仅作诊断、不改门、不生成候选）。
2. 将"重叠%"等汇总统计**随产物存档**（附直方图/每 ring 的 x 分位），而非只存 min/mean/max。
3. 修正 64850/63959、0.013/0.0071、"FIT 833"→822 三处；表格逐行标 FIT/留出域。
4. 五项裁定各自只写一个状态标签。
5. 将 `cl2_11_ring_probe.json / cl2_11_ring_xy_probe.json` 复制入 CL2-11 目录并在 manifest 标注跨目录写入与授权出处；补 `manifest（逐 SHA）`。
6. S01 字段改名以消除"独立测量"歧义。

---

## 4. 作者是否该给 CL2-11 PASS？

**不应给"无保留的 PASS"。**

- 本轮**调查目标达成**：结论"现有资料**不能**区分 A/B/C/D（D 提取子型待可读 bag）/E，物理根因 UNKNOWN，只出补证计划"是**正确且保守**的，且**未越级**把库存 PASS 当 TLS PASS。
- 但按本轮自己的验收口径（"全部停止条件满足才 PASS"、TLS01 仍 BLOCKED），以及存在 **I106 manifest 缺失、CLUSTER-01 追加不可核验、probe 写入旧轮目录、§6 过强论证、两处数值引用错误**，**不满足干净 PASS**。
- 合理记法：**CL2-11 调查工作 = PASS_WITH_FINDINGS（有条件通过）**；**121647 有效 TLS / 修复条件 = BLOCKED**；不得声明"TLS 已过"或"具备修复条件"。若要求单一状态，则本轮整体为 **BLOCKED**（与 CL2-10 一致）。

---

AUDIT_COMPLETE