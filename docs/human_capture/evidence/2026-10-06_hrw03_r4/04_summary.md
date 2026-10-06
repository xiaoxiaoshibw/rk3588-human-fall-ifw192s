# W03-R3.1 Reference Background Builder 交付摘要（离线，未接 production）

- 日期：2026-10-06（Asia/Shanghai）
- writer：OpenCode（DeepSeek v4.1 Flash，本会话）；ponytail 已加载（full，路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`）。
- 性质：**离线构建 + 只读证据**。未改在线行为（`pipeline_frame` / `extract_foreground` / R2.6b 清理一行不动）；未采集、未部署、未 commit、未联网。
- 依据：用户对 W03-R3.0 的评审判定（[11_user_verdict.md](../2026-10-06_hrw03_r3/11_user_verdict.md)）与 [W03-R3 验收规范](../../W03_R3_ACCEPTANCE.md) §3 R3.1 条。
- 实施计划：[00_plan.md](00_plan.md)。复现入口见文末。

## 1. 交付内容（additive，仅 2 个生产文件）

| 文件 | SHA256（R3.0 基线 → 本轮） | 改动 |
|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | `30c257b7…96b66` → `5bce92a4…142b4` | 新增 `build_reference_map(frames, opts)` + `reference_static_keys(ref, min_occ)`（`_api` 导出）；PIPE 新增 `bg_ref_hit_min_pts=1`、`bg_ref_occ_min=0.5`（v1 候选）；头注释同步 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | `0d3991c2…49cc5` | 新增 3 例（见 §2）；旧 32 例一行未改 |
| `pc_apps/human_replay/human_detect.js` | `555685b5…250c0`（**未动**） | — |
| `pc_apps/human_replay/human_detect.html` | `62bf9126…1cad37`（**未动**） | — |

builder 语义（用户指定）：

- 本帧 observed = 体素当帧点数 ≥ **1**（在线为 ≥2，会漏「每帧 1 点长期稳定」的稀疏面）；
- `O_v = #observed 帧 / N_reference 帧`（分母 = 无遮挡空场帧总数，不被监视对象污染）；
- 每体素输出 `key / occ / obs / 形心 x,y,z / jit / pts_total / pts_per_frame / confidence(=occ, v1)`；
- 工作空间裁剪与在线一致（`z∈[0.10,2.50]`）；**无任何在线写入路径**（构建一次、运行只读）。

## 2. 单测

`node human_pipe_lib.test.js`：**35 passed, 0 failed**（旧 32 + 新 3）：

1. `R3.1: 每帧仅 1 点也计 observed（≥1 门）` —— 同一体素每帧 1 点：在线 map size=0，参考图 occ=1 入图（M1 直接回归）。
2. `R3.1: persistence 抵御噪声 + 阈值显式可控` —— 1/10、4/10 不入图；9/10、10/10 入图；显式 0.95 只留 10/10。
3. `R3.1: 统计字段 + 工作空间裁剪与在线一致` —— 形心/抖动/密度、地面与 z_max 裁剪。

其余套件（见 [04_unit_tests.log](04_unit_tests.log)）：`human_replay_lib` 45/45、`human_detect_lib` 11/11、`panel` PASS。

## 3. 证据运行（console 同口径：TLS 配平后）

- 会话：`cap_20261004_203349`（102 帧，候选空场）；job `c9712acad48c4fb7a78cb119c08d4cdb`（transform_id `5d8fd5c0…`）。
- 输入 SHA256：meta `c3b55d1e…38392`、points.bin `2ed3fc60…10323`。
- 运行：`node 01_r31_reference_builder.js cap_20261004_203349`（1.8s）→ [02_r31_stats.json](02_r31_stats.json)、[03_r31_run.log](03_r31_run.log)。

### 3.1 参考图统计

| 指标 | 值 |
|---|---|
| 参考体素总数（≥1 点出现过） | **5286** |
| 占用率直方图（0.0–1.0，0.1 宽） | 739 / 295 / 209 / 166 / 170 / 161 / 172 / 190 / 228 / **2956** |
| 在线 map（对照） | 2063（strong 1885 / supported 178） |

