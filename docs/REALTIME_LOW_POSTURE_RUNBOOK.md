# 实时低位/倒地提示：明天现场使用手册

2026-10-28。适用当前板端 release `7530fd08…` + 本机 Qt（已修复配平告警和巡检）。

## 0. 先明确它是什么

- 系统输出的是 `ground_alert_v1`：目标中位离地高度 **≤0.7 m 且持续 ≥1.5 s** 的“持续低位提示”。
- **蹲下、坐地也可能触发**；`confirmed` 始终关闭。它不是跌倒确诊，准确率/召回率仍是 UNKNOWN。
- Qt 上两处可见：顶部状态条右侧的红色「低位提示」徽标；结果卡大字的「持续低姿态提示」和持续时间。

## 1. 开窗前 3 分钟只读检查

板端进程（不重启）：

```powershell
ssh ldiar-wel "ps -ef | grep range_service_node | grep -v grep"
```

应看到 release `7530fd08…`、`--declare-empty-prefix`、`--site-id board_20261027_level`。

状态（只读探针，脚本在 `docs/evidence/2026-10-28_qt_live_alert_fix/BOARD_STATE_PROBE.py`）：

```powershell
Get-Content -Raw docs\evidence\2026-10-28_qt_live_alert_fix\BOARD_STATE_PROBE.py |
  ssh ldiar-wel "docker exec -i slam-localization bash -lc 'source /opt/ros/noetic/setup.bash; python3 -'"
```

必须同时满足：

- `service.releaseId=7530fd08…`、`instanceId=live_range_808475d4…`；
- `background.status=ready`；
- `ground.available=true`，SHA `4b0c1700…`；
- `health.inputStatus=receiving`。

任一项不满足：**不要开始测试**，按第 7 节重新初始化。

## 2. 现场布置（决定成败）

- **清掉视场里新增的静止物**。当前服务锁着一个 20 个源行、高度 1.19 m 的静止小目标（`g35_t0155`）；它可能是箱子/椅子/桌面物。它会先占住目标，真人进入后是否切换没有保证。
- 垫子、保护员就位；垫子位置在窗口内不要移动。
- 人从视场外进入，避免一开机就站在画面里。

## 3. 启动 Qt

先关掉现在开着的旧窗口（它加载的是修复前的 QML），然后：

```powershell
console_v2\start_latest.cmd --live-url ws://192.168.31.58:8765
```

入口会先增量构建当前源码，再启动。进入「☰ 功能 → 实时锁定」，确认：

- 已连接，`instanceId` 与板端一致；
- 3D 有目标框、结果卡有高度（例如 1.0–1.3 m）；
- 地面有效；「配平视图」显示「已配平」（有地面时自动配平）。

## 4. 动作（约 40 秒）

| 时间 | 动作 | 观察 |
|---:|---|---|
| 0–10 s | 从 3 m 外进入，站定 | 目标锁定、高度出现 |
| 10–20 s | 横向走动 2–3 m、转身 | 同一 track 是否连续 |
| 20–25 s | 蹲下或坐地 ≥2 s | 可能触发「低位提示」，按设计预期 |
| 25–30 s | 起身走出 | 提示应清除 |
| 30–40 s | 垫上受保护躺下 ≥5 s，再起身 | **主验证段**：应触发并保持，起身后清除 |

不做无保护跌倒；受试者可随时停止。

## 5. 判定口径

- 躺下后，从首次 `heightMedianM<0.7` 起 **≤2.0 s** 出现「低位提示」（1.5 s 规则 + 余量）；
- 起身后 **≤1.0 s** 清除；
- 站立/走动段不应触发；
- 蹲/坐段触发按设计预期，不算误报；
- 记录：触发时刻、持续秒数、清除时刻、`track_id`、高度。

建议把 Qt 结果卡和顶部状态条一起截一张图，作为当天记录。

## 6. 常见问题

| 现象 | 先查 |
|---|---|
| 「配平不可用」 | 当前会话没有有效地面（`ground.available=false` 或 SHA 不匹配）。高度/低位判断也会一起不可用 |
| 目标一直锁着不动的物体 | 视场里有开窗后新增的静态物；移出，或按第 7 节重新空场初始化 |
| 有目标但没有高度 | 地面丢失/支撑门失败；看结果卡原因 |
| 没有目标 | 背景未声明、输入断流、目标未进入/太小；看 `health.inputStatus` |
| 状态几秒不动 | 服务 500 ms TTL；检查板端进程和网络 |
| 躺下不触发 | 目标中位高度没降到 0.7 m 以下（遮挡/只看到部分身体）、目标被切换、地面失效 |

## 7. 如果板端重启过（背景会丢）

RAM 背景不落盘，重启后 `background.status` 会变成 `background_not_declared`。此时：

1. 清空现场（人和其他移动物退出视场）；
2. 由维护人按既有识别服务启动方式重新声明空场（`--declare-empty-prefix`），等 50 帧背景 ready；
3. 用当前空场重新拟合现场地面（`--fit-ground-out` + `--site-id`），确认 `ground.available=true`；
4. 再按第 1 节复查。

不要在有人站在画面里时重新“学背景”，也不要把旧背景清单当新空场。细节见 `docs/BOARD_RANGE_SERVICE.md`。

## 8. 不能写进结论

- 不是确认跌倒；没有跌倒正例 GT，不能写准确率/召回率/误报率。
- 不写“稳定锁同一个人”（人体身份 UNKNOWN）或“物理地面有效”。
- 单次演示不能外推到其他场地/安装角度。
- `nohup` 没有重启自恢复；窗口期间不要重启板端服务。