# ADR-003：冻结旧行为基线，禁止静默批准安全例外

日期：2026-10-24。状态：兼容分层设计采用；全兼容要求存在未解决冲突，**并未冻结为可发布契约**。

## 决定

独立ConsoleV2.Api实现HTTP适配，默认127.0.0.1:8901。服务端与客户端能力同时保留；所有旧会话、GT/配平/验证/人体识别、联合录制路由进入登记表，静态资源映射也属于兼容范围。新能力走/api/v2/*；新增GET /api/version返回{api:1,app:"ConsoleV2/x.y"}。版本号只描述协议，不代表所有路由通过。

Api自己的wire DTO保留键存在性、null、数值/布尔类型、数组顺序、created_iso字符串倒序、hidden计数、local-only省略字段和旧错误文本。核心Result/领域模型不能直接序列化；旧HTML send_error和JSON分支分别实现，不用框架默认错误页替换。file保留白名单、URL解码后的路径拒绝、Content-Length、octet-stream、1MiB读写，不能声称HTTP chunked。

使用同fixture固定文件/板端返回/时钟，旧human_replay_lib.py为oracle。逐条比较JSON已有字段、响应状态/Content-Type、下载字节与SHA。正常化仅显式列出的动态端口、临时根、耗时和板端实时值，不能丢弃error/缺省/null/SHA或重排列表。fixture安全写只在临时目录；原始数据禁写。旧页面逐页连实际新服务验证，JS单测不能替代该项。

## 安全冲突登记（不是已接受的例外）

| ID | 旧行为基线 | 新硬约束 | 设计处置及R7状态 |
|---|---|---|---|
| C1 | /api/delete本机可删文件，scope=board/both可发DELETE | 无直接删除、清单确认隔离 | 不实施危险删除；拟拒绝v1危险调用而由v2计划隔离/恢复承接。旧成功状态/效果无法相同，BLOCKED，不能自行用403算兼容 |
| C2 | rename改meta.name；save_annotations改meta.human_annotations及bak | 源meta只读 | 不伪造旧写成功；v2侧表仅新能力，不宣称替代旧持久化语义。BLOCKED |
| C3 | multi只拒绝顶层集合，部分GT/leveling/validation仍可写 | 非环回或BOARD_MODE破坏性POST全403 | 设计统一拒绝；扩大拒绝范围是可观察差异，BLOCKED；loopback也不能绕过Gate |
| C4 | 旧页面POST无绑定计划的确认token | 所有数据修改必须Gate授权 | 不能把HTTP请求/Origin当确认；旧调用无授权时不写，未证明页面兼容，BLOCKED |
| C5 | GET gt/export可创建store | 只读路径不得绕过Gate创建目录 | 设计GET返回读视图，不创建store；文件系统副作用不等价，单列差分，不用JSON相同掩盖 |

R1不替用户选择放宽哪个条款；这些分支保留oracle测试并记录预期差异/阻断，不删测试、不xfail后声称全绿。R7报告至少分READ_PROTOCOL、WRITE_PROTOCOL、SAFETY、PAGES四组，任一必需组BLOCKED/FAIL时总体不能PASS。R9也不能在冲突未解决时标“完全替代旧Console”。不依赖冲突的R2只读spike可继续。

## 授权与网络策略

初版产品只允许绑定127.0.0.1，非环回监听配置启动拒绝，既不公开敏感GET，也不把“只禁写”称为对外访问控制。当前不新增认证系统；未来如需非环回监听，须另做认证与会话/GT/原始文件读取授权设计，明确与旧BOARD_MODE的GET放行契约差异后再发布。旧行为基线不因此改成GET403并宣称等价。

隔离安全fixture可以模拟非环回对端/BOARD_MODE，验证破坏性POST在dispatch前403；socket对端优先于代理头，忽略X-Forwarded-For作为授权来源。GT写、配平/验证任务、录制、同步等也属修改，不仅是DELETE。具体与旧403 JSON字段的差异必须逐fixture列出，不通过本轮启动对外监听验证。

v1原先Origin“存在才检查”及Content-Type差异继续保留事实记录；不能用它代替可信用户确认。需要新增Origin/Host校验时记录安全加严差异，不静默规范化。已签发token仍需重新校验权限/源绑定。新的token签发仅由App可信用户交互通道到Gate完成，不能提供“调用即确认”的无鉴权HTTP端点。

兼容服务占用端口和旧联合随机端口书签见ADR-004；兼容例外未解决前API_CONTRACT保留“候选”状态，只冻结旧oracle输入和源码SHA，不把本ADR称为用户批准。
