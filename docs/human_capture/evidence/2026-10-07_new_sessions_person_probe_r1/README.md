# 2026-10-07 新四段会话 · 现行管线人体对照 probe（r1，诊断）

- **授权**：用户本轮「ok开始」（回应上一轮建议：「用现行管线圈出这四段的人/物粘连与资格判定逐帧对照（授权后、新 evidence 轮）」）。四段会话的离线配平由上一轮「别忘记配平」直接授权完成。
- **范围**：只诊断。复刻 R39 closeout 的 **P（生产在线路径）口径**：leveled → denoise → `build_static_map`（全帧）→ 逐帧 `pipeline_frame`。未跑 S/registration/参考图；未改任何生产代码；W03 记录与状态不变；W04–W09/采集/部署未启动。
- **输入**：`captures/remote/` 四段原始会话 + 各自 leveled job（SHA 见 `00_manifest.json`）：
  - 215540 → job `21666bec7e7b44b2bdbbaa790bf4501b`（recommended=tls）
  - 215607 → job `2ed2cf6a4d2342ebb87f4e7fa68fdf3c`（**非 recommended**：TLS−RANSAC d 差 3.69cm>3cm 一致性门；诊断只用其有效 tls 数据，`authoritative=false`）
  - 215623 → job `a9e1e01fa6644f93aa686daa330a5fcd`（recommended=tls）
  - 215643 → job `e46d035de1b34378b841ca3bc2a1c8f6`（recommended=tls）
- **人体参考区域**：固定圆柱 center=(2.10,−0.57)/(2.13,−0.50)/(2.14,−0.45)/(2.11,−0.36)，r=0.55m，z∈[0.05,2.30]（来自前置 leveled 定位；**非逐点 GT**）。
- **方法/工具**：`probe.js`（P 链 + `audit_lib.ownership` 点级归属 + 逐帧统计，输出独占创建）；`diagnose_absorption.js`（吸收机制定位）；`audit_lib.js` = R39 轮副本（SHA 相同）。生产代码 SHA 记录于 `00_manifest.json`（`human_pipe_lib.js` / `registration.js` / `audit_lib.js`）。
- **ponytail**：实读（opencode skill，base `C:\Users\30680\.config\opencode\skills\ponytail`，full）。执行：复用 R39 P 口径与 audit_lib（不复制生产代码）、固定圆柱代替逐点 GT、单脚本 + 一次机制诊断，未引入新依赖。

## 结果

四段均为「同一人、同位置、全程站立/举手 5.7–6.8s」（举手：215607/215623）。逐帧人体点去向（点/帧）：

| 会话 | 原始（圆柱内） | 前景（p50，min–max） | 成簇（p50） | 标签分布（帧） | track | confirmed | merge |
|---|---|---|---|---|---|---|---|
| 215540 | ~1.83k | 43（32–57） | 42 | HUMAN_CANDIDATE 9 / NON_HUMAN 51 / 无簇 4 | 1（f0–63） | 无 | 0 |
| 215607 | ~1.90k | 36（30–44） | 0（0–30） | HUMAN_CANDIDATE 16 / NON_HUMAN 11 / 无簇 40 | 1/7/13 | 无 | 0 |
| 215623 | ~1.93k | 32（25–39） | 0（0–39） | 无簇 55 / NON_HUMAN 9 / HUMAN_CANDIDATE 2 | 5/7/13 | 无 | 0 |
| 215643 | ~1.23k | 23（14–36） | 0（0–26） | 无簇 55 / NON_HUMAN 1 | 3（f4） | 无 | 0 |

删除机制总计（person 点）：**STATIC 自匹配 ≈95%（66k–122k 点）、加 GROUND/CLEANUP 后总删除 ≈97–98%**；GROUND 1.7k–3.0k（脚下 z<0.10 按设计剔除）、CLEANUP 45–102。

吸收机制定位（`diagnose_absorption.log`，f0）：

- online 静态图中位于人体中心 r<0.5 的体素 **91/94 个**（strong 81/91）——**人体自身被自我建模进静态图**；
- 人体点 → 静态体素匹配距离 p50≈8.6cm（上限 12cm），|dx|/|dy|/|dz| 中位 ≈3–4cm——匹配到的正是人体自己的体素。

## 结论

1. **「静立吞人」边界定量复现**（`human_pipe_lib.js` 头注自述：静立 ≥85% 帧的人会被吞进背景；非新 bug）：全程静立的人 ~97–98% 被离线全帧静态图删除（其中 ≈95% 是静态自匹配），前景仅剩 14–57 点/帧。残片去向：215623/215643 多数帧凑不足 60 点门、完全无簇；215540/215607 的残片多数能成簇但被判 NON_HUMAN（少数帧 HUMAN_CANDIDATE）。
2. **资格判定"轮不到"**：没有任何 track 达到 3/5 确认（confirmed 全空）。几何门在残片上没有出错——“看不到人”发生在更上游。
3. **人/物粘连未出现**（merge=0）——因为人根本没有以完整簇存活；粘连风险需在"运动的人 / 已确认的人"数据上另测。
4. 对应外部研究 N1（背景可见性/ever-free）与 W04「身份保持」议题：若目标是"静立的人也要保留"，需要新的设计（保护规则/N1），不是调聚类或资格门能解决的。

