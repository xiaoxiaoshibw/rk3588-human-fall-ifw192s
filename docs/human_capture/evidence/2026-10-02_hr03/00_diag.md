# HR-03 集中诊断：操作矩阵 → 函数映射

日期 2026-10-02；写码前一次性过，不允许跳。

## 数据契约（板上真实 meta 事实，从 3 个现成会话盘面验证）

板上 meta.json 真实字段（比 README §2 多）：

| 字段 | 取值/说明 |
|------|-----------|
| format / format_version | `"human_capture_session"` / `1` |
| session_id | `cap_YYYYMMDD_HHMMSS` |
| created_iso / time_domain | 继承源 |
| duration_sec | `frames[last].bag_time_sec - frames[0].bag_time_sec`（剪辑后重算） |
| frame_rate_hz_measured | **3 个样本全部是 None（字段不存在）** → 剪辑不生成此字段 |
| point_layout.stride_bytes | 28（fields x,y,z,intensity,ring,timestamp + pad@18/24） |
| point_stride_bytes | 28（top-level，剪辑继承） |
| point_file | `"points.bin"` |
| topics / sensor / total_dropped_points / topic_message_counts | **剪辑不继承，不落盘**（IMU/状态流不能切，落虚假字段就是谎） |
| human_annotations | 剪辑清空 `[]` |
| total_points | `sum(count_points)` 剪辑重算 |
| extraction | `{tool:"human_replay_trim/0.1", source_session:<原 sid>, source_range:[s_seq, e_seq]}` 全替换（源 extraction.source_bag_* 对剪辑而言已失真） |
| frames[i].seq / stamp_sec / stamp_nanosec / dropped_points | **原值继承**（不重编号） |
| frames[i].offset_points | **重新 0 起累计**（count_points 不变） |
| frames[i].bag_time_sec | **减去剪辑首帧的 bag_time_sec**（剪辑内 t=0 起） |

字节切片：`[frames[s].offset_points*28, (frames[e].offset_points + frames[e].count_points)*28)` —— 纯字节流，零重编码，零 dtype 解析。

## 操作矩阵（每条 → 函数/守门）

| # | 场景 | 触发面 | 守门位置 | 行为/错误信息 |
|---|------|--------|----------|---------------|
| M1 | startup：合法 src + 合法 [s,e] | `trim.js` CLI | `compute_trim_slice` → `rewrite_meta_for_trim` → `pre_trim_check` | 生成 dst/，落 meta+bin+`__trim_record.json`，exit 0 |
| M2 | --start > --end / 越界 [0, n-1] / 非整数 | `trim.js` argv | `compute_trim_slice` 越界守门 | `区间越界: ...`，exit 1 |
| M3 | seq 非连续（跳帧：frames[i].seq 不 +1） | 同上 | `compute_trim_slice` seq 守门 | `seq 非连续: frames[k].seq=X 期望 Y`，exit 1 |
| M4 | points.bin 实文件字节数 ≠ `max(offset+count)*stride`（meta 说谎/文件被截） | 同上 | `compute_trim_slice(meta, s, e, bin_size_bytes)`（bin_size 由调用方 `fs.statSync` 取） | `总点数与 points.bin 字节数不符:`，exit 1 |
| M5 | 目标目录已存在 | `trim.js` | `trim.js` existsSync 守门（早于一切 IO） | `目标目录已存在: <dst>`，exit 2 |
| M6 | 磁盘余量 < 剪辑后 bin 字节 + slack | `trim.js` | `free_bytes_for_path` 逐层向上找已存在祖先 → `pre_trim_check` | `磁盘空间不足: 需 X 字节 余量 Y 字节`，exit 3 |
| M7 | 同 sid 再剪同 [s,e]（重跑） | 同 M5 | existsSync | 同 M5（拒绝 overwrite，符合"人工删旧目录后重跑"预期） |
| M8 | src 目录缺 meta.json / points.bin | `trim.js` | fs.existsSync 早出 | `src 缺 meta.json/points.bin`，exit 1 |
| M9 | 空格路径 / 非 ASCII 路径 | `trim.js` argv 透传 | 全部走 `path.join + fs.createReadStream/WriteStream` | 无需特殊处理（spawn.argv 已脱 shell） |
| M10 | points.bin 切片实写 | `trim.js` | `pipe_slice(src_bin, dst_bin, start_byte, end_byte)` | `fs.createReadStream({start,end-1}).pipe(WriteStream)`，**不全量读 40MB**（ponytail: stream 一条链，够用；巨量会话需分包再升级） |
| M11 | dst meta / bin sha256 回写 | `trim.js` | `sha256_file` | `__trim_record.json` 收录双 sha256 + src_sid + range + 总点数 |
| M12 | 浏览器按"剪辑" | `replay.js` HUD | 复用 `frame_slice` 算两 idx 对应 seq → `trim_command_string` | 复制命令字符串到剪贴板/粘到 `<textarea>`，用户自取——**UI 不落盘** |
| M13 | AI 读剪辑产物 | `load_session.py`（参考读法） | 字段集保持与源同 schema（除 extraction + annotations） | `python -B load_session.py <dst>` 应跑出 frame listing；annotations=[] 合法 |
| M14 | 速度档兼容（R6） | `replay.js` default_fps | 剪辑 meta 不落 `frame_rate_hz_measured` → lib `default_fps` 回退 10 | 产物 fps=10（NN：源 9.68 由 N frames/源 duration 推也≈9.7，新一差；`default_fps` 已有回退，不另造段落 |
| M15 | ui trim 区复位/取消 | `replay.js` | "剪辑起点/终点" 按钮置位 + "取消剪辑" 复位 | 不构成数据动作；HUD 显示选中区间 |

## 已知矛盾裁决

- **`frame_rate_hz_measured` 裁剪后表达**：N 帧剪辑的 duration ≈ (N-1)/原 fps，真实 fps = (N-1)/duration = 剪辑自我一致。但**板上 3 个样本都没这字段**（None），为避免引入"剪辑特有字段"，决定**不落**——消费者 `default_fps` 回退 10Hz，误差 <5%。**理由：ponytail + 契约最小面**。若 Codex 验收认为"沿用"就是"必须有"，后续单独立项。
- **`topic_message_counts`/`total_dropped_points`/`topics`**：同上丢弃。理由：剪辑只切点云帧，IMU/状态 684/29 条无法切片；落虚假值比不落更伤下游。
- **README §2 里 `extraction.point_step_bytes` 字段名 vs 板上 `point_step_bytes_src`**：以板上为准；剪辑干脆重写 extraction，不沾旧字段冲突。

## 剪贴板限制硬化说明

浏览器 `navigator.clipboard.writeText` 需要 secure context + 用户手势 + focus；用户选目录后处于 HUD 上合适的"剪辑"按钮 click 里调用——具有手势。失败 fallback：textarea + `document.execCommand('copy')` + 用户手动 Ctrl+C。零依赖零弹窗。

## 大文件不全量读策略

`cap_20261002_163621` = 122MB。剪辑 [s,e] 通常切中段。`fs.createReadStream({start,end-1})` 是内核级拷贝，零内存驻留。`pipe` 链背压由 node 自带。sha256 用流式 update。
