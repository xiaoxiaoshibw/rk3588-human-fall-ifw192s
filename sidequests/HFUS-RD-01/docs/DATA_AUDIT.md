# DATA_AUDIT — 九会话与 GT 审计（HFUS-RD-01 交付 2）

日期 2026-10-12 · 数据源：`captures/remote/<sid>/{meta.json,points.bin}` +
`pc_apps/human_replay/gt_store/<sid>/GT_V1.json` + D05 R04 冻结 ledger
(`docs/human_capture/evidence/2026-10-12_hfus_d05_r4/runs/fast/`，
SHA 见各 SUMMARY.sessions.input_sha256)。

## 1. 会话清单（九会话真实账，分子/分母为实测）

| sid (尾) | 名 | 帧 | 时长 s | 原始点数 | reviewed PERSON 对象 | GT 人点 | GT 人点占比 | rev_status |
|---|---|---:|---:|---:|---:|---:|---:|---|
| 175227 | S1-empty-with-furniture | 304 | 31.4 | 14,931,203 | 0 | 0 | 0% | reviewed |
| 175429 | S3-walk-x-near | 258 | 26.6 | 12,673,527 | 258 | 286,822 | 2.26% | reviewed |
| 175553 | S3-walk-y-far | 464 | 48.0 | 22,796,699 | 99 | 561,361 | 2.46% | reviewed |
| 175804 | S4-walk-stop-walk | 239 | 24.7 | 11,740,802 | 11 | 13,327 | 0.11% | reviewed |
| 175943 | S5-turn-in-place | 202 | 20.8 | 9,924,142 | 6 | 8,841 | 0.09% | reviewed |
| 180235 | S6-occlusion | 238 | 24.6 | 11,693,048 | 71 | 27,268 | 0.23% | reviewed |
| 180337 | S7-far-5m | 251 | 25.9 | 12,328,975 | 12 | 24,361 | 0.20% | reviewed |
| 180557 | S8-still-retention-long | 523 | 54.1 | 25,689,368 | 53 | 57,045 | 0.22% | reviewed |
| 180751 | S9-two-person-cross | 126 | 13.0 | 6,190,058 | 35 | 46,922 | 0.76% | reviewed |

**点云布局**：28B/点 `[x,y,z,i]f32 + ring u16 + ts f32 + pads`（见各
`meta.json.point_layout`）。坐标系：原始为传感系；leveled =
`R@xyz + T`，冻结于 D05 R04 `SUMMARY.reference.coordinate`
（= `render_person_label.R/T`，主对角姿态约 26.7° 俯仰/3.2° 翻滚）。

## 2. GT 三态与历史坑复验

- **索引域**：`raw_point_indices` 字段名误导——**leveled-compact 域**
  （`gt_lib.js` 核心不变量 1：finite && (x,y,z)≠(0,0,0) 过滤后稠密下标）。
  本轮用 `(x,y)` 残差法实证：直接当 raw 帧域读 median 残差 2.13m（伪），
  按 compact→raw 映射后 median 0.133m/p90 0.21m，z p5..p95=[0.13..1.48]
  与 GT `z_min/z_max` 对齐 → 确证为 compact。ledger `gt[].indices` 与
  `GT_V1.json` 解码逐字节相等。
- **Ledger 内域**:`candidate.raw_indices`、`stages.*_ids` = **raw 帧域**。
  跨域运算必须走 `common.gt_raw_indices()`。
- **S9 (180751)**：`GT_V1.session_sha256 = {}`（meta 键缺失），
  D02/D05 已登记 INVALID_BINDING。本轮**仅探索**，不进任何合格判定
  （`explore_only=True`）。复验：真实问题仍然存在。
- **S1 propagated 语义矛盾**：S1 会话 GT 全 reviewed，但历史 D02 记录
  `1818/1824 propagated` —— GT_V1 现在看到的 `object_count=258` 且全部
  `source=='human'`、`review_status=='reviewed'`，那个 propagated
  矛盾不在 `GT_V1.json` 中（在更早历史 draft 层）。本轮把 S1 视作
  reviewed empty scene（无 GT 人），并把 ledger 的 S1 gt_hits 全数当作
  伪关联证据（见 §3）：候选-GT 关联是空挂。
- **S8 静止窗**：历史 S8 自创"最长连续静 1.76s"登记未复验——本轮只按
  GT 对象时间分布统计，未另测 >20s 静止段；保持 BLOCKED，不作为
  充足"静保"样本依据。

