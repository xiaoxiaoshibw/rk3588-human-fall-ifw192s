# Qt 控制台应用

独立于 `spike/` 的真实会话与识别结果查看器：Qt 6 / C++17 / QML / Quick3D，C# / .NET 8 负责数据、播放和协议。当前应用为本地开发版本，通过固定快捷入口运行当前源码，未发布新单文件包。

## 运行

### 固定快捷入口（2026-10-26）

桌面双击 **雷达控制台（最新版）**，或从任意目录运行仓库里的`console_v2/start_latest.cmd`。
快捷方式指向固定脚本，每次调用当前`app_dev.py`增量构建C#和Qt/C++，构建成功后才启动；没有回退旧exe的分支。更新本仓库应用代码后继续使用同一个快捷方式，不需要重新找exe。

快捷入口使用`--isolated-run`：服务构建缓存位于`.tools/app-build/service`，每次把当前DLL及依赖、Qt exe和运行库放到本次`.tools/app-evidence/<id>/service|runtime`运行。缓存本身不被执行，旧Qt窗口/DLL不会阻塞下一次构建和复制；旧窗口可以保留，新点击会打开新版本窗口。QML从当前`app/native/Main.qml`加载并热重载，C#/C++修改在下次点击时构建生效。

构建控制台默认最小化；失败时停止并保留控制台提示/日志，不启动旧版。每步日志在`.tools/app-evidence/<id>/`。入口使用本机PATH里的Python和已准备好的可携工具链，不自动拉取Git或安装新Qt SDK。若更换SDK路径，在`app_dev.py`维护工具链位置，桌面入口不变。

默认打开离线会话，不自动连接板端、启动录制或修改设备。需要已有分析结果/联合录制服务等启动参数时，可传给固定脚本，例如：

```powershell
console_v2/start_latest.cmd --session D:/Code/ldiar/data/sessions/cap_20261025_203653 --joint-url http://127.0.0.1:<端口>/
```

`app_dev.py build|check|run --isolated-run`也可直接使用。未带该参数的既有开发入口保持原路径，供原生集成测试或需要固定构建目录的开发者使用。

先用已知具有空场条件的会话生成统一结果（不要把任意前几帧声明为空场）：

```powershell
python -B -W error pc_apps/range_fall/runtime_replay.py --session data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<新的运行目录>
python -B -W error console_v2/app_dev.py run --analysis docs/evidence/<新的运行目录>/analysis.json
```

`app_dev.py build|check|run` 与原 `dev.py` 分开；`check` 全帧只读解码后执行真实原生窗口的播放、暂停、seek、逐帧及截图。所有日志在 `console_v2/.tools/app-evidence/<id>/`。`--session` 指定初始会话，`--analysis` 可重复注册结果；缺结果的会话显示 UNKNOWN。开发运行使用现有可携工具链，不联网安装或重新发布 R2 包。

### 界面开发热重载（2026-10-25）

改 QML 布局/配色/空态不再需要增量构建重启：

```powershell
python -B -W error console_v2/app_dev.py run --qml-file console_v2/app/native/Main.qml
```

`--qml-file` 从磁盘加载该 QML，保存文件后约 0.3 秒只重建界面引擎；Viewer、几何、命名管道与回放状态不动。QML 写错时窗口消失、进程存活，修好并保存即自动恢复。自检（先复制源文件到 `.tools/hotreload/` 副本再运行，向副本追加注释触发一次重载，未发生重载则退出码 2）：

```powershell
cp console_v2/app/native/Main.qml console_v2/.tools/hotreload/Main.qml
python -B -W error console_v2/app_dev.py run --qml-file console_v2/.tools/hotreload/Main.qml --smoke-reload
```

不带 `--qml-file` 仍从 qrc 资源加载，发布路径与既有自检不变。

## 功能与边界

