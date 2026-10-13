I'll begin by reading the scope, skill, and core evidence files.

Now the core source files — frozen baseline and candidate floor_sheet, plus benchmark and probes.

Now the evidence JSONs and tooling scripts.

Now the evidence JSONs, author analysis, and 09B reference docs.

Now the remaining evidence JSONs and 09B patch.

Let me list the evidence directory to see all artifacts (prior attempts, manifest, return).

已按要求只读审计。以下为 CL2-09C 逐项中文报告。

先说方法与边界：本次仅用 read 工具检查了指定文件；**没有执行任何命令、测试、基准或 SHA 计算**。凡涉及"实际数值/退出码/哈希/板端"的结论均来自作者留存证据，我未亲自复算，统一标 **UNKNOWN**，且不把 UNKNOWN 当作逻辑 FAIL。受权限限制我**无法读取** `01_baseline.json`、`10_evidence_manifest.json`、return 文件，也无法列目录（目录读取被 deny），故最终 manifest/return 的闭合状态我无法核实——这与 00_SCOPE 所说"审计后追加"一致。

---

## 一、核心等价性逐问结论（C03/C04 的实质）

被改动范围仅 `candidate/floor_sheet.py` 的 `_roi_metrics` 旧失败兜底（253–289 行）；`frozen` 为原生产（无兜底，229–239 直接返回），`baseline/floor_sheet.py` 为 09B 完整实现（253–267 旧兜底），`candidate` 为 09C。

**1) 预计算整数差的 hypot 是否完全保持浮点结果 —— 是。**
`distances[a][b] = float(np.hypot(*(keys[a]-keys[b])))`（candidate 255–257）与旧代码 `float(np.hypot(*(pts[a]-pts[b])))`（baseline 260）对同一全局下标对的输入是同一 int64 整数差、同一 `np.hypot` 调用，结果位相同；`separation=min(abc,da[d],db[d],dc[d])`（282）与旧 6 个 hypot 的 `min` 同一取值集合，min 无累积误差。`keys` 在两模块均来自同一 `sorted` 顺序，故逐对比特一致。

**2) 嵌套部分最小间距剪枝是否必然安全 —— 是。**
记 `separation = min(abc, ad, bd, cd) ≤ abc = min(ab, ac, bc) ≤ ab`。剪枝条件为 `ab*cell_m < gate 或 ab ≤ winner_sep`（263）、`abc*cell_m < gate 或 abc ≤ winner_sep`（275）。一旦部分量已 `<gate`，则完整 separation 也 `<gate`；一旦部分量 `≤winner_sep`，则完整 separation `≤winner_sep`。旧代码在同等条件必然 `continue`。故剪枝只丢弃旧代码也会丢弃的组合，**不会漏掉任何可行赢家**。

**3) winner_sep 随循环更新会否删掉更优/改变稳定并列 —— 不会。**
`winner_sep` 仅在 `candidate["ok"]` 时更新（287–288），与旧代码一致；替换要求严格 `>`，等距后续组合被 `≤winner_sep` 跳过，因此保留"组合字典序最早且 ok 的最大间距组合"这一稳定并列语义。candidate 的 a/b/c/d 遍历与 `itertools.combinations(range(n),4)` 字典序逐项相同（含 c 共线时 d 走升序 `outside`），故到达 `describe` 的顺序与 ok 集合均一致。由问 2 的单调性，winner 序列与 baseline 完全相同。

**4) 共线与重复行为是否保持 —— 是。**
- 整体共线提前返回（245–251）与旧代码逐行相同。
- 单四元组：旧判定 `np.all(span[:,0]*span[0,1]==span[:,1]*span[0,0])` 在 a,b 固定下等价于 `collinear[c] and collinear[d]`；candidate 用 `collinear[c]` 决定 d 是否限定于非共线 `outside`（278），恰为"跳过且仅跳过共线四元组"。
- 重复点（axis=0、`span[i]=0`）在两侧都被判共线并跳过，且此类四元组分离度必为 0、本就过不了 0.5m 门。
- `test_duplicate_keys_cannot_displace_valid_four` 亦覆盖。

**5) 原成功与拒绝的完整 dict 是否相同 —— 是。**
`describe`（229–240）与旧实现逐字段相同；旧成功直接 `return previous`（243–244）；拒绝时 `winner` 初值为 `previous`（258），只有通过 `describe` 的 ok 组合才替换，返回的都是 `describe` 产物。故成功/无解两种返回的完整 dict 与 baseline 位相同。`test_equivalence` 用 `assertEqual` 比较完整 dict（而非 ok 标志）。

**6) 无 cap 是否仍可能最坏 O(n^4) —— 是，且作者已如实披露。**
candidate 未加上限/超时/截断；最坏情形（无可行情侣使 `winner_sep=-1`、门不剪、`collinear[c]` 多为假）内层 d 循环约 `n-c-1`，总计 `Σ_{a<b<c}(n-1-c)=C(n,4)=O(n^4)`。另每个 (a,b) 做一次 O(n) 的 `span/collinear/outside`，累计 O(n^3)，不改变量级。253 行注释与 07_AUTHOR_ANALYSIS 均明确"最坏仍 O(n^4)、不宣称绝对时限"。