**传播/auto 标签**：GT_V1 中 `source` 仅 `human`（无 propagated/model），
满足三态 REVIEWED_POSITIVE 语义。**未发现**机器 auto 标签流入最终
reviewed 池。跨会话泄漏防线：划分（见 §4）按 sid 硬断言互斥。

## 3. 主数据发现（驱动本轮路线决策）

a) **Ledger 的 S1-GT 伪关联**：S1（家具空场）里 644/644 候选被
ledger 的 `gt_hits` 打成交集，当 GT 点本身为 0 → 说明 ledger 后向
关联逻辑在某路径把「无 GT 可比」当成了 0/0=覆盖完备。证据：把 S1
候选当 oracle 正例会得到 F1 虚高。**本轮已修标**为 P_FP_S1（专用
伪正例池）而不是信赖旧 ledger 结论。

b) **reviewed 正例真实覆盖率极高但负标签为零**。点级：人点占整帧
0.09%–2.46%，对象级（S9 除外，510 object-instances）提案覆盖
`cov>=0.5 : 94.9%`，接受后仍是 `94.9%`，oracle-RF 独立误拒率
`0/510`（accepted 通道不留 RF-单独拒绝的人）。这次主归因：
**分类器不是损失源**——但**负类整洁率**崩坏：accepted 候选中
`FP/h = 70,049 – 134,984`（候选级），S1 全家具场景 RF `prob>=0.55`
frac = 58.2%。这是**家具混诈**主导，不是点损失主导。

c) **每帧人点 <3%**，非人点 97% 以上无标签——D4 逐点语义分割的
**负类监督不可获得**；RandLA-Net 级模型在数据契约上 **DATA_BLOCKED**。

d) **BG 损失真实但不再是首凶**：GT 点在 BG 保留 43%（S3-near）…
98%（S8-still）；UNKNOWN 理由点占比 0–66%（S5-turn 最严重 66%，
S3-far/S8-still 0%）。该层曾被 D05 诊断为主凶，本轮按全九会话复核
后确认：BG 损失在 **sparse/turn 场景显著**（S5-turn、S7-far5m、
S8-still 残量），在常规行走的 S3-near/S3-far 已经收敛。

## 4. 折叠策略（预登记冻结，本次未改）

train = [175227(S1), 175429(near), 175804(walk-stop), 175943(turn)]
val = [175553(far)]
test = [180337(far5m), 180557(still)]
stress = [180235(occlusion)]
explore = [180751(S9)]（永远不进判定）

按 sid 互斥断言（`d3_classifiers.py: load()`），同 sid 不出现在两个
fold。负例采样仅来自 S1（644 个家具候选；其中 ledger 伪关联的
P_FP_S1 子池一并保留）——**没有其他 reviewed 负例**，这是决策置信
的主要限制（见 §5）。

## 5. GT 缺口与最小人标清单（输入下一轮的 REVIEW 支持）

1. **S1 家具 GT 细化**：对 644 个 mainline 候选打 P/N 人标（至少
   抽样 100 个覆盖点数/位置/类型桶）。当前把它们全部按 N 处理是
   不代表任何 reviewed 负事实；只是诚实反映 S1 无 GT 人。此清单
   决定 D3 阈值是否敢用在生产。
2. **S8/S7/S5 无 GT 段的候选标签**：S8（54.1s）只标 53/523 帧，
   其余 470 帧候选全 UNK；需要先确定那些帧人是否在场，再决定是否
   能升 N_S8 池。
3. **S9 修复**：`session_sha256` 缺 meta 键 → 无法绑定；修复后 S9
   就能作为 双人交叉 压力集。
4. **逐点监督**（D4）：如开 RandLA-Net 支线，需要新增(a) S1 家具
   帧级 ~500 张散点负例，(b) 每会话 5–10 帧人全身逐点实例标注，
   (c) 非人刚性簇（墙柜门）逐点负例；否则仅能在弱标签下做正例
   传播。

## 6. 溯源

- 代码：`sidequests/HFUS-RD-01/tools/{common.py,d1_attribution.py,
  stage2_features.py,build_d3_dataset.py}`。
- 关键 JSON：`sidequests/HFUS-RD-01/work/{candidates_stage2.jsonl,
  d3_dataset.jsonl}`；`docs/sidequests/evidence/2026-10-12_HFUS_RD_01_r1/
  {D1_LAYER_SUMMARY.json, D1_FUSION_ABLATION.json,
  D1_TRACK_EVENTS.json, D4_RANDLANET_FEAS.json}`。
- 输入 SHA 见各 JSON `fold_sids` 与 D05 R04 SUMMARY。
