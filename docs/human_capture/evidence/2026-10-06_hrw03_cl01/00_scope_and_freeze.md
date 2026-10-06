# 00 · CL-01 范围与冻结记录（Foreground Clustering Failure Audit + Controlled Clustering AB）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**第一阶段只读审计**。本目录全部脚本为离线 shadow/只读，**生产零改动**；不采集、不部署、不 commit。
- 工单：R3.4 / CL-01（foreground clustering failure audit → controlled clustering AB）。R3.1/R3.2/R3.3 结论冻结，不重开 background matcher 调参。

## 1. 冻结对象与 SHA 复核（执行开始时）

| 对象 | SHA256 | 期望 | 判定 |
|---|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `5bce92a433e58d537c05bfd36f516077f94e80bf351a94aae8efad46b04142b4` | `5bce92a4…142b4`（与 R3.1/R3.2/R3.3 一致） | **PASS** |
| git HEAD | `e79b1301eebc0bbe6ca07302498ae02cb2c03c24` | 记录基线 | — |

数据输入 SHA（只读）：

| 会话 | 用途 | points.bin SHA256 | meta.json SHA256 |
|---|---|---|---|
| `cap_20261002_223757` | current（WD01 / HP01 / HP03 / f10·f30·f55） | `8afb660b7bf0631462d4cde6f82bd89884b2e83acea1da25c07316c87b5fbb37` | `71915d5181b8fc409d83a8e1650671801d2d50cf09ef4a3832d43b51ec3f4ca8` |
| `cap_20261004_203349` | reference 空场（R3.1 artifact 源） | `2ed3fc60d99b3a2f42e0951835ad847fae2f490859e487b167fbccb1b5f10323` | `c3b55d1e11ed8a043bd3645af7ed07e920024c05f3cb48b15d523405edd38392` |

最终复核（CL-01 收尾时）必须重跑 `sha256sum pc_apps/human_replay/human_pipe_lib.js` 并与上表一致；不一致 = FAIL/STOP/REPORT DIFF。

## 2. 本阶段边界

**禁止**：改 `human_pipe_lib.js` / production HTML/JS / detector 参数 / WebUI production 行为 / background matcher / registration / reference / occupancy threshold / ground leveling / static-map builder / 现有 evidence / commit / deploy / 采集新数据。

**允许**：新建独立 audit/experiment 脚本；读现有 session/reference；shadow 运行；输出 JSON/CSV/Markdown；独立 debug HTML；本目录新增文件。

**严格顺序**：代码审计 → 确认 baseline semantics → synthetic micro-cases → 真实问题帧 cluster lineage → failure taxonomy → bridge analysis → 只读审计总结 → 设计 controlled AB → shadow 脚本实现 A/B/C/D → 统计 → debug HTML → summary → SHA 复核。
**在只读审计完成以前，不实现 B/C/D。**

## 3. 本目录文件计划（进度标记）

| 文件 | 内容 | 状态 |
|---|---|---|
| `00_scope_and_freeze.md` | 本文件：范围/冻结/SHA | DONE |
| `01_pipeline_audit.md` | 生产聚类调用链审计（文件/函数/行/输入/输出/membership） | DONE |
| `02_clustering_semantics.md` | connectivity 代码事实 + synthetic 证据 | DONE |
| `03_failure_taxonomy.md` | 失败分类法（真实帧归类） | DONE |
| `04_synthetic_cases.js` / `.log` | synthetic micro-cases A–F（+对照 G/H） | DONE（21/21 PASS） |
| `05_cluster_probe.js` / `.log` | 真实问题帧 cluster lineage + bridge 分析探针 | DONE |
| `06_cluster_stats.json` | per-cluster 统计（含 bridge 字段） | DONE |
| `07_bridge_analysis.json` | 桥接/articulation/removal-probe + oracle probe 汇总 | DONE |
| `08_ab_plan.md` | controlled AB 计划（A/B/C/D + 参数来源） | DONE |
| `09_ab_shadow_impl.js` | A/B/C/D shadow 实现 + A 复刻自检 | DONE（8/8） |
| `10_ab_synthetic_results.js` / `.json` / `.log` | synthetic A–H × 全 variant | DONE（10/10） |
| `11_ab_real_frame_results.js` / `.json` / `.log` | 全 165 帧 + 重点帧全部指标 | DONE |
| `12_ab_debug_data.json` / `12_ab_debug_gen.js` / `12_ab_debug.html` | 同帧 A/B/C/D* 并排 debug（component/标记/A 对照着色、person 框、拆分/合并事件） | DONE |
| `13_ab_summary.md` | 最终回答（Q1–Q7）+ `NO_CHANGE` | DONE |
| `13_sha_recheck.js` / `13_sha_recheck.log` | 收尾 SHA 复核 + EOL 事件取证 | DONE |
| `README.md` | 索引与复现 | DONE |

> 第一阶段只读审计收尾复核：`human_pipe_lib.js` SHA256 = `5bce92a4…142b4`（与开始一致）。
> 第二阶段收尾：**raw sha256 = `f580778c…`（FAIL）**；CRLF↔LF 归一后 = `5bce92a4…142b4`（内容等价 PASS）——
> `pc_apps/human_replay/` 11 个文件在 `2026-10-06T21:15:11` 被**外部进程**批量改写为 CRLF（非本会话），
> AB 计算读取的是 phase-1 LF 内容（`11_ab_real_frame_results.json` run 时记录）。详见 `13_sha_recheck.log`。
> 本会话未回改 EOL、未修改任何 production 文件。

## 4. 复现

```bash
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/04_synthetic_cases.js
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/05_cluster_probe.js
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/09_clustering_ab.js
```

环境：Windows + Node v24.14.0（无三方依赖；`human_replay_lib.js` / `human_pipe_lib.js` 直接从 `pc_apps/human_replay/` require）。
