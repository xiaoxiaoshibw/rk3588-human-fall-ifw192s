# ConsoleV2 R2：真实解码、Quick3D 与单文件包

2026-10-24 开始，2026-10-25 收尾。结论：**A 的固定发布版绑定加载失败，已按约定选 B（Qt C++ QML 宿主 + C# 服务）**。B 的本机解码、渲染、单文件运行与显示缩放检查通过；启动存在一次 8.68s 异常，独立干净 Windows 环境未运行，R2 完整通过仍未宣告，不提前开始 R3—R9 业务。

源码在 [console_v2/spike](../../console_v2/spike/)，复现入口见 [README](../../console_v2/README.md)。机器原始记录在 [R2 evidence](../evidence/2026-10-24_console_v2_r2/)，汇总 [RESULTS.json](../evidence/2026-10-24_console_v2_r2/RESULTS.json) 由原始样本重算，分位数使用 nearest rank。

## A → B 的实证

- SDK 8.0.426 / runtime 8.0.32 已准备，并非因缺 SDK 判 A 失败。固定 Qml.Net 0.11.0 + WindowsBinaries 0.11.0 的 net8 项目编译零警告、零错误；实际运行 exit 2，在 `Qml.Net.Internal.Interop` 初始化中失败。见 [A_load_01.stderr](../evidence/2026-10-24_console_v2_r2/A_load_01.stderr)。
- 该包 `QmlNet.dll` 的 PE imports 实际要求 Qt5QuickControls2/Widgets/Gui/Qml/Core；Qt6 不能满足 Qt5 ABI。原生探针与 SHA 在 [A_NATIVE_PROBE.json](../evidence/2026-10-24_console_v2_r2/A_NATIVE_PROBE.json) / [PE imports](../evidence/2026-10-24_console_v2_r2/A_QmlNet_PE_IMPORTS.txt)。A 窗口/FPS 为 NOT_RUN，不能写成 A 帧率不达标；未调用自动下载 Qt5，也未证明所有可能的绑定分叉都不可行。
- B 是真正由 C++ `main` 创建 QGuiApplication/QQmlApplicationEngine 的方案，不将 C++ 宿主冒称 A 插件。后续产品进程关系仍遵守 [ADR-001](ADR/ADR-001-technology.md) 与 [ARCHITECTURE](ARCHITECTURE.md)；本次临时服务不承担产品 API。

## 输入与实际执行路径

只读 `cap_20261018_110029` 的前三个声明帧，stride 28，点数分别 49115 / 49106 / 49103。C# 实际读取 XYZ/intensity float32、ring uint16、timestamp float32；18/24 起的 padding 不解释为字段。Python/NumPy 独立解码并对全部字段重新构造 22 字节规范记录，全帧 SHA、XYZ SHA、投影 SHA 均容差 0。三个真实帧 × 原始/50000/500000 三模式全部一致，见 [single_CODEC_DIFFERENTIAL.json](../evidence/2026-10-24_console_v2_r2/corrected_gui/CODEC_DIFFERENTIAL.json)。另有四项 C# 自检及 stride16/截断/point_file 路径穿越/负 offset 四项拒绝检查。stride16 此处刻意拒绝，通用支持属于 R3。

压力构造严格为 `source_row=i%finite_count; tile=i/finite_count; x+=(tile%4)*2m; y+=(tile/4)*2m`；仅非零 tile 加位移，精确产生 50000 或 500000 点。真实模式不做平铺；保留零 XYZ，仅对非有限 XYZ 显式过滤并计数（这三帧为 0）。界面明确标 `Synthetic tiled stress`，不存在真实 50 万点单帧的断言。

映射前 validateLayout 拒绝≤0/超过18MB容量，检查恰好三份连续描述符、单帧≤500000点、bytes=count×12、总和恰好等于容量，避免Windows零长度整对象映射语义。C# 预读、校验、构造三份不可变共享内存缓冲，当前用户专属命名管道发送长度受限描述；Qt 只读映射并复核每帧 SHA。每次提交使用 Qt 拥有的 QByteArray 深拷贝，三帧循环并持续重新上传顶点；共享映射保留至自有 Qt 子进程退出。静态组不重复上传，另行列出。该路径刻意不做业务、HTTP、板端访问或 Python worker，不代表 R3 的异步/零拷贝或 R4 的按源时钟回放已实现。

## 环境、测量口径与结果

Windows 11 build 26300；Ryzen AI 9 H 365（10 核/20 线程），实际 RHI 为 D3D11 / Radeon 880M，驱动 32.0.31035.1003。Qt 6.5.3 MinGW，匹配 GCC 11.2，CMake Release、`-Wall -Wextra -Werror`；服务 Nullable / TreatWarningsAsErrors。硬件记录见 CPU/GPU/OS.json，实际 Qt backend/driver 日志在每轮 result 的 qt_logs。桌面还存在虚拟显示器和系统注入的 Nahimic DLL；未更改驱动或网络。

