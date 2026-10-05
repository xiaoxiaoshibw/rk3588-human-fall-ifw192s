# OpenCode GL-04 R2 集中返工

唯一生产写入者OpenCode `opencode-go/deepseek-v4.1-flash`，default DB，使用用户允许的同model default-DB紧凑新会话。R1原session `ses_f03dbb94affeLd27gZz6bQalDp`保留；官方V1 summarize请求240秒超时、导出无summary记录，helper已停止，无活动写入者；恢复证据见r2/02_*，不假称压缩成功、不用隔离DB。Codex唯一编排/独立复审。只改preview四文件：index.html、human_fall.js、human_fall_lib.js、human_fall_lib.test.js。正式页有外部新增Q/E旋转，保留不写；core/config/driver/其他webui/原数据/旧证据/旧断言全冻结。无GL05/部署/采集/板端网络/commit/reset等动作。

判据仍GL04_ACCEPTANCE v1（仅结果列更新，非新要求）。先读R1 CODEX_REVIEW.md及10_codex_runtime.txt；直接沿原02_operation_matrix.md全表集中诊断，新写`evidence/2026-10-02_gl04_r2/00_diag.md`逐行到函数/赋值顺序/守门/检查映射后才改源码。无需重新读全部历史大文档。R1软件REWORK：12个独立运行时失败＋真实六图读数/性能错误。生产消息R/t/support缺口V10继续BLOCKED，不改core/topic，不造通过。D01 NOT_RUN。

## 三个共享根因（整堆修复，保留已有通过）

### 1 权威字段 / 当前显示帧

用户要求输入位置是snapshot.coordinate的ground子块和`ground.support_polygon / support_polyline`。不要把自创top-level ground_render当唯一入口。文档化唯一可选synthetic输入`coordinate.ground`（显式schema/R/t/from/to/calibration/GDID/geometry版本），support从snapshot.ground指定字段消费，声明其frame/单位/版本绑定。此扩展仅在offline fixture体现，生产缺字段即disabled/fallback，不能宣称后端已经提供。

原始raw header保留真实frame_id，presented raw与snapshot/state比较seq/stamp/spatial frame/session/epoch/calibration schema/GDID/content；render metadata/transform只能取**当前presented entry**，外来/未来snapshot不能抢改当前points。同一帧mode的points/boxes/axes/labels/readings/support必须一套坐标；ground AABB只actual_points，位置center_ground字段，source字段保持原义。原始模式仍可用，切换/降级及时恢复source buffer；grid始终可见、supports独立layer源/ground均一致，无支持不造。

支持预算≤3000/层，使用LineLoop避免额外闭合顶点超预算，保留源indices及sampled_from/total；图例明确grid/支持面/支持线的颜色与透明度。按原任务显示当前seq/stamp/frame_id/length单位/calibration_id/schema/geometry版本/ground状态；当前ground frame与source frame分别明示。候选ground明确“配平预览（未地面核验）”。

### 2 资格 / 生命周期 / 选择

共享guard覆盖进入前、进行中、失效、恢复：unknown/none ground、坏/unsupported calibration.schema、frame/version不匹、snapshot过期、ws断连/静默过期、verifier unavailable（权威state.sensor_quality.ground_monitor字段；参考node_runtime现有输出，只读）、当前candidate缺详情。失效→fall unknown/position null或明确UI空/框unknown颜色，拒select；ready baseline不能代替当前candidate观测，不删历史events，保留原ack/watch/lock/capture/release语义。

列表闭包不持有可变“旧snapshot仍可用”资格。render时捕获不可变token：snapshot identity+完整坐标/变换绑定内容+candidate签名；submit时再与当前fresh token比对，same-ID changed content、新ID、caller原地修改都不可沿旧选择。同内容合法不误拒。raw/session/frame不匹都拒。drag当前mode框经当前camera投影取8角min/max，最终走同一个select guard，提交原snapshot_id/candidate_id（不是client leveled id）。不要只修列表漏drag/hfSendSelect底层。

当前MVP每次更新，rotate/zoom/resize/DPR-only都要重投，DPR变化同步renderer backing和overlay backing，宽高都核对。near/far/behind/退化守门保留，选择前更新矩阵防最后一帧camera变化。

### 3 synthetic / 实测性能

browser不得执行scenario几何/求bbox/构造变换/逆推样本。把synthetic生成执行放**本轮新evidence**，离线计算完整source和ground实际点min/max/center、R/t和supports及PC2 wire，JSON fixture同样本固定帧；browser只加载fixture/渲染字段，不拟合或求candidate几何。用已安装node/Python无新库。R1新增syntheticScenario的既有断言也不能改：若保留Node离线helper，必须严格仅在CommonJS/Node分支暴露和执行，browser分支不可调用、浏览器入口只fetch离线JSON，记录两执行环境证据；不能仅移函数到browser lib且仍在浏览器执行。覆盖正常/全倾斜/无外参，明确synthetic/offline；可增加证据用offline JSON输入（用本轮fixture路径/query读静态JSON），方便Codex按操作矩阵加载变体做真实browser失效检查，不做第二网站。无外参ground入口灰掉/回退。

FPS是近似实际renderer.render帧数/单调时间，不是pcPresHz；queue_dropped只取真实已知snapshot/state字段或明确unknown（pcSkip“未呈现”保留原名，不冒充队列丢弃）；连接显示真实online/offline synthetic状态，三者同时panel。不要造0。render FPS不同于display/output Hz，原panel保持原义。

## 自验 / 回传

保留原18和R1全部旧断言文本不动，只追加新检查。R1 ground_render helper输入作为旧preview兼容输入可保留；用户指定coordinate.ground/ground.support_*是当前权威输入，两个来源同时存在而冲突必须拒绝，旧路径不能覆盖/绕过新路径守门，实际生产topic不变。不以兼容测试冒称后端已提供。先复现R1失败，再检查全M01–M11，新增check不能照抄实现。辅助检查/日志/fixtures/manifest只写r2，不覆写r1或旧证据。源码SHA包含未跟踪，全树baseline见r2/00_before_manifest；正式四文件基线包含外部Q/E变更，禁止覆盖。不要跑326/7/12+2；preview未触正式/core。

Codex会独立运行所有合理checks和真实browser；你没有browser则NOT_RUN，不自报visual PASS。末尾按RETURN_TEMPLATE追加returns/GL-04.md“OpenCode GL-04 R2”，只SUBMITTED/BLOCKED，逐固定ID/矩阵、命令/exit/SHA/证据/未跑；R1历史不覆写。提交后停止写入。控制上下文，不重读所有旧历史；超过120k先停写并记录恢复锚点，交Codex压缩，禁止新模型/隔离DB/第二writer。
