# HR-W03 R2.6b / R3 前置审计与实施方案

- 日期：2026-10-06（Asia/Shanghai）
- 性质：**只读审计 + 实施方案**。未改任何生产代码；未采集/部署/联网/commit。等待用户确认后才开始 R2.6b / R3 实现。
- 依据：用户 2026-10-06 提示词（W03-R2.6b Topology-Preserving Cleanup + W03-R3 Reference Static Environment，先审计后实施）。
- ponytail：已加载（full），路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。
- 上一轮证据：[2026-10-06_hrw03_r1/README.md](../2026-10-06_hrw03_r1/README.md)（R2.1–R2.6 实测与 topology regression）。

基线 SHA256（本轮审计时点）：

| 文件 | SHA256 |
|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | d04cfeffb45f1355f979b0ada67a4d19e7113e665a11e5a1f513640ab627cf91 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | 2228c7db995b38134cdfba2ba042f25293ed4d431ba28e1b35119beafde0678f |
| `pc_apps/human_replay/human_detect.js` | 730cd258c05a6074f05341b7e58f5cc95b9a2baa83fe0fe5f7622b1dbb8fc901 |
| `pc_apps/human_replay/human_detect.html` | 82329f2fdfacfc4c38481f2cf6c357f1e2c69db5b38baad55e150d5d838743a2 |
| `pc_apps/human_replay/human_replay_lib.py` | 999d600db9536c38d7f171039798554467e82a3961cdcb25cfd948a7e1d13633 |
| 会话 `cap_20261002_223757` meta/bin | 71915d51… / 8afb660b…（见 captures/leveled manifest） |
| 会话 `cap_20261004_203349` meta/bin | c3b55d1e… / 2ed3fc60…（同上） |

---

## 1. 当前 clustering 的 XY grid / adjacency 实现位置

全部在 `pc_apps/human_replay/human_pipe_lib.js`，且均已导出（`_api`，L646–665），R2.6b 可直接复用：

| 项 | 位置 | 语义 |
|---|---|---|
| XY 网格 | `key_vox(x,y)` L80–82 | `floor(x/0.15)+","+floor(y/0.15)`，`PIPE.voxel_m=0.15` |
| XY 体素化 | `voxelize(xyzi)` L115–134 | XY 柱累加器（n、Σx…、zmin/zmax） |
| 聚类邻接 | `cluster_voxels(vox_fg)` L271–304 | 字符串键解析后 **4 邻**（ix±1, iy±1）BFS；`cluster_min_voxels=3` 过滤（L303） |

**关键事实**：聚类是 **XY-only（忽略 z）**；而 R2.6 的孤立清理判据用的是 **3D 背景体素 + 26 邻域**（`key_bg`，0.15/0.12 m）。两套语义不一致正是 regression 的根因（3D 孤立点可以是 XY 图上的桥接格）。

## 2. 当前 background model 数据结构

- `build_static_map(frames_xyzi, opts)` L146–198 → `Map<intKey, {x, y, z, hits, tier}>`
  - key = `key_bg` L89–92（3D 整数编码，base 8192/offset 4096，供 26 邻域枚举）
  - 每帧命中 ≥ `bg_hit_min_pts=2`；`strong` 占用率 ≥0.85；`supported` ≥0.65 且逐帧形心抖动 ≤0.05 m 且 26 邻域 strong ≥2
  - Welford 累加器算全帧形心与抖动；**occ/jitter/density 算完即弃**（只留 tier）——R3.1 需 additive 扩展
- 匹配：`extract_foreground` L205–217（工作空间裁剪 z∈[0.10, 2.50] + 有界背景匹配）+ `_bg_match` L220–231（3×3×3 体素邻域，点到全帧形心 < `bg_match_radius=0.12 m`）
- 运行时持有：`human_detect.js` `S.pipe.static_keys`（L33–43；建模于 L219–242）；Node 证据脚本每会话现场构建。

## 3. 当前 session 加载格式

- 目录 `captures/remote/<sid>/{meta.json, points.bin}`；28 B/点（x,y,z,intensity f32×4 + ring u16 + pad + timestamp f32 + pad），`STRIDE_F32=7`（`human_replay_lib.js` L8–9）。
- `frame_slice(meta)` L14–37 校验 offset 连续 → `{start_pts,count,...}`；`strided_f32_copy` L43–53 抽 `[x,y,z,i]` 四元组。
- 浏览器：`/api/file?sid&name`（白名单仅 meta.json/points.bin，`human_replay_lib.py` L166–188）；载入时 `GET /api/leveling/leveled_latest`（`leveling.py` L376–425，取 **report mtime 最新**且 `recommended=="tls"` 的 TLS transform）→ `human_detect.js` L117–127 in-place 应用。
- Node 证据脚本（ab_r26/inspect_split）：**直接读 points.bin，未应用配平**。→ R3 离线 harness 必须显式应用 transform 并记录所用 job/frame。

