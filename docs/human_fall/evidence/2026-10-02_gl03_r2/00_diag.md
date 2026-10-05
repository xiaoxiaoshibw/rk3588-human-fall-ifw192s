# GL-03 R2 集中诊断（2026-10-02）

范围：只闭合 R1 遗留的 G03 上游资格门控与 O01 诊断方法两处缺口。R1 已通过的
几何/optional/选择缓存/预测参考框不重做。

## 1. G03 源 frame 资格未门控（根因）

R1 只在 `_validated_ground_derived` 里用 `ground_derived.from_frame != frame_id`
挡掉了 GDID 与新 ground 几何（`bbox_ground_from=unavailable`）。但 `build_snapshot`
在 `_validated_ground_derived` **之前**就已：

1. `basis = ground_plane_basis(ground)`（`lidar_candidates.py:523`）——只校验
   `ground.status=='valid'`，不看 frame；
2. 用 `basis` 施加高度过滤（:524-526），并用它给候选算 `height_m`/
   `ground_relative_available=True`（`_point_features` :325-336）；
3. `coordinate.ground_relative_available`、`quality.ground_valid` 直接由
   `basis is not None` 得出（:569/:581）。

于是 foreign frame（`frame_id='other_lidar'`）配上属于 `innolidar` 的 ground 时，
即使 GDID 空、新框 unavailable，**旧高度链仍然有效**：`height_m` 有值、
`ground_relative_available=True`、`ground_valid=True`，且高度范围过滤被错误应用。

节点侧同理：`_ground_valid()`（node_runtime.py:954）只看
`self.ground.status=='valid'` 与 monitor，不看当前帧是否属于该 frame；因此
`_observability` 仍 `valid`、`process` 把 foreign 帧候选喂给 tracker，旧
innolidar 快照还能被新 select 接受。R1 的独立负例
`test_G03_foreign_frame_cannot_enable_legacy_height_or_live_measurements` 正是
暴露这一点。

**共享根因**：缺一个「source-frame 资格」判据，在高度/ground 计算 **之前** 统一
作用于 `build_snapshot`（高度过滤、`_point_features`、coordinate/quality）与
节点（`_ground_valid`/`_ground_context_unavailable`/required request gate/
`status_state`）。R1 只关了最外一层（ground 几何），未关旧高度链。

**修复位置**：`lidar_candidates.py` 新增 `ground_frame_eligible(ground, frame_id)`；
`build_snapshot` 以它决定 `basis`；`node_runtime._ground_valid` 以它并在
`process`/request gate/`status_state` 复用同一判据。规则：仅当 `ground` 为
`valid` 且其 `frame`（若非空字符串）等于实际 `frame_id`（若非空）时资格成立；
缺 frame 的 legacy 摘要保持原行为。无需 derived 也适用（source-only 也不得跨
frame 用平面）。保留原始 seq/stamp/epoch 与原始点云诊断，不以异常杀 worker。

## 2. O01 方法错名/证据不足（根因）

R1 `60_o01_explore.py` 把 `median(raw-Z) ± 3·MAD`（实测厚 1.474 m、删除 pool
78.7%）命名为 “suspected plane ablation”。这是 **z 统计带**，不是倾斜地面平面
支持消融：无法对候选平面 (n,d) 做 `abs(n·p+d)<=0.05` 的成员消融，因此不能据它
推断「地面桥接不成立」。保留原 60/61/62，R2 另写正确诊断，引用
`14_current_planes.json` 的未核验候选 n/d 作显式 hypothesis，按已记录阈值
`abs(n·p+d)<=0.05` 做成员/连接消融，并逐对对齐同输入/采样/range/投影基底。
如实标注 pool 行索引非原帧索引、跨 47 帧、ROI 仅 2 个截断帧。不提升地面 trust/
身份/物理 flags，不猜人/机器人，无完整帧/真值继续 BLOCKED。

## 3. 回传路径

R1 误写到根 `returns/GL-03.md`；R2 仅在 **绝对路径**
`D:/Code/ldiar/docs/human_fall/returns/GL-03.md` 末尾追加，不另造回传目录。

## 4. O01 正确平面支持消融结果（R2）

脚本 `20_o01_planes_ablation.py` → `21_o01_planes_ablation.json`。保留 R1 `60/61/62`
不动，仅新增正确诊断。复用生产连接实现 `ground_plane_basis`/`_horizontal_coords`/
`_connected_clusters`，避免独立复制错误。

- 输入：pool sha `528d8ed2…`（97411 行，跨 47 帧，**行索引非原帧索引**）；
  ROI sha `4c9ccaac…`（仅 2 个截断帧）。planes sha 记录于 JSON。
- 假设：引用 `14_current_planes.json` 的 **6 个未核验候选** n/d（`trusted=false`），
  按已记录阈值 `abs(n·p+d) <= 0.05 m` 做支持集消融。每对比较同输入/采样/cell=0.25m/
  同一投影基底。
- 结果（full → non-plane 分量数）：
  - plane3 **horizontal_candidate=true**（n≈[0.265,0.164,0.950], d=0.1456，支持 7.9%）：1→1，**delta=0**
  - plane0（非水平，倾斜 0.443rad，支持 19.5%）：1→2，delta=1
  - plane2（非水平，倾斜 0.411rad，支持 9.4%）：1→7，delta=6
  - plane1/4：delta=0；plane5：2→2，delta=0
- 诚实结论：**水平候选地面**（唯一可能的地面支撑）移除后**不改变连通分量数**，
  无证据显示地面平面桥接了本应分离的独立簇；但若移除某些**非水平**候选平面会拆出
  多个分量，说明它支持的是非地面结构（墙/斜面/物体），**不能**据此推断地面桥接。
  无可信真实地面 identity、无完整帧/原始索引，仍**保持分离默认关闭**
  （`separation_decision.default_off=true, enabled=false`），真实单帧大框根因与
  人/机器人身份 **BLOCKED**。不提升 trust/身份/物理 flags，不猜标签。

## 5. 计划

最小修复 → R2 独立脚本（含 9 方法：R1 八项 + R2 foreign-frame 项）→ 受影响
GL03/fall 完整回归 → GL02 12+2；follow/UI 若 SHA 未变引用 R1 证据。日志全落
本目录，记录真实 exit 与 source/data SHA。