固定视口初始 1120×720，点大小 1，统一颜色、相机正弦旋转，swap interval 0。每轮预热 1 秒；性能组各测 10 秒并跑三轮，全部样本、n/P50/P95/P99/max 保留。FPS 为 `frameSwapped` 软件呈现信号间隔，不是物理屏幕刷新、光子或 GPU 时间戳；本机屏幕 144Hz，计数可以超过它。场景点云占屏有限，无点选/着色/业务叠层，不外推复杂场景吞吐。

GUI 指标准确名称为 **回调内 drain 点已累计的 GUI 活动区间时间**。采样发生在 copy/update 之后、槽函数和外层 notify 返回之前；GuiWorkLedger 立即计入活动事件的已执行前缀，返回时只加后缀，嵌套事件只计一次。**drain 之后的回调/notify 尾段会进入后续区间**，不能声称完整当前回调或外层事件全部归属同一帧。固定注入时钟自检覆盖多次前缀排空/后缀/空闲/完整事件。原生 `gui_event_work_per_frame_ms` 及旧派生字段保留为既有标签；最终 RESULTS.json 改用 `gui_drain_interval_*` 并把完整 outer-notify 按帧预算标 NOT_RUN。表内 16ms 比较只适用于该区间代理，不据此宣布完整产品 UI 阻塞门已过。另存 heartbeat 与拷贝耗时，均不等于物理屏幕/GPU时间或未派发事件前的全部 OS 等待。

| 动态输入 | 三轮 FPS | 三轮 GUI drain 活动区间 P99（ms） | 采样并发工作集和（MiB） | 本机门槛 |
|---|---|---|---|---|
| 真实约 4.91 万点 | 171.93 / 170.40 / 169.34 | 0.832 / 0.848 / 0.836 | 194.2–200.3 | 记录对照 |
| 精确 5 万点合成压力 | 168.82 / 176.82 / 171.99 | 0.459 / 0.436 / 0.439 | 194.1–194.9 | FPS≥60 PASS；区间代理≤16ms |
| 精确 50 万点合成压力 | 133.97 / 132.65 / 131.75 | 1.912 / 2.217 / 2.105 | 295.5–296.0 | FPS≥30 PASS；区间代理≤16ms |

静态 50 万点（相机仍旋转）181.25 FPS / GUI区间 P99 0.228ms / 254.3 MiB，仅作重复上传成本对照。正式动态 50 万点最大已采样 GUI 活动区间为 3.722ms。内存采用外部进程树约 10ms 采样的“同时工作集总和”，实际采样间隔记录在原始文件；共享页可重复计算，不是精确 OS 峰值、私有内存或显存。

10 次新进程启动首帧外部观测上界：661.10 / 691.63 / 681.59 / 700.73 / 691.83 / 689.93 / 673.73 / 696.18 / 697.70 / 730.99ms，P95 **730.99ms**。另一个首次 Qt payload 解包运行 **1839.95ms**，均在 2.5s 内。启动包括 C# 三帧读取/哈希/压力构造、Qt 解包或复核、子进程加载、首次呈现通知；未清 OS 文件缓存、Qt QML 缓存及驱动 shader 缓存，首解包前也已运行诊断，因此**真正全冷 OS/GPU 启动 NOT_RUN**，不把新进程 P95 偷换为完整冷机保证。

GUI记账修正后的当前24轮，全部启动观测 P95 **1792.20ms**、max **1839.95ms**，本组无超过2.5s的样本；前一版 `measured_final/dynamic_0_0` 首帧 **8683.35ms** 异常仍保留，阶段记录45.393→8160.241ms，payload复核/解包约 **8114.85ms**。同输入/缓存路径三次独立诊断590.69/601.45/614.17ms，未复现且底层原因UNKNOWN，不将其归因驱动或宣称已修复。三版原始测量各自保留，不混算；当前权威源为 corrected_gui/corrected_。

## 包与显示缩放

[SpikeService.exe](../../console_v2/spike/package-single/SpikeService.exe) 为 **96,298,082 字节（91.84 MiB）**，单一交付文件、自包含 .NET，嵌入 590 文件/75,373,138 字节 Qt payload。没有打入 meta.json/points.bin；首次启动在应用自有目录解包，缓存复用前逐文件 SHA 复核，部分解包不覆盖、不自动删除。payload/最终 exe/源码 SHA 分别见 [QT_PAYLOAD.json](../evidence/2026-10-24_console_v2_r2/corrected_gui/QT_PAYLOAD.json)、[FINAL_SOURCE_SHA.json](../evidence/2026-10-24_console_v2_r2/corrected_FINAL_SOURCE_SHA.json)。这证明单文件分发，不表示运行时没有解包目录。

