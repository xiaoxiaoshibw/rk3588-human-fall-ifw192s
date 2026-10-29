# ConsoleV2 API 契约清点（R0 草案）

旧实现是 oracle。以下记录实际行为，不代表 V2 已实现；R1 处理安全冲突后冻结，R7 执行新旧差分。所有行当前 V2 状态 NOT_IMPLEMENTED。文件与行号以本轮源码 SHA 为准。

R1状态补充：已交付[架构](ARCHITECTURE.md)与[ADR-003](ADR/ADR-003-api-compatibility.md)。旧oracle行为基线保持；直接删除、meta写入、远程写策略、授权token与GET副作用存在相互冲突的要求，尚未获准作为兼容例外，故本文仍为候选契约，**不宣称“全部路由已冻结为可实施契约”**。R2只读spike可继续；R7全兼容/R9迁移通过必须保留这些未解项，不能由作者修改Golden消除失败。

## 回放服务（human_replay_lib.py）

JSON 通常为 `application/json; charset=utf-8`，带 Content-Length 与 Cache-Control:no-store（`:209`）；`send_error` 默认 HTML，不能统一改为 JSON。成功默认 200。非环回或 BOARD_MODE 的顶层拒绝为 403 JSON `{ok:false,error:string,board_mode:true}`（`:60`），即使只是非环回 board_mode 字段也为 true。

| 方法/路径 | 参数与响应 | 状态/安全与代码 |
|---|---|---|
| GET /api/sessions | scope=local 时不访问板；sessions,board_error,hidden{purged,missing} | 200 JSON；`:301` |
| GET /api/manifest | sid；sid,local{present,files[{name,bytes,sha256}],total_bytes},board | 非法sid 400 JSON；板404/不可达写进 board.error 仍200；`:506` |
| GET /api/file | sid,name 仅 meta.json/points.bin；原字节 | 200 application/octet-stream，Content-Length，1MiB块；非法400 HTML，缺失404 HTML；`:275` |
| GET /api/board/status | 透传状态加 current/current_created_iso；状态不可达只返回 ros:down,error | 200 JSON；无current/查询异常填null；`:355` |
| GET /api/sync_status | running(bool),sid,last_sid,last_result,last_error,recoverable(bool),recover_sid；闲置初值相应null/false | 200 JSON；`:696` |
| POST /api/sync | {sid}；ok,note 或 ok:false,error | 缺sid400 HTML，忙409 JSON，其余200；multi禁403；`:638` |
| POST /api/board/record/start | body实际未转发，调用板端空JSON | 200或板HTTP原码JSON，连接失败502；multi禁403；`:402` |
| POST /api/board/record/stop | 同start | 同上；`:404` |
| POST /api/board/request_download | {sid} → PATCH板端{extra:{download_requested:true}} | 缺sid400 HTML；代理错误同上；multi禁403；`:406` |
| POST /api/recover | {sid}；ok,sid 或 ok:false,error | 非法400、缺模块503、失败409、成功200 JSON；multi禁403；`:709` |
| POST /api/load | Tk选择；取消{ok:false}，成功{ok:true,sid} | 200；根外/缺文件400 JSON；multi禁403；`:773` |
| POST /api/delete | {sid,scope:local/board/both}默认both；sid,board?,local? | 非法400 HTML；代理502 JSON；成功200 JSON；multi禁403；`:533`。**安全冲突，禁止照搬执行** |
| POST /api/rename | {sid,name}；ok,sid,name | 400/404/409/500 JSON；成功200；multi禁403；`:579`。会写meta |
| POST /api/save_annotations | {sid,annotations}；ok,count,meta_path,sha256 | 400/404/409/500 JSON；成功200；multi禁403；`:837`。会写meta/bak |
| GET /api/gt/exports | sid可选；导出列表 | 200/400 JSON；`:458` |
| GET /api/gt/exports/file | sid可选,name白名单；流式原字节与Content-Disposition | 200 octet-stream、非法400 JSON、缺文件404 HTML；`:427` |
| GET /api/gt/pull_status | running,last_result,last_error,detail | 200 JSON；`:763` |
| POST /api/gt/pull | 后台权威pull；ok,note | 200（注释202风格不等于实际202）、忙409；multi禁403；`:732` |

sessions行必须按来源区分：板端合并行含 sid,state,created_iso,duration_sec,size_bytes,frames,download_requested,transferred,local,bytes,name；local-only 行**没有** size_bytes/download_requested/transferred。其余字段可能 null，不能补 false/0/空串。frames 使用旧 `(li and li.frames) or board.frame_count`。created_iso按字符串倒序，空值按空串，不能擅自转UTC重排。只有无本地副本的 purged/missing 板端行才计隐藏。`?scope=local&scope=local` 不等于单一scope=local（`:303`）。

file sid 检查（`:284`）与通用 SID_RE 不同：拒绝空、点、斜杠、反斜杠，但没有通用100字符白名单。新栈安全加严必须记录差异。URL解码后进行测试；恶意路径不触及真实数据。1MiB分块是逐块写出，**不是 HTTP Transfer-Encoding:chunked**；旧服务发送Content-Length。

