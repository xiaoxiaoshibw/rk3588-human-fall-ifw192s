# 2026-10-06_hrw03_cl01 · Foreground Clustering Failure Audit + Controlled Connectivity AB（READ-ONLY）

- 工单：R3.4 / CL-01 —— 把“聚类错误”从 background matcher / registration 中独立拆出来；
  **阶段 1** 只读审计（synthetic micro-cases → 真实帧 lineage → failure taxonomy → bridge analysis）；
  **阶段 2** controlled clustering AB（A/B/C/D，shadow，不改 production）。
- writer：OpenCode（DeepSeek v4.1 Flash）；ponytail 已加载（full，`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 生产零改动（本会话全程未写 production）；收尾 raw SHA 出现外部 CRLF 批量改写事件（内容归一 = `5bce92a4…142b4`），见 §收尾 SHA 事件。
- **未采集、未部署、未 commit。**

## 一句话结论

**阶段 1（只读审计）**：当前 production clustering = **XY 0.15m 柱 + 4 邻 BFS、Z 完全不参与连边**（无 radius/形态学/合并/后处理）。
对象级主要失败是 `MERGE_STATIC`（**宽接触**型，不是单点桥），由“在线背景漏删的静态残留 + XY 邻接”共同造成；
f10/f30 的疑似“人+物合并”实为**纯静态残留簇**（无站立人体点，需修正旧口径），f55 才是真人+静态合并；
系统级另有 >4000 个小碎片（`STATIC_FRAGMENT`）与显示层 `POST_FILTER_ERROR`（干净人体被证据层判 NON_HUMAN）。

**阶段 2（connectivity shadow AB，A/B/C/D，165 帧）**：XY4 不是对象级 merge 的主要放大因素——放宽到 XY8 显著恶化
（+353 事件/+69481 点 merge），收紧到 XYZ26 会同时过拆与过连，constrained-3D（D*=G0.30）无新 merge、保住干净人体
（retention ≥0.998）并部分拆开 f150 的低层结构块（−633 点），但 f55/f155/f160 关键 merge 不变、碎片 +42%。
**最终标签：`NO_CHANGE`**（详细见 `13_ab_summary.md`；SHA 事件见 §收尾）。

## 收尾 SHA 事件（重要）

本目录收尾复核：raw `human_pipe_lib.js` = `f580778c…`（字节级 FAIL）；
**CRLF↔LF 归一后 = `5bce92a4…142b4`（内容等价 PASS）**。原因是 `pc_apps/human_replay/` **11 个文件被外部进程在
`2026-10-06T21:15:11` 批量改写为 CRLF**（+1 byte/行，非本会话所为；AB 计算读取的是 phase-1 LF 内容，
`11_ab_real_frame_results.json` run 时记录在案）。取证：`13_sha_recheck.log`。本会话未修改任何 production 文件。

## 文件

| 文件 | 内容 |
|---|---|
| `00_scope_and_freeze.md` | 范围/冻结/SHA/进度 |
| `01_pipeline_audit.md` | 调用链审计（file:line、membership 变更点、四套体素域、诊断缺陷） |
| `02_clustering_semantics.md` | connectivity 事实（10 问）+ synthetic 证据表 |
| `03_failure_taxonomy.md` | 分类法 + 重点帧归类 + 桥接/聚合发现 |
| `04_synthetic_cases.js` / `.log` | Case A–H 合成审计（21/21 PASS） |
| `05_cluster_probe.js` / `.log` | 真实帧 lineage + bridge 探针 |
| `06_cluster_stats.json` | 逐簇统计（18 重点帧 + 165 帧聚合 + runtime） |
| `07_bridge_analysis.json` | cut vertex / removal probe / oracle probe |
| `08_ab_plan.md` | controlled AB 计划（先于实现） |
| `09_ab_shadow_impl.js` | A/B/C/D 实现 + A 复刻/等价自检（8/8 PASS） |
| `10_ab_synthetic_results.js` / `.json` / `.log` | synthetic A–H × 7 variants（10/10 PASS） |
| `11_ab_real_frame_results.js` / `.json` / `.log` | 165 帧聚合 + 21 重点帧 + 下游观察 |
| `12_ab_debug_data.json` / `12_ab_debug_gen.js` / `12_ab_debug.html` | 同帧 A/B/C/D* 并排交互 debug |
| `13_ab_summary.md` | 最终结论（Q1–Q7，`NO_CHANGE`） |
| `13_sha_recheck.js` / `.log` | 收尾 SHA 复核 + EOL 事件取证 |

## 复现

```bash
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/04_synthetic_cases.js     # 阶段 1
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/05_cluster_probe.js       # 阶段 1（06/07 JSON）
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/09_ab_shadow_impl.js      # 阶段 2 自检
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/10_ab_synthetic_results.js
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/11_ab_real_frame_results.js
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/12_ab_debug_gen.js
node docs/human_capture/evidence/2026-10-06_hrw03_cl01/13_sha_recheck.js
```

输入：`captures/remote/cap_20261002_223757`（current，leveled via `captures/leveled` 最新 tls job）、
`captures/remote/cap_20261004_203349`（reference）。环境：Windows + Node v24.14.0，零三方依赖。

## 边界提醒（给下一阶段）

- 本目录所有“静态/人体”字段都是 **proxy**（reference 匹配 / 已登记位置），不是逐点 GT；跨会话 registration 残差会压低远场 ref 匹配率。
- AB 必须固定：session/frame/registration/背景 matcher/半径/阈值/ROI/leveling/预处理/候选规则/显示规则；
  唯一主变量 = clustering connectivity。`cluster_neighbor_hops` 是死参数，不要误用。
- `cleanup_isolated_fg` 的拓扑保护与 `cluster_voxels` 共享 4 邻语义；任何 connectivity variant 都必须同步说明该交互。