全部 24 轮正式运行在 evidence 工作目录启动 exe，PATH 仅 System32，移除 DOTNET_ROOT/Qt 插件与导入路径，Qt 依赖来自包的自有提取目录。初版模块补充诊断 [NATIVE_MODULES.json](../evidence/2026-10-24_console_v2_r2/NATIVE_MODULES.json)（属于修前快照；当前每轮 module_paths 另存最终包实际DLL路径）：Qt 进程加载自身目录 Qt/GCC DLL、Windows/显卡与桌面注入 DLL；服务未借用全局 coreclr.dll。[.NET 8.0.32 官方 singlefilehost 构建源码](https://github.com/dotnet/runtime/blob/v8.0.32/src/native/corehost/apphost/static/CMakeLists.txt#L106)将 coreclr_static 链入宿主，与本机服务仅映射自身 exe/OS DLL 的观察相符；这不是 NativeAOT。

100%/150%/200% 强制 `QT_SCALE_FACTOR` 的 DPR 分别 1/1.5/2，原生截图逐张检查文字、模式、页脚及点云无裁切。150% Qt 自动约束窗口到 1120×707 逻辑像素，200% 到 962×531，以适应现有屏幕；物理图像分别 1680×1061、1924×1062。见 [100%](../evidence/2026-10-24_console_v2_r2/corrected_gui/dpi_1.0/window.png)、[150%](../evidence/2026-10-24_console_v2_r2/corrected_gui/dpi_1.5/window.png)、[200%](../evidence/2026-10-24_console_v2_r2/corrected_gui/dpi_2.0/window.png)。这验证当前无交互 spike 的布局/渲染缩放，不证明将来的输入坐标/拖拽、多屏热迁移。截图抓取造成 GUI 最大 31/59/65ms，原样保留，截图组不混入无截图吞吐组。

现有主机未发现 Visual Studio vswhere，也没有 WindowsSandbox.exe；未更改 OS 功能或安装虚拟机。干净 PATH 与模块路径属于本机依赖证据，**独立无 SDK/VS/Qt 的全新 Windows 实机或 VM 验证为 NOT_RUN**，按 R1 ADR 不能将此项翻绿。包未签名；完整 Qt/.NET 许可证打包及软件回退路径需 R9 实作，不宣称已可发布。

## 回归、失败与边界

旧 sessions/board_mode 共 11 项 Python（`-B -W error`）、四套 JS 行为集通过；旧 HTTP 真实会话“列 22 段→meta 逐值→完整 points 流 SHA→三帧解码”通过，板端调用 0。最终 [CONTINUITY.json](../evidence/2026-10-24_console_v2_r2/corrected_CONTINUITY.json) 复核 54 份会话文件 path/bytes/SHA、11 份旧源码、R0/R1 历史 evidence 与三个 junction 保持。工作树整体有其他任务变化，不声称整个仓库无变动。

OpenCode 首次审核已完成（实际 opencode-go/gpt-6-luna#low、0 工具事件），其三项中等意见已修正：当前机器字段改 fresh_process 并显式 true_cold_status=NOT_RUN；摘要分列 heartbeat 与 GUI 工作 P99；服务入口限定 count/updates，三项非法参数在读取不存在输入之前拒绝。最终包重新跑了 24 轮测量及逐值/反例检查；修前快照保留，当时结果使用 final_ 前缀和 measured_final 子目录；二次审核后又修正GUI计时和映射前边界，当前权威结果改用 corrected_ / corrected_gui，每个Qt进程实际执行GUI前缀/后缀自检与一正五反例布局检查。

初次 C++ 构建缺 QVector3D include 已修；SDK 网络中断/SSL EOF、Qt 缺 QuickTimeline、强制 release 部署插件失配、NuGet runtime pack 停滞与重试均保留日志。最终 corrected_gui/native_build、corrected_gui/publish_corrected 零编译警告/错误；windeployqt 仍有未安装翻译 catalog 的提示，当前无翻译功能不隐藏它。最早开发 DLL QA 首帧 **2.77s FAIL**，且截图造成长帧；与最终包/配置不同，仅留诊断，不作受控优化对照。二次汇总首次传相对路径触发 relative_to 异常，resolve 后 final_02 通过；一次汇总脚本将服务与 Qt 两个 first_frame 消息混为一谈而 KeyError，已按 DPR 字段筛选；不改原始测量。另见 [RUN_DISPOSITION.json](../evidence/2026-10-24_console_v2_r2/RUN_DISPOSITION.json)。SDK 首次运行生成了未信任的 ASP.NET 开发证书，后续禁用自动证书生成；未将它信任或更改已有凭据。

OpenCode 结果另列机器输出，不将未完成/401 写成审核通过。R2 技术路线 B 已有可执行证据；独立干净环境及真正全冷启动仍缺。1GB 首帧、386 帧 1× 零丢帧、200 次 seek、HTTP Golden/旧页兼容及人体/物理有效性均 NOT_RUN/UNKNOWN，分别属于后续轮；当前程序不能替代旧控制台，本 spike 未监听 8901，未改旧服务。

当前三个显示缩放PNG已逐张复看，模式/文字/页脚与点云可见；以上旧启动异常仍作为未解风险保留，独立干净环境未验证。

OpenCode第三次提出的计时尾段归属问题采用其建议的范围收窄：RESULTS.json/上文明确采样点和后缀归后续区间；未改编译代码或重写原始样本，不再宣称完整按帧GUI阻塞预算已验证。