示例（本地独有行）：
```json
{"sessions":[{"sid":"fixture_a","state":"local-only","created_iso":null,"duration_sec":null,"frames":1,"local":true,"bytes":28,"name":null}],"board_error":null,"hidden":{"purged":0,"missing":0}}
```
示例（初始同步）：
```json
{"running":false,"sid":null,"last_sid":null,"last_result":null,"last_error":null,"recoverable":false,"recover_sid":null}
```

## 委托路由（不可只迁移顶层通配符）

下表列出真实子路由；具体请求/响应完整分支由同轮 ROUTE_SOURCE.json 的源文件/行号索引与旧源码绑定，R7 Golden fixtures 仍需补齐各分支，不能把此表当测试通过。

| 所属源码 | GET | POST | 错误/安全要点 |
|---|---|---|---|
| leveling.py:351 | /api/leveling/sessions、source?sid、leveled_latest?sid、job?id、artifact?id&method&name | /api/leveling/run，JSON≤65536B，成功202 | 参数/产物非法400 JSON、运行冲突409 JSON、job无内存任务或leveled_latest无结果404 JSON；artifact流式octet-stream |
| validation.py:156 | /api/validation/sessions、source?sid、latest?sid、job?id、artifact?id&method&name（job/artifact还可传sid） | /api/validation/run，成功202 | 参数/文件/绑定错误400 JSON、运行冲突409 JSON；latest无结果404 JSON；job可磁盘恢复，不同于leveling |
| human_detect.py:50 | /api/human_detect/sessions、source?sid | 顶层没有POST委托 | GET source含sid,meta,leveling_embedded；非法400 JSON，未知404 HTML；不能误写POST应405（顶层实际404） |
| gt_server.py:241 | /api/gt/session?sid、export、progress?sid、alias?sid | /api/gt/save、auto、freeze、alias | 未知404 JSON；400/404/409/500分支见源码；GT写不是顶层multi拒绝集合；auto会运行并缓存，不是只读 |

GT session 返回 ok,sid,meta_sha,points_sha,n_frames,display_name,duration_sec,frame_rate_hz,draft,draft_alias,version_aliases,suggestions_auto,suggestions_fusion_run,frozen_versions（`gt_server.py:325`），不是原样返回meta/manifest。save 用 doc 与并发SHA，freeze要求 annotator 与文档校验，alias参数为sid/scope/version/name（`:427`）。export与exports不是同一路由，不可合并。R0不调用auto/run/save/freeze。

子路由请求/响应补充（JSON状态/错误语义仍以上表和源码分支为准）：

- leveling/run（`leveling.py:106`）要求恰好 schema=1,sid,source,config；source含meta_sha256/bin_sha256；config为pitch_deg/roll_deg/physical_height_m加mode=auto，或加regions/ground_confirmed/basis。返回job_id,state；job返回job_id,sid,state,message,created，完成时增加report/artifacts/report_sha256，失败时增加error（`:301`）。sessions返回sid加旧本地描述；source返回sid,meta,source,profile；leveled_latest返回ok,sid,transform。各方法产物不是API新增schema，report/transform原文须冻结。
- validation/run复用上述请求和job创建；sessions行初始含sid,available,status,job_id，成功读取后可增加duration_sec/frames/total_points，已有结果增加recommended/methods，失败增加error（`validation.py:130`）。source字段同leveling/source；latest/job返回校验后的job；磁盘恢复job增加persisted/floor_identified/reference_only（`:44`）。未知路由404 HTML，运行冲突409 JSON，参数/文件/源绑定错误400 JSON（`:223`）。
- human_detect/sessions行有sid,duration_sec,total_points,frames,frame_rate_hz_measured,created_iso,session_has_leveling,bytes；读取meta失败时可只有sid,error（`human_detect.py:24`）。source返回sid,meta,leveling_embedded，不能与sessions行中的session_has_leveling互换。
- gt/save输入sid,doc,expected_sha（可选并发检查）；返回ok,sid,sha256,n_objects,session_meta_present（`gt_server.py:342`）。gt/auto输入sid,max_frames（可选）；返回ok,sid,n_frames_with_suggestions,frames,source="model",review_status_default="unreviewed"（`:483`）。gt/freeze输入sid,annotator；返回ok,sid,version,sha256,object_count；校验失败可含errors，孤儿版本冲突可含orphan_version（`:496`）。
- gt/progress?sid返回ok,sid,n_frames,annotated_frames,reviewed_frames,unknown_frames,person_objects,furniture_objects,track_ids,conflicts（`:269`）。gt/alias GET返回ok,sid,draft,versions；POST返回ok,sid,scope,version,name,written_at，其中draft scope的version为null（`:427`）。
- gt/export无sid时返回ok,sessions,final_exports；有sid无name时返回ok,sid,files；有sid/name时返回ok,sid,name,sha256,doc（`:580`）。该GET调用_ensure_store，会创建缺失store目录，不能称所有旧GET均绝对无文件系统副作用。gt/exports另一入口返回ok,sid及list_exports字段（`human_replay_lib.py:458`）。
- 顶层委托模块缺失时返回503 JSON：leveling/validation/human_detect/gt（`human_replay_lib.py:473`至`:503`）。该降级路径也要进入Golden错误夹具。
- gt/exports响应固定包含ok,sid,files,sessions；未传sid时sid=null、files为全局导出白名单、sessions为目录名，有sid时sessions=[]（`gt_server.py:97`）。不存在store时两个数组均为空。
- leveling/artifact中非法id/method/name、任务非ready、文件不在清单/不存在或SHA变化，都经ValueError/OSError返回400 JSON（`leveling.py:327`、`:448`），不能概括成缺文件404。leveling/job仅查内存，重启后无任务返回404 JSON（`:426`）。validation/job先读运行中内存任务，其余走saved_job磁盘恢复；缺结果/校验失败走400 JSON；validation/latest没有匹配job才返回404 JSON（`validation.py:181`至`:225`）。
- leveling/run与validation/run仅在Origin存在且不匹配Host时拒绝，且此拒绝为400 JSON；**缺Origin放行**。它们校验长度1..65536和JSON解析，但**不检查Content-Type**，缺失/错误Content-Type本身不导致拒绝（`leveling.py:357`、`validation.py:165`）。联合录制的Content-Type检查是另一套策略。
- gt/session在meta存在但points缺失时仍可200，points_sha=null（`gt_server.py:317`）。gt/alias POST的name缺省/null/空串都会清除别名，不能因此将其他字段的缺省/null合并；scope=draft时返回version=null。gt/export不传name与传空name都走列表分支，指定name才读doc，而且此路由**不接受FINAL_EXPORTS三个全局文件名**；全局下载另走gt/exports/file（`:580`至`:606`）。

