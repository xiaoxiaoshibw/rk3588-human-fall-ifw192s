# 静立人保留 · 融合优先级规则草案 v1（阶段 1 设计稿）

状态：**DRAFT**（设计草案；不构成实施授权；本文件无生产改动）。
依据：[STILL_PERSON_RETENTION_PLAN.md](STILL_PERSON_RETENTION_PLAN.md) 阶段 1；Arm C 实测（参考层保留 97.4–98.0%、并集语义下仅 1.2–2.1%）；[W03_R3_ACCEPTANCE.md](W03_R3_ACCEPTANCE.md) 共同门"REFERENCE_STATIC > ONLINE_PERSISTENCE 优先级"；现有代码 `human_pipe_lib.js`（`build_static_map` / `build_reference_map` / `extract_foreground` / `_bg_match`）与 `registration.js`（artifact 门）。

## 1. 问题与目标

- 现状（S 链）= 两阶段顺序匹配：`reference → online`，效果等于**并集**——任一地图命中即删。静立人被在线自建模（人体体素 occ≥0.85 → strong）整块删除（Arm C 实测）。
- 目标语义：**空场模板里没有的东西，不得仅凭"在线持久"被删**（REFERENCE_STATIC 优先于 ONLINE_PERSISTENCE）。
- 不回归：WD01/WD02 静态泄漏仍被清；空场固定物 0 candidate / 0 confirmed；**不改** 0.65/0.85、0.12m、occ≥0.5 等阈值；不改聚类/资格判定/跟踪/Fall；P（在线-only）路径不变。

## 2. 术语与现状机制（对照现状）

| 术语 | 来源 | 机制（现状，不改） |
|---|---|---|
| reference_static | 空场会话 | `build_reference_map`：每帧 ≥1 点即 observed；`occ ≥ 0.5` 入图 |
| online_persistence | 当前会话 | `build_static_map`：每帧 ≥2 点命中；strong = occ ≥ 0.85；supported = occ ≥ 0.65 + 抖动 ≤0.05 + 26 邻域 strong ≥2 |
| 匹配（match） | 两者共用 | 点的 3×3×3 体素邻域内任一静态体素，其全帧形心距点 < **0.12m**（`_bg_match`） |
| 现状 S 删除 | — | `match(refkeys, p) OR match(online, p)`（并集） |

## 3. 规则草案（Fusion v2）

### 3.1 形式定义

```
删除 p  ⇔  [ ref_match(p)  OR  ( online_match(p) AND ref_supported(online_hit(p)) ) ]
           AND NOT protected(p)          // protected 为可选第二层，v1 默认关闭

ref_supported(v)  ⇔  match(refkeys, [v.x, v.y, v.z]) ≠ null   // v = 命中的在线静态体素
```

- `ref_supported` **复用既有 3×3×3 邻域 + 0.12m 半径**，不新增参数。
- 退化形式：`ref_supported ≡ false` ⇒ 纯参考层删除（= Arm C"参考层"列，给出收益上界与代价上界，用作 A/B 对照臂）。

### 3.2 场景用例

| 场景 | ref_match | online_match | v2 行为 | 与现状对比 |
|---|---|---|---|---|
| 静态家具（在空场中） | ✓ | ✓/✗ | 删 | 相同 |
| 空场漏检的家具（参考覆盖缺口） | ✗ | ✓ | 邻接参考 → 删；**孤立 → 保留为候选** | 现状删；v2 代价（需量化） |
| **全程静立的人（本四段）** | ✗ | ✓ | `ref_supported ✗` → **保留**（进候选/可确认） | 现状 97–98% 被删 → 修复 |
| 后到静止的人（共同门场景） | ✗ | ✓ | 同上，保留——**无需已确认 track** | 共同门要求满足且更强 |
| 新搬入/新放置的物体 | ✗ | ✓ | 保留为候选，由几何门裁决 NON_HUMAN（不删点） | 现状删除 |
| 贴靠空场家具的人（局部 <0.12m） | 局部 ✓ | — | 局部点仍被参考层删（已知代价） | 相同（S1b 可选缓解） |

### 3.3 S1b（可选第二层）：已确认轨道保护

- 保护足迹：活跃 track（`human_confirmed` 或近窗内 `CONFIRMED_HUMAN`/`HUMAN_CANDIDATE` 票）在最近 **K 帧**（建议 K=8，与 `track_lost_max` 同量级）内簇体素的并集；仅对 **online 删除**豁免（reference 删除不豁免——空场证据更强；如需另议）。
- 纪律：窗口有界、绝不无限保框；输出必须区分"观测/预测不足"；关联含糊即撤销保护（回 UNKNOWN）——与 W04"身份与姿态分离"条款对齐。
- 成本：引入 1 个新参数（K）；因 v2 主规则已覆盖人的保留，**建议 S1b 仅在 A/B 显示"贴靠家具损失"不可接受时启用**。

### 3.4 模式与降级

