# 雷达控制台 ConsoleV2 · 源码构建与局域网使用

这是 Qt 控制台（`console_v2`）的源码分发包：**不含**数据、采集、历史证据、构建产物和工具链，
接收方在自己机器上编译后运行。同一局域网内的多台机器可以各自编译、各自连接板端，互不影响。

## 1. 准备工具链（Windows 10/11 x64）

| 组件 | 版本 | 用途 | 获取 |
|---|---|---|---|
| .NET SDK | 8.0.x | 编译/运行 C# 服务 | https://dotnet.microsoft.com/download/dotnet/8.0 |
| Qt | 6.5.3 **MinGW 64-bit** | 编译 Qt/Quick3D 界面 | Qt Online Installer（勾选 Qt 6.5.3 → MinGW 64-bit） |
| MinGW | 11.2.0 64-bit（随 Qt 安装器） | C++ 编译器，必须与 Qt 的 MinGW 配套 | Qt 安装器 → Developer and Designer Tools → MinGW 11.2.0 64-bit |
| CMake | 3.21+ | 配置 Qt 工程 | https://cmake.org/download/ （安装时加入 PATH） |
| Python | 3.10+（可选） | 视频同步、网页标注台、离线分析 | https://www.python.org/downloads/windows/ |

Python 可选依赖：`python -m pip install numpy av pillow`。没有 Python 时，实时、回放、
3D/2D 视图、原生标注页仍可用；视频窗口、旧版网页标注台、离线分析会提示不可用。

安装后可在 PowerShell 里自检：

```powershell
dotnet --list-sdks          # 应出现 8.0.x
cmake --version             # 3.21+
g++ --version               # 11.2（Qt 自带 MinGW）
```

如果 Qt 没装在默认位置，或使用绿色版工具链，用环境变量指定（任选一种）：

```powershell
$env:CONSOLEV2_QT     = 'D:\Qt\6.5.3\mingw_64'
$env:CONSOLEV2_MINGW  = 'D:\Qt\Tools\mingw1120_64\bin'
$env:CONSOLEV2_DOTNET = 'C:\Program Files\dotnet\dotnet.exe'
$env:CONSOLEV2_CMAKE  = 'C:\Program Files\CMake\bin\cmake.exe'
```

也可以把整个仓库自带的 `console_v2\.tools`（Qt + .NET 可携工具链）一起拷过来，
构建脚本会自动优先使用它，不需要安装上面三项。

## 2. 首次构建并启动

双击 **`编译并启动.cmd`**。脚本会：

1. 发现工具链（找不到时给出缺失项和安装地址）；
2. `dotnet build` 编译 C# 服务；
3. CMake + MinGW 编译 Qt 程序（首次约 1–3 分钟）；
4. `windeployqt` 把 Qt 运行库部署到 `console_v2\app\runtime`；
5. 启动界面，默认进入“实时锁定”并连接 `config\console.json` 里的板端地址。

构建日志与工具链快照在 `console_v2\user_data\build\`；运行日志和 JSON 报告在
`console_v2\user_data\logs\<时间>\`。

只构建不启动：双击 **`构建.cmd`**；构建完成后双击 **`启动控制台.cmd`** 启动。
重新构建会复用 `console_v2\app\build-dist` 的增量缓存。

## 3. 配置（`config\console.json`）

| 键 | 说明 |
|---|---|
| `dataRoot` | 会话库目录。默认 `console_v2/user_data/sessions`（源码树内、已被 gitignore）。可以填局域网共享 `\\主机\共享\sessions`。 |
| `boardUrl` | 板端 Foxglove 只读地址，默认 `ws://192.168.31.58:8765`；留空则启动后手动连接。 |
| `autoConnectLive` | `true` 启动即连实时；`false` 只打开离线会话。 |
| `python` | 可选，指定 Python 解释器；留空自动找 PATH 和 `<源码根>\python\python.exe`。 |
| `state` | 会话显示名、原生标注草稿目录（需可写）。 |
| `logs` | 每次启动的日志目录；不可写时自动退到 `%LOCALAPPDATA%\ConsoleV2\logs`。 |

