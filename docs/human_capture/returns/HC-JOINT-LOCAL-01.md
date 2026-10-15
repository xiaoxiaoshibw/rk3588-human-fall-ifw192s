# HC-JOINT-LOCAL-01 R1 回传

- 用户授权：总控制台USB和雷达同时录制，数据直接本机，不放3588。
- Codex唯一writer；2026-10-13；SUBMITTED，独审NOT_RUN，未ACCEPTED。
- 唯一验收：[v1](../evidence/2026-10-13_hc_joint_local_r1/ACCEPTANCE_V1.md)。逐项与限制：[报告](../evidence/2026-10-13_hc_joint_local_r1/REPORT.md)。
- 起始分支master、HEAD 026e06303f60ed1bbe4ddc4d037836db68da6d27；console_gui/html/tests/README起时已有用户修改。新增块与文件按报告列出，未恢复旧Git版本。首读关键源码SHA记录在SOURCE_SHA.json。
- ponytail实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 根因：原控制台仅相机预览/板端录制；现直接读两路既有流，在PC统一编排并流式落盘。不使用板端staging/下载流程。
- 新增本机录制服务/页/测试；控制台实例端口、退出收尾、EXE/ZIP入口保持既有快捷方式目标。
- 26项自验通过；真实自动/手动两段、现有回放列表读取、冻结启动/浏览器验证。设备短录制PASS，时空标定/动作/长时/同步准确度NOT_RUN或NOT_EVALUATED。
- 真实链路已发现雷达设备跨度与接收跨度差异，详情LIVE_CHECK.json；保存原时钟与原消息，不伪造相机曝光时间或跨模态GT。
- 保持板端服务/配置/驱动/模型/GT/旧证据/旧会话，不提交推送。样本与源码/发布包SHA见SOURCE_SHA.json与RELEASE_CHECK.json。

## R2 用户真实超时返工（2026-10-13）

- 用户两次失败反馈授权修复；用户已关闭总控制台以更新EXE。Codex唯一writer，SUBMITTED未ACCEPTED，独审NOT_RUN。
- [唯一R2 v1](../evidence/2026-10-13_hc_joint_local_r2/ACCEPTANCE_V1.md)、[诊断/逐项报告](../evidence/2026-10-13_hc_joint_local_r2/REPORT.md)。
- 相机末帧后3秒超时，雷达仍在接收；板端maxsize4队列踢客户端但连接保持的机制与现象吻合，实际日志不可读，归因不冒称证实。
- 最小本机修复：相机传输有界重连、断段事件、明确错误来源、失败不吞文件写错误、元数据写完再发布终态。板端保持不变。
- 28项软件自验通过；真实30秒899相机/139雷达帧无超时，另手动停止通过。实际相机重连仅合成验证，独立保留本轮首个竞态失败。
- 雷达实际缺号126和时钟跨度差异保留，网络吞吐/完整性/精确同步未通过；本修复不宣称无丢帧。旧两段失败会话保留原状。
- 最终新EXE/ZIP、冻结启动与SHA在R2证据。技能路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。无部署/服务重启/模型GT/commit/push。

## R3 界面文案对齐（2026-10-14）

- 用户指出联合录制卡片/页面文案是旧"数据直接保存到本机"口径，与现行行为（板端先存、停止后拉回）不符。
- [唯一R3 v1](../evidence/2026-10-14_hc_joint_local_r3/ACCEPTANCE_V1.md)、[证据与逐处对照](../evidence/2026-10-14_hc_joint_local_r3/README.md)。SUBMITTED未ACCEPTED，独审NOT_RUN。
- 实际改动：console.html 卡片desc、README.txt 入口行与联合段、joint_capture.html 死状态 completed_with_gaps（删除）、joint_capture.py/test.py 过时注释；行为/接口/板端/数据零改动。技能路径C:/Users/30680/.claude/skills/ponytail/SKILL.md。
- 自验：console_html 12PASS、joint_capture 4PASS、console 7PASS、--check-joint-capture exit0 page_ok；日志与SHA在R3证据。
- 未闭合：停止后拉回仍为自动触发（无手动按钮）；EXE/ZIP未重打（有实例占用dist），文案要生效需重打并重启控制台。浏览器/设备NOT_RUN，不commit/push。