## 局限

- 离线"全帧建图"口径；与生产滚动建图的差异未测。
- 固定圆柱代替逐点 GT；行为仅 4×6s 站立/举手，无低姿态。
- 215607 配平非 recommended（诊断可用，不能进正式链路门槛）。

## 产出

`probe.js` / `diagnose_absorption.js` / `audit_lib.js`（R39 副本）/ `probe_cap_20261007_*.json`×4 / `00_manifest.json` / `probe.run.log` / `diagnose_absorption.log`。

## Arm C（静止模板保留率阶梯，2026-10-07 晚新增）

用户直派「静止模板」：空场会话 `cap_20261007_233658`（5.5s/54 帧；配平 job `3c793d7bda0f4ced86b20ac8076e7b0e`，recommended=tls）作为参考模板。

- 配准：3/4 产出（`captures/registration/<src>__to__cap_20261007_233658`；WARN=SPARSE_CORRESPONDENCE → DEGRADED；fit p50 1.0–1.2cm、holdout p50 0.67–0.72cm、inlier 0.46）。**215607 因配平 conflict（非 recommended）被 LEVELING_SHA_MISMATCH 拒绝**，跳过（符合口径）。
- 链（离线，S 链形态）：registered cloud → 参考图匹配 → 在线图匹配 → cleanup/聚类/判定/跟踪。
- 结果（人体点/帧中位）：

| 会话 | 原始 | 参考层存活 | 参考+在线 | 成簇 | 标签（帧） | confirmed |
|---|---|---|---|---|---|---|
| 215540 | 1851 | **1803（97.4%）** | 39（2.1%） | 0 | NONE 43 / NON_HUMAN 13 / 候选 8 | 0 |
| 215623 | 1921 | **1883（98.0%）** | 24（1.2%） | 0 | NONE 66 | 0 |
| 215643 | 1234 | **1205（97.6%）** | 23（1.9%） | 0 | NONE 56 | 0 |

- 空场自身 P 复验（`empty_scene_check.json`）：66 簇全 NON_HUMAN、max 985 点、0 confirmed。
- **结论**：空场模板能保留静立人（97–98%）；当前"参考 ∪ 在线"并集语义下在线自建模仍把人生吞（1.2–2.1%）。缺的一环是融合优先级（`REFERENCE_STATIC > ONLINE_PERSISTENCE`），属 `STILL_PERSON_RETENTION_PLAN.md` 阶段 1（需另行授权）。
- 首跑缺陷记录：圆心向参考系变换漏 z 维 → 圆柱退化；产物隔离于 `failed_runs/`，最终跑见 `retention_ref.run.log`（修复后重跑）。
- 新增文件：`retention_ref_probe.js`、`registration.run.log`、`retention_ref.run.log`、`empty_scene_check.json`、`retention_ref_*.json`（3 份 + 215607 的不适用记录）。

## 效果页（retention_view.html）

- 文件：`retention_view.html` + `retention_view.js`（Three.js/OrbitControls，复用 `pc_apps/human_replay/vendor/`）+ 数据 `view_data_cap_20261007_*.js`×3、`view_refvox.js`（生成器 `make_retention_view.js`）。
- 内容：3 会话 × 8 帧，裁剪区（人位 ±1.9m）逐点**命运着色**，四种模式：原始（含人）/ ① 空场模板层（人被保留、家具变暗）/ ② 参考+在线（现状，人被在线层删除=红）/ ③ 在线误删高亮（绿=保留，红=被在线删）；另可叠加显示空场模板体素（绿点，3743 个）。
- 坐标=对齐到空场会话（233658）的配平系；计数为显示点（未抽稀，每帧 ~26k）。
- 自检：viewer 数据与保留率口径逐类一致（215540 f0：人区 1825=raw；模板删 1=REFERENCE；在线删 1731=ONLINE；cleanup 3；保留 43）。
- 打开：双击 `retention_view.html`（file:// 相对脚本可加载）或本地 http 服务（如 `python -m http.server` 于仓库根）。

## 结构证据探针（人体语义分类层草案依据）

- `structure_probe.py` / `structure_probe.log`：沿身体轴的 10cm 带剖面 + 头/颈/躯干/腿/上肢特征，对象 = 人（站 215540 / 举臂 215607）、WD01（223757 的 1.74m 家具）、箱子堆。
- 结论：单特征不可分（颈/头比值会被肩带污染），组合特征可分——剖面 cv（人 0.10–0.11 vs WD01 0.02）、腿柱细度（0.07 vs 0.15）、顶紧凑度（0.07 vs 0.26）、举臂偏置（0.39 vs 0.19）。
- 设计：见 [HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md](../../HUMAN_SEMANTIC_CLASSIFICATION_DRAFT.md)（三值输出 + 结构标志 + 组合规则 + UNKNOWN 纪律）。

未 commit / 未 push；生产文件与既有证据未改动（配平/配准产物为工具设计输出）。