路径支持环境变量；相对路径相对源码根目录。改完重新运行启动脚本生效。

## 4. 局域网使用

- **实时锁定（多人同时）**：每个人在自己机器上启动控制台，连接同一个 `boardUrl`。
  客户端是只读订阅，不改变板端识别、不启动/停止服务、不写设备；多开不会互相踢掉。
  前提：板端识别服务在运行、板端防火墙放行 8765/TCP、双方在同一网段。
- **离线会话**：把 `data/sessions` 放到一台机器的共享目录（SMB），其他人的
  `dataRoot` 指向 `\\主机\共享\sessions`。只读共享即可浏览；删除会话、改名、保存标注
  需要写权限，权限不足时界面会显示失败原因，不会改源文件。
- **不共享数据也可以**：没有会话时启动器会创建 `placeholder_live_only` 占位会话
  （0 帧点云，仅用于实时模式），不会伪造识别结果。
- **诊断**：双击 **`局域网诊断.cmd`**，输出工具链、数据目录、板端 TCP 连通性，
  并写 `console_v2\user_data\logs\<时间>_diagnose\lan-check.json`。

> 板端地址、数据目录是每台机器自己的配置；源码和构建产物可以各拷一份，也可以放在共享盘上
> 只读运行（日志/标注会自动写到本机可写目录）。

## 5. 目录说明

```
<源码根>/
  config/console.json          运行配置（板端地址、数据目录）
  编译并启动.cmd / 构建.cmd / 启动控制台.cmd / 局域网诊断.cmd
  launcher/                    构建与启动脚本（PowerShell 5.1 兼容）
  console_v2/app/native/       Qt/QML/C++ 源码
  console_v2/app/service/      C# 服务源码
  console_v2/app/runtime/      构建产物：ConsoleV2.exe + Qt 运行库
  console_v2/app/build-dist/   Qt 增量构建目录
  console_v2/user_data/        会话/日志/标注状态（gitignore）
  pc_apps/range_fall/          离线分析、距离图、标注台依赖
  pc_apps/annotator_v2/dist/   旧版网页标注台静态资源
  src/human_fall_detection/    算法 core 与回放脚本
  src/inno_lidar_ros/config/ifw192s/  雷达角表
```

## 6. 常见问题

| 现象 | 处理 |
|---|---|
| 提示缺少 .NET/Qt/MinGW/CMake | 按第 1 节安装；或设置对应 `CONSOLEV2_*` 环境变量后重跑 `局域网诊断.cmd`。 |
| CMake 报编译器与 Qt ABI 不匹配 | Qt 必须用 MinGW 版，编译器用 Qt 自带的 `mingw1120_64`；不要混用 MSVC Qt。 |
| 界面起不来、日志写 `Mapping open failed` | 上一次窗口未完全退出或安全软件拦截命名管道/共享内存；关掉旧进程重试。 |
| 实时一直“连接中/无数据” | 板端地址是否可达（诊断里的 `boardReachable`）、板端识别服务是否在跑、防火墙 8765。 |
| 视频窗口/网页标注台不可用 | 安装 Python 并 `pip install numpy av pillow`，或在配置里填 `python`。 |
| 共享目录里删除/改名/保存标注失败 | 共享是只读的；把 `dataRoot` 指到可写目录，或给共享写权限。 |
| 日志/报告写到 `%LOCALAPPDATA%` | 源码目录不可写（例如放在只读共享盘），属于预期回退。 |

边界：界面里的目标/高度/低位提示都是几何结果，人体身份、真实跌倒和物理地面有效性
仍是 UNKNOWN；`confirmed` 默认关闭。分发源码不会改变这些语义。