- 会话回放：数据库列表、完整真实帧读取、源时间驱动播放、暂停、逐帧、seek、倍速、旋转缩放、同帧目标点集/RAW框/状态/高度、**删除会话**（本地+板端：先出 sid/bytes/sha256 清单对话框确认，板端走 HC 现有 `DELETE /api/v1/sessions/<sid>`（ready/failed/transferred 可删，录制中拒绝），本地删除校验路径无目录链接；删除当前打开的会话会自动切换到剩余会话，最后一个本地会话不可删）。
- 实时锁定：用户点击连接后，只读订阅 Foxglove WebSocket 的原始 `/innolidar_points` 与配置前缀下的 `state`。默认前缀 `/single_target_live/`；自动锁定由板端算法模式提供，客户端不改变配置或假设设备正在运行。当前只支持 ROS1 float32 XYZ 的完整原始流；不接受抽样显示话题。状态与 seq、秒、纳秒、frame_id 完全匹配，缓存8帧、TTL2秒，失效隐藏目标。此入口消费现有生产算法，不意味着新距离图链已部署。实时模式下回放进度条/播放控件隐藏，画面跟随实时流。
- 3D 视图交互：左键拖动旋转、右键拖动平移、滚轮缩放。「框选目标」模式下左键拖出矩形即本地视锥框选：QML 用相机 `mapToViewport` 探针经验标定投影模型（不依赖 Quick3D 欧拉角/深度约定），C++ 对每帧点云按同一视锥重投影收集框内点（橙色点集 + 传感器系 AABB + 高度中位数），旋转缩放视角后仍逐帧跟踪框内目标；这是本地几何测量，不发送任何板端命令，人体/跌倒真值 UNKNOWN。`--smoke-pick` 冒烟自检该链路（框住窗格中央必须选中点，否则退出码 2）。**着色**：单色 / 深度（径向距离 0.1–8 m 固定标尺，红近→蓝远，与 2D 距离图同语义）/ 高度（逐帧 z 范围，viridis）/ 反射（逐帧强度范围，inferno；live 流无 intensity 字段时自动回退单色）。着色经 UV 采样 qrc 内嵌 256×1 渐变 PNG（DefaultMaterial diffuseMap，点原语可用）；强度随帧从服务端传给查看端并参与 SHA 校验。
- USB联合录制：原生配置表单、开始/停止、状态和计数。保存根目录可「浏览…」目录选择（FolderDialog）或手输绝对路径，空值时预填录制服务上报的 output_root。通过 `--joint-url http://127.0.0.1:<端口>/` 调用用户已经启动的本地联合录制服务。USB相机接在板端，现有协议使用 MJPEG URL；没有PC本地UVC枚举。应用不会自动启动可写Python worker或访问设备。停止返回stopping/saving时继续查询，不假称已经保存完成。USB 页打开期间每秒轮询状态；空闲预览由本地录制服务的预览泵按请求供帧（状态行 `预览流` 显示 off/connecting/live/error 与失败原因），录制服务未启动或相机不可达时不再只有「等待预览帧」。

联合录制客户端复用 `pc_apps/console/joint_capture.py` 的协议。本轮后端改为拒绝已有录制登记、独占创建新sid目录，冲突不会覆盖旧joint/points；相机恢复追加和meta后写仅发生在本次新建目录。写worker强隔离仍未实现。真实录制与设备链需单独实测，本地mock不能代替物理同步或采集成功证明。

需要录制时，用户先显式启动本地服务（仅启动不会访问设备或创建输出目录，不自动打开旧相机页面）：

```powershell
python -B -W error console_v2/joint_server.py --output-root D:/Code/ldiar/data/sessions
# 从打印的JSON复制本地url，然后在另一终端启动Qt：
python -B -W error console_v2/app_dev.py run --analysis <analysis.json> --joint-url http://127.0.0.1:<端口>/
```

Qt内点击开始才执行联合采集；停止后查询至completed/failed，成功会刷新会话列表。预览读取本地录制服务的最新JPEG：录制中来自录制相机线程，空闲时来自录制服务的预览泵（仅 USB 页打开期间按请求连板端相机，5 秒无请求自动断开）。

## 数据与进程

