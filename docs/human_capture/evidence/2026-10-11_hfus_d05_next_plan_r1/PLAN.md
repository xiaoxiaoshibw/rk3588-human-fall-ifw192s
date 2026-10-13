# HFUS-D05 下一步收口计划 v1

日期：2026-10-11（Asia/Shanghai）。本轮交付计划与只读核查，不启动新的算法变体或 D06/D07。优先级沿用 D05：识别效果 → 可验证 Demo → 性能 → 文档。

权威入口：`docs/human_capture/README.md`；本轮直接用户指令补充 D05 背景与规划范围。D05 工单为 `docs/human_capture/tickets/HFUS-D05.md`，既有冻结标准为 `../2026-10-11_hfus_d05_r1/BASELINE_D05.md`。本计划不替换标准、不调整阈值。旧统一计划的 D05a（分类器）/D05b（跟踪）与当前 D05（UNKNOWN/CLEANUP/时序）不是同一项，不混用验收结论。

## 1. 当前事实与纠偏

本轮读取源码、探针及已完成 SUMMARY。开始核查时 branch=`master`，HEAD=`026e06303f60ed1bbe4ddc4d037836db68da6d27`。工作树保持原状；没有全树重新 SHA，不宣称本轮全树冻结。既有 D05 的 58 文件 SHA 清单与集成全树基线只作为历史来源，实施前须验证适用资产。

| 项目 | 核查结果 | 对下一步的影响 |
|---|---|---|
| D04 base | 9 会话 SUMMARY 存在，SHA `03f1d16c83cac653fd65b0cc351339f8e0d695364a851ec31f7cf22e1cff247f` | 保留原账，继续以它作效果对照 |
| A03 | 9 会话 SUMMARY 存在；8 正式会话 strict/legacy 计数均与 base 相同 | 当前无终端收益，不把它称为有效恢复 |
| B | 9 会话 SUMMARY 存在；near strict accepted TP 114→113、observed_confirmed TP 111→110，strict FP 均为 0 | 按冻结净退化规则，该变体当前不可晋级；legacy near TP 213→214 不能抵消 strict 回退 |
| A06/C | 核查时各有一个真实 Node 评测进程，输出尚不完整 | 等完成并验完整性；不重复启动、不编辑其加载源码 |
| ABC | 尚无完整 SUMMARY | 是否执行取决于冻结组合门，不按“已有恢复点数”启动 |
| D05 Demo / FINAL / return | 尚未完整落盘 | 工单仍未收口，不能报完成 |
| CLEANUP 归因 | 探针里各有人体 GT 的会话 `bg_keep_pct == cleanup_keep_pct` | 当前只证明已审核人体点没有在该阶段额外丢失；不推广为全体点/全部场景都不删除 |

归因百分比必须重新标明分母。near 的 UNKNOWN 无参考支持删除为 149937/286822≈52.3%，BG 总丢失为 56.9%；S5 分别为 8552/8841≈96.7% 与 99.7%。不能将“保留 43.1%”写成“UNKNOWN 删除 43.1%”，也不能把所有 BG 损失都归于 UNKNOWN。原探针与旧叙述保留，新报告记录纠偏。

## 2. 按依赖推进的执行顺序

### P1：完成现有实验账本与来源核验

1. 等 A06/C 进程结束，记录退出码或说明退出码不可得；用 SUMMARY、逐帧 JSONL、输入 metadata 三方验证。各变体应有 9 会话、总计 2605 帧；正式评分只取 8 会话内有资格的帧，S9 为探索行。验证帧数、索引、时间戳、有限值、无截断/重复、GT/输入/模型/源码 SHA。
2. 已完成 A03/B 不覆盖、不无故重跑。失败或残缺输出原样保留；确需补跑时写新轮次目录，注明新旧源码 SHA 与原因，不删“烟测垃圾”或旧失败证据。
3. 逐变体冻结 source manifest。运行期间修改过 hook 时，实际加载版本与落盘源码必须能对应；不对应则该结果不能用于晋级。
4. 核查 GT 的 `source`。当前 runner 复用的 `export.objects()`不按 source 过滤，不能仅凭会话 eligible/reviewed 就断言全部对象都是独立人工真值。核对后保留同口径 legacy 历史账；人工对象正式分与 propagated/auto 探索列分开，任何重计分在新目录重算 base 与变体双方，不覆盖冻结账。

完成条件：每个实验可追溯到完整输入、实际源码、GT 资格及逐帧结果。缺失项报告 NOT_RUN/BLOCKED。

### P2：修复汇总器，再作效果裁决

唯一 writer 接管 `d05/make_regression.js`，先处理已发现的两项直接缺陷：`'use strict'` 下 `SESSIONS = ...` 未声明会触发 ReferenceError；缺失 SUMMARY 当前被静默略过，却仍可写出 FINAL。

汇总必须校验实际会话/帧/资格/版本/SHA，显式列齐变体状态。ABC 合法跳过时记录 NOT_RUN 与门判断依据，不能伪造完成。对每会话分别输出 proposal、strict accepted、strict observed_confirmed、legacy accepted/confirmed 的 TP/FP/FN/unmatched_unknown、重复 ID、P50/P95/P99 与相对 base 差分。S9 不进入效果门；strict FP=0 且存在大量 unmatched_unknown 不证明家具误检为零，必须同时展示 S1 的 legacy 误检压力与语义资格限制。