## R4 拉回完成自动打开回放 + EXE 重打（2026-10-15）

- 用户确认「下载完自动弹出加载界面，下载完之后结束」= 联合录制拉回完成后自动打开会话回放载入该会话（同一确认里"手动拉"歧义按自动收口，未改拉回触发）。
- [唯一R4 v1](../evidence/2026-10-15_hc_joint_local_r4/ACCEPTANCE_V1.md)、[证据与合同/重打记录](../evidence/2026-10-15_hc_joint_local_r4/README.md)。SUBMITTED未ACCEPTED，独审NOT_RUN。
- 实现（本机 PC 侧 6 文件）：联合页 completed 迁移 → `postMessage({type:'joint-completed', sid})` → `console.html` 校验本实例 origin + sid 白名单后打开会话回放并以 `?sid=` 载入（已开过回放强制重载）；`human_replay/index.html` 新增 `?sid=` 消费者；独立窗口打开时不跳。板端/数据/模型/GT 零改动。
- 自验：console_html 15（12旧+3新）、joint_capture 4、console 7、human_replay node 45/1/11/38/7、sessions+fetch 18 全PASS；源码与冻结 EXE 的 `--check-joint-capture` 双 exit0（`page_version` 3/3 内嵌契约 true）。冻结 `--check-startup`：replay/fall 服务起，real fall 因既有缺 `cap_20261013_094333`/`131958` 未起（源码同测复现，非本轮）；真机端到端实录 NOT_RUN。
- 重打包：`Console.exe` / `Console_Pointset.exe`（63,068,261 / 63,067,883B，备份 `.bak-20261015`）、`LiDAR_Console.zip` 重生成（125,861,355B）；构建输入与仓库源码逐文件哈希一致。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（复用 postMessage/URL 查询串/既有载入接口，零新依赖）。
- 限制：自定义保存目录不在回放服务目录下时自动载入失败（回放状态栏可见）；"弹出"= 控制台内切换（pywebview 吞 window.open）。无板端/部署/采集/commit/push。

## R5 拉回失败修复：fetch 子进程 → 进程内官方实现（2026-10-15）