## 4. empty-scene session 审计（本地 10 个会话）

| sid | 帧/时长 | 配平 | 内容已知性 |
|---|---|---|---|
| **cap_20261004_203349** | 102 / 10.46 s | 有 TLS（最新 job c9712aca, 10-05 17:29；pitch 26.99°, roll -2.95°, tz 1.317 m） | **已确认空场**（R2.6 回归用） |
| cap_20261002_163621 | 89 / 9.08 s | 无 | draft 推断 idle 基线，未确认空场 |
| cap_20261002_233210 | 99 / 10.16 s | 无 | 未确认 |
| cap_20261004_202456 / 203135 | 91 / 113 帧 | 有 TLS | GL-V01 录制，内容未确认空场 |
| cap_20261002_223757 | 165 / 17.0 s | 有 TLS（最新 job 6bc5aabf, **10-06 10:43**；pitch 26.47°, roll -0.37°, tz 1.323 m） | golden（活动目标） |
| 其余（165321/182355/clip/synth） | ≤29 帧 | 无 | 短/合成 |

**结论**：本地最适合建 reference map 的是 `cap_20261004_203349`；但仅 10.5 s，低于用户 20–60 s 目标——先用它做离线验证，正式参考图需后续从板端拉取更长空场或新录（需另行授权）。

**风险（必须先测）**：跨会话配平不一致。223757 与 203349 的最新 TLS 相差 Δpitch≈0.53°、Δroll≈2.58°、Δtz≈0.006 m；roll 差在 |y|=3 m 处 ≈0.13 m z 偏移，已到匹配半径 0.12 m 边界。R3.2 必须实测 203349→223757 的 reference match ratio；若不足，备选方案 = 把参考会话的 transform 当作 scene transform 同时应用于两会话（需用户拍板）。

## 5. Reference Map 最小侵入式接入点

1. **构建**：`build_static_map` 加 additive 字段（occ/jit/density 保留），导出即 reference builder（复用同一循环，不新写第二套体素化）。浏览器在 human_detect.js 选空场会话 → 走现有载入路径（含 leveled_latest）→ denoise → build → 存 `S.pipe.reference_keys`。记录来源 sid + transform id + meta/bin SHA。构建期 NO HUMAN = 只选空场会话。
2. **运行**：`extract_foreground(xyzi, online_map, ref_map)` → `_bg_match(ref) || _bg_match(online)`，先参考后在线、逐点只计一次；`pipeline_frame` 经 `ctx.reference_keys` 透传。**不新增匹配参数**（复用 bg_voxel_xy/z + 0.12 m + 3×3×3）。
3. **融合**：background = reference OR online（online 模型不动，职责分离）。
4. **冻结**：参考图构建一次、运行期只读（无在线写入路径）；v1 建议内存持有 + 可选客户端下载 JSON 归档；文件化持久化（/api/file 白名单或新增只读 route）待 v1 验证后再定。
5. 诊断输出：`reference_static_points` / `online_static_points` / `residual_points`；R3.4 场景失配统计后置。

## 6. 拟修改文件（待确认）

| 文件 | 改动 | 轮次 |
|---|---|---|
| `pc_apps/human_replay/human_pipe_lib.js` | R2.6b cleanup veto + 新诊断；R3.1 builder additive 字段；R3.2 双 map 匹配；pipeline_frame 透传 | R2.6b → R3 |
| `pc_apps/human_replay/human_pipe_lib.test.js` | 更新 6 个旧清理测试字段名 + 新增 veto/参考图/融合测试 | R2.6b → R3 |
| `pc_apps/human_replay/human_detect.js` | 透传 ref map、诊断显示、参考会话选择/构建 UI | R3.1/R3.2 |
| `pc_apps/human_replay/human_detect.html` | 面板行与控件（最小） | R3.1/R3.2 |
| `docs/human_capture/evidence/2026-10-06_hrw03_r2/*` | ab_r26b.js + 结果 JSON + R3 脚本与证据 | 全程 |
| （条件）`pc_apps/human_replay/human_replay_lib.py` | 仅当选"文件化参考图经 /api/file 白名单"时 | 待定 |

**不修改**：`human_detect_lib.js`（HR-W02）、`Tracker`/`fall_assess`/证据层（R2.6b 不碰）、`human_replay_lib.js` 核心、`leveling*`、`webui/`、板端、`captures/` 输入、`ML/`。

