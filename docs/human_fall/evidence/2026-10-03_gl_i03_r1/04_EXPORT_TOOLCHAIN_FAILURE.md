# 会话导出CLI单次挂起 / Codex记录

本次opencode export ses_efe7c0901ffeyCaOVy5f9A4Az4于19:35:04启动、19:38后仍未返回。没有模型推理/生产writer；未再尝试export、未启动后续链中的第二export/probe。核确切进程链后停止本次自建pwsh37344/python35700/export37272；不批量按名称杀进程，不停用户服务。宿主exec session38256最终exit=-1；export子进程真实退出码未取到，记不可得，不伪造0/超时码。

不将此工具链挂起误算算法失败或Go推理不可用。首probe12.64秒exit0/PROBE_OK及阶段一390.344秒exit0成立。为核实际模型，仅以sqlite mode=ro读取default DB指定session的message.data（不读credential、不修改DB/schema/auth/全局config），01probe与03diag均确认唯一opencode-go/deepseek-v4.1-flash，最终finish=stop。具体机器可读证据04_actual_models.json及只读脚本留档。

设计门不受此导出辅助工具阻断；阶段二仍需新的≤1min无工具probe，异常即停本次派工，不切模型/DB/认证。没有假称export成功或恢复旧服务。
