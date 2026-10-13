# 采集 Run Sheet · HUMAN-UNIFY-R1 数据补齐轮

**版本**: 2026-10-10 · **状态**: 待用户执行
**目标**: 覆盖统一核心 (BASE_A/BASE_B/U1/U2/U3) 当前未能量化的场景缺口
**总耗时**: ~25 分钟录制 + ~3 小时你自己的 QC 标注 (按段算)

---

## 1 · 装备与场地 (录制前检查)

| 项 | 状态 | 备注 |
|---|---|---|
| RK3588 板 (`192.168.31.58`) 在线 | ☐ | `capture_server.py` 已跑 |
| 雷达激光雷达雷达 IFW192S 已配平 | ☐ | 空场模板 (leveled) 在板端已 LOCKED |
| 板端 `capture_state` 空闲 | ☐ | 用 `curl http://192.168.31.58:8766/api/v1/record/current` 查 |
| PC 磁盘 ≥5 GB | ☐ | 每段 ~200-400 MB |
| 空场 30 秒无人 | ☐ | 本场唯一的 REF envelope 来源 |
| 皮尺 + 地面胶带 | ☐ | 离雷达 0.5m 起， 每 0.5m 打标 |
| 场地家具位置固定 | ☐ | 不要换沙发/柜位置， 否则 REF 失效 |
| 灯光 | ☐ | 与先前 114641 系列一致， 别动 |

> **重要**: 不要换 leveling。空场 REF 只能用一个 — 否则每段都要重录空场， 时间×N。

---

## 2 · 地面参考标记 (10 分钟)

以雷达安装点为原点 (0,0)， y+ 方向为雷达 视靶 方向 （约 240°H 视场中线）:

```
y+ (远场)
  ↑
  |  ● y=5.0m   (贴 "5.0" 胶带)
  |  ● y=4.0m   (贴 "4.0")
  |  ● y=3.0m   (贴 "3.0")
  |  ● y=2.5m   (贴 "2.5")
  |  ● y=2.0m   (贴 "2.0")
  |  ● y=1.5m   (贴 "1.5")
  |  ● y=1.0m   (贴 "1.0")
  |
  ├───────────────── x+ (横轴)
  |
  +--x方向每 1m 标记 （只在 y=2.0m 和 y=4.0m 两条线上）
```

**用地面胶带贴出**:
- y=2.0m 水平线， 上贴 x=-2,-1,0,+1,+2 m 5 个标记
- y=4.0m 水平线， 上贴 x=-2,-1,0,+1,+2 m 5 个标记 （如果你房间够深；不够就只画 y=2m 那条）

这些是**演员的走线参考**。

---

## 3 · 采集段清单 (9 段， 每段 20-60 秒）

按下面的顺序录， 段间 silence ≥3 秒 （便于切分）。**不要**在段间移动家具。

### 段 1 · S1-empty-with-furniture (30 秒） — 必录
- **目的**: 补充 REF envelope; 同时测 BASE_A/B 在"已有家具"上的误报率
- **动作**: 全场无人， 任何摄像头/手机静音
- **验证**: 录完后看一眼 film_person 应该有震街头朝上的空场
- **文件名建议**: `cap_<日期>_<时间>_empty`

### 段 2 · S3-walk-x-near (20 秒） — 必录
- **目的**: 单人**横向**走， 与 154007 对应， 补 near-distance
- **动作**: 人**赤脚或便鞋**， 从 (x=-2.0, y=2.0) 起， 沿 2.0m 胶带线行走到 (x=+2.0, y=2.0), 匀速 （约 1 m/s ≈ 慢走）, 计 4 秒； 然后折返走回来 4 秒； 再走一次 4 秒； 共 12 秒。然后原地站立 5 秒作为保留测试。
- **验证**: gt 标 walk / stand 帧混
- **文件名**: `cap_<日期>_<时间>_walk_x_near`

### 段 3 · S3-walk-y-far (25 秒） — 关键 ⭐
- **目的**: 单人**纵向**走， 从近场走到远场 — **直接测 recall 距离衰减** （旧库 0 段）
- **动作**: 从 (x=0, y=1.0) 起， 沿 y 轴 走到 (x=0, y=5.0), 匀速 1 m/s 共 4 秒； 站立 5 秒； 然后返回走到 (0, 1.0) 共 4 秒； 站立 5 秒。再重复一次。
- **特别**: 走过 y=3.0 / 4.0 / 5.0 时**慢一拍** （感知器离散点变少）
- **文件名**: `cap_<日期>_<时间>_walk_y_far`

### 段 4 · S4-walk-stop-walk (30 秒） — 必录
- **目的**: 评估 track fragmentation （旧库 154007 场景的最佳对照）
- **动作**: 从 (x=-1.5, y=2.0) 走到 (+1.5, 2.0) 约 3 秒； 立刻停下**钉住站 5 秒**（双手下垂自然）; 再走到 (-1.5, 2.1) 3 秒； 停 5 秒； 再走一圈回来 3 秒。
- **特别**: 停的瞬间不要微微摆动 — 这是测**静止保留**
- **文件名**: `cap_<日期>_<时间>_walk_stop_walk`

### 段 5 · S5-turn-in-place (20 秒） — 中
- **目的**: track 连续性 （旧库 0 段）
- **动作**: 站在 (0, 2.0), 双脚不动， **原地转身**: 面北 → 面东 → 面南 → 面西 → 面北， 每个方向停 2 秒。转身约 1 秒一个 90°。
- **文件名**: `cap_<日期>_<时间>_turn_in_place`

