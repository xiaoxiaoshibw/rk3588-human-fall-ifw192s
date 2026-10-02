# GL-02 R5→R7 Codex最终独立验收 / 2026-10-02

结论：**GL-02软件PASS（合成数学、标定产物、入口/生命周期、mock ROS运输）；D01设备兼容NOT_RUN；P01真实物理BLOCKED。** 不等于真机或人体有效性通过，未部署/采集/commit/push/reset。GL03软件前置已满足，本轮未启动。

用户已授权Codex直接派OpenCode CLI `opencode-go/deepseek-v4.1-flash`修复并自行复审，不再需要用户转交。R6修四个共享根因，R7闭合pending标定切换回执；单写入者始终保持。所有原始失败、R5提交与旧R4证据保留。

## 全表结果：GL02_ACCEPTANCE v1

| ID | 结果 | 独立证据及适用范围 |
|---|---|---|
| A01 数学 | PASS | R7 54_codex_fall：多倾角/高度/轴/逆变换；派生与物理资格分离 |
| A02 输入 | PASS | R6 50_codex_lifecycle严格完整父ID/整数schema三入口15反例，R6 53/54原类型反例；R7相同代码SHA及51/54复核 |
| A03 证据/兼容 | PASS | R6 53/54及R7 51/54；旧v1未知外参、IMU/physical/confirmed不升级 |
| A04 入口绑定 | PASS | R7 52/53及51：full/paired/ground-only/empty canonical绑定、caller解绑、损坏/混合/bare拒绝；startup不再凭ID真假绕过 |
| A05 版本资格 | PASS | R7 50/53/54：新calibration同GDID和新GDID退休资格/清快照缓存，旧事件/源时间保留；pending在清绑定前返回原ID取消终态 |
| A06 完整产物 | PASS | R7 51/52：完整input SHA/evidence、note、reference、unknown transforms/rotations、合法扩展保持；同版本四入口deepcopy；非法其他块拒绝 |
| A07 ROI可信 | PASS | R6 53/54与未变ground SHA；R7 54：GL00支持门槛、无可信支持unknown/degraded，不冒用自动AABB |
| A08 监测 | PASS | R7 51/53/54：整片+0.1正例、双向散点/10%遮挡负例、间断清连续、锁存好帧/同版本reload不清除 |
| A09 消费门控 | PASS | R7 51/54：ready坏帧/watchdog退休、恢复不复用，失效先于features/fall；辅助IMU降级保持原义，release仍可用 |
| A10 请求全过程 | PASS | R7 50/51/52：真实select→capture→pending→坏帧/断流取消、原ID终态、源时钟不推进、恢复新采样；缓存重放/冲突先于门控；ready/版本切换全矩阵；实际包装层AST执行验证ACK话题路由含postcompute抑制 |
| A11 导出 | PASS | R7 54：新版本独立文件、冲突不覆盖、损坏不能启用，A06 provenance保持 |
| A12 范围/回归 | PASS | R7 fall272；R6独立follow2/UI各18；64条最终SHA、同一提交未漂移；仅4生产文件+1回归文件变化 |
| D01 | NOT_RUN | R5记录SSH255/timeout；本轮不重复联网。Python3.8语法解析通过仅为静态兼容，不冒充Python3.8.10/NumPy1.17.4或ROS实跑 |
| P01 | BLOCKED | 缺现场地面身份/安装角/点云原点高度/阈值证据；合成夹具不能代替真实物理验收 |

## 独立命令与SHA

仓库根`python -B -W error`：R7 50_pending 2/2、51_lifecycle 12/12、52_R4 3/3、53_R3 5/5、54_fall 272/272，均exit0。R6独立R2 7/7、static6/6、Claude R5 4/4、follow2/UI18+18均exit0。未变化的源码与配置使用已验证R6证据，不机械重复无关回归。R1旧bare断言的获审例外继续保留。

`55_codex_final_manifest.json`包含64条源/配置/follow/UI/driver哈希，结束时全部与R7提交manifest匹配。相对R5：calibration.py、node_runtime.py、selection.py、human_fall_node.py四生产文件和test_gl02_ground_frame.py一个新增回归变化；其余59条相同。R7相对R6仅node_runtime和该回归变化。改动文件按Python3.8语法解析通过。catkin `src/CMakeLists.txt`仍ReparsePoint，Windows无法读取其Linux链接内容；未替换/修改。

R6回传写“66条”与实际64条不符，以manifest实数为准；不影响四文件范围结论。R6工具初始manifest读取Windows catkin链接报WinError1920，修正为排除不可读链接后，在首个生产编辑前重新核对15个R5提交SHA并取得64条清单；错误工具输出保留，不冒充成功。

## 覆盖遗漏及收口

R5原R4产物/坏帧pending修复确实通过，整表首次实测发现四根因：严格父字段校验、ready失效退休、缓存顺序、ACK运输（R5 CODEX_REVIEW和64日志）。R6四根因独立通过后，Codex在最后请求矩阵核对补查pending标定切换：原代码清request_id无终态（R6 61日志）。此行本来就在v1表，属于Codex此前漏测，不能称新增需求。R7在验证成功后清绑定前生成failed终态，显式纯API以lifecycle.baseline_ack返回；无ROS在线reload调用，不新增热更新框架。

最终按每一入口/状态行核对对应证据；必需软件没有剩余FAIL/未验证条目，D01/P01不升级。

## CLI故障与恢复

实际会话`ses_f07cd9a4dffeTqh7fUyhmsUyLO`，导出元数据证实provider/model为opencode-go/deepseek-v4.1-flash。R6 CLI exit0；R7初次exit1，服务HTTP400，最后成功步total=200013 tokens（含cache）；代码及272回归已完成，缺回传收尾。

同模型新会话最小probe exit0；结合旧长会话失败，支持上下文过大解释，服务未给明确overflow原因，故不将推断写成已证实上限。按[OpenCode v1官方Server API](https://dev.opencode.ai/docs/server/)和本机`/doc`实际schema，临时本机127.0.0.1服务调用同session/provider/model的`POST /session/:id/summarize`。接口True且导出summary=True/finish=stop；总结请求78k tokens，后续续跑结束约40k。恢复CLI exit0、回传已追加，原错误不覆盖。独立源码/检查确认没有重做或回退已完成修复。只停止自建41902端口服务，不中断用户TUI。

`56_cli_metrics.json`记录CLI自报成本：R6 0.06728004、R7中断前0.04549356、续接0.008934036；不含单独probe/summary，也不是账户结算、完整成本或模型间性价比排名。以当前指定Flash模型、紧凑任务、单写入者、Codex独立验收、提前压缩长上下文作为本项目执行方案。
