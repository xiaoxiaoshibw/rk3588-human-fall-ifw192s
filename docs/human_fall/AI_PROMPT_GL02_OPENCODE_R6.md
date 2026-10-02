# GL-02 R6：已有v1入口/请求矩阵集中修复

你是当前工单唯一生产代码写入者。工作目录D:\Code\ldiar，用户明确授权Codex自动派你（OpenCode CLI，opencode-go/deepseek-v4.1-flash）返工，不再要求手动转Claude。用户最新授权覆盖AGENTS/CLAUDE旧手动派工文字。只处理GL02，不启动GL03，不部署/采集/联网板端，不commit/push/reset，不碰driver差异、src/CMakeLists.txt、冻结配置、历史证据。

按顺序完整阅读：AGENTS.md、CLAUDE.md、docs/human_fall/WORKFLOW.md、GL02_ACCEPTANCE.md v1、evidence/2026-10-01_gl02_r5_codex/CODEX_REVIEW.md、同目录codex_r5_lifecycle_checks.py、GEOMETRY_CONTRACT.md、INTERACTION_CONTRACT.md、RETURN_TEMPLATE.md、C:/Users/30680/.codex/skills/ponytail/SKILL.md。不用读全部历史日志，报告已把同根因集中；按需查函数调用者。

先复现12方法脚本和检查四根因的兄弟入口，在新的evidence/2026-10-01_gl02_r6/00_diag.md留下根因/修复计划，再实现最小共享修复。

## 必须闭合（源于验收v1，不改断言）

1. A02/A04：完整artifact calibration_id必为非空字符串，schema_version必须严格整数1（不是bool/float）。validator、startup、full reload统一拒绝非法ID/版本，失败原子无修改。startup有传calibration就校验，合法无标定/ground-only保留，不靠id truthiness绕过。保留所有合法同版本metadata/deepcopy入口。
2. A09/A10：ready在monitor未知/degraded/锁存或watchdog无云时退休，历史baseline保留retired，不重复退休；同版本恢复不自动复用ready，需新capture。失效要在features/fall消费者前生效。pending保持失败终态和原request_id回执，不用接收秒推进源采样时长。失败样本可作为历史保留，但新任务不能拼接。
3. A10：同request_id同内容先返回原缓存回执并idempotent_replay=true，即使monitor已坏/云stale；不同内容按request_id_conflict。缓存查询不执行动作，未缓存的新请求仍受required/monitor/schema/epoch/版本等既有校验。不以终态替换原accepted/pending缓存。复用SelectionBackend缓存语义，不复制一套不一致的缓存实现。
4. A10：watchdog与postcompute stale都必须把capture终态发到既有selection_ack话题。state additive字段可以保留，但不能只发state。超时抑制候选/事件/位置时，不丢此前产生的任务终态。避免同一回执在多路径重复发布。允许最小human_fall_node.py生命周期连接；不改WebUI/冻结字段/消息schema。

允许修改：core/calibration.py、core/node_runtime.py、必要core/selection.py共享缓存接口、scripts/human_fall_node.py、必要相关回归测试、新R6证据和末尾追加returns/GL-02.md。不改Codex独立脚本和旧日志/原测试断言，不把生产节点推导物理flags。其余路径若认为必须改，先在诊断写明已有要求关联，以最小实现继续，不向用户发问。

## 验证与提交

仓库根使用python -B -W error，先codex_r5_lifecycle_checks.py，再R4/R3/R2/static、Claude R5脚本、fall完整回归、follow、两个UI。每项命令真实退出码落新目录；任何失败继续集中诊断，同根因别拆零散补丁；保持Python3.8/NumPy1.17 API兼容，Linux/板端没有实际跑就NOT_RUN。

提交完整源SHA（含必要包装层/SelectionBackend）和范围前后检查，按RETURN_TEMPLATE在returns/GL-02.md末尾追加“OpenCode GL02 R6”，按A01–A12/D01/P01报告SUBMITTED，不能自判总体PASS。不把设备超时当理由反复联网。末尾列修改文件、日志目录、命令结果与未跑项，然后停止写入交给Codex独立复审。

效率：复用已有代码和证据，先读当前调用链，再改共享根因；不做框架/新依赖/全库重构/并行实现者。不要用同样失败的提示词无脑重试，遇失败先记录具体错误并收敛入口。