## 联合录制独立服务（joint_capture.py:400）

| 方法/路径 | 行为 | 状态/Content-Type |
|---|---|---|
| GET /api/status | recorder.status，完整字段见Recorder.status源码 | 200 JSON |
| GET /api/preview | latest图像，无latest走not found | 200 image/jpeg 或404 JSON |
| GET /api/camera?sid | sid白名单，camera.mjpeg流式 | 200 video/x-mjpeg+Content-Length；缺失/非法404 JSON |
| POST /api/start | options对象，recorder.start | 200 JSON；请求/运行错误400 JSON |
| POST /api/stop | 仍要求JSON非空body，recorder.stop | 同上 |
| POST /api/open-folder | 打开本地目录并返回status | 同上；V2必须受控，R0不调用 |

POST Origin存在时必须等于 `http://127.0.0.1:<实际端口>`，否则403 JSON；Content-Length须1..8192，Content-Type以application/json开头，body必须对象（`:445`）。不能把此服务策略等同回放服务策略。

status初态（`joint_capture.py:181`）含state,output_root,camera_url,radar_board_url,radar_frames,camera_frames,bytes,error,session_id,path；仅recording且有t0时增加elapsed_sec。录制过程可增加camera_recovering、stop_host_unix_ns、duration_sec、synchronization等（`:228`起），缺省和null需按阶段冻结。start接收camera_url/radar_board_url/duration_sec/output_root等options（`:194`），默认时长300秒，允许1..300；stop/open-folder也必须提供有效JSON对象。

## 板端消费契约与新能力

`human_replay_lib.py:129` 起实现 GET status/current/sessions/session、POST record/start|stop、PATCH session.extra；`:161` 用HEAD确认meta/points存在；fetch负责权威下载。联合录制 `joint_capture.py:27` 定义同组端点，并管理幂等键。板端服务真实分发见 `src/human_capture/scripts/capture_server.py`。本轮只读源码，不触发设备REST。

V2目标新增 `GET /api/version → {api:1,app:"ConsoleV2/x.y"}`，业务新增走 `/api/v2/*`；默认环回8901，同时保留服务端与客户端能力。独立ConsoleV2.Api承载兼容服务，R1再落实依赖关系。

## Golden 比较规则（计划，未执行新旧对照）

- 临时fixture冻结板端响应/失败、时间、文件、SID；成功/缺省/null/空数组/各错误分支分别比对。JSON只允许明确新增字段；既有键逐字段值与类型一致（bool不等于int）。数组顺序不归一化。
- 正常化仅明确绑定的临时绝对根路径、动态端口、耗时、板端实时值；不删除error/state/null/缺省或SHA，不用泛化正则掩盖差异。HTTP状态、Content-Type、长度、下载字节/SHA另比。
- 覆盖local-only/合并/隐藏墓碑/HEAD失败与超时、重复scope、非法/URL编码路径、缺文件、sync忙/短路/失败与初态、BOARD_MODE与模拟非环回；所有写fixture限制临时目录。
- `/api/delete` 等安全冲突独立记FAIL或经明确设计的兼容例外，不能从Golden删除后宣称全绿。旧页面连新服务逐页验证另记，目前 NOT_RUN。