C#只读持有会话文件，校验元数据、全部帧边界、源时间、完整meta/points SHA；有结果时逐帧核对原始字节SHA、来源行和RAW包围框。QML不读点云文件或运行算法。Qt使用异步QLocalSocket对接.NET命名管道，GUI不执行阻塞管道读写；点云走单槽共享内存，Qt深拷贝并返回ACK后才能复用槽。来源行在C#重建目标二进制，不把长数组塞进Qt控制消息。复制完成不等同GPU呈现。应用日志限定在私有app-evidence目录，报告独占创建。ACK 是“槽已被读走”的唯一证据，因此 30 s 内没收到就**不能**继续覆盖共享槽：服务端记一条 `ackTimeout` + `failed`（写明 submission 与等待毫秒）后以退出码 2 结束，报告里能直接看出是界面卡住而不是“Pipe is broken”。

统一结果来自 `range_fall_analysis/1`：源SHA、配置/源码绑定、原始坐标米制、逐帧目标来源行、规则状态、疑似区间；只在运行完成和实际消费序列复跑一致后生成。确认告警保持关闭，人体/真实跌倒效果为UNKNOWN。

本轮用户要求三线并行继续完整项目，因此推进该独立本地应用；原R2的独立干净系统、真正冷机、旧启动异常和完整帧UI计时缺口仍保留，不将其改为PASS。API兼容、写worker隔离、发行与设备验证也不能由此视作完成。


## LiDAR距离图与躺倒候选（2026-10-25）

会话结果注册后，点击「2D距离图」可显示同帧径向距离，点击「查看导出文件」查看PNG16毫米图、预览、目标mask及元数据。新v2图片上下和左右统一转正；旧v1只读兼容，显示转正但旧下载保持原生方向。缺结果或切到实时流时清空距离图。原动态状态与新增静态躺倒几何候选分开，人体语义仍UNKNOWN。

结构、算法边界与坐标见[DEPTH_FALL_ARCHITECTURE.md](../../docs/DEPTH_FALL_ARCHITECTURE.md)。当前转正结果为`docs/evidence/2026-10-25_depth_fallen/oriented386/analysis.json`及`oriented780/analysis.json`，通过`--analysis`注册；不改原始会话。若当前应用占用DLL，关闭只读开发应用后再运行标准增量构建；本轮额外在独立`.tools/depth-fallen-*`目录构建和验证，未终止其他正在运行的Qt会话。


### 相机交互回归（2026-10-26）

左键旋转、右键平移；每次按下建立独立起点，混合按键不会切换手势。取消、失焦、切视图和切工具清理手势；开发热重载保留相机角度、距离和焦点。构建后从仓库根运行`python -B -W error -m unittest discover -s console_v2/app -p test_camera.py`，通过应用自身Qt鼠标事件验证真实QML及私有副本热重载，不访问板端、不采集或删除会话。

### 实时流畅度与工作空间（2026-10-26）

- 左上「☰ 功能」打开抽屉，集中放会话回放、实时锁定、USB联合录制和标注台。选中后收起；右上「收起侧栏」独立隐藏设置，「放大点云」同时收起侧栏与结果卡，点击「恢复面板」还原。
- 「修改会话名称」支持中文，显示名称写在`console_v2/user_data/session_names.json`；sid、目录、meta/points、识别结果和GT绑定保持。原始编号仍在列表副行/提示中可见。CLI `--names-file`可为自动测试指定私有名称文件。
- 「打开标注台」原为在浏览器打开 annotator_v2；2026-10-26 起标注台改为**本窗口内的原生页面**（见下节），该按钮保留为「旧版网页标注台 ↗」，只在需要网页版的部位/区间细标时使用。按需本机服务仍继承同一data root和注册analysis，不写原始数据，落既有独立gt_store_v2；该按需服务随本控制台关闭。
- 实时完整原始点云启用Foxglove已有permessage-deflate，保持全点数；用8帧缓存提供350ms本地同帧缓冲，按点云节奏推进，识别超时不再无限等或按识别频率节流。只有完整源header匹配的结果可进入对应画面，不把旧目标混到新源帧；未被算法处理的帧仍显示UNKNOWN。界面显示接收fps/源频率估计/接收跳号；录制HTTP请求在后台串行处理，不阻塞帧分发或ACK。`--live-url ws://192.168.31.58:8765`显式启动只读实时连接。
- `core/subscription_health.py`及human_fall_node增加断连重建和诊断；只在持续无TCPROS连接10秒时重建订阅，不因算法慢重置连接。这是本地防复发补丁，未部署到板端。本轮板端通过向现有节点重发其已登记publisher列表恢复三个失联订阅，无服务重启/采集/驱动网络改动。
- 回归入口：`python -B -W error -m unittest discover -s console_v2/app`（真实Qt控件/名称侧车/标注启动、延迟识别与2秒慢录制状态、原回放/鼠标/同帧ACK）；Web运行`npm test`/`npm run build`及Python服务测试。机器证据见`docs/evidence/2026-10-26_console_live_workspace/`。接收/Qt副本送达不等于GPU物理呈现fps；无GT不宣称人体/跌倒效果。