### 段 6 · S6-occlusion (25 秒） — 关键 ⭐
- **目的**: ID switch / reentry （旧库 0 段）
- **动作**: 现场需要一个**沙发/衣柜/屏风**在 (x=1.5, y=2.5) 位置附近 （你已经有一个沙发在左下） — 人从 (x=0, y=2.0) 走到沙发背后 (x=2.0, y=2.5), 在沙发后**完全消失 ≥2 秒** （蹲下或低身）, 再从沙发另一侧 （x=3, y=2.0) 走出。
  - **重复 2 次**
  - **特别**: 人从雷达视野完全消失的帧， 预期 tracker lost>0
- **文件名**: `cap_<日期>_<时间>_occlusion`

### 段 7 · S7-far-5m (20 秒） — 关键 ⭐
- **目的**: recall 距离衰减端点
- **动作**: 人站到 (0, 5.0) 远场标记， 站立 10 秒； 然后走到 (0, 4.0) 站 3 秒； 再走到 (0, 3.0) 站 3 秒； 再走到 (0, 2.0) 站 3 秒； 最后走回 (0, 5.0)。
- **文件名**: `cap_<日期>_<时间>_far_5m`

### 段 8 · S9-two-person-cross (25 秒） — 中
- **目的**: ID switch 主战场 （旧库 0 段）
- **动作**: 两个人：
  - A 从 (-2.0, 2.0) 走到 (+2.0, 2.0) 匀速 1 m/s
  - B 同时从 (+2.0, 2.0) 走到 (-2.0, 2.0) 匀速 1 m/s
  - 在 (0, 2.0) 附近**相遇， 但不要接触**, 各绕半步距离
  - 到达对面后**各停 5 秒**
  - 然后**原路返回**相遇一次
- **文件名**: `cap_<日期>_<时间>_two_person_cross`

### 段 9 · S8-still-retention-long (60 秒） — 关键 ⭐
- **目的**: 真静立 1 分钟， 测 retention/背景吞人边界
- **动作**: 站到 (0, 2.5), **完全不动 60 秒**（可以轻微站立呼吸， 不要摇）, 然后离开画框。
- **特别**: 这段直接验证 BASE_A 是否把人吸进背景 （预期： 5-10 秒内消失）
- **文件名**: `cap_<日期>_<时间>_still_60s`

---

## 4 · 录制操作 (每段）

```bash
# 1) 检查板端空闲
curl http://192.168.31.58:8766/api/v1/record/current || echo "idle"

# 2) 开始录制
curl -X POST http://192.168.31.58:8766/api/v1/record/start

# 3) 等段 N 秒 (用秒表, 不要看表猜)
sleep <N>

# 4) 停止
curl -X POST http://192.168.31.58:8766/api/v1/record/stop

# 5) 板端会把段写入 <新 cap_ timestamp>
# 等 ≤30 秒板端 finalize

# 6) PC 拉回本地 (在 D:\Code\ldiar 里)
python pc_apps/human_replay/fetch.py
# fetch 会自动从板端下载新 session 到 captures/remote/

# 7) 改名 (将 sid 重命名为语义名, 不破坏目录)
# 在 human_replay webui (console.exe) 里直接改
```

**每段后立即跑起**: `python render_with_gt_box.py <sid> 0 frames/sandbox_<sid>_f0000.png` 验证渲染正常 + 有 GT 覆盖。

---

## 5 · 录制当天你自己 QC (录制后 1-2 小时）

1. **我帮你跑**: `python render_all_frames.py --sid <sid>` — 我把你的新段渲成"带刻度 + 自动 GT 框" PNG
2. **你逐帧看图** （我用同样的 191 帧/段 × 9 段 ≈ 1720 帧； 跟我做 154007+143945 一样）:
   - 在 frames/ 里缩略图看图
   - 把不准的帧写进 `qc.json` (OK/miss/wrong_pos 三类）
3. **我合入 GT**: 把你的 qc 写回 `gt_labels/<sid>.json`, 喂给 engine 跑 BASE_A/B/U1/U2/U3 → 量化 recall/F1/time-to-detect

---

## 6 · 录制规矩 （必须遵守， 否则数据废）

| 禁止 | 原因 |
|---|---|
| 换 leveling | 整个 REF envelope 失效， 全部要重录空场 |
| 移家具 | 同上 |
| 段间没 silence ≥3 秒 | 段难切 |
| 多段共录 | 难分 GT 段 |
| 人穿反光大白衣 | 雷达强度高， 可能影响 intensity feature |
| 演员在录制中自己喊"3-2-1" | 会录到声音， 但本身没问题； 但作为时间戳记号 OK |
| 段在 30 秒内全部切 | 每段 ≥5 秒才有意义 |

---

## 7 · 交付列表 (录完后给我的）

```
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_empty/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_walk_x_near/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_walk_y_far/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_walk_stop_walk/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_turn_in_place/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_occlusion/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_far_5m/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_two_person_cross/
captures/remote/cap_<YYYYMMDD>_<HHMMSS>_still_60s/
```

每段: `meta.json + points.bin` (fetch 自动）
我把它们渲染→出 QC 帧→你 QC→合 GT→跑统一核心 quantification

---

## 注：关于天气/房间光线

不影响激光雷达， 但影响你读 QC PNG 的颜色对比 — 建议在日光灯或白天录， 不要黑灯瞎火。