- 用户反馈联合录制完成后「fetch 拉回失败；板端会话 cap_20261015_111738 仍为 ready」（186 帧/本机 0.0 MB 只剩 stub），直派修复"无法拉取"。
- [唯一R5 v1](../evidence/2026-10-15_hc_joint_local_r5/ACCEPTANCE_V1.md)、[根因/现场恢复/重打记录](../evidence/2026-10-15_hc_joint_local_r5/README.md)。SUBMITTED未ACCEPTED，独审NOT_RUN。
- 根因（R2 提交 6ecc3a2 引入 `_StagedFetch` 后，两条运行路径都不可用）：`_StagedFetch.pull` 起 `sys.executable -I fetch.py`——冻结版 sys.executable 是 Console.exe 本身（子进程=再开一个控制台：用户日志 stdout 可见 51004 端口、mode=SOURCE_BYPASS、real fall 报错；exit=0 且看似"正常"所以无报错可读）；源码版 py3.11+ 的 `-I` 隐含 `-P`（脚本目录不进 sys.path，`import config` 直接失败）。两点均已实测/日志双证。
- 修复（本机 PC 侧 2 文件，零新依赖）：pull 改**同进程** `runpy.run_path` 调官方 `fetch.process_session`（SHA/布局校验、状态机、失败回退全部沿用）；`FETCH_DIR` 源码/冻结(_MEIPASS) 两分支解析；页面自定义「雷达板端服务」地址传导官方 fetch（原版忽略）；新增 StagedFetchTest 2 用例钉死合同。另清理该文件一次写盘竞态残留的杂散行并全量复验。
- 自验：joint_capture 6、console 7、console_html 16、sessions+fetch 18 全 exit0；源码 `--check-joint-capture` exit0。**真实板端端到端拉回**（板端控制词打桩、fetch 走真网络）11:17 的 cap_20261015_111738：186 帧、points.bin 255,522,036B（9,125,787 点×28B 整）、板端 ready→transferred，`joint_cap_20261015_111738` 原地补全为可回放会话。冻结 `--check-joint-capture` exit0（page 3/3），`--check-startup` 因既有缺 `cap_20261013_094333` exit1（同 R4）。
- 重打包：`Console.exe` 193,806,359B（备份 `dist/Console.exe.bak-20261015_before_jointfetch` = 11:07 版）、`LiDAR_Console.zip` 151,031,729B；zip 内源码与仓库同哈希；exe 内嵌 `human_replay\fetch.py` 在 archive 列表可见。重打后须**重启总控制台**（joint_capture 模块在 exe 内嵌，源码旁路不覆盖它）。
- 限制：冻结 exe 内真实「录制→拉回」整链与浏览器人工操作 NOT_RUN；`--check-*` 目的文件独占创建，重跑指到旧文件会 FileExistsError（用户此前 traceback 即此，非录制缺陷）；相机仍不写盘（0B 占位，现行设计）。板端/驱动/配置零改动，无部署/采集/commit/push。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full 强度；复用官方 fetch.py 本体、删 subprocess）。

## R6 复盘整改（A1–A4/A7/A8）与重打（2026-10-15）

- 触发：用户"是不是代码架构问题，深入排查审查" → 全仓复盘得出 A1–A8；随后"逐个修复然后审查 返工 打包 没问题就不返工"。
- [唯一R6 v1](../evidence/2026-10-15_hc_joint_local_r6/ACCEPTANCE_V1.md)、[证据与逐项/重打记录](../evidence/2026-10-15_hc_joint_local_r6/README.md)。SUBMITTED未ACCEPTED，独审NOT_RUN。
- 修复（PC 侧 5 文件）：**A4** 发布探针新增 `joint_fetch_ok`（`load_fetch` 加载 + `process_session` 可调用，不触网；纳入 `--check-joint-capture` 退出码——同类集成点 bug 下次重打即被拦）；**A2** 拉回目录单源化（`console_gui._replay_dir()` 解析一次经 `fetch_dir` 传入，joint_capture 仅缺省时按源码/`_MEIPASS` 回退）；**A3** `joint.json` 补 completed/failed 终态（`finished_iso/radar_frames/bytes/error`，写失败不伤已落盘数据）；**A1** `human_limb` 冻结守卫（冻结形态 import 即明确退出，源码不受影响）；**A7** 删 `human_replay_lib.py` 未用 `import subprocess`；**A8** 检查报告已存在 → 可读提示 + exit 2（原 FileExistsError traceback）。
- 未修（记录级）：A5 板端 IP/端口硬编码散落 5+ 处（需注入机制，另轮）；A6 `cap_*`/`joint_*` 双拉回编排并存（R5 已文档化）。
- 自验：joint_capture **7**（+1 `load_fetch`）、console 7、console_html 16、sessions+fetch 18 全 exit0；源码与冻结 `--check-joint-capture` 双 **exit0** 且 `joint_fetch_ok=true`（page 3/3）；`--check-startup` exit1（既有缺 `cap_20261013_094333`）；A8 重复写 exit2 无 traceback；human_limb 守卫双向探针；真实 E2E（打桩板端 + 真实 fetch 只读复制 → 临时目录）**completed**、`joint.json` 终态、`points.bin` 255,522,036B 整、板端状态机未动（临时目录已清理）。
- 重打包（含两轮审查返工）：`console_gui.py` 为共享文件，被并行工作流 13:00:25/13:07:57/13:17:52 三次写入（learn 扩展 hook，`CURRENT.json` 未放置=停用态；handler 定义已接受全部参数）。stage1（13:02）落在写 #1 窗口 → 判定不可复现弃用；stage2（13:11）正确冻结写 #2（PKG 阶段读取）；写 #3（13:17:52）不追入本轮产物（该工作流自管打包）。终版 `Console.exe` 193,807,707B/B2457635…（备份 `.bak-20261015_r6_stage2`=终态副本、`.bak-20261015_r6_stage1`、`.bak-20261015_before_r6`=R5 版）、`LiDAR_Console.zip` 151,034,726B/495B8901…（13:15 重生成）；zip 内 `源码/joint_capture.py` 与树头同哈希、`源码/console_gui.py` 为构建冻结版（差异归档 `PARALLEL_CONSOLE_GUI_ZIP_vs_TREE.diff`）。生效须**重启总控制台**。
- 限制：冻结 exe 内真实「录制→拉回」整链与独审 NOT_RUN；编辑期间 `joint_capture.py` 两次出现写盘竞态残片（字节级清理 + 全测试复验 + 双读 SHA 稳定后才入库，终态哈希在 `FILE_SHAS.json`）。无部署/采集/commit/push。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full；复用官方 fetch 唯一加载器，零新依赖）。