### 启动默认状态与功能页巡检（2026-10-27）

- 启动就停在**会话回放**（第 0 页）：侧栏与结果卡展开、回放暂停在首帧、会话已载入；四个功能页（会话回放 / 实时锁定 / USB 联合录制 / 标注台）由用户在「☰ 功能」抽屉里自己选，启动时不替用户切页。会话带视频时同步视频窗口仍会自动打开（既有行为），关掉后可用「同步视频窗口」重开。
- `--tour-report <新文件>` 巡检默认落地与四页切换、状态条文案和正文 ≥12 px、两处帧号、标注画布非空且同帧、隐藏时不拷贝；用 `QTest::keyClick` 实际测试空格播放/暂停、左右逐帧、Home/End、Esc、改名输入框的空格与光标移动，并点击主播放按钮。live 快照模拟测试要求五个回放键不发命令（不连接设备）。最后暂停在帧 3，写 `tour.png` 与 JSON。回归 `python -B -W error -m unittest discover -s console_v2/app -p test_ui_tour.py`。仅 tour 的报告失败路径发送 `quit` 正常结束服务，结果以 JSON status 为准；其他自检退出路径未统一。
- 同一轮清掉两类 Qt 告警：7 个 `QQuick3DGeometry` 在首帧到达前就被渲染，构造时补 `stride`+`Position`（`Viewer.h`）；视频子窗 `flags` 原来读没有 NOTIFY 的 `root.flags`，改读可 NOTIFY 的 `headlessChecks`（报告模式由 C++ 同时置位）。`nativeStderr` 日志现在带 `atMs`，便于定位告警发生的阶段。
- 已知未修：快速连续切页时 Qt 布局引擎会自报一次 `Layout polish loop detected`（两次迭代后自恢复，历史运行里早已存在）；巡检只放行这一条，其它任何 stderr 告警都判失败。正常单页运行（如标注台自检）现在 stderr 为 0 条。

### 界面规范 P1：会话列表 / 坐标轴与图例 / 就近错误 / 配平视图（2026-10-27）

- **会话列表单行 + 过滤**：每项一行（名称 · 次要编号 · 分析状态点），高 30 px，正文 12 px，长名称省略、tooltip 与
  `Accessible.name` 带完整编号。`sessionFilter` 只筛列表：不发命令、不动已加载会话/播放位置/数据；有匹配数与
  「没有匹配的会话」提示，`清除` 按钮一键复原。列表行用 `Button` 但不再有死属性 `Button.text`（自定义 contentItem 下无用）。
  点行切会话时用 `pendingOpenSid` 守住：服务端真的切过去之前，快照里的旧 sid 不会把选择切回去（否则会给旧会话
  发一次注定被拒的 `gtLoad` 并清掉新会话的标注状态）。6 s 没有回帧则自动放开守卫。
- **3D 坐标轴**：右下角 74 px 指示器画 X/Y/Z，方向来自相机 `mapToViewport` 实测投影（不是写死的屏幕方位），
  传感器系 `(x,y,z)→(x,z,-y)` 与点云节点 `-90°` X 旋转一致；单位 `m`，tooltip 写明「Z 是传感器轴，不是离地高度」。
  **箭头长度按投影长度缩放**（只归一化方向会把“朝观察者”的轴拉成和竖直轴一样长，Y/Z 两支箭头会叠在一起；
  自检直接量两个标签的像素距离）。只在相机/配平/视口尺寸变化时刷新，播放与 seek 不触发（`refreshCount` 有回归）。
