# P03 R1 00_diag — auto 分支触点行级映射

2026-10-05，单 writer Claude Code。ponytail：`C:\Users\30680\.claude\skills\ponytail\SKILL.md` 已读。范围只 `pc_apps/human_replay/`，不设备/commit/console 重打包。

## auto 触点（行号 = `leveling.py` 当前 HEAD）

| 函数 / 行 | auto 是否触碰 | 本单动作 |
|---|---|---|
| `validate_request` 105-134 | **是（唯一语义扩展点）** | 允许 `config.mode=="auto"`；此时 regions 允许空列表、跳过「len(regions)!=4」与 ground_confirmed/basis 必填 STOP；mode 缺省=旧路径**字节级保持**（包括旧默认 R3 区域、grab box、确认 STOP）。auto 模式仍需 physical_height_m、basis 可省（auto 依据由 detect 自动生成）。 |
| `freeze_domain` 137-172 | 间接受影响（regions 来自 config，长度由 4 变 K）| **不改代码**；detect 输出 K 个 ROI 直接替代 config.regions。注意 `np.count_nonzero(codes == i) < 20 for i in range(1, 5)` 假定 4 区；detect 已保证 K=4（否则不切 auto，K<4 直接失败）。 |
| `compare` (quality.py) 40-112 | 不变 | anchor=initial[2]（名义显示系 z 轴）；detect 时 nominal pitch/roll 用请求里的同一字段。 |
| `run_job` 217-261 | 嵌入 detect 调用 | 在 `config = request["config"]` 之后、freeze_domain 之前：`if config.get("mode")=="auto": config["regions"]=detect_ground_domain(all_finite_points, nominal_pitch, nominal_roll, anchor=initial_z)["regions"]`。注意 detect 需要点云 **不依赖 regions**，所以必须先加载 raw 全帧再调用；freeze_domain 已经加载，再加载一次会 2×I/O —— 所以把 detect 放到 freeze_domain 之前，**用 memmap 快速扫一遍**（同 28B 步长，不复制到 freeze_domain 内避免改该函数）。 |
| `start` 264-288 | 不改 | detect 失败会走既有 `_jobs[job_id].update(state="failed", message=...)` 通道，前端已有错误显示。 |
| `export_dataset` 174-214 | 不改 | 每法（TLS/SVD/RANSAC）仍独立 transform/dataset，自动流程用户选其一或由 consensus 推荐 TLS。 |
| `handle` 314-366 | 不改 | 同源检查/大小门/路由都保持。 |
| `replay.js __load_session_sid` 224-232 | **加一次 GET** | `GET /api/leveling/leveled_latest?sid=` 返回最近完成 job 的 TLS transform.json（有就返回，没有 404）；前端存在就应用，无则原样。新增 GET 路由放 `handle` 同一 dispatch 块内。 |

## 显式不绕开的 STOP

- `ground_confirmed=True` + `basis>=2` 的人工确认 STOP：**auto 新模式不使用手动勾选**（勾选 UI 只在人工路径有效），detect 自身生成的 `basis` 字符串（如"自动连通域 4 区，支持率 0.xxx"）写入 report.config.basis；这保留 LEVELING_README「依据出处独立于数值」的精神，不绕过语义（依据存在，只是来源从人换成算法且公开可审）。
- 请求失败显式 reason：`ground_auto_candidate_invalid: <detail>`、`ground_auto_regions_invalid: <detail>`、`ground_auto_consensus_invalid: <detail>`，不静默回落默认区域。

## R2 锚点对照（只比较不复制）

auto 模式在 cap_20261004_202456/_203349 上跑出的 TLS `pitch_deg` 与 `03_RESULTS.json` 的 `estimators.tls.pitch_deg=26.62326136` 差值必须 <1.5°；roll/d 差如实报告（无门）。差值超 1.5° 则 P03-A 保留 FAIL 交付（证据照存），不裁数据/不降阈。

## 负路径

1. `n_z<.85 or d∉[.8,1.8] or support<.3` → candidate_invalid
2. 连通域<4 → regions_invalid
3. 网格空/凸包无有效点 → regions_invalid
4. leveling `run_job` 三法质量门/两两一致性仍走 GLW01 既有；auto 不另开门。

## 数据/代码边界

- 改动文件：`pc_apps/human_replay/leveling_lib.py`（新）/ `leveling.py`（仅上述 3 处小改）/ `leveling.js`（auto 提交按钮与显示）/ `replay.js`（消费 transform）/ `human_replay_lib.test.js`（如纯函数进 lib）/ `leveling_auto_test.py`（新）。
- GL-W01 手动 UI/降级/导出语义不变；`leveling_test.py` 全量回归。
- 不动 LEVELING_README.md 的「四级确认哲学」语义，只追加一节「auto 模式」。