### 3.2 阈值扫描（ref_keys / 其中稀疏「每帧<2 点」/ 与在线交集 / 在线未被覆盖）

| thr | ref_keys | sparse(<2pt/frame) | in_online | online_not_ref |
|---|---|---|---|---|
| 0.20 | 4252 | 2379 | 2063 | 0 |
| 0.30 | 4043 | 2170 | 2063 | 0 |
| **0.50** | **3707** | **1834** | **2063** | **0** |
| 0.65 | 3455 | 1582 | 2063 | 0 |
| 0.80 | 3184 | 1312 | 2063 | 0 |
| 0.90 | 2956 | 1087 | 2061 | 2 |
| 1.00 | 2312 | 582 | 1879 | 184 |

- **在线 map 2063 个体素在 ≤0.8 的全部阈值下 100% 被参考图覆盖**（`online_not_ref=0`）。
- 候选阈值 0.5 下参考图 3707 体素；其中 **1834 个是「每帧 <2 点」的稀疏面**——正是在线 ≥2 门结构性看不见的类别；
  「occ≥0.5 且每帧<2 点且不在在线 map」合计 **1632** 个。
- 示例（top1）：`(10.07, -1.57, 1.64)` occ=1.0（102/102 帧可见）、196 点、1.92 点/帧、jit 0.021 —— 一条完全稳定的远场面，在线 map 完全不可见。

### 3.3 自吸收自检（同会话，上界参照；**不是**跨会话证据）

- 3,131,751 个工作空间内点：现行匹配规则（3×3×3 + 形心距 <0.12m）吸收率 **0.9987**；仅邻域存在 0.9999。
  说明在**同一会话**内，参考图 + 现行几何规则已能吸收空场几乎全部点；跨会话（Δroll≈2.58°）留给 R3.2。
- 复现 digest：同输入重建两次 sha256 相等（`14c1633b…1148d`），deterministic=true。

## 4. 与 R3.0 根因的对应

| R3.0 机制 | 本轮状态 |
|---|---|
| M1 遮挡污染分母 | **按构造消除**（空场帧分母；WD01 类「受试者挡住自己家家具」不可能再改变参考图） |
| M2 ≥2 命中门漏稀疏面 | **builder 已修复**（≥1 门；0.5 下回收 1632–1834 个体素，含全部在线体素） |
| M3 点到形心距离 vs 体素几何 | **本轮不碰**（R3.3，仅当 R3.2 证据支持；R3.1 不预先断言 0.20 半径或 AABB matcher 取舍） |

## 5. 边界 / 未做 / 已知限制

- **未接 production**：无 UI、无 `pipeline_frame` 透传、无双 map 匹配（用户要求先过 R3.2）。
- **未做跨会话 audit**（R3.2 第一件事：223757 current vs 203349 reference，Δroll≈2.58° 风险实测）。
- `cap_20261004_203349` 仅 10.5s 候选；正式 20–60s 空场录制/拉取需另行授权。
- `bg_ref_occ_min=0.5` 为未标定候选值（噪声尾直方图见 3.1）；persistence/阈值只作 diagnostic/confidence，无删除权。
- 未采集新数据；未部署；未 commit；未联网。未动 `human_detect.*` / Tracker / PCA / joint_status / R2.6b cleanup / leveling / console / web 板端。

## 6. 下一步（按用户指定顺序）

1. **R3.2** 跨会话 leveled reference alignment/matching audit（223757 vs 203349 reference）；
2. 依 audit 证据决定：参考图 transform / scene transform 备选 / 阈值；
3. **R3.3** voxel-surface（点→AABB）matcher（仅当 R3.2 证据支持）。

## 复现

```bash
node 01_r31_reference_builder.js cap_20261004_203349
cd ../../../../pc_apps/human_replay && node human_pipe_lib.test.js
```
