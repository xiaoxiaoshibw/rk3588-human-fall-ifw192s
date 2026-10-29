# ADR-006：显式根目录、启动校验和分阶段测量

日期：2026-10-24。状态：设计采用，运行实现未开始。

## 配置

应用自有配置默认AppData/ConsoleV2/settings.json；命令行显式参数优先于该文件，环境变量覆盖仅允许已文档化的白名单，不承接旧SDK示例的自动下载。测试用显式临时配置。缺输入数据根或无效配置直接报错，不创建data根、不修junction、不依赖启动cwd。初次配置明确选择现有根，开发默认只读指向现有data/sessions。

配置schema_version与app版本分开，未知字段不悄悄丢弃，未支持主版本拒绝启动；未来升级先保留旧配置与变更说明，不能就地破坏。路径从配置文件所在目录或显式绝对路径解析，保存规范化后值与原输入供诊断，不使用程序集Location推断单文件资源目录。

| 配置 | 默认/验证 |
|---|---|
| api.listen / api.port | 初版只允许127.0.0.1 / 默认8901；端口1..65535，冲突不回退随机；非环回配置启动拒绝，不发布对外敏感GET |
| data_root | 已存在、可读、规范化根；junction目标绑定；原始会话只读 |
| legacy_gt_read_root / gt_write_root | 旧gt_store只读参考；新可写store独立显式路径；不迁移或覆盖旧store，不宣称旧Console自动看到新store的写入 |
| board_base / gt_board_base / camera_url | 分开配置，缺省沿R0捕获8766、GT8088、相机8081的角色；校验scheme/host/port，无用户凭据URL；启动不自动连接/录制 |
| cache_bytes | 明确字节上限，R2按实测选默认；未测前TBD，不编造内存通过；活动租约计入 |
| quarantine_root | AppData/ConsoleV2/quarantine；卷不符拒绝，不自动改盘 |
| log_level / diagnostics_root | Info / AppData/ConsoleV2/logs；诊断不写会话目录 |

运行中修改数据根、store、板端或隔离根时：停止接收新修改、收敛现有任务/租约、作废旧计划token、重新校验，不能在任务中途切换。只改变显示主题无需重开数据。配置保存也是应用自有写入，不经会话Gate，但必须原子保存并留旧版本；没有无限自动备份或清理用户数据策略。

## 日志与错误

结构化JSONL记录utc、monotonic_elapsed、level、event、requestId、sid、frame、generation、phase、duration_ms、error_code及必要堆栈。源文件SHA写摘要，点数组/相机字节、token/凭据、完整HTTP头不写日志。兼容响应保持oracle原文时，日志另带内部错误码，不把日志异常结构直接返回页面。

正常日志只写自有目录，体积轮换仅限应用日志且上限明确；不碰data或历史evidence。mutation journal与恢复清单不走普通日志淘汰，初始无自动清空。审计不可写时修改失败关闭，仍允许只读诊断。只读API读取失败如实映射，不自动下载、改写meta或生成GT缓存。

## 性能与证据

打点分别记录进程创建→API绑定→UI可交互、open请求→meta→映射→解码→Qt提交→首次呈现，不能以服务端JSON返回当作首帧。记录源节奏、已读/已提交/已呈现/取消/落后帧，seek从用户请求到目标帧首次呈现计算。

完整points SHA不挡首帧读取；Provisional/Verified/Stale状态分开显示与记录，完整性核验任务另计时。冻结GT/写计划使用Verified源绑定，不能用长度/mtime代替SHA；首次打开没有全量SHA时仍可只读显示，但不能宣称整段数据已验证。

所有基准含软件/依赖/输入SHA、CPU/GPU/RHI、Windows/DPI、构建模式、冷热缓存条件、重复次数、原始计时样本和分位算法。冷启动至少10次、固定10s渲染路径、seek固定seed的200次；warm-up剔除需事先规定并保留原样本。内存统计C#/Qt/worker进程集合峰值，B不能只报C#服务内存。没有GC/GPU/进程计数就标UNKNOWN，不拼接不同轮数字凑预算。

开发机器证据放新docs/evidence/<日期>_console_v2_<阶段>/，既有R0证据只读；正文进展追加PROJECT_STATE/PROGRESS。OpenCode只读审核按用户已有要求使用，记录真实模型/会话/工具权限和发现，未完成调用不记通过；审核不替代实际测试、spike或GT，亦不增加永久人工审批流程。