- **当前色带图例**：工具行里的图例条直接绑定 `cloudGeometry.colorRange`（着色实际用的 lo/hi）。单色=不分层；
  深度=固定 0.10–8.00 m（红近→蓝远，**文案由 `colorRange.lo/hi` 拼出**，不写死）；高度=逐帧 Z 范围（`viridis`，
  注明「传感器轴，非离地高度」）；反射=逐帧强度范围（`inferno`，注明「无单位，非置信度」）。
  只有反射依赖强度字段：缺强度时只有反射回退单色，**深度与高度照常着色**（live 无 intensity 也不会牵连它们）。
  视图按钮（聚焦目标 / 框选目标）移入工具行，不再压住点云。
- **就近错误提示**：每条要回包的命令带一个 `seq`，服务端在终止回包里原样带回，界面按 `seq` 结算——不再用
  “最后发出的命令”猜通道，所以 A 通道的失败不会显示在 B 的控件下面。失败原因显示在发起动作的控件下方，
  可单独「清除」；状态条复用红点 + 一行提示。正常 / 可恢复（琥珀）/ 持续失败（红色，**过去 30 s 内同通道 ≥3 次**，
  滑动窗口，窗口滑走后自动降级）三态。无主回包（未知/重复 `seq`）只计 `staleReplies`，不覆盖新状态；
  超过 30 s 没有回包的命令计 `expiredCommands` 并让出位置。USB 页每秒 `jointStatus` 轮询带 `poll:true`：
  **不发 `seq`**，回包既不结算用户动作、也不会把录制服务的失败记到别的通道上。
- **配平视图**：`--ground <BOUND_GROUND.json>` 绑定地面（只读，`status=valid` + 本会话）后，工具行「配平视图」可用：
  只把显示旋转到「地面法向 = 世界竖直」，点云/高度/判定一律不改；未配平时底部提示写「原始传感器坐标 / m（未配平）」，
  坐标轴单位标注在 `m·原始` / `m·配平` 间切换。未绑定地面时按钮禁用并说明原因。
- 回归：`--tour-report` **112 项**（含过滤真实按键/清除/无匹配/过滤后选择、图例范围与真实帧范围逐值对照、
  深度文案由 lo/hi 拼出、无强度时高度/深度仍着色、坐标轴 yaw=0/90 的方向与 Y/Z 标签分离、指示器刷新计数、
  配平前后法向残差 <0.01°）；新增 `test_alert.py`（本机 mock 录制服务 503 → 真实按钮 → 就近提示/红点/清除/
  持续失败；`seq` 归因的跨通道/重复/超时/滑动窗口单元级检查，共 20 项）；`test_ui_tour.py` 另外要求整轮
  `commandError` 为空、`staleReplies=expiredCommands=0`、且 `qt.qpa.mime:` 平台消息不算 QML 告警。
  证据见 `docs/evidence/2026-10-27_ui_p1/`（原始）与 `docs/evidence/2026-10-27_ui_p1_review/`（审查与修复）。

### 界面规范 P0：状态条 / 字号与颜色角色 / 快捷键（2026-10-27）

