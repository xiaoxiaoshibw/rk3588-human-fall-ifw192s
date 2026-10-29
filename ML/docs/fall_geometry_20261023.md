# 秒制几何与事件评测（2026-10-23）

实现为本地旁路，不改变生产跌倒状态。目标是让输入、时序和判分可核对；IFW192S 效果仍 UNKNOWN。

## 可运行入口

```powershell
python -B -W error -m unittest discover -s ML/src
python -B -W error ML/src/replay_fall_geometry.py --session data/sessions/cap_20261018_110029 --output docs/evidence/<new_directory>
python -B -W error ML/src/prepare_fall_events.py --frames <replay_directory>/geometry_frames.jsonl --annotation <annotation.json> --output <new_cache_directory>
python -B -W error ML/src/evaluate_fall_events.py --input <evaluation_input.json> --output <new_report.json>
python -B -W error ML/src/urfall_geometry_proxy.py --root data/downloads/urfall_20261023_v1 --output <new_directory>
```

每个输出目录必须为新目录。无真实标注时不生成真实召回；`synthetic_e2e/` 仅验证软件契约，不是人体效果。

## 数据契约

- `fall_geometry.py` 接收米制目标 XYZ、秒制时间、身份/代际/标定绑定、实测状态和显式地面平面。逐帧输出地面相对高度、主轴角度、垂直跨度、速度与质量。缺地面/坏点/预测/断档输出 UNKNOWN，不补造观测。
- 固定开发规则：直立 ≤30°、低位 ≥65° 且跨度 ≤1.10 m、质心高度 ≤0.8 m、下降 ≥0.35 m、观察到中间姿态；下降上下文 2.0 s、低位保持 0.3 s、恢复直立 0.5 s、最大帧间隔 0.5 s。各值尚未得到目标域效果证据。
- 身份/代际/标定改变清状态；同目标缺测打断下降/保持证据，已触发事件不因缺测当作恢复。只有实测恢复才释放，防止同一次事件因掉锁重复触发。
- `frames.npz` 保留全帧、NaN 与逐元素 mask、绑定和 `segment_index`。-1 是 UNKNOWN；模型不得跨 segment 构上下文。标注事件和各窗口一律保留，空输入/未知标签不伪装成可训练负例。
- `fall_events_v1` 标注时间为视频秒，`LiDAR秒 = 视频秒 + clock.offset_s`。标注/原始输入/回放 ledger/代码各有 SHA；缓存校验回放 ledger 与 SUMMARY 绑定，不默认视频和雷达同钟。
- `evaluate_fall_events.py` 的输入为 `sessions` 数组，每项含 `annotation`、`alarms`（每项 `alarm_s` 为雷达秒）、显式 `negative_intervals` 与可选 `unknown_intervals`（区间为视频秒）。主召回包含全部 confirmed 真值事件；legacy `observable` 仅作诊断，不能来自几何闸门。
- 一对一事件匹配范围 `[t_start,t_impact+1.5s]`；重复报警单列。及时事件要求延迟不确定区间上界 ≤1.5s。没有负例监测时长就不输出每小时误报。UNKNOWN 监测时长保留在总时长，另报覆盖率。Wilson/Poisson 区间是描述性区间，不把同人多次事件当独立人员泛化证明。

## UR Fall 补充对照的边界

来源：[官方页面](https://fenix.ur.edu.pl/~mkepski/ds/uf.html)，许可 CC BY-NC-SA 4.0，用于非商业学术开发。官方说明 PNG16 深度为 `C*pixel/65535` 毫米；前视跌倒 C=6000，前视日常 C=7000，不能混用。

下载包括官方特征表、70 份同步表、预先选择的 fall-01/adl-01 前视深度 ZIP。保留原始下载及 SHA，两个 ZIP 做 CRC 和每张 PNG 的 16 位灰度头检查。未核实相机内参，未将深度像素伪造为已标定 XYZ。

补充运行只用官方已分割人体的 H/D/P40，H/D 从毫米转米，共用因果下降与锁存逻辑。它不具备原始 LiDAR 的点集提取问题，也不具备 PCA 主轴输入；这是不同的几何表示。逐帧姿态标签只用于事后参考，HHmaxRatio 不输入（站立参照可能包含未来信息）。主体编号缺失，不能宣称人员留出。

固定规则首次对照：30 条 fall 中 29 条在姿态过渡参考窗内触发，40 条 ADL 中 0 条触发；这是已分割深度特征代理结果，不能写成 96.7% 真实跌倒召回或 IFW192S 成绩。首次低位标签不是精确落地 GT，首个过渡标签不是经独立视频确认的起点。

发现官方 `adl-37` 特征到 350 帧，同步表只到 330 帧。首次严格运行因此拒绝，失败目录保留；后续把无时钟的 20 行逐行记为 UNKNOWN，不外推时间，仍保留全部 70 个序列。未按结果调参。

唯一代理漏检为 fall-21：低位开始 1.568 s，序列最后时间 1.801 s，仅 0.233 s，未达到固定的 0.3 s 低位保持；它具备下降证据，应输出 low_hold_pending，而不是 low_without_descent。该例仍计为代理漏检，不缩短保持时间、不剔除分母。

M2 的原始深度重建/地面和分割验证仍待补足。下一步处理原始输入与作者特征的差异，再决定时序模型的训练表示；M3/M4 需要现场人员与设备，M6 需要板端执行授权。计划不把这些依赖当作本地代码已完成的证据。
