# COMMIT-AUDIT-20261010 验收表 v1

2026-10-10（Asia/Shanghai）。仅核对用户“分析一下哪些可以提交先提交了”授权的本地分组 Git 提交；不改变任何 HC/HR 或 HF/GL 工单的验收状态。唯一证据目录：`evidence/2026-10-10_commit_audit_r1/`；回传：`returns/COMMIT-AUDIT-20261010.md`。

| ID | 要求 | 本轮结果与证据 |
|---|---|---|
| G01 | 记录原 branch/HEAD、完整工作树及含未跟踪文件的 SHA | PASS：baseline.json / baseline-status.txt；8788 文件，缺失/软链接单列；标准忽略的 captures/dist 等不纳入 Git 基线 |
| G02 | 下载/同步/改名单独构成可运行提交，不引入未提交 GT/算法依赖 | PASS：group_a 树、candidates.json；隔离副本 7 套回归退出 0 |
| G03 | Console/会话入口提交只依赖 HEAD 与第一组提交 | PASS：group_b 树、candidates.json；隔离副本 11 套回归退出 0 |
| G04 | 混合文件按功能拆分，保留未提交内容和用户差异 | PASS：仅 Git index 写入选定内容；split-manifest.json / source-preservation.json |
| G05 | 页面 script 依赖闭合、Python 警告严格失败、板端 3.8 语法兼容 | PASS：dependency-check.json / tests.json；板端 3.8 仅静态语法验证，不冒称该版本运行实测 |
| G06 | 不提交大体积派生数据、EXE/ZIP、人工 GT 草稿或未验收算法 | PASS：分组路径白名单及实际提交清单；派生文件留在原地 |
| G07 | 记录提交内容、验证命令、限制和每组提交 SHA | PASS：提交正文、commits.json、README.md 与回传 |
| G08 | 不 push/reset/checkout/clean，不更改驱动或原始 captures | PASS：只执行本地对象/index/commit 与隔离测试；无上述操作 |
| D01 | 本轮设备、物理、部署、采集与候选源码 EXE 构建/启动 | NOT_RUN：本轮仅 Git 收录与离线软件回归；旧发布证据仅作历史归档 |

G02/G03 的 PASS 是提交完整性自验，不是工单 ACCEPTED 或生产放行。SESSION-SYNC-RELEASE 唯一表仍为 `SESSION_SYNC_RELEASE_ACCEPTANCE.md v2`；其中历史 EXE SHA 与本轮拆分后的源码候选不能混用。HUMAN-UNIFY、HR-RET-V2、RF-OPTIMIZATION、SEM、骨架等原 FAIL/BLOCKED/NOT_RUN 保持。

最终范围补记：源码收录 G02/G03 与功能拆分 G04 仍 PASS；完成提交后的额外全工作区 SHA 核对发现范围外 `pc_apps/human_replay/gt_annotator.js` 改变（本任务未写入该文件），全工作区冻结 BLOCKED，见 final-scope.json。外部修改保留，不回滚、不用它替换已测试的提交源码。