- 顶部 68 px 的品牌区块压到 52 px，右侧换成**常驻状态条**（`objectName: "statusBar"`）：模式（回放/实时）、会话、帧 `n / 总数`、目标状态、低位提示、未注册分析、当前页名。目标状态的颜色只表达“是否偏离正常”。
- 字号 4 级：`fontBody 12 / fontLabel 14 / fontTitle 18 / fontHero 22`（`root.font*`），侧栏标题使用 `fontTitle`。7 个命名颜色：`colorText #e6f4ff`（正文）、`colorMuted #9ab2c9`（次要）、`colorDim #67859e`（暗背景提示）、`colorInfo #62dfcf`（正常）、`colorWarning #ffcf5c`（过渡/低姿/未注册）、`colorAlarm #ff7a5c`（告警/疑似）、`colorSelection #20b8a5`（选中，绑定 palette.highlight）。当前页正文使用 `colorMuted`；状态条与结果卡先迁移，旧字面量逐步迁移。
- 回放快捷键（窗口级）：`Space` 播放/暂停、`←/→` 逐帧、`Home/End` 首末帧、`Esc` 取消框选与选中；控件行下面有一行快捷键提示。
- 滑块右侧常显 `当前帧 / 总帧数`；没有注册 analysis 的会话在状态条显示「未注册分析」，悬停说明用 `--analysis` 注册；结果卡大号状态在无结果时显示「无结果」（目标/高度两栏仍是 UNKNOWN，P1 再清理）。
- 标注画布只在标注页可见时同步点云（切到标注台补一次当前帧），隐藏时不再每帧整帧拷贝；`--tour-report` 报告里的 `annotationCopies` 可对比。
- 回放键在 live 模式禁用，共用发送入口同时拒绝 play/pause/step/seek；主窗与视频窗播放按钮均用 `togglePlay()`。改名输入框保留文字编辑键。
- 历史证据 `docs/evidence/2026-10-27_ui_p0/` 只读保留；其中 before 帧 3 / after 帧 5，并非同帧，34 项日志也只代表当时版本。修复后的源 SHA、同帧 3 截图和当前回归见 `docs/evidence/2026-10-27_ui_p0_review_fix/`。

### 原生标注台（Qt 内重写，2026-10-26）

功能抽屉里的「标注台」现在切到本窗口内的标注页面，不再打开浏览器：左侧选会话 / 当前人物 / 区间，中间是 XY 俯视画布，底部沿用原回放控件切帧。

- 画布由 C++ `AnnotationView`（`QQuickPaintedItem`，`console_v2/app/native/AnnotationView.h`）绘制当前帧点云（按高度着色 + 米制网格 + 比例尺）：左键空白拖出新框、点框选中、拖框身移动、拖角缩放、右键平移、滚轮缩放。坐标是传感器原始系、米，与 `gt_annotate/2` 的 `x/y/w/h/zMin/zMax` 同义。
- 框按人物（P1、P2…，可「新增」）与帧保存，同一人物同帧只允许一个框；可见性 visible/partial/occluded、复核标记、z 上下限可改；撤销/重做覆盖框、人物和区间。
- 动作 / 事件区间（如 `fall`）用「起点」「终点」取当前帧、「新增区间」写入，列表可跳转/删除。
- 保存/重载走本机 C# 服务：默认写 `pc_apps/annotator_v2/gt_store_v2/<sid>/draft.json`（`--gt-root` 可指向私有目录，带尾分隔符也可以），临时文件原子替换 + 版本冲突拒绝，并按 `pc_apps/annotator_v2/src/domain/validation.ts` 的 error 级规则校验字段（格式 / 坐标系 / 帧界 / 宽高 / z 范围 / 人物引用 / 同人物同帧重复 / 区间范围 / 建议 id 重复与空建议 / 取样清单；warning 级的 adopted/accepted 建议问题不拒绝）。载入网页版草稿后 `persons/suggestions/sampleFrames/annotator` 原样保留。会话编号不接受 `..` 等路径片段，`Load` 与 `Save` 都要求解析后的路径仍在 store 根目录下。
- 跨会话保护：换会话先清空界面 GT 再重新载入，只接受 `sessionId` 与当前会话一致的 `gt` 回包；本会话没载入完成时「保存」会被拒绝。保存中按钮禁用、回包只认在飞那次，保存期间又改过则保持「未保存」；「重载」在有未保存修改时要连点两次。翻帧后不属于当前帧的选中框会被清掉，属性面板和「删除选中」只作用于当前帧。
- **本轮范围**：整人框 + 区间 + 保存/重载。网页版的**身体部位像素标注、2D 距离图像素层、算法建议采用、同帧 3D 视图**尚未搬进 Qt，需要时仍用「旧版网页标注台 ↗」。框是人工范围，不是人体分割或跌倒真值；不写原始会话、不连板端。
- 自检：`--annotation-report <新文件>` 用真实窗口鼠标事件跑「拖框 → 拖框身移动 → 保存 → 重载 → 加区间 → 保存 → 旧版本保存被拒 → 重载恢复版本 → zMax≤zMin 被拒」，外加外会话回包丢弃、未载入不许保存、翻帧清选中；配合 `--gt-root` 私有目录。`--self-check-gt` 只跑 store 级回归（不启动 Qt：尾分隔符根、`..` 越界诱饵、suggestions 两条例）。回归 `python -B -W error -m unittest discover -s console_v2/app -p test_annotation.py`（含真实网页草稿兼容与 store 级用例）。机器证据见 `docs/evidence/2026-10-26_annotation_review_fixes/`。

