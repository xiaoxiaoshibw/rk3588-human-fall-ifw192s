# GL-03 R3 集中诊断（2026-10-02）

范围：只闭合 R2 复审确认的两处共享缺口——reference 完整上下文（G03/G04/G05 四方法原失败，`71_reference_before`）与 O01 统计口径/物理语义（`CODEX_REVIEW.md`、`04_o01_independent_audit.md`）。R2 已通过的原九方法、source 高度/frame 门控、普通回归不重做。

## 1. reference 上下文未绑定（根因）

R2 的 `_reference_block`（`lidar_candidates.py:403`）直接消费调用者传入的 `transform`，只判 `status=='unknown'`，不校验：

1. `transform.from_frame` 是否等于实际 producing `frame_id`；
2. `transform.to_frame` 是否等于 `calibration.frames.reference`；
3. 传入 transform 是否与 artifact-owned 的 `transforms.T_reference_lidar` 冲突。

因此 foreign `from_frame`、错误 `to_frame`、与已知父记录冲突的 standalone transform 都能产出 `center_reference_m`/`bbox_reference_*`（`codex_reference_checks.py` 前两方法）。

节点侧同根因：`FallNodeCore.__init__` 只在启动时保存 `self.transform`；`_source_frame_mismatch`（`node_runtime.py:758`）只看 `self.ground.frame`，无 ground 时 reference `from_frame` 错误仍 `degraded` 可选人/带 reference 位置（第三方法）；`apply_ground_context` 完整 artifact 重载只换 `calibration`，`self.transform` 仍是旧版本矩阵，新 calibration id 配旧 T（第四方法）；`_prediction_in_source` 猜 `self.transform` 而非实际绑定域。

**共享根因**：缺一个「实际 producing frame + 已知 reference label + 当前 canonical transform」的 reference resolver。不能只在 ground 守卫上再加一处。

## 2. 修复位置与规则

`core/calibration.py` 新增共享入口 `resolve_reference_transform(calibration, transform, frame_id)`：

- artifact 带 known `T_reference_lidar` 时为权威；standalone known transform 与它结构性不一致即 conflict，不静默采用（返回不可用）；
- 无 known artifact 记录时合法 standalone transform 保持既有支持（R1/R2 纯 API 回归不变）；
- `from_frame` 非空且不等于非空 `frame_id` → 不可用；`to_frame` 非空且不等于已声明 `frames.reference` → 不可用；记录本身不合法 → 不可用；
- 未知/不可用只令 reference 坐标为空，普通「无 ground 无 reference」source-only degraded 原义不变。

`build_snapshot` 用该 resolver 决定 `_reference_block`；节点用同一 resolver 在校验成功的 context 绑定后重解析：artifact-owned T 覆盖旧 standalone（caller 解绑、深度拷贝），无 ground 也守 `from_frame`/`to_frame` 门控（`process`/`handle_request` gated/`status_state` 均经 `_source_frame_mismatch`/`_ground_context_unavailable`），prediction 改用实际绑定 transform。不新增 schema/热更新框架。

## 3. O01 统计与语义纠正（R2 复审）

R2 脚本已按完整 pool 支持 mask 计 `support_count_in_pool`，但报告/摘要把 `14_current_planes.json` 的旧逐面剥离 `support_fraction_of_pool`/`residual_rms_m` 与本轮 mask 统计混用（例如 plane3 旧 7.8964% 被当成 R2 结果）。R3 新诊断从本轮完整 97411 行 pool 同 mask 重算 count/fraction/RMS；旧逐面剥离值若引用一律改名 `historical_peeled_*` 并注明成员集合不同。full/ablated 两臂保持同输入/采样/投影/cell=0.25m/band=0.05m，可复用的 R2 成员量/AABB 数字必须与重算结果一致。

物理语义：六个 plane 身份全部未知；`horizontal_candidate`（source-Z 近法向提示）不是 world-Z、不是地面身份，不能说 plane3 是唯一可能地面或排除地面桥接；n/d 消融只能报告「不同假设支持移除改变 pool 连接」，不能确认现场单帧大框根因。无可信真值 → 不启用分离、不删近地厚层、不改 trust/物理 flags。

数据标注：pool 每帧先滤非有限/零点、每 20 个有效点抽 1、跨 47 帧拼接、CSV 四位小数；ROI 仅 2 个截断帧 6000 行；不是完整生产候选过滤链或逐帧原始数据。

## 4. 计划

最小修复 → 先跑原 9 方法 checker（R1 未改副本）+ 新 4 方法 reference checker → 受影响 GL03/fall 全量 → GL02 生命周期 12 + pending 2 → R3 O01 重算脚本 → source/data SHA 与真实 exit 日志全落本目录，回传仅追加 `returns/GL-03.md`。设备/真实物理继续 NOT_RUN/BLOCKED，不自判总体 PASS。