最小自检覆盖：缺 SUMMARY、少会话、截断 JSONL、输入 SHA 不符、S9 误入正式行、合法 NOT_RUN 组合，以及完整输入成功合并。失败保留，禁止先写 FINAL 后补数。

组合门沿用冻结 §5：至少一个单变体在目标会话有净收益且无悔退化。A03 已无信号，B 已有 strict 回退；等待 A06/C 实测再决定。ABC 固定含 B，须单独披露 B 回退风险，不能因 A 有收益自动推荐 ABC。如 ABC 获准实验，仍须它自身全链实跑；任何 A+C 新组合要先新登记，不能替换冻结 ABC。

### P3：补充关键语义核查，限定重跑范围

- A03 当前只对原 0.4m 门拒绝的点再要求 0.3m 参考支持，在同一距离语义下天然无法救回；它不等价于“将原门改为 0.3m”。此外 `min_local_pts=1` 时 `nb===0 || nb>=1` 不构成密度筛选。记录真实算法语义，不能把 A03 无收益解释为所有自适应 UNKNOWN 方案都无效。
- C 优先核查真实候选字段/track_id 是否能触发 still streak、boost 是否触发、配置记录的 0.45m 与实际恢复半径 0.4m 的差别。检查当前帧重新聚类/分类/跟踪、退出后的 ghost、seek/倒放/gap/跨会话状态清空；合成自检 PASS 不能代替真链触发证据。
- C 的 `recovered_pts` 仅表示注入 anchor 邻域内的 RETAINED 点，可能与原 retention 重叠。因果新增点用同帧 C 与 base 的原始索引集合差计算，不能直接把计数当作净救援数。禁止将恢复点本身作为后续恢复唯一证据。

若发现实现契约缺陷，只在 D05 隔离目录修复，记录新源码 SHA，重跑直接受影响变体到新目录。若需要改变算法参数或假设，先登记新实验轮次；保留第一轮负结果。

### P4：交付真实三窗 Demo

复用既有点云加载器、Three.js r127 与回放控件，在 `d05/` 新建页面，保留 D04 页面。三窗固定 RAW / D04 base / D05 当前变体，按 session_id+frame_index+timestamp 对齐。

九会话切换、播放/暂停/步进/重置、A/B/C 切换、候选 ID/评分/层点数、被删/净恢复/候选/最终识别着色，以及 near/far/静止/家具/失败帧跳转必须落地。恢复着色使用原始点索引差集；BG/CLEANUP 完整点集若现有 ledger 没有保存，由 D05 新 exporter 只读重放实际冻结版本导出，不能从候选点集臆造阶段 mask，也不改冻结 instrumentation。

`MANIFEST_DEMO.json` 绑定输入、ledger、源码和层点集 SHA，页面报告校验缺失/不符。S9 常显 INVALID_BINDING，未审核区域显示 UNKNOWN，失败案例与成功案例同等可见。真实浏览器操作九会话、帧切换、同步、重置和 SHA 错误路径，保存截图/操作证据；单纯 HTML 存在不能判 Demo PASS。

### P5：公平性能复核、独审与回传

现有 A03/B P95 高于 D04，但核查时 A06/C 正并发评测，原 D04 与新运行也不是同一次控制条件；先报告观测值，性能因果结论 NOT_RUN。效果候选确定后，在无其他评测竞争的条件下串行复核，统一预热/计时范围。D04 冻结效果账保持；需要现行 base 性能对照时另写性能证据，不替换它。Windows 离线性能不等于板端实时能力。

按现行工单/统一计划适用授权执行指定 OpenCode 只读独审，复用现有脚本与模型，不启新的生产 writer；核验退出码、完整审查日志与工具权限边界。独审结论不能代替真实 A/B。

追加 `returns/HFUS-D05.md`，分别报告工程、算法、GT 资格、生产接入。原冻结文档目前没有逐项验收 ID/显式版本号，收口前新增行政映射附件并由工单指向唯一当前验收版本；只给原要求编号，不后设成功阈值、不降低断言。新附加实验标准另列，不能倒写成跑前预登记。

## 3. 分工与写入边界

本轮规划只有主控文档 writer，没有派新代理，也没有干预正在运行的其他会话进程。后续实现主控独占 evaluator、组合和共享接口；确需并行时，Demo 独占新页面/exporter 文件，另一角色只读核查 GT/来源/重置契约，不能同时改 hook 与运行共享代码。任何代码 writer 首先读取并回传 ponytail 路径。

本轮已读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。复用现有 loader/matcher/renderer/独审脚本，避免另建运行框架。

## 4. 后续阶段门

先完成 D05 真实评测与 Demo，即使全部算法 FAIL 也交付失败账与可视化。冻结门未通过时，D06 组合晋级 BLOCKED；分类器重训、模型替换、跟踪改版不能混入当前 D05 补数。D07 等可靠当前检测与人工区域证据，缺失则 BLOCKED。板端/物理/部署/采集本轮 NOT_RUN，不 commit/push，不动 captures、GT、模型、生产链及旧证据。

本计划状态：PLAN_READY。它不构成 D05 完成或算法 ACCEPTED。
