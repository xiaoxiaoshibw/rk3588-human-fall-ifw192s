
## 2026-10-17 R1 录制前开工提示词与OpenCode二轮只读审核

### 本轮信息

工单HFUS-TCMS-02-PRESTART-PROMPT，Codex为文档唯一writer，SUBMITTED非ACCEPTED。本轮仅提示词与审核，未启动未来PREDEV实现。唯一[PP验收v1](../evidence/2026-10-17_hfus_tcms_02_prestart_prompt_r1/ACCEPTANCE_V1.md)，SHA e951fdc405471c205b29f748a95e99c245b67a35782baa32949bb9638d052742。当前[提示词v2](../evidence/2026-10-17_hfus_tcms_02_prestart_prompt_r1/AI_PRESTART_PROMPT_V2.md)，SHA 7d6e11c7fb965bebf822788156ca210d985bb00a1a1465ebbd860148076723d6。

起始master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；BASELINE 13036非忽略tracked/untracked路径，错误0，排除data及受保护junction，GIT_STATUS_START.z保留；相关185文件首尾SHA一致，非整树冻结。ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md（本聊天已读取）。策略ENGINEERING文档交付，未来算法RESEARCH写入提示词。

### 集中诊断与实际变更

首轮四项：授权锚定、源码路径、可测判据、旧回归迭代留痕，v2已集中闭合。安全import与开发参数可冻结后测试D两项按实际代码和实验原则修订。见[REVISION_NOTES](../evidence/2026-10-17_hfus_tcms_02_prestart_prompt_r1/REVISION_NOTES.md)。只新建本项证据/提示词及追加WORKFLOW、REVIEW_LOG、回传；旧源码/配置/模型/GT/数据/历史证据保持。

### 逐条验收

PP01 PASS 指定文档与源码读取；PP02 PASS 范围/缺件/未来派发；PP03 PASS 地面/双账/双路/状态；PP04 PASS 可测软件判据及回放；PP05 PASS 两轮真实CLI审核；PP06 PASS 基线/185保护SHA与文档范围。详见[REPORT](../evidence/2026-10-17_hfus_tcms_02_prestart_prompt_r1/REPORT.md)。算法/浏览器/设备/物理NOT_RUN，A–D真实效果BLOCKED。

OpenCode v2.0.29，请求opencode-go/deepseek-v4.1-flash，plan，standalone；仅read/glob/grep/list，snapshot=false，无全局配置修改。首轮exit0 PLAN_REVISE → v2 exit0 PLAN_PASS；session ses_eba68d10dffeHwgGWWgY51cr6D，export exit0。实际模型元数据见REVIEW_IDENTITY，底层权重未知。命令/原jsonl/stderr/exit与两版意见保留；旧CLI models位置参数不兼容在REPORT说明，未换模型。辅助文档/哈希脚本用python -X utf8 -B -W error；一次打包脚本将编码名写为utf8-sig导致LookupError，改utf-8-sig后继续，不影响提示词或审核结论。

### 未闭合与交复审

无提示词阻塞项；PLAN_PASS仅提示词可交付，不是算法/人审GT/物理独立验证。用户实际派发后另按PREDEV唯一表实施，本项不凭文件存在自动开工。完整证据入口为REPORT、OPENCODE_REVIEW_V2、DELIVERY_SHA256.json及PROTECTED_CHECK。未进行算法测试，因为无代码改动；无训练/采集/部署/驱动网络/Git写。
