# ADR-001：A为候选，R2以实测决定A/B

日期：2026-10-24，2026-10-25追加R2实测。状态：R2已选择B；本机spike通过，独立干净环境/真正全冷启动仍NOT_RUN。

## 背景与决定

用户要求.NET8 + QML/Qt Quick3D默认路线A，失败切Qt C++壳+C#服务B，C需书面同意。保留此顺序，不因熟悉某UI栈而跳到C。R1只约束验证顺序，R2才创建spike；不提前建立业务工程。

A由C# Host拥有QML宿主与API，Qml.Net连接ViewModel；需要时允许小型C++ Geometry插件仅处理二进制顶点缓冲。插件不是Qt主程序，不借此把B冒称A。若需自行维护Qt6绑定分叉才可加载，要明确记录该额外成本，不静默换绑定。B才由Qt C++程序拥有QML宿主，C# headless服务拥有数据与API。

查阅的[Qml.Net官方README](https://github.com/qmlnet/qmlnet/blob/master/README.md)说明.NET/Qt互操作和原生库依赖，但该页面不能证明Qt6.5+/.NET8组合可用；其自动发现/下载Qt的示例不作为产品启动策略。R2只使用明确准备、版本绑定的本地运行库；生产启动不联网补依赖。该兼容性保持UNKNOWN，不凭文档年龄断言失败。

## R2判定顺序

1. 环境准备：当前PATH下dotnet有.NET8运行时，无SDK输出。记录SDK/Qt/编译器/CPU/GPU/驱动/Windows与RHI后端、包版本和SHA。缺工具链时该阶段记ENVIRONMENT_BLOCKED，后续NOT_RUN，不能作为A性能不达标依据。
2. A绑定加载与窗口：固定Qt6.5+、.NET8，创建最小QML/Quick3D窗口，记录实际加载模块路径；类型加载失败、ABI不符、崩溃分别留日志。
3. 数据/渲染：cap_20261018_110029真实3帧stride28、首点与全帧逐值对照；实际单帧最大49124点。500000点压力数据必须记录真实帧组合/复制规则、来源行、构造SHA，与真实帧模式分开。不能拿静态图刷新计数当点云更新吞吐。
4. 包：发布exe，核查Qt平台插件/Quick3D/QML导入及原生依赖；离开源码目录、无VS环境运行，记录高DPI100/150/200%的视口与输入坐标。未找到独立环境则NOT_RUN，不用本机装有运行时的结果证明自包含。
5. 同一已冻结输入测性能：50万点≥30FPS、5万点≥60FPS、10次冷启动P95≤2.5s、UI阻塞P99≤16ms；还记录峰值内存、包体积、真实/压力两组帧耗时。R2报告清楚warm/cold、采样数、分位算法和测量边界，不以平均FPS掩盖阻塞。

必要组合实测失败或不可用，保留日志并追加本ADR的R2决定与原因，转B执行同一输入/预算。B也失败则不擅自用C。资料不足/环境不足不伪造A FAIL；技术选择仍未决，先解决可解决的环境条件。

## 打包约束与后果

[.NET单文件部署文档](https://learn.microsoft.com/en-us/dotnet/core/deploying/single-file/overview)明确区分托管打包和原生库解包；[Qt Windows部署文档](https://doc.qt.io/qt-6.5/windows-deployment.html)覆盖Qt/QML/插件依赖搜集。R2分别记录单文件发布结果、解包目录与依赖清单，不声称PublishSingleFile能自动包含全部Qt资源。允许R2先诊断目录包，但目录包不能通过原“单文件exe”要求。

若仅文件形态不达标，仍报告该门FAIL；B也需验证，不把切B当作单文件问题已解决。R9交付与许可证清单随所选真实依赖生成，R1不预先宣称可发布。

## R2追加决定（2026-10-25）

已准备SDK8.0.426/runtime8.0.32、Qt6.5.3与匹配GCC11.2。固定发布版Qml.Net0.11.0/WindowsBinaries0.11.0的net8项目实际编译通过，但运行在Interop类型初始化失败，包内原生DLL实际依赖Qt5而非Qt6；原生加载/PE imports/SHA及异常原样保留。A必要绑定组合FAIL，窗口和FPS为NOT_RUN；不是缺工具链或帧率失败，也没有据此断言自行维护Qt6绑定分叉绝不可能。

选择B：Qt C++程序拥有QML/Quick3D窗口，C#只读服务拥有输入与共享缓冲，不使用C。B已真实渲染前三帧及精确50万合成点，动态三轮最低131.75FPS、修正GUI记账的drain活动区间P99最高2.217ms；单文件exe96,298,082B，干净PATH运行与DPI1/1.5/2布局检查通过。详细输入构造、逐值对照与原始统计见[SPIKE](../SPIKE.md)。

10次新进程启动P95 730.99ms，首次Qt解包1839.95ms；未清OS/驱动/QML缓存，真正全冷机NOT_RUN。本机模块来源可查，但独立干净无SDK/VS/Qt系统未找到，按上文判定仍NOT_RUN。技术路线可据绑定失败选择B，不能据本机结果宣布完整R2门已过；不提前编写R3—R9业务。后续先补可获得的隔离环境验证并保留原口径，不能用未测项自动改判A或切C。

前一版measured_final的24轮另有一次8683.35ms首帧异常（payload复核/解包阶段约8114.85ms），完整保留，底层原因UNKNOWN；不以十轮P95通过声称全部启动达标。见measured_final、当前corrected_PERFORMANCE_SUMMARY与POST_REVIEW_DISPOSITION。

计时最终口径：drain之后的回调/notify尾段进入后续区间；活动区间代理不等于完整outer-notify按帧时间，后者NOT_RUN。RESULTS.json为当前结果入口，旧corrected_原始字段名不扩张其证明范围。
