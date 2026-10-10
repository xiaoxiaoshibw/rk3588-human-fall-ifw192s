
# 会话入口集成与新 EXE 发布验收（R2）

2026-10-10，Asia/Shanghai；Codex 主控。用户本轮明确授权源码集成、真实构建、更新 dist 和实际 EXE 验证。状态：SUBMITTED，逐项自验见下表；不将独审意见、测试数量或本地运行等同于现场识别准确率验收。

## 已交付的结果

最小入口补丁已应用到 `D:\Code\ldiar`，新 `pc_apps/console/dist/Console.exe`、`LiDAR_Console.zip` 及已有的解压目录 `dist/LiDAR_Console/` 已更新。另生成 `dist/session_sync_test_20261010/Console.exe`；交付目录中的 `Console.session-sync-test.exe` 与最终 dist EXE 字节相同。

**新 EXE 两张卡片均不再带固定 sid。** 实际启动新 EXE 后，访问它自己持有的壳页和回放服务、点击卡片，传统聚类与人检锁定均实际载入 `cap_20261009_181716`：45 帧、2,210,880 点、61,904,640 字节。旧 sid `cap_20261004_203349` 能被明确指定；非法 sid 有可见提示并回退；真实 `_clip_…` 会话深链亦已通过。

| 产物 | SHA256 |
|---|---|
| Console.exe / Console.session-sync-test.exe | `e66ce260a0aa994b1880a4dba1fcb7fe4dc991a95bb4f1172cd4e35634c7341b` |
| LiDAR_Console.zip | `758afea0114a408792eeb81b912e9c86e76ef1a33bb6935068151a29ecd4c413` |
| 备份的旧 Console.exe | `9a1822cc5da8917b4bfb113b1fa0cc3411f0237b10857d8a032f843c926c9f50` |

最终 EXE 65,103,408 字节，ZIP 65,214,120 字节。详细产物路径、大小及校验见 `evidence/artifacts.json`。

## 基线、备份与修改边界

原仓库 master / HEAD `347a5bf05ee82766436382f4fc3d1a8ed15c1132` 保持不变；未 commit、push、reset 或 clean。原树本来就有大量未提交和未跟踪文件，本轮未用 HEAD 整树覆盖它们。

应用前核验上一轮全部 151 个交付文件 SHA，核验原源码与上一轮基线、隔离 7 文件副本及旧 dist SHA，均一致。记录当前 83 个范围内源码/资产文件的 SHA、Git 状态，备份被修改文件及旧 EXE、ZIP、解压版 EXE、INI，然后 `git apply --check --ignore-space-change` 成功，再应用补丁。Git 的 CRLF 空白告警已记录；仅规范化本轮 7 个入口/测试文件的换行，未格式化其他源码。

最终实际修改 8 个既有文件，新增 3 个文件：

| 范围 | 文件与用途 |
|---|---|
| 原入口补丁 | human_detect.js、human_detect.html、human_track.html、human_replay_lib.py：统一发现、默认与深链，独立提示；索引排除缺文件、坏 JSON、空帧/空点及非 28B 对齐文件 |
| 新增文件 | session_selection.js、session_selection.test.js、session_selection_test.py |
| 本轮真实数据兼容返工 | session_selection.js 支持合法剪辑后缀、100 字符上限；显式空 sid 提示为“（空）”，测试覆盖相应拒绝路径 |
| 发布配套 | Console README.txt 更新行为与测试版说明；make_release.py 将入口及测试文件纳入 ZIP 的参考源码 |
| EXE 验收揭示的启动缺陷 | console_gui.py 禁止地址复用、Windows bind 前设置 SO_EXCLUSIVEADDRUSE，默认端口不可用时选独立随机端口；其他绑定错误重新抛出。console_test.py 改为真实占用套接字回归，并验证实际 socket 属性及错误传播 |

当前 Console **源码**两卡早已不带 sid，因此 `console.html` 未被本轮重复修改；通过真实重建将它送入新 EXE。

算法、RF 模型、阈值与点云处理流程没有被改动。`human_detect_lib.js`、`human_pipe_lib.js`、`rf_person.js`、`rf_person_v1.json`、`detect_overlay.js`、`replay.js`、`panel.js`、`bg_envelope.json`、`config.py`、`leveling.py`、`human_replay_lib.js` 均与本轮现行基线 SHA 一致，其他范围内非允许文件亦无改动。B2-A-FIX-R1 的 notify/reset/attach_color/frame identity 路径原样保留。

