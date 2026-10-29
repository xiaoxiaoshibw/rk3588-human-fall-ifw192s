# ConsoleV2 R0：事实基线

2026-10-24。仅调研与离线验证；没有 ConsoleV2 业务实现。事实来自当前脏工作树，不以 HEAD 代表未跟踪源码。机器记录见 `docs/evidence/2026-10-24_console_v2_r0/`。API 细表见 [API_CONTRACT.md](API_CONTRACT.md)，当前是候选契约，尚未通过新旧服务 Golden 对照。

## 入口、服务与配置

- 仓库说明提及的根目录 `open_console.bat` 当前不存在，不能写成可用启动入口；实际源码入口为 `pc_apps/console/console_gui.py`。其 `:297` 在同进程用 `runpy` 加载回放服务；默认环回 8901，占用后退到随机端口（`:318`）。新旧不能同时独占 8901，“并行安装”不等于同端口并行监听。
- `pc_apps/human_replay/human_replay_lib.py:34` 定义 PORT=8901；独立启动 `:917` 接受 HR_PORT；BOARD_MODE 下监听 0.0.0.0，其余 127.0.0.1。GUI 启动路径与独立 main 的配置读取不可混同。
- `pc_apps/console/console_gui.py:76` 启动联合录制服务；`pc_apps/console/joint_capture.py:475` 绑定环回随机端口。联合录制与回放原本是不同服务，不可据“相邻路由”误认为旧版全在 8901。
- `pc_apps/human_replay/config.py:13` 定义 SID_RE=`^[A-Za-z0-9_\-]{1,100}$`；`:19` BOARD_MODE；`:21` BOARD_URL；`:35` HR_DEST_ROOT；`:36` HR_FETCH_DIR。板端捕获 REST 默认 `http://192.168.31.58:8766`，GT 拉取另用 8088（`human_replay_lib.py:56`）。本轮没有连接设备。
- 浏览器依赖静态页面、脚本与 API 一起可达，不能仅凭 JSON 路由存在就宣布页面兼容。回放静态服务在 `human_replay_lib.py:250`，联合页根路由在 `joint_capture.py:419`。
- GUI实际依赖pywebview与WebView2（`console_gui.py:2`、`:25`）；PyInstaller打包通过_MEIPASS定位资源（`:29`）。壳页用replay_port/fall_port/capture_port/real_fall_port/plane_port等查询参数接入多服务（`:44`）。源码启动不等于打包启动验证，本轮不启动GUI。
- `pc_apps/console/console.html:133`起的入口包括会话回放、GT标注、会话数据库、联合录制、板端/相机及研究页；validation/human_detect/human_track等带archived标志，不能当作已删除API。相机直连8081/stream（`:141`）。离线原型可依赖sidequests数据（`console_gui.py:87`），静态证据页缺目录会返回None（`:61`）；清理后的完整GUI可用性尚未验证。

## 会话格式：源码优先，示例不是 schema

- `docs/human_capture/README.md:68` 是早期 XYZI float32、16B/点格式，帧 offset/count 都是点索引（`:92`）。不能以该节断言当前数据仅 16B。
- 当前转换器 `src/human_capture/core/bag2session.py:104` 的结构化行是 28B、小端：x/y/z/intensity float32 位于 0/4/8/12，ring uint16@16，padding@18，timestamp float32@20，padding@24。`:213` 输出 point_layout，`:221` 输出 point_stride_bytes。原 ROS timestamp float64@18 与导出 float32@20 不同。
- `frames[].offset_points/count_points` 决定切片，字节位置为 offset×stride；不能按 seq 当数组下标。`bag2session.py:184` 是实际索引生成处。
- 提示词中的数字是示例而非实测：R0 探针读取真实 meta，记录三帧原始字节 SHA 和首点解码；不重写 meta、不生成新点云。1GB/386/780/50万点是否满足分别核实，R0 不给渲染性能结论。
- 旧列表 `human_replay_lib.py:73` 只纳入同时有 meta/points 的合法目录；`:89` 强制非空 frames、非零文件且 bytes%28==0；`:94` 在 stride 和末帧索引存在时核对文件尾。它不是完整校验器，也没有普遍支持 16B。V2 数据层支持 16B 与 v1 列表保持旧筛选是两个要求；新增完整性视图走 v2。
- `cap_20261017_141348` 缺 meta 是已知状态，不能补造。本轮扫描结果（而非旧文档数量）写入 SESSION_SCAN.json。

## 数据、配平与 GT

- `data/README_数据目录说明.md:5` 说明 captures/remote、leveled、registration 是 junction。本轮检查链接类型和目标，不重建。data 是输入，测试写临时目录；不调用真实删除、改名、录制、下载。
- `pc_apps/human_replay/leveling.py:351` 用 resolve(root).parent/leveled 定位输出；`:180` 导出各方法 meta/points/transform/quality；`:270` report，`:296` manifest；`:327` 文件白名单与 SHA；`:376` leveled_latest 仅暴露符合资格且 SHA 对齐的 TLS。数据清理后结果可能已不存在，不能从历史报告推定当前可下载。
- `pc_apps/human_replay/gt_server.py:43` 用 HR_STORE_DIR 或源码旁 gt_store；`:123` 原子写；`:252` 起分发 session/save/auto/freeze/export/progress/alias。除 draft、GT_V*、fusion_frames，还需 manifest、aliases 及全局导出。冻结版本身份依赖 SHA，不能随意添加序列化字段。
- 联合录制 camera.mjpeg 由 `joint_capture.py:430` 输出 video/x-mjpeg；无视频返回 404 JSON；preview 没有 latest 时走普通 404（`:423`），不是空 JPEG。

