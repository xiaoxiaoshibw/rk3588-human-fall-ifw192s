# 06 · R3.5 Step-0 总结（Residual Attribution Tool 交付）

- 日期：2026-10-06；writer：OpenCode（DeepSeek v4.1 Flash）；ponytail full（复用生产纯函数 + 既有 shadow 代码，零新依赖）。
- 状态：**Step 0（归因工具 + 归因结果）完成并全检 PASS**；B/C/D/E 全部未实现；production 零改动；无 commit/采集/部署。
- 前置文件：`00_provenance.md`（SHA/冻结）、`01_baseline_equivalence.md`（G0/守恒/确定性，全 PASS）、`05_frame_analysis.md`（GQ1–GQ6 与逐帧）。

## 1. 一句话结论

在固定 ICP 条件下的逐点归因显示：**测试集内静态残漏的主账在"背景层覆盖/配准"（registration 与 reference-absorb 合计约 50–98%），纯 matcher geometry 只占 1.7%（WD01）/5.5%（WD02）；同时发现站点窗口的"静态残块"其实是与受试者同步出现/消失的可移动状态，且参考图复制了同一状态——f10/f30 的"纯静态"前提需要用户复核。**

## 2. 核心数字（点级 share；详见 05 §1/§3）

| 组 | Registration | Ref absorb | Ref missing | Sparse | Matcher geometry |
|---|---:|---:|---:|---:|---:|
| WD01（静态金标物） | 14.5% | 83.5% | 0.3% | 0.01% | 1.7% |
| WD02（远场静态 proxy） | **60.8%** | 31.9% | 0.7% | 1.1% | 5.5% |
| 站点窗口 f10/f30 | 4.6% | **89.2%** | 0% | 0% | 6.2% |
| NEAR_FURN（f55/150/155/160 窗口） | 9.3% | 21.7% | 25.7% | 0.3% | 42.9% |
| ALL（165 帧） | 18.2%（voxel 42.8%） | 29.4% | 36.8%（≈人体，应然） | 4.6% | 11.0% |

关键复现：WD01 icp 命中 98.0–99.3%（none 84–86%）；WD02 icp 92.7%（none 34.2%）；clean 人体窗口吸收 0–1 点/帧；f155/f160 人体高带（z≥1.2）保留 94.9% / 91.6%；f55 99.8%。

## 3. 新发现（需用户复核，未擅自改分类）

**站点窗口（1.45,0.85）0.8–1.3 m 残块 = 受试者到站/离站同步的可移动状态（椅/装置/本体不可逐点区分），且 reference 含同一状态**：
- 时序列：f0–33 ≈1160 → f55–62 崩落 → f65–142 ≈250（裸站点）→ f154–164 ≈1400–1620；
- 裸站点佐证：f10 块 961/1204 点在 {63,80,92,123} 无对应（同帧桌体低带 3750/4230 有对应）；
- 跨会话：f10 块 ↔ REF 块 NN p50 = 0.026 m；REF 块 50 体素、mean occ 0.94；f10 块点 99.4%（icp）可被 ref 吸收。
- 影响：f10/f30 不能计为"静态修复成功"；正式空场录制需保证站点无人/无物移动；fusion 类方案需带可移动性防护。

## 4. GQ 速览（详见 05 §3）

- **GQ1**：registration = WD01 14.5%、WD02 **60.8%**、ALL 18.2%（voxel 42.8%）；tls-direct 单独无效（WD02 tls< none）。
- **GQ2**：参考覆盖对已知静态基本不缺（WD01 0.3%/WD02 0.7% missing；sparse ≤1.1%）；ALL 的 36.8% missing 主要是人体（应然）。站点块在线漏建是 M1/在场型（occ1<0.65 占 531/534），M2 稀疏门仅 2 点。
- **GQ3**：纯 matcher geometry 1.7%（WD01）/5.5%（WD02）；其中 ~60–75% 是 `Z_MATCH_XY_FAIL`（平面漂移、高度贴合）——与 registration/sampling 残余同源，无独立大头。
- **GQ4**：f155/f160 未命中带 60.5%/83.4% 落在 [0.12,0.24)（shell 成立），但主体是非静态/人体（657–788 点/帧），吸收 shell ≈ 吃人体边界 → 不得据此实现 AABB。
- **GQ5**：f10/f30 "错误在背景层形成，非 matcher" 成立；但主语是"reference 复制了可移动状态"，不是"纯静态泄漏"。
- **GQ6**：f55 人体高带吸收 0.16%（现状安全）；混合带（0.3–1.2）已吸收 52.8%（下半身+块，逐点不可分）；"吸收更多"≠改善。

