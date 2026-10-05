# PC human_capture / replay 修复记录

## 2026-10-05 HR-02 本地会话优先 R1

用户明确要求断板时用本地会话。Codex唯一writer，作者自验完成：O1–O6 PASS，D1 NOT_RUN；SUBMITTED，无独立外部复审，不报ACCEPTED。根因修复本地优先列表及冻结exe数据根路径；实际打包版浏览器离线显示9会话并回放，原meta/bin保持。桌面快捷方式更新到版本化exe，旧exe与lnk备份保留。

唯一表：[HR02_OFFLINE_ACCEPTANCE v1](HR02_OFFLINE_ACCEPTANCE.md)。[回传/证据索引](returns/HR-02_OFFLINE.md)。此记录不改变 HF/GL 工作项、板端或物理边界。