---

## 7. R2.6b 实施方案（Topology-Preserving Cleanup）

**算法（保守 veto，可证明 cleanup-induced split = 0）**：

1. 保留 3D 判据：前景 3D 体素点数 ≤1 且 26 邻域无前景体素 → 只**标记** `isolated_3d_candidate`，不删。
2. 同一遍扫描构建前景 **XY 集合**（`key_vox`，与聚类同格），并记下每个 candidate 点所属 XY 键。
3. 对每个 candidate XY 键统计 **4 邻域**内前景 XY 体素数 n4（与 `cluster_voxels` 同邻接）：
   - n4 ≥ 2 → **KEEP**（`xy_topology_vetoed`；"可能改变 XY connectivity"）
   - n4 ≤ 1 → REMOVE
4. 单遍快照语义：全部判定完再一次性删点；不递归、不传播。共享同一 XY 键的多个 candidate 同判。

**正确性**：被删 candidate 在清理前 XY 图上度 ≤1；若存在"存活点对"因删除而断开，其路径上必有一个被删点具有两个路径邻居（度 ≥2），矛盾。⇒ 不产生 split。无新增参数（禁止 cleanup_xy_radius/grid 一类近似拓扑参数）。

**诊断（cleanup 返回 + pipeline_frame 透出）**：
`isolated_3d_candidates`、`xy_topology_vetoed`、`actually_removed_points`、`actually_removed_voxels`、`fg_before_cleanup`、`fg_after_cleanup`、`cluster_before`、`cluster_after`、`cleanup_split_delta`；若 `cluster_after > cluster_before` 置 **TOPOLOGY_REGRESSION**。
（cluster_before/after = `cluster_voxels()` 输出数，仅在有 candidate 时算 before，避免常态双跑。）

**测试**：新增 4 例——(a) 度 2 桥接 candidate → 保留（veto）；(b) 度 1 叶 candidate → 删除；(c) 同 XY 键多 candidate → 全保留；(d) A–q1–q2–B 链 → 全保留；另更新既有 6 例字段名（语义断言不变）。

**AB 验收（`ab_r26b.js`：before=R2 复刻 vs after=生产 pipeline）**：

| 会话 | 判据 |
|---|---|
| `cap_20261002_223757` | 每帧 `cluster_after ≤ cluster_before`（split=0）；每帧 `green_after ≤ green_before`（new green=0）；frame16 不再出现 1115+87 分裂 |
| `synth_bend_v1` | 190/190 帧人簇保留，retention 不低于 R2.6 |
| `cap_20261004_203349` | 无新簇/新 green，不得差于 R2.6（1→0） |
| 记录 | 与 R2.6 的删除量差（veto 保留量）、每帧 delta 全量表 |

**流程**：实现 → 单测 → 三会话 AB → 证据入本目录 → 已知边界 → 停写等审阅。不 commit。

## 8. R3 实施要点（R2.6b 通过后才开始）

- **R3.1** builder：复用 `build_static_map` 循环输出带 occ/jit/density/tier 的参考体素；来源（sid/transform id/SHA）入档；空场保证。
- **R3.2** matching：双 map OR 抑制（先参考后在线）；容差沿用现有 3×3×3 + 0.12 m；输出 reference_static_points / residual_points；**先实测跨会话匹配率**（见 §4 风险），必要时启用 scene transform 备选。
- **R3.3** fusion：reference OR online，online 模型不动。
- **R3.4** scene diagnostics：reference_match_ratio / miss / unexpected_static / persistent_unknown；第一版只告警不重建（后置）。
- **R3.5** planarity：仅诊断、禁止"看到平面就删"（后置）。
- **W03 最终验收**：空场（墙/摆件/设备）0 candidate、0 confirmed；golden 中墙/摆件→background、人保留；真动作（upright/walking/bend/crouch/sit）需真人数据——本地目前只有 synth，真人类验收将 BLOCKED 直到 W04 采数。

## 9. 待用户确认

1. R2.6b 采用"度 ≤1 才删"的保守 veto（可证明不产生 split；会保留部分可删点）——确认？
2. R3 参考图 v1 内存构建 + 可选 JSON 下载归档；文件化持久化后置——确认？
3. 跨会话配平不一致的备选：参考会话 transform 当 scene transform 同时用于两会话——是否接受该 fallback 原则？
4. 空场参考先用 `203349`（10.5 s）离线验证；20–60 s 正式空场后续另行授权拉取/录制——确认？
5. 严格单层推进：R2.6b 验收通过后才动 R3.1——确认？

---

> 本轮（审计）未改生产代码、未采集、未部署、未联网、未 commit；无 git 操作。
