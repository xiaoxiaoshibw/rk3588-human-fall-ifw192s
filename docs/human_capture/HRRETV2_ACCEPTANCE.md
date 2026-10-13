# HR-RET-V2 唯一验收表 v1（融合 v2 生产接入）

生效：2026-10-08（Asia/Shanghai）。本表是该工单唯一现行判据（此后引用不复制多份）。
口径：融合层语义 = `FUSION_PRIORITY_RULE_DRAFT.md` §3.1；生产管线 = console leveled 口径；P（在线-only）路径不变。

| ID | 要求来源 | 可观察预期 | 触发/负例 | 检查/证据入口 | 层级 | 现行状态 |
|---|---|---|---|---|---|---|
| V2-01 | 草案 §3.1 | `extract_foreground_fused`：参考命中→删；在线命中且其体素邻接参考（<0.12m）→删；在线-only→保留；工作空间裁剪与 `extract_foreground` 一致 | 负例：无参考时不得仅凭在线删；地面点剔除 | `human_pipe_lib.test.js` 新增用例；代码审查 | 软件 | **PASS（本轮自验，increment 1）** |
| V2-02 | 草案 §5.1 | 三段静立人融合层保留 ≥95% | — | `evidence/2026-10-08_fusion_v2_ab_r1`：99.9/100/100% | 离线诊断 | **PASS（自验）** |
| V2-03 | 草案 §5.1 | 端到端：人每帧可见候选；cleanup 不减人 | 举臂段确认未达需给出原因 | `fusion_v2_chain_results.json`（候选 64/66/56 帧；确认 62/23/0，623 原因=旧证据门） | 离线诊断 | **PASS（自验）** |
| V2-04 | 草案 §5.2 | WD01 删除 ≥REF−2pt；WD02 ≥REF−2pt | — | `fusion_v2_ab_results.json`：99.3 vs 99.2；62.9 vs 62.4 | 离线诊断 | **PASS（自验）** |
| V2-05 | 草案 §5.4 | 工具自复现上一轮（±3pt/±20%） | 复现失败先查工具 | 同证据：REF/UNION 逐点一致 | 离线诊断 | **PASS（自验）** |
| V2-06 | 草案 §5.3 | 代价（非人泄漏）公开在案 | — | README：2.1–2.5k 点/帧 + 箱子窗口少删 1.9–8.4pt | 离线诊断 | **PASS（记录）** |
| V2-07 | 草案 §5.2 | v2 语义下空场 0 candidate / 0 confirmed | — | `evidence/2026-10-08_hrretv2_r2/empty_v2_results.json`（identity-reference 口径；0 簇 / 0 确认 track 帧） | 集成 | **PASS（自验，increment 2）** |
| V2-10 | 本工单 | 新函数+单测落地；P 路径逐位不变（无调用点） | — | `lib_tests.log`；diff | 软件 | **PASS（本轮自验，increment 1）** |
| V2-11 | 本工单/R3.9 口径 | 旗标默认关=行为不变；开=仅 VALID artifact 走 v2，其余保持 P | 负例：STALE/DEGRADED/无 artifact 不启用 | `registration.test.js` V2-11a/b；`digest_results.json` D1/D3（真实 artifact 全 STALE → 不启用） | 集成 | **PASS（自验，increment 2）** |
| V2-12 | 本工单 | 加载路径与浏览器/节点实际行为验证（含回退） | — | `browser_check.md` + `browser_replica_results.json`（7/7）；`digest_results.json`（D1–D5） | 集成 | **PASS（自验，increment 2）** |
| V2-13 | 流程 | 相关回归全过（human_pipe_lib / human_replay_lib / panel 套件） | — | `lib_tests.log` | 软件 | **PASS（inc1+inc2 套件；38/38 + registration 全 PASS + 45/45 + panel + 11/11，exit 0）** |
| V2-14 | 流程 | 独立复审（非本 writer）逐条核对 | — | 复审记录 | 流程 | **NOT_RUN（inc2 已交付，待独立复审）** |
| — | 边界 | 设备/物理/部署/采集 NOT_RUN；采集另单（板端 2026-10-08 不可达，BLOCKED） | — | — | — | NOT_RUN |

记录规则：每条 PASS 必须有本轮或仍适用的已验证证据；变更代码/证据后受影响行重验。