需要区别：旧 EXE 与当前源码在 detect_overlay、replay、panel 上本来就有既有差异；新包包含当前源码的这些版本。本轮没有重写它们，也不声称它们与旧包字节相同。对应差异和 SHA 在 `baseline.json`、`final-scope.json`。

## 真实 EXE 端到端问题及修复

最初的新 EXE 和既有 Python 服务在 Windows 上同时监听 8901。标准 HTTPServer 使用 SO_REUSEADDR，第二个 bind 未必报错；请求实际落到既有源码服务。仅看到 EXE 持有端口，不能证明 HTTP 响应来自它。该轮浏览器结果已封存为 **NOT_ACCEPTED_AS_EXE_E2E**，没有计入最终通过记录。

修复是局限于 Console 启动器的服务器子类：禁用 reuse；Windows 使用 SO_EXCLUSIVEADDRUSE；只对地址占用/访问拒绝等端口不可用错误回退，EINVAL 等错误原样抛出。原函数返回实际端口，壳页 query 与 iframe 随实例端口更新。SO_REUSEADDR 可能造成共享端口请求归属不确定，独占选项须在 bind 前设置，见 [Microsoft Winsock 文档](https://learn.microsoft.com/windows/win32/winsock/using-so-reuseaddr-and-so-exclusiveaddruse)。

最终测试不再仅检查某进程持有端口，而是检查**该端口只有一个 listener owner**：

| 实例 | EXE 启动路径 / 回放与壳页端口 | 实际验证 |
|---|---|---|
| 无 INI 的打包副本 | work/exe-runtime-r2/Console.exe，57408 / 28508 | 两份真实会话副本；两页默认、旧 sid、非法 sid；真实 running 配平任务；打包资源故障注入 |
| 已安装 dist | D:\Code\ldiar\pc_apps\console\dist\Console.exe，63576 / 44857 | 原 INI 保持不变；两张卡片实际加载最新；真实剪辑深链 |

两实例均从最终 EXE 字节启动，不是 Python 源码服务替代。功能 UI 操作通过浏览器访问同一 EXE 进程持有的壳页和 iframe 服务；未使用原生窗口鼠标自动化。原生 EXE / WebView2 进程已启动，端口 PID、路径、owner 和页面 DOM/截图均保留。

## 场景验收表 v2（本轮唯一当前表）

| ID | 要求 | 自验结果 / 证据 |
|---|---|---|
| R2-01 | 原源码、隔离补丁、旧 dist 与证据 SHA，备份后集成 | PASS：baseline.json、backup/、integrated-source.patch、final-scope.json |
| R2-02 | 无 sid 默认最新；稳定排序与半成品排除 | PASS：最终 Node 12 组；真实 EXE 两页加载最新；Python 两种本地接口排除 meta-only 等输入 |
| R2-03 | 合法旧 sid 与合法剪辑 sid 保留 | PASS：打包实例旧 203349 两页；安装 dist 的真实 clip 深链；不把缺 meta 的旧固定 sid 当有效样本 |
| R2-04 | 非法/不可用 sid 提示与回退 | PASS：两页真实 EXE 非法深链；Node 缺失/空 sid 回归 |
| R2-05 | 空列表与 API 失败清晰结束 | PASS：通过 localhost 故障代理，仅把列表响应替换为空或 HTTP 503；HTML/JS/其他资产均来自最终 EXE；两页禁用下拉并显示清晰提示 |
| R2-06 | 配平中会话仍可发现，不依赖 TLS 完成 | PASS（入口条件）：在隔离真实数据副本的新 EXE 上 POST 配平，实测 job=running 时本地列表仍包含该 sid；leveling-in-progress.json |
| R2-07 | 真实构建、更新 dist 与测试版产物 | PASS：PyInstaller 最终退出 0；make_release 退出 0；ZIP 内 EXE 与源码 SHA 一致 |
| R2-08 | 新 EXE 真正启动、链接与数据一致 | PASS：compiled GUI 与最终源码的字节码/常量结构相同；14 个静态/源文件 SHA 一致；独占端口、无固定 sid、浏览器真实加载 |
| R2-09 | B2/RF/算法/阈值保护与相关回归 | PASS：16 套集成回归；最终选择 12 组、Console 5 项；冻结资产 SHA 不变 |
| R2-10 | 独立 OpenCode 审核与反馈处理 | PASS（审核执行与闭环记录）：本轮所有审核调用返回；意见、返工、自验与处理依据均保存。未将模型退出码当成无缺陷结论 |
| R2-11 | 原服务、生产原始数据及板端保护 | PASS：原 Python PID 8356 / 8901 始终保留；原始会话输入 SHA 不变；板端零操作；配平产物只写隔离副本目录 |
| R2-12 | 证据、回滚与报告 | PASS：交付目录、仓库 evidence/returns、验收表 SHA 与备份清单 |

R2-05 是明确的故障注入测试，不声称生产目录真的被清空或生产 API 自然返回 503。R2-06 使用软件测试数值 config（pitch=0、roll=0、height=1.0），**不是现场安装角/高度确认**。任务随后 `failed: floor_not_found`，说明这组测试配置未找到假定地面；未修改阈值来制造成功，也不把它称为配平质量通过。它验证 raw 完整会话在 running 状态仍被发现；两页实际解析加载另有 UI 证据，但没有把该 UI 加载时刻称为任务仍处于 running。本轮没有现场识别精度、地面物理校准或板端采集结论。

本地最新有效会话仍为 181716；远端是否有更晚会话未查询，也没有 fetch、重新采集或操作板端状态。旧固定 `cap_20261002_223757` 当前缺 meta.json，无法作为有效显式深链测试输入。

## 构建、回归、独审与证据

真实打包使用已安装 Python 3.12.10、PyInstaller 6.21.0、项目 Console.spec，NumPy 1.26.4；未安装新依赖、未改 spec。构建先写暂存 dist/workpath，核验后更新目标 dist。源目录稳定后的最终构建及 compiled bytecode 比对防止将中间版本误发布。构建迭代日志都保留，未用中间产物替代最终测试。

16 套集成回归全部退出 0；随后针对真实 clip、提示文案和端口问题进行必要复验：选择器最终 12 组通过，Console 最终 5 项通过。Python 使用 `-B -W error`。原全树 diff 空白检查因既有 CRLF/历史差异报错；最终限定范围、识别 CRLF 的检查另存，不通过格式化其他文件掩盖失败。

OpenCode 使用 `opencode-go/deepseek-v4.1-flash`，工具全部禁用、只读提供有边界的审阅材料，设置 360/240/120 秒超时并实时保存日志。本轮未超时：入口首审与补审、端口首审与返工复审、测试闭环复审都返回了文本。

意见处理：空 sid 提示已修正；冷启加载函数在普通同步 script 的顶层赋值，时机经代码与实测确认；新脚本经内嵌 SHA 确认入包；Windows 端口问题增加独占绑定与错误过滤；独审指出 EINVAL 测试若两次都报同错会虚假通过，已新增 constructor 尝试次数断言，并复验；正向 EADDRINUSE 回退本来已有真实占用端口测试，删掉 fallback 会使该测试直接报错，独审最后提出的条件性覆盖提示已据此核对。未把“未执行测试”的模型意见改写成模型亲自执行或无条件整体 PASS。

使用 ponytail 技能，路径 `C:\Users\30680\.codex\skills\ponytail\SKILL.md`；浏览器使用当前 CUA API。Codex 是唯一生产源码写入者；OpenCode 没有代码修改或执行权限。

主要证据：baseline.json、final-scope.json、integrated-source.patch、build-command/result、pyinstaller 日志、make-release 日志、embedded-verification.json、artifacts.json、回归日志、selector-final、console-final、最终 EXE runtime JSON、final-exe-browser-cases.json、leveling-in-progress/job-final、fault-proxy 请求日志、OpenCode 所有 packet/JSONL/结果/文本。

## 回滚与保留事项

`backup/` 保存改动前源码与旧产物，包含源码已存在的用户差异。需要回滚时，仅从备份恢复本轮被改动文件和目标 dist；三个新增入口/测试文件的删除也应限定到本轮路径。不要 git reset/clean，不要用旧 HEAD 或旧 EXE 内嵌源码覆盖整个脏工作区。现有 INI 未修改。

打包副本的测试原始文件与派生产物都在 work/exe-runtime-r2，未覆盖 captures/remote 的生产数据；测试启动的 EXE、浏览器页和故障代理均已关闭。用户原回放服务未重启，它的 Python 模块可能仍保留启动时版本；使用**更新后的 Console.exe**，它会选自己的独占端口，避免混用该服务。

验收表 v2 SHA256：3daaec5d0fbfe40e932a23fafc738f11aaddcbbba97b9e1286bd706d117648e6

补充完整性边界：本地索引检查文件存在、JSON/非空帧表、非空点文件与 28B 对齐，不代替逐帧偏移或逐点内容的全量数据验真；本轮真实测试输入另有源 SHA 及配平 source 契约检查。历史 gl/hr02 等版本目录未覆盖，本轮更新目标以 artifacts.json 为准。
