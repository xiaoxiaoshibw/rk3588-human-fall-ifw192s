# ConsoleV2（Qt 应用开发版与 R2 技术验证）

2026-10-25：按用户要求三线并行推进，新增独立 `app/`：真实会话回放、同帧距离图结果、Foxglove实时目标订阅、USB联合录制客户端。入口 `python -B -W error console_v2/app_dev.py run --analysis <analysis.json>`；完整运行方式与边界见 [app/README.md](app/README.md)。应用未替代旧控制台，R2历史spike/单文件包保持，干净系统/真正冷机等缺口仍未收口。

以下为保留的 R2 技术验证入口，不与新应用能力混算。

当前是 Qt C++ Quick3D 宿主 + C#/.NET8 只读 spike（路线 B），不是完整控制台。结论与尚未验证的门槛见 [SPIKE.md](../docs/console_v2/SPIKE.md)。A 的固定 Qml.Net 0.11.0 发布包需要 Qt5，真实加载 Qt6 失败；未使用路线 C。

## 日常开发

`python -B -W error console_v2/dev.py run` 增量构建后查看，`python -B -W error console_v2/dev.py check` 构建并跑差分/原生离线检查；不重打单文件发布包。模块修改位置、离线开发和发布验证的区别见 [开发与迭代](../docs/console_v2/DEVELOPMENT.md)。

## 运行已打包程序

在仓库根 PowerShell 执行。程序不自动连接板端，不监听 HTTP，不改真实会话；运行到期自动退出。报告文件必须不存在，重复运行需用新的报告名；解包缓存可复用但不能覆盖不完整目录。

```powershell
$r2out = Join-Path $env:LOCALAPPDATA 'ConsoleV2/SpikeEvidence'
$r2runtime = Join-Path $env:LOCALAPPDATA 'ConsoleV2/SpikeRuntime'
New-Item -ItemType Directory -Force -Path $r2out | Out-Null
$r2report = Join-Path $r2out ('run_' + (Get-Date -Format 'yyyyMMdd_HHmmss_ffff') + '.json')
& ./console_v2/spike/package-single/SpikeService.exe --session D:/Code/ldiar/data/sessions/cap_20261018_110029 --count 500000 --duration 10 --extract-root $r2runtime --report $r2report
```

`--count 0` 显示前三个真实帧；`50000`、`500000` 为明确标识的合成平铺压力。`--updates static` 不重复上传；默认 dynamic。`--decode-only 1` 只验证解码，`--self-test 1` 运行编解码自检。输出仅允许本轮 evidence 或上述 AppData 专属目录，路径含目录 reparse point 拒绝；没有删除、搬移数据入口。

## 复现构建与检查

已准备的依赖全部位于 `.tools/`，不要求 VS：.NET SDK 8.0.426、Qt6.5.3 MinGW、GCC11.2。Python3.12/NumPy/psutil、CMake 与 Node 来自开发机现有环境；它们只用于开发与核验，不随程序要求安装。依赖获取与中断记录保留于 R2 evidence；下载器不当作通用安装器。A 探针保留在 `spike/a_probe/`。

用 `tools/run_spike_command.py <新日志名> <程序> <参数...>` 在限定可携 SDK 环境运行并保存 argv、退出码与 stdout/stderr；日志名不可复用。构建顺序：

```powershell
$env:CONSOLEV2_SPIKE_OUT = Join-Path $r2out ('repro_' + (Get-Date -Format 'yyyyMMdd_HHmmss_ffff'))
python -B -W error console_v2/tools/run_spike_command.py configure_repro 'C:/Program Files/CMake/bin/cmake.exe' -S console_v2/spike/native -B console_v2/spike/build -G 'MinGW Makefiles' -DCMAKE_BUILD_TYPE=Release -DCMAKE_CXX_COMPILER=D:/Code/ldiar/console_v2/.tools/qt/Tools/mingw1120_64/bin/g++.exe -DCMAKE_MAKE_PROGRAM=D:/Code/ldiar/console_v2/.tools/qt/Tools/mingw1120_64/bin/mingw32-make.exe -DCMAKE_PREFIX_PATH=D:/Code/ldiar/console_v2/.tools/qt/6.5.3/mingw_64
python -B -W error console_v2/tools/run_spike_command.py build_repro 'C:/Program Files/CMake/bin/cmake.exe' --build console_v2/spike/build --parallel 8
python -B -W error console_v2/tools/run_spike_command.py deploy_repro console_v2/.tools/qt/6.5.3/mingw_64/bin/windeployqt.exe --no-translations --no-opengl-sw --qmldir D:/Code/ldiar/console_v2/spike/native --dir D:/Code/ldiar/console_v2/spike/package-dev D:/Code/ldiar/console_v2/spike/build/QtSpike.exe
python -B -W error console_v2/tools/package_spike.py publish_repro
```

`windeployqt` 采用自动 debug/release 匹配，不能强加 `--release`，本次 MinGW plugin 判定会漏平台插件。Qt 安装模块含 declarative/Quick3D/ShaderTools/QuickTimeline，完整成功命令见 evidence 的 command.json。单文件 publish 为 self-contained win-x64，包含 Qt payload 的逐文件 SHA manifest；不会携带源数据。

核验入口 `python -B -W error console_v2/tools/verify_spike.py --single` 对实际 exe 做三真实帧 × 三模式的 Python 差分与反例；`measure_spike.py formal` 保存启动/动态/静态/DPI 原始样本。共享命令工具现在默认生成全新的 `.tools/spike-evidence/runs/` 私有目录，拒绝历史evidence作为输出。核验未重发的旧单文件包时，仍需如上设置 `CONSOLEV2_SPIKE_OUT` 为该旧包支持的全新AppData专属目录；日常开发直接使用 `dev.py check` 和当前服务DLL。`finalize_spike.py` 是R2归档专用程序，依赖其基线文件；不要把归档目录作为新运行输出。本轮已有结果见SPIKE，历史机器产物保持只读。

后续业务按 R3→R9 顺序，在 R2 未验证项明确收口后继续；API 默认 127.0.0.1:8901 和旧契约不因本 spike 改变。R1 分层与写入隔离要求在产品代码中实现，本探针的固定三帧数组/同步服务/粗粒度进程生命周期不直接当作产品数据层。