## API 实际差异与待决事项

1. 旧 `/api/delete` 在 `human_replay_lib.py:533` 可向板端发 DELETE，`:569` 对本地 rmtree，无确认令牌。与新方案“无直接删除、确认后隔离、原响应不变”冲突。**V2 不实现或调用该删除行为，不能宣称全兼容**；R1 必须记录安全例外和旧页面行为，R7 不得把 removed 伪称为隔离成功。
2. 旧 `/api/rename` 在 `:579` 会改 meta.name；旧 `/api/save_annotations` 在 `:837` 会改 human_annotations。这与“meta 只读”冲突。R1 明确哪些用户触发的受控写可通过 IMutationGate；不能悄悄改成侧表而声称存储语义不变。
3. 旧 `/api/sync` 注释称子进程，实际 `:670` 在线程内 `fetch.process_session`，并先尝试 PATCH download_requested，再做本地已有判断（`:648`）。复用权威 fetch 是要求；不能把注释当实际进程模型。
4. 非环回与 BOARD_MODE 共用 `_multi`，顶层仅拒绝明确路由集合（`:380`）；GT 写并未一刀切禁用，配平/validation 另有同源规则。提示词“所有破坏性 POST 都 403”比旧策略更强，须逐路由标记而非声称现状已做到。
5. 主提示词末尾固定 R0、主提示词/R7 路由遗漏、API 服务归属在架构图重复，均待 R1 统一。`GET /api/version` 与 `/api/v2/*` 是新增目标，旧实现没有这些路由。

## 五项最大风险与后续输入

| 风险 | 已知依据 | 下一步 |
|---|---|---|
| A 路线绑定/Qt6/打包尚未验证 | 提示词第0节仅提出目标 | R2 分开测绑定加载、三帧解码、真实点数和50万压力、exe与高DPI；未测 UNKNOWN |
| 删除/只读/兼容语义矛盾 | 上述真实写入口 | R1 ADR 明确安全例外，禁止用正常化抹掉业务差异 |
| 列表字段缺省和16/28行为变化 | 本地独有行缺 size_bytes/download_requested/transferred | Golden 保留缺省与 null 区别；新能力进 v2 |
| 端口与多服务拓扑 | replay 8901 fallback、joint 随机口、GT 8088 | 明确冲突报错/配置与静态资源接法；旧页面逐页实测 |
| 真实数据/历史产物不可用及未知性能 | 缺meta、配平结果清理、无渲染实测 | 只读扫描绑定输入 SHA；R2 不用历史帧率推断新栈 |

R0 完成条件：事实表、路由清点、旧测试、真实只读 HTTP/解码与 OpenCode 只读审核落盘。后续是 R1 架构/ADR，再到 R2；在 R2 过线或据证切 B 之前不开展 R3—R9 业务实现。人体/物理效果与新栈性能均 UNKNOWN。

## 本轮机器观察

- SHA基线：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，41771份非忽略文件、9,609,477,505B；基线在R0文档初稿创建后、测试前采集，并非修改前原子快照。参见 WORKTREE_SHA.json、GIT.json。
- 24个会话目录中22个有meta/points，全部stride28，文件大小均与帧count总和一致；其余是缺meta的 `cap_20261017_141348` 与空 `.joint_fetch_staging`。54份会话文件SHA前后无变化；11份受查旧实现源码SHA无变化。没有真实stride16样本，后续只能明确使用临时夹具验证该格式。
- 指定R2输入 `cap_20261018_110029`：386帧、530,652,080B、最大49,124点/帧；首帧预算输入 `cap_20261017_113516`：780帧、1,072,369,704B、最大49,133点/帧。50万点负载必须另列构造方式，不能冒充真实单帧。
- 旧Python sessions_test 7、board_mode_test 4通过，均 `-B -W error`；JS human_replay_lib 46、human_detect_lib 11、human_pipe_lib 38与panel行为集通过。真实只读端到端选较小的 `cap_20261014_164522`：HTTP列出22段、meta逐值一致、完整points流式SHA一致，板端访问0次；三帧点数49121/49131/49134，记录原字节SHA与首点解码。没有测渲染帧率或声明V2性能通过。
- 探针初次struct格式多了一个float，随后Windows路径键分隔符不一致；已修正，FAILURE_01/02保留。旧测试无需因诊断脚本修正重复执行；最终CHECKS.json与REAL_READ_ONLY_E2E.json记录成功结果。
- 用户要求的OpenCode只读审核已落盘：[完整报告](../evidence/2026-10-24_console_v2_r0/OPENCODE_REVIEW_03.md)与REVIEW_RESULT_03.json。实际模型为opencode-go/gpt-6-luna、low，agent=r0audit，工具事件0；报告判定无R0阻断，提出2项中等与3项低风险文档修正，已逐项对照源码处理。前两次DeepSeek未完成尝试单独保留，未计通过。此审核不代表V2业务、Golden或R2已完成。
