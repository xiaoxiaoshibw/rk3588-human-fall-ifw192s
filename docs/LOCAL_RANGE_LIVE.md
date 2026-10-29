# 本机实时 2D→3D 算法入口

## 2026-10-27 现场地面与连续报警契约

本轮入口 `pc_apps/range_fall/live_site_check.py`：先完成隔离构建并复制 service，再打开Qt；Qt订阅原始云和状态后才开始唯一45秒上游窗口。运行命令和最终实际结果在 `docs/evidence/2026-10-27_live_ground/`，历史记录中的 ground=false 不代表本轮最终加载状态。

`live_bridge.py --fit-ground-out NEW --site-id ID --duration 45 --wait-client` 只尝试一次现场拟合。取连续25帧选地面、后续3帧独立验证，原始点只在RAM。复用 `floor_roi.detect_floor_regions_v3`（包括v1/v2路径）及 `leveling_quality.compare`，不把当前有人画面声明为空场。选区保留整个XY柱的高度，墙、家具、人物造成的高度跨度/法向/残差失败会排除整个区；选择最低水平连通片，并检查空间覆盖、四区独立支撑、TLS/SVD/RANSAC一致和逐帧稳定。安装高度0.8–1.8 m、seed法向z≥0.8沿用既有拟合入口的先验，不能当安装真值；不适用时拒绝，不自动调宽。

`GROUND_FIT.json` 保存同一次拟合的来源URL、源身份、完整header与wire SHA、平面、候选/选区、残差、质量和稳定性；`SITE_GROUND.json` 的SHA指向它。`site_ground()` 拒绝旧式只有声明的现场地面和离线地面；必须有28帧连续来源与通过的质量证据，法向朝传感器、offset>0。高度直接复用 `RangeRuntime` 的同源目标来源行，公式为 `raw_xyz·normal + offset_m`（米），无显示配平参与。

拟合异步执行，已发出的在线前缀不回填；加载只影响后续帧。每帧在冻结的完整高度选区复用原质量统计，至少3个独立区通过才允许高度与相关报警。遮挡/支撑不足/平面漂移立即使当帧不可用并清历史；恢复支撑可恢复计算，但不自动重拟合。源回退/标定变化必须重绑。普通WebSocket短重连清时间历史，连续同源header仍可接流；真正超过既有2 s源缺口仍由原runtime停用背景。该几何监视不能证明物理地面身份，也不能检测所有沿平面平移/旋转，物理安装适用性仍UNKNOWN。

断流、过期、坏输入、地面换版统一清低位、姿态、动态历史；界面仍执行完整header、SHA、350ms预览等待和ACK检查。Qt现在透传原动态规则的证据与拒绝原因。`ground_alert_v1` 仍是0.7 m/1.5 s持续低位提示，蹲/坐地可触发。`ground_alert_gap_v2` 只在账本做候选比较：唯一同ID预测轨迹的≤0.3 s空洞可暂停证据，空洞不计持续时间且不报警，换ID/竞争/地面无效清空；它不替换原提示。原动态疑似需0.35 m下降、0.35 m/s下降率、1.5 s低位及水平跨度≥0.6 m或顶部≤0.7 m，confirmed仍关闭。无真实跌倒GT，准确率/召回率及人体身份均UNKNOWN。

2026-10-27 后续实测：用户再次要求代操作后，正常前台入口成功运行45秒，431/431帧处理、主链/客户端覆盖0、397帧有几何目标；候选竞争31帧、跟踪ID切换3次，仍不能认定稳定锁同一个人。Qt启动时构建占用了大部分窗口，仅最后22帧进入界面；发现并修复目标框重复Position属性导致的D3D管线错误，以及启动URL未同步到输入框的问题。修复后离线loopback 3项 + UI巡检1项通过，没有追加真实流测试。证据见 `docs/evidence/2026-10-27_live_operate_user/`。下方两次工具拦截是此前历史记录，已不代表当前运行结果。

短时测试顺序：先完成 `python -B -W error console_v2/app_dev.py build --isolated-run` 并确认构建成功，再开始有时限的bridge，Qt复用已经构建的host；避免先消耗45秒接流窗口再编译Qt。CLI `--live-url` 现在会同步地址框，实时只读测试结束后连接关闭，不自动重启或切回旧板端。

本机通过 Foxglove **只读订阅原始 `/innolidar_points`**，运行相同 ScanGrid / RangeRuntime / GroundAlertObserver，提供本机 `ws://127.0.0.1:8952` 给 Qt。板端旧识别节点断流不会阻断本机算法。没有 ROS 发布、部署、服务启停、点云录制或模型。