## 5. K1–K6 判定

| 假设 | 判定 | 依据 |
|---|---|---|
| K1 registration=主因（WD01 族+低层结构） | **SUPPORTED（WD01/WD02）；对 f55 族低层结构的扩展 REJECTED** | WD02 60.8%、WD01 14.5%；站点家族 registration 仅 4.6–9.3%，主因是覆盖/人体 |
| K2 在线漏建解释 f10/f30（M1+M2/D 层） | **SUPPORTED（背景层形成）with 修正**：机制是 M1/在场型（≠M2）；且簇=站点可移动状态 | 在线视角 TIER_REJECT 553/547（occ1<0.65 占 531/534）；ref 吸收 99.4%（含污染） |
| K3 f55 族=真人+贴邻（静态部分 online-miss+registration） | **SUPPORTED（合并与贴邻）with 改写**：残块主体=非静态/人体壳层；真静态 in-window 仅 52 点 | shell 788/877 非静态；人高带吸收 0.2%；混合带 53% |
| K4 f155/f160=结构边界 shell；ICP 应压到 ~0 | **PARTIALLY CONFIRMED（几何壳层存在）；REJECTED（≠静态边界；非 ICP 可消）** | shell 60.5%/83.4% 但 85–91% 非静态；icp 吸收增量有限且吃人体 |
| K5 WD02 远场（覆盖缺口+半径 → ICP+AABB 后消解） | **SUPPORTED（ICP 消解 92.7%）with 重估**：覆盖缺口份额小（missing 0.7%+sparse 1.1%）；AABB 部分 NOT_RUN（本轮禁止） | none 34.2% → icp 92.7%；geometry 5.5% |
| K6 retention 余量薄（放宽需近家具单独计量） | **PARTIALLY SUPPORTED**：clean 窗口 0–1 点吸收（余量满）；但近家具高带已 5.0–8.4% 吸收，混合带 53–67% | f160 高带 8.4%；f155 5.0%；f55 0.16%；clean 全 0 |

## 6. 下一步建议（**仅建议，本轮不实现**；按实测份额排序）

1. **registration / 共享坐标系**（最大静态份额：WD02 60.8%、WD01 14.5%）：下一实验应优先做"固定配准臂下的完整管线评估"（R3.2 已备选的 scene-transform 方案一类），目标是把"配准恢复"转成可判定的生产候选；**不要**用扩大半径/邻域掩盖配准残差。实现需用户另行授权。
2. **reference 质量防护**（新证据驱动）：正式 20–60 s 空场录制（BLOCKED，待授权）时保证站点无移动；并设计 shadow-only 的"时间一致性/可移动性"防护实验，防止参考图复制会话特定状态（f10/f30 案例）。
3. **matcher geometry**：**不建议作为优先项**（1.7–5.5%），且 f155/f160 的 shell 主体是人体——任何 AABB/半径类扩张在 absence of 逐点 GT 前不得进入实验（工单 §12 维持）。
4. 维持：不动 0.65/0.85、不动 connectivity（CL-01 `NO_CHANGE`）、不动 R2.6b/leveling/Tracker/UI；`POST_FILTER_ERROR` 走独立工单。

## 7. 边界与未做

- 未实现 B/C/D/E；未改任何 production 文件（原料 mtime 未变）；未 commit/采集/部署/联网；未覆盖任何旧 evidence。
- proxy ≠ GT；ICP 仅为固定实验条件（解非唯一已登记）；参考图仍为 10.5 s 候选；结论限 PC/Node 离线口径。
- 站点混淆与 f10/f30 分类 = **待用户裁决**；本轮已按工单要求只测量、不重分类、不晋级。

## 8. 产物清单

`00_provenance.md` / `01_baseline_equivalence.md` / `02_attribution_results.json`（digest `4b89a044…`）/ `03_attribution_points.csv` / `04_attribution_voxels.csv` / `05_frame_analysis.md` / 本文件 / `10_r35_attribution.js` / `11_tool_run.log` / `12_run1_stdout.log` / `13_run2_stdout.log`。
**Production modified? NO。**