### 两会话区域骨架预览

运行 `console_v2/start_skeleton_preview.cmd`（任意cwd）构建当前源码，并显式注册2026-10-26两份全段结果。默认离线，点击播放后进入有目标的帧；“区域骨架候选”开关控制3D与2D距离图显示。金色线为实测区域中心连接，浅色点为区域中心；它们不是已验证的头/肘/膝关节，左右及头脚身份UNKNOWN，观测不足留空。原跌倒规则独立保留，confirmed仍关闭；此轮骨架不作为跌倒证据。生成新会话结果可运行 `python -B -W error pc_apps/range_fall/skeleton_replay.py --analysis <existing-analysis> --out <new-directory>`，源会话及旧结果只读。

### 附带视频同步窗口与连续相机预览（2026-10-26）

- 打开会话时自动查找本目录非空视频，优先`camera.mjpeg`；支持`.mjpeg/.mjpg/.mp4/.mov/.avi/.mkv/.webm`（具体容器/编码由本机PyAV支持）。检测到视频自动弹出独立窗口，也可点回放栏「同步视频窗口」重开；多个视频可下拉切换。窗口跟随雷达播放/暂停、逐帧/拖动和倍速，提供±60秒的毫秒偏移；切会话、切实时、关闭窗口清图并释放解码文件。
- 联合录制的`camera.mjpeg + camera_frames.jsonl`用相机接收时刻与雷达`bag_time_sec`选最近帧；取帧差超过250ms显示没有相近视频帧，不跨缺口补旧图。普通视频按自身PTS和雷达首帧相对时间对齐，可调偏移。跨设备时钟/硬件同步未验证，窗口明确标注；不会自动改原始视频、索引、meta或points，也不会把同步观看当物理同步证据。
- 视频使用当前PC已安装的PyAV/Pillow，只读本地文件，解码请求/返回均为最新值单槽、最高30次/秒，预览图限制1280×720；解码在独立进程，不阻塞点云。这个开发入口需其`--python`解释器安装PyAV/Pillow（本机已验证），不增加板端依赖或下载模型。
- USB相机预览由原来随1秒状态轮询换静态JPEG，改为独立异步读取最新画面：最多一个在途本地请求，50ms检查，帧号去重、未变化204、源画面超过1.5秒遮蔽；收起侧栏/离开USB页立即停止预览请求。保留每个代理实例内的唯一板端相机取流和5秒预览租约，录制状态轮询与点云/预览分别推进。
- 原PC代理15116/57011保留；新代码本地实例45316/62911用于本轮联测和新窗口，始终idle，未发录制开始/停止。停止旧代理的提议被自动审批拦截，改用并行本地实例；不是绕过策略停止旧服务。真机约10.02fps预览 + 9.68fps点云接收（短窗），接收跳号0；非GPU物理呈现/长期稳定性结论。机器证据见`docs/evidence/2026-10-26_video_sync_preview/`。

使用`console_v2/start_video_sync.cmd`可手动启动当前已有的85帧联合会话并自动显示视频窗口；复用现有最新版构建入口，本轮绑定空闲本地代理62911。若重启了本地代理，可在脚本后传`--joint-url http://127.0.0.1:<新端口>/`覆盖；常规`start_latest.cmd`保持原默认参数。自动审批阻止了本轮最后的后台启动操作，因此没有把“入口已写好”等同于“最终展示窗已打开”。