- **无 reference artifact（纯 P 场景）**：保持现状 online-only；静立边界仍存在（阶段 3 ever-free 处理）。能力旗标语义："有有效模板才走 v2"。
- **reference STALE / DEGRADED / REJECTED**：沿用既有 loader 状态机；DEGRADED 仅诊断可用（shadow），REJECTED 不得使用；SHA 绑定与 stale 语义不变。
- 阈值、匹配半径、builder 参数一律不动；v2 只是"删除决策"的融合层变化。

## 4. 实现边界（未来工单范围草案）

- 只动融合层：新增 fused 删除函数（或 `extract_foreground` 的 fused 变体），替换 S 链的双阶段 `extract_foreground`；**P 路径、cleanup、聚类、classify/joint、Tracker、Fall 全部不动**。
- 参考实现骨架（示意，非最终代码）：

```js
function fused_remove(p, refkeys, online) {
    if (match(refkeys, p)) return "REFERENCE";        // 同 _bg_match
    const hit = match(online, p);
    if (!hit) return null;                            // 保留
    if (!match(refkeys, [hit.x, hit.y, hit.z])) return null;  // online-only 持久 → 保留
    return "ONLINE_SUPPORTED";
}
```

- 生产接入走 R3.9 一类评审：默认关闭的能力旗标、只有 VALID artifact 使用、浏览器/节点实际行为单独验证。

## 5. 验证协议（A/B 门草案）

### 5.1 受益集
- 四段静立人（215540/215623/215643 已有配准；215607 先解决配平 conflict 再入集）：目标 = v2 人点保留 **≥ 95%**（与参考层差 ≤3pt），且能成簇进候选；记录 confirmed 或 UNKNOWN 原因。

### 5.2 不回归集
- WD01（223757 窗口）：删除量 ≤ 现状 S；WD02 远场：静态候选 = 0（对齐 W03_R3_ACCEPTANCE §2.1/§2.3 口径）。
- 空场 233658：0 human candidate / 0 confirmed。
- clean 人窗吸收：不劣于现状 S；**31 点/T38-05 语义问题与本规则正交**，不得借本规则掩盖（GT 仍待）。
- T38 共同门（`cleanup_split_delta`、无新 green/purple 语义等）不因融合层改变。

### 5.3 代价集（新增公开指标）
- "参考覆盖缺口泄漏"：v2 下被保留的 online-only 持久点（未邻接参考），按区域/距离统计——作为 v2 的公开成本。

### 5.4 方法与记录
- 离线臂：改造本轮 `retention_ref_probe.js`（v2 模式），同注册 artifact / 同 refmap+online / 同点级归属；输出"保留率阶梯 v2 列 + 代价集计数"；新文件名独占，不覆盖既有产物。
- 全部代码/artifact/输入 SHA 记录；无生产改动。

### 5.5 通过条件（供未来验收表：F01–F06 草案）
- F01：融合语义实现与本文 §3.1 一致（含退化臂对照）。
- F02：四段人保留 ≥95% 且进候选。
- F03：WD01/WD02/空场不回归。
- F04：31 点/T38 语义不被本规则改变或掩盖。
- F05：（若启用 S1b）保护窗有界、含糊撤销、无无限保框。
- F06：无新增阈值参数（S1b 的 K 单列论证）。

**§5 已执行（2026-10-08，离线，用户直派）**：[evidence/2026-10-08_fusion_v2_ab_r1](evidence/2026-10-08_fusion_v2_ab_r1/README.md)——**8/8 PASS**：工具逐点复现上一轮；V2 人保留 99.9–100%（融合层）；WD01 删除 99.3%（=REF）；WD02 62.9%（≥REF）；代价=非人泄漏 2.1–2.5k 点/帧（公开）。

## 6. 已知代价与开放问题

1. 参考覆盖缺口 → 候选噪声；R3.3 AABB matcher 已部分缓解，进一步改进（覆盖/匹配）可另开项，不在本草案内承诺。
2. 贴靠家具的人局部点仍被参考层删（S1b 或 W04 处理）。
3. 空场参考质量/时长：当前 5.5s 诊断模板；正式 20–60s 空场录制仍需采集授权。
4. 术语歧义：R3.2 阶段门写"background = reference_static OR online_static"，共同门写"REFERENCE_STATIC > ONLINE_PERSISTENCE 优先级"；**本草案按"优先级"解释**（否则静立人无解，与共同门冲突）。如编排方裁定另一解释，改草案、不改数据。
5. 与 ever-free/N1（阶段 3）关系：v2 解决"有模板"场景；无模板场景仍需 N1 或文档化边界。

## 7. 下一步（均需另行授权）

- （a）实现 v2 离线诊断臂并跑 §5 A/B（新 evidence 轮，无生产改动）；
- （b）按 §5.5 建正式工单与唯一验收表（F01–F06）；
- （c）生产接入评审（R3.9 一类，能力旗标默认关闭）。