**7) 剖析分项边界/开销披露是否诚实 —— 基本诚实。**
`profile()` 明确 patched 会加计时开销；caveat 明说 `np.all` 混合"共线+独立性"两检查、`spacing_min` 对旧 generator 含内嵌 hypot/enumeration 的 inclusive 时间、循环体与标量门控留在 residual、禁止相加/当基准用（benchmark.py 58–61）。03_profile_03.json 忠实记录。**唯一措辞小瑕**：`spacing_min is inclusive of nested hypot/enumeration in the legacy generator` 对 candidate 不成立（candidate 的 `min` 只吃已算标量），但这是 baseline 导向的描述、且总 caveat 已禁止比较，不构成误导。非 FAIL。

**8) 基准是否真正无 mock 且同输入同环境 —— 基准分支是。**
`benchmark.py` 的正式基准分支（75–99）不进入任何 `patch`；`patch` 只在 `profile` 分支使用。同进程、同 `data` 对象、基线/候选交替顺序各 3 次，逐轮 `assert results['baseline']==results['candidate']`，并记录 python/numpy/platform 与两侧 SHA。**披露局限**：`method` 已说明"首样本仅是该输入首次调用，不是冷 OS/冷 BLAS 进程"；`processor` 为空串，机器标识偏弱。均属已披露的边界，非逻辑 FAIL。

**9) 35 原回归和新差分完整性 / 121647 门控 / E01/D01** —— 见下表。

**反例搜索结论**：我针对 (a) 同间距部分 ok 部分不 ok、(b) 重复点致 axis=0、(c) c 共线而 d 非共线、(d) 剪枝误删可行赢家 四类刻意寻找具体反例，**未发现**使 candidate 偏离 baseline 的输入。所有偏离路径都被"部分量 ≥ 完整量 + 单侧跳过"堵死；这是全定义域证明，强于抽样差分。

---

## 二、逐 ID 判定

| ID | 逻辑/结构审计 | 执行/数值 | 依据与边界 |
|---|---|---|---|
| C01 | 机制 PASS | **UNKNOWN** | prepare.py 会 `assert sha(B/name)==digest` 复算 09B manifest，并 guard 输入/历史/生产 `floor_sheet.py`；但 `01_baseline.json` 被权限拒绝读取，branch/HEAD/全树库存与起止 SHA 我未复算。 |
| C02 | PASS | **UNKNOWN** | benchmark.py 58–61 caveat 诚实披露插桩开销、np.all 混合、min inclusive、residual 与不可比较；具体秒数见 03_profile_03.json（作者执行）。 |
| C03 | **PASS（等价证明）** | 执行 UNKNOWN | 完整保留成功/拒绝 dict、最大间距、稳定并列；无 cap、未改 `describe`/SVD/门控（253–289 对照 253–267）。 |
| C04 | **PASS（等价证明）** | 执行 UNKNOWN | test_equivalence.py 以 09B 完整枚举为 oracle 用 `assertEqual` 比完整 dict；覆盖小/大、成功/无解、重复、并列、反序、阈值边界。 |
| C05 | PASS（结构） | 执行 UNKNOWN | 05_regression_03 命令为 `-B -W error`，41 项（35 冻结+6 差分）全 ok（stderr 87–89）；Py3.8 语法经 `ast.parse(feature_version=(3,8))`（test_selector 78–79、test_equivalence 73）。板端 3.8/NumPy1.17 未跑。 |
| C06 | PASS（结构） | 数值/执行 UNKNOWN | 25/60/100 × 有解/无解（+line）真实基准，样本、环境、SHA 齐备；"冷"仅为进程内首调用（已披露），`processor` 空。生产时延验收应保持 NOT_RUN。 |
| C07 | PASS（结构） | 执行 UNKNOWN | session_probe.py 重放得 11 clean cells，三方选择相同；ordinal72 P95=0.05029186936019117 FAIL、`effective_TLS=BLOCKED`、无新 TLS/导出（06_*）。门控未降。 |
| C08 | 进行中 | **UNKNOWN** | 即本独审会话；session export/退出码/权限须审计后写入，我无法自证。 |
| C09 | 待闭合 | **PENDING/UNKNOWN** | 最终 manifest/return 审计后追加；`source_summary.json` 仅前置完整性，作者分析称失败尝试（sandbox temp、回环 socket、Git Bash 版本查询等）已保留，但我无法列目录核实。 |
| E01 | **BLOCKED（保持）** | — | 仅隔离 candidate，未接生产/未发布/未部署；改动不触 `pc_apps/human_replay/floor_sheet.py` 生产文件。 |
| D01 | **NOT_RUN（保持）** | — | 无设备/物理/B2/B3/采集；121647 有效 TLS 维持 BLOCKED。 |

---

## 三、非阻塞观察（非 FAIL，给出最小范围建议）

1. `02_fix.patch` 注释只写了"每对只算一次"，未点出引入 `n×n` 距离表的 **O(n²) 内存**（作者分析里有，补丁注释里没有）。建议仅补一行注释，不动逻辑。最坏 O(n⁴) 与不设 cap 已如实声明，故不构成放宽验收。
2. `spacing_min is inclusive of nested hypot/enumeration in the legacy generator` 对 candidate 分支表述不精确（candidate 的 min 不含嵌套 hypot）。建议改为"对旧 generator 分支 inclusive"。文档性，非正确性。
3. `04_benchmark.json` 的 `processor` 为空串、baseline 样本随轮次递增（33.5→43.0→48.6 s，疑似热漂移），已用交替顺序与中位数缓解、并注明"真实本地测量"，不影响结论方向，但削弱绝对精度。
4. `line` 全共线用例 speedup≈0.92（25 格），实为 0.1 ms 量级噪声（该路径在 245–251 提前返回、根本不建距离表），非真实回退。

无任何真实 FAIL，故不降低验收。

---

AUDIT_COMPLETE