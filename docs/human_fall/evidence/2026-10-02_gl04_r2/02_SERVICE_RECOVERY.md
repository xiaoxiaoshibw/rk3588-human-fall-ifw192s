# GL04 R2 服务恢复分流

R2指定model default DB无工具probe成功：01_service_probe_meta，exit0，12.23秒，OPENCODE_DB未设置。R1实现已exit0停止写入，源码SHA与提交不变。

自建localhost4098 OpenCode serve（PID34700，02_helper_owner）官方/doc确认POST /session/{sessionID}/summarize body providerID/modelID。请求R1原session，provider opencode-go/model deepseek-v4.1-flash，directory D:/Code/ldiar。Invoke-RestMethod明确HttpClient.Timeout 240秒超时（02_summary_error），无成功响应；并行只读/status也无响应。停止已核owner的自建helper，不停其它用户进程。helper真实退出1来自Stop-Process，不伪造成功。

随后default DB `opencode export ses_f03dbb94affeLd27gZz6bQalDp --sanitize` exit0，02_session_export；末尾仍R1 finish stop，同model/provider，没有summary=True新消息，不假称压缩成功。原session保留。

按用户“同model default-DB新会话”明确许可，以R1独立报告/源码SHA/GL04 v1及紧凑R2提示词新建会话。原服务超时单列，不计算法返工失败，不改auth/DB/全局配置/模型，不并行写入者。生产缺口V10与此服务问题分开。