## R7 雷达被拉两遍（同数据两名）根因修复（2026-10-15）

- 用户直派「现在视频和雷达实时录制有 bug，雷达数据会被拉两遍但是名字不一样」并贴面板两行（同帧/同长）。
- [唯一R7 v1](../evidence/2026-10-15_hc_joint_local_r7/ACCEPTANCE_V1.md)、[根因/对照/限制](../evidence/2026-10-15_hc_joint_local_r7/README.md)。SUBMITTED未ACCEPTED，独审NOT_RUN。
- 根因（R6 记录级 A6 的落地）：联合拉回落 `output_root/joint_<sid>/`，而板端登记与回页面板都按 `local.get(sid)` 找本机副本 → 板端行判「本地无」→ 点行 `/api/sync` 再拉一遍成 `captures/remote/<sid>/`，同时 `joint_<sid>` 又作为 local-only 行单列。现场两份 `points.bin` 同为 237,644,764B（142730，14:27:57 / 14:28:17）与 255,522,036B（111738）；真板 `download_requested=true` 证明第二份来自面板行点击。
- 修复（PC 侧 5 文件，零新状态/零新依赖）：会话目录名改为**板端 sid**（与面板同键，`/api/sync` 短路 `C.DEST_ROOT/<sid>/meta.json` 天然命中）；sid 白名单守卫（异常 sid 不落路径、不拉回）；联合页 sid 兜底与文案、README、console_html 示例同步。
- 自验：面板行为对照（隔离临时根 + 真板只读 GET）改名前两行 `local=false`/`local-only`、改名后一行 `local=true`（`PANEL_ROWS_BEFORE/AFTER.json`、`panel_row_probe.py`）；`joint_capture_test` **8**（+2）、`console_html` **17**、`console_test` **7** 全 exit 0；`human_replay` 代码零改动。
- 重打与生效（用户选定「重打 EXE/ZIP 并重启总控制台」）：`Console.exe` **193,812,397B / 2E275737…**、`LiDAR_Console.zip` **151,042,810B / 44A9711F…**；冻结 `--check-joint-capture` **exit 0**（page 3/3、`joint_fetch_ok` true），`--check-startup` exit 1（`real fall replay did not start`，R4/R5/R6 冻结探针逐字同一既有失败）。首轮重打（193,810,755B）落在并行写入窗口内弃用（备份 `dist/Console.exe.bak-20261015_r7_stage1`）；stage2 构建窗口前后输入哈希一致，zip 内源码副本与树逐文件同哈希（`BUILD.json`）。
- 合并后复验：并行工作流的「相机落盘」特性并入同一 `_run`（`camera.mjpeg`+`camera_frames.jsonl`+`/api/camera`），终态 `joint_capture.py=1FCF83A0…`；源码 **10**/**17**/**7** 全 exit 0（`*_POST_MERGE.log`，R7 当轮 8 项日志按不覆盖原则保留）；运行中的冻结 exe 行为探针（`/api/camera` 会话专属 404 vs `/api/bogus` 通用 `not found`，页面含 R7+R8 文案）证代码已在 exe 内（`RUNNING_EXE_PROBE.txt`）；15:02 重启总控制台，joint 服务 idle、输出根 = 面板同一物理目录（`RESTART_CHECK.txt`）。
- NOT_RUN/限制：真机改后新录一段（面板应只一行）NOT_RUN（现场验收）；现场 3 组重名副本未动（`captures/`/`data/` 处置需 sid+字节+sha256 清单 + 用户确认）；独立复审 NOT_RUN；未 commit/push/部署。
- 并行写入如实记录：本轮编辑期间 `joint_capture.py` 被另一路工作流 14:38:46（加相机落盘）/14:40:29（撤回）两次写入，本轮改动存活，片段存 `R7_CHANGE_HUNKS.txt`。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full；一行改名 + 一处守卫，复用面板既有 sid 键，零新依赖）。

