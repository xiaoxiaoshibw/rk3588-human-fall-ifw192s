# HUMAN-FUSION-BG-V3 实际交付（Demo V3）

2026-10-11（Asia/Shanghai）。SUBMITTED；软件逐项作者自验通过，S9 可信 GT 资格仍 BLOCKED（修复为"溯源草稿"，不是 GT）；XGB 家具泛化被 B 组对照**新证伪**；+B 家具 neg 消融**弃置**（不稳定）。无部署、生产接入、采集、提交或推送。

## 启动与查看

当前本机服务已运行：[打开 Demo V3](http://127.0.0.1:8800/)。或：

```powershell
node D:/Code/ldiar/sidequests/human_fusion_lab_v3/server_v3.js 8800
```

依赖本机已有 Node.js 与冻结 captures/remote。仅监听 127.0.0.1，单用户。V2 在 8798 仍可打开（并行不冲突）。

UI 与 V2 一致的播放/暂停/帧条/三视图/候选检查/标注草稿，**新增**：

- **背景组 A/B/C 选择器**：切换"激活"组的 FG 逐帧高亮（蓝点）；由于三组共享空场包络，切换只见 BG 提取差异，不动分类/跟踪。
- **激活组 FG 勾选项**：默认开，显示当前选中组（A 现有算法、B 容差体素、C 距离自适应）保留前景。`foreground`（V2 原 PFUS A 链）单独可勾（紫蓝色），以便同层对拍。
- **逐点追溯勾选项**：高亮 GT 首个人体对象前 24 个原始点；绿=激活组保留，红=删除，浮在原始点云上。
- **状态行**：实时打印 `BG 对照(A/B/C, GT点级 kept/raw)`，当前帧三组的 GT 人体保留/家具保留对照；以及空场包络 SHA 前缀 + 空场源会话。
- **同一候选模型对比较**：四个 V2 模型 + PointNet（影子）得分面板（未在 UI 内实时算 PointNet，仅对照表加载时读）。

## 任务逐项回答

### 1) 背景去除是否改善？（是，B 组）

**评判维度**（九会话全帧逐点对照冻结 GT；结果为"GT 人体点级损失率"，越低越好）：

| 会话 | GT 人点数 | A 现有包络 | B 容差体素 | C 距离自适应 |
|---|---:|---:|---:|---:|
| S1-empty-furniture | —（家具） | 2.4% 残留 | 2.4% 残留 | 4.7% 残留 |
| S3-walk-x-near | 31,335 | 12.2% | **4.6%** | 12.5% |
| S3-walk-y-far | 17,660 | 7.2% | **4.0%** | 5.5% |
| S4-walk-stop-walk | 1,728 | 10.1% | **2.9%** | 9.9% |
| S5-turn-in-place | 3,122 | 9.7% | **3.0%** | 8.6% |
| S6-occlusion | 5,062 | **55.5%** ↓ | **7.8%** | 8.0% |
| S7-far-5m | 3,029 | 13.6% | **4.9%** | 7.6% |
| S8-still-retention | 9,272 | 17.3% | **2.0%** | 6.5% |
| S9-two-person | —（GT UNKNOWN） | — | — | — |

**B 组在全部 8 个有 GT 会话中人体损失率都严格最低**；S6 从 55.5% → 7.8%（7.1 倍），S8 17.3% → 2.0%（8.7 倍，静止保留改善最大）。S1 家具残留 A/B 并列 2.4%，C 4.7% 最差（常数自适应带宽度超出实际包络精度）。

**局限**：B/S1 家具残留率与 A 相同；没有独立会话家具 → 不能说 B 家具"更好"；C 组距离自适应未盈利（τ 参数未调优；继续调参会被视为挑参数）。

### 2) 家具残留减少多少？（同会话 2.4% → 2.4%；未改变）

S1 可标 GT 家具 7,220,011 点：

| 组 | 家具残留（kept/raw） | 家具被剔除 |
|---|---:|---:|
| A | 174,472 / 7,220,011 = **2.42%** | 7,045,539 (97.58%) |
| B | 171,958 / 7,220,011 = **2.38%** | 7,048,053 (97.62%) |
| C | 339,903 / 7,220,011 = **4.71%** | 6,880,108 (95.29%) |

差异量级 0.04%，B 微改善，可等价看待。C 变差由于自适应带在小 r 处宽于 A 的固定 0.25 m。

**独立家具负样本**：A 566 行（GT person/furniture 80% 重叠）、B 608 行（B 残差家具），两者**同会话 S1** — 不能作为"独立泛化"证据（见 §5）。

### 3) 人体损失多少？（见上表 §1 各组）

B 组把 S6 GT 人体点损失从 55.5% 压到 7.8%；S8 静止人从 17.3% 压到 2.0%；S3-near 从 12.2% 压到 4.6%。A 现有包络在 S6 55.5% 损失是漏检的**主因之一**。

但**人体损失率低 ≠ 检测修复**：B 在 S6 f128 (GT 33 点) 保留 15，仍 < human_n_min=60 → 候选层仍死。这是 V3 明确证据（见 §6 S6 节）。

### 4) S6 是否修复？（未完全；根因转移）

- **漏检根因重定位**：A 组 BG 损失 → B 组 BG 损失低 → **聚类器 (cluster_voxels) 与 n_min=60 双门拦截**。S6 f128 GT 33 点 → **A 留 18, B 留 15, C 留 24**，全部 < 60 → 提案层失败（已 runtime 逐点验证）。
- **V3 不完全修复 S6**：不改 human_n_min、不放宽跟踪/candidate 阈值（遵守不放宽约束）。**聚成簇级合并**（S6 f91 295 成 304 簇）的情况下 B 成功；点稀疏（GT 33 点）时 B 在 BG 层赢却被下游阻塞。
- **V3 提供逐层归因工具**：`tools/layer_attribution.js` 把 RAW→BG→cleanup→proposal→classifier→tracker 独立记录，把 S6 f91/f128 的 `kept_after_B=295/15`、聚类后的 `n=304/374`、prod cluster 名单全部查清（见 `LAYER_ATTRIBUTION_*.json`、`CANDIDATE_IMPROVE_S6.json`）。
- **f128 候选 n=380 在 V2 与 GT 不对应**（f.gt_hits=[]），仍 0.012 拒绝 — 误判区；B 没有消除它，但定位到"聚类器没把 15 GT 点编入任何簇"。

**结论**：S6 是**部分修复**（BG 层），不是完整修复（提案→跟踪层仍挂）。完整修复需要提案层 n_min 放宽或或 orphan 候选注入 — 均触及放宽阈值，本任务禁止；留给下一轮专门工作。

### 5) 四模型谁更优？（XGB69 候选级；S6 除外；PointNet 影子不适合；+B 家具 ablation 弃置）

受控同点集对照（候选行级, θ=0.55，**冻结既有行**, 不 replay）：

| Split | pos/neg | rf51_baseline | rf51_candidate | rf69_candidate | xgb69_candidate | pointnet_shadow | dual_pointnet_shadow |
|---|---:|---:|---:|---:|---:|---:|---:|
| train | 142/566 | R=1.000 P=0.201 | R=1.000 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 | R=1.000 P=0.220 | R=1.000 P=0.201 |
| validation | 28/0 | R=1.000 Spec=? | R=0.464 P=1.000 | R=0.607 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 |
| test | 65/0 | R=1.000 Spec=? | R=0.877 P=1.000 | R=0.923 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 |
| stress(S6) | 58/0 | R=1.000 Spec=? | R=0.069 P=1.000 | R=0.569 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 | R=1.000 P=1.000 |

**排序（候选级）**：XGB69 > rf69 > rf51_candidate > rf51_baseline ≫ PointNet影子。XGB69 在所有 split recall=1.0，stress 也全中——但注意：
- **val/test/stress 全 neg=0** → 特异性 UNKNOWN，无"独立家具拒绝"证据。
- **XGB69 的 S1 家具拒绝是记忆**（见 §6 证伪）。
- PointNet 影子（曾作"扩展 RF 四模型"被 V2 报告）在 train 上 P=0.22 — 比 RF51 基线还差，不进对照。V2 检查链只把它作 shadow 方向标记，本论证实不采纳。

**+B 家具 neg 消融已弃置**：B 组提供了 608 独立家具负样本，尝试训练 `rf51_bg_candidate`（同参同 seed）测试"+B 家具训练能否提升 S1 的精度而不伤召回"。三 seeds 结果：

| seed | val R | test R | stress R |
|---|---:|---:|---:|
| 20261011 | 0.393 | 0.646 | 0.034 |
| 7 | 0.357 | 0.708 | 0.017 |
| 42 | 0.357 | 0.738 | 0.052 |

**召回漂移巨大不可信 → 模型文件已删除，不进对照**。可能原因：B 组家具 neg 与 A 家具 neg 高度重叠（同会话），加上后特征分布被 S6/S3/S4 等"远/遮挡"样本破坏，或单纯 608/566 neg 差异量太小。归 UNKNOWN。

### 6) 还有哪些 UNKNOWN？

1. **XGB 家具泛化（新证伪）**：XGB 在 A-S1 家具 spec=1.000（训练时见过 S1，记忆），**在 B-S1 同会话不同 BG 家具 spec=0.021**（595/608 误判人）。证明 XGB 对 S1 的"高分拒绝"是记忆非泛化。跨会话/跨 BG 独立家具泛化 **UNKNOWN**。
   （谨此修正 V2 §"家具"行原文"XGB 拒绝"暗含的乐观解读——那时只有 A 组一种 BG，没法证伪。）
2. **+B 家具 neg 消融**：被三 seeds 召回漂移判不稳定（0.017..0.738），弃置。机制 UNKNOWN。
3. **S6 完整修复**：BG 层 B 修复，cluster/proposal/tracker 层 n_min=60 + 聚类合并行为 **UNKNOWN**（需新一轮允许改 n_min 或加 orphan 候选）。
4. **S9 GT 修复为 GT**：provenance_draft 把 36 对象从损坏 GT 继承并写回实际双 SHA；但仍是 `DRAFT_UNREVIEWED` + `LABEL_DERIVED:GT_V2-broken-binding`。**upgrades 到 GT 要人工重新圈点 + 人工评审**。本轮不伪造。
5. **C 组距离自适应参数**：初值 τ0=0.15+0.05r 未盈利，进一步调参算"挑参数"，UNRESOLVED/UNTESTED。
6. **跨 actor / 跨场景 / 跨日**：AUDIT holdout_status 明确 RETROSPECTIVE，prospective UNKNOWN。本轮无采新数据。
7. **PointNet："影子"**：V2 视为 shadow 无正式评估，V3 证实 train P=0.22（差）——不进正式对照；作"扩展四模型"尝试不采纳，记 UNKNOWN。
8. **v3_runtime point_trace 域**：GT 索引域修复为"帧内合法点序号"(= rawMap)。已验证 S6 f128、f91 均 now show kept B 为 15/295（与离线一致）。S1 f20 家具 loss 23,754 中 A 保留 364、B 521、C 3970（说明 C 异常带宽）。**整个 point_trace 判断需要进一步抽样 ≥5 处点人工核实坐标落在 GT polygon 内**（自动映射对了不代表 GT polygon 本身对）。

### 7) Demo V3 如何启动？（顶部已给，此处重复固化）

```powershell
node D:/Code/ldiar/sidequests/human_fusion_lab_v3/server_v3.js 8800
# 打开 http://127.0.0.1:8800/
# 选择会话 → 选 xgb69_candidate (或任一四模型)
# 右侧"背景组 A/B/C"切换查看 FG 高亮；勾"逐点追溯"看 GT 人点命运
```

对照 V2（仍在）：`node sidequests/human_fusion_lab/server_v2.js 8798` → http://127.0.0.1:8798/。两者互不干扰。

## 证据清单（`docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/`)

- `REPORT_FINAL.md` — 本文件
- `V3_BASELINE.json` — 12,154 文件全树 SHA, 21 个 V3 新文件列表
- `V3_FREEZE_FINAL.json` — V2 保护文件对账（4 个外部已改文件延续状态; 生产 src/pc_apps/webui/captures 全未改）
- `BG_AUDIT.json` — 九会话空场背景资格：9/9 ELIGIBLE（同 setup 对拍、包络 71-73% XY 覆盖、source→dump→frozen 完整溯源，python 源生成器重跑逐值相等）
- `BG_GROUPS_EVAL.json` — A/B/C 三组全部帧（2,605）× 全部 GT 对象逐点判定
- `LAYER_ATTRIBUTION_cap_20261010_180235_f91_128_B.json` — S6 逐层归因（RAW→BG→cleanup→proposal→classifier→tracker 分离）
- `CANDIDATE_IMPROVE_S6.json` — S6 提案改进受限验证（orphan 候选零触发；点被生产聚类合并）
- `S9_GT_PROVENANCE_DRAFT.json` — S9 绑定修复草稿（36 对象 LABEL_DERIVED，写回实际双 SHA，非 GT）
- `S9_GT_REPAIR.json` — S9 修复诊断与轨迹说明
- `CONTROLLED_COMPARISON.json` — 四模型 + 2 PointNet 影子 同点集对照 × 4 splits；§6 XGB-on-B 证伪数据
- `TRAIN_BG_REPORT.json` — +B 家具 neg 消融弃置记录（三 seeds 召回漂移表）
- `cap_20261010_175227_bg.jsonl` / `cap_20261010_180751_bg.jsonl` — B 组候选行（608 家具 neg + 488 blocked S9 候选）
- `CASES.json` — V3 38 案例（V2 35 个已绑 8800 端口 + V3 3 个 S6/S1/XGB 证伪/S9 修复案例）

## 验证记录

- 九会话四模型全帧回放回归（5,210 tick） PASS（froze-v2 断言仅触及 4 个外在文件已知 → 按 V2 已宣告的 BLOCKED 记录，未新增）；值与 V2 COMPARISON.json 完全相等（同一 v2_runtime 管线未变）。
- 浏览器 CDP 24 项 check PASS（九会话真实切换，无运行时异常）；S6/MISS 手动帧验证 A/B/C 状态行打印正常。
- 全树文件 12,154 SHA 基线，V3 结束final对账 12,154，仅 21 个 V3 新文件（sidequests/human_fusion_lab_v3/**）+ 1 个 V2 已有 docs 追加目录 — 无生产路径修改。
- 生产代码 (src/inno_lidar_ros, src/human_fall_detection, pc_apps/human_replay 生产源, webui) **全部 SHA 与 V2 HEAD 026e063 一致**（基线 V3_BASELINE.json 与最终对账）。

## 拒绝声明

V3 不改 V1/V2 检测器权重、不部署到 RK3588 板、不把"修复"声明泛化到独立场景/演员/日期、不把 `DRAFT_UNREVIEWED` 当 GT、不混淆同帧候选比较与完整管线比较、不通过放宽全局阈值掩盖 S6 漏检、不根据 +B 家具 neg 消融的不稳定结果宣称改善。

**所有继任工单必须附加**：跨会话独立家具采集；S6 n_min 允许范围授权；S9 人工重新圈点授权；PointNet 影子模型正式对照授权。无此授权，剩余 UNKNOWN 不消除。