入口 `console_v2/start_local_range.cmd`。默认仅实时距离图，明确显示 `background_not_declared`，不把任意启动画面冒充空场。

已有经声明的内存背景，用 `--background-url http://127.0.0.1:PORT/background --background-manifest PATH` 交接。交接仅允许无代理、无重定向的 loopback HTTP，校验50帧清单、标定、形状、观察数与原有背景参数；只读NPZ，不落地点云或背景。当前这次用户明确授权的50帧已在 `docs/evidence/2026-10-27_live_local/EMPTY_BACKGROUND_MANIFEST.json` 登记；内存服务URL记录在同目录 `EMPTY_BACKGROUND_SERVICE.json`。服务退出后背景不存在，不能只凭旧清单继续运行。

另可在确实空场时显式加 `--declare-empty-prefix`，只用启动后的连续50帧建立背景；不要在人已经在场时使用。两种背景模式互斥，背景冻结、不把后续人物学入背景。换源、回退、坏消息或上游重新连接会要求重新绑定，不能把未知输入自动当成新空场。

Qt「实时锁定」填本机URL；前缀仍 `/single_target_live/`，原始话题仍 `/innolidar_points`。该前缀只在本机 WebSocket 内，不在板端发布。回放默认启动和功能抽屉仍由用户选择；这个脚本不会替用户切换Qt页面。

主点云独立转发；算法和部位各有最新任务槽。部位使用独立Python进程，避免GIL抢占主跟踪；超过350ms显示期限的部位结果丢弃，不套到下一帧。原始源header、完整消息SHA、目标源行、骨架支撑中位数、PNG SHA和尺寸经C#验证后才交给Qt。无新结果/过期/断连清旧目标与距离图。

地面单独绑定。拒绝把离线 `BOUND_GROUND.json` 直接改名用于现场。显式 `--ground FILE --site-id ID` 需要 `live_site_ground/1` 声明：`binding={siteId,frameId,gridSha256}`、`plane={normal,offset_m}` 与带SHA的provenance原始JSON一致；坐标为当前原始传感器系。声明不等于物理验证，安装改变后必须重新绑定。无现场地面时允许几何目标跟踪和距离图，**低姿态判断不可用**，不产生 confirmed。

依赖仅PC已有 Python/NumPy/websockets；不引入板端依赖。完整body区域着色仍在网页，实时Qt输出部位点数与区域骨架，不能冒称解剖关节或人体分类完成。

验证入口：`python -B -W error -m unittest test_live_engine`（pc_apps/range_fall）与 `test_local_bridge`（console_v2/app，按现有测试约定指定FALL_APP_DLL/HOST）。`live_tracking_check.py --session ... --reference ... --ground ... --out NEW` 将既有真实会话重封为驱动ROS1消息，逐帧对比目标、部位、PNG和因果提示；这是本地消息替身，不是现场效果。

## 2026-10-27 本轮状态

用户已明确声明空场并授权接下来的50帧；实际收到50个连续源帧，40788个背景像素观测充足，背景只留在本机RAM。内存服务已停止订阅上游，不会继续录制或重新学习。

1166帧既有会话重封为26字节驱动ROS1消息后，与完成结果的目标源行/ID/高度、PNG、部位源行和提示逐帧一致。Qt本机消息替身端到端最终主链30/30处理、0覆盖，部位25帧赶上显示期限，4个待处理部位被新请求替换；过期/缺失不借旧部位。最初两轮线程版只处理19/30，失败账本保留，最终改为独立进程。

**真实45秒推理未执行。** 本机启动真实源适配器先后被自动审批拒绝；第二次已有用户明确的45秒授权，仍只返回 `blocked by policy`。没有换工具或启动方式重试，没有真实锁定、告警或现场性能结论。

供用户在自己的终端复现的命令（未由agent执行成功）：

```powershell
console_v2\start_local_range.cmd --background-url http://127.0.0.1:54723/background --background-manifest docs/evidence/2026-10-27_live_local/EMPTY_BACKGROUND_MANIFEST.json --duration 45
```

内存服务必须仍在运行且雷达来源/安装未变；端口失效不能仅凭旧清单伪造背景。Qt实时地址为 `ws://127.0.0.1:8952`。目前没有绑定现场地面，几何目标与距离图可以运行，低姿态提示明确不可用。不能把本机消息替身截图上的LIVE字样当成真实现场实测。

证据：`docs/evidence/2026-10-27_live_local/CHECKS_FINAL.json`、`POLICY_BLOCKS.json`、`MOCK_E2E_SUMMARY.json`，最终全帧检查在`full386_final/`与`full780_final/`。