## R8 相机预览同步落盘（camera.mjpeg + 逐帧索引）（2026-10-15）

- 触发：用户「视频看不了 / 把视频文件拉下来」。只读核对：三个联合会话 `camera.mjpeg` 恒 0B；板端 8081 只有 `/stream` / `/snapshot` / `/status`（`/files` `/list` `/recordings` `/record` 等一律 404），无录像/历史 → 那两次录制的相机画面从未保存。用户选择「给联合录制加相机写盘」。
- [唯一R8 v1](../evidence/2026-10-15_hc_joint_local_r8/ACCEPTANCE_V1.md)、[证据/限制/并行写入记录](../evidence/2026-10-15_hc_joint_local_r8/README.md)。执行者 OpenCode CLI `opencode-go/deepseek-v4.1-flash`（用户直派 writer）；SUBMITTED未ACCEPTED，独审NOT_RUN。
- 实现（PC 侧 4 文件，零新依赖）：`Recorder._camera_preview_only` 录制中把预览帧逐条写进会话 `camera.mjpeg`，并把 `{offset,length,recv_unix_ns}` 记入 `camera_frames.jsonl`（跨断流重连续写；接收时刻非硬件同步，仅作索引）；`_run` 停板后 `stop_event.set()`+`preview.join(10)` 先关文件再组装，`joint.json` 增 `camera_frames`；新增 `GET /api/camera?sid=`（流式回放该会话录像，sid 白名单，越权/无文件→404）；联合页新增「相机录制回看」逐帧播放/拖动面板；`README.txt`/页面文案同步。
- 自验：`joint_capture_test` **10 PASS**（+2：帧落盘、路由边界）、`console_html` **17**、`console_test` **7** 全 exit 0；联合页 JS 语法检查通过。日志/SHA 在 R8 证据。
- NOT_RUN/限制：真机端到端（真板相机→落盘→页内回看，需重打+重启+设备）与 `human_replay` 回放器内嵌同屏显示未做；回看只对最近一次联合会话；相机与雷达未做硬件同步。**EXE 未由本轮重打**——R7 并行工作流 14:50/14:57 两次重打因 `joint_capture.py/html` 早于其打包，已把本改动带入冻结 `Console.exe`，生效须以 R7 终版为准并重启总控制台；R7 的 `FILE_SHAS.json`/`TESTS_*.log` 早于本改动，已过期，需重生成。板端/数据/模型/GT/`human_replay` 零改动；无 commit/push/部署/采集。技能路径 `C:/Users/30680/.config/opencode/skills/ponytail`（skill 工具加载，full；复用既有 `jpeg_frames` 与预览线程，只加落盘 + 一条只读路由 + 一个页面播放器）。
