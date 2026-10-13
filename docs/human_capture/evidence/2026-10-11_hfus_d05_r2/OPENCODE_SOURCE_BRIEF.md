# 指定只读独审：HFUS-D05-R02 源码

实际使用 opencode-go/deepseek-v4.1-flash；仅read/glob/grep/list，不写文件，不shell、不评测，不派代理。先完整读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`、AGENTS.md、docs/human_capture/README.md、本目录ACCEPTANCE_V1.md和D05_CORRECTION_AUDIT.json。

审查 `sidequests/human_fusion_lab_next/d05/r02/{hook_split.js,trace.js,run.js,analyze.py,check.js,perf.js,demo_server.py,demo.html}`；读相关background/engine_b、instrument、strict_v2、D04 runner以理解真实调用者。

核查GT-free分离、XY key互斥/点守恒、原质量门不降、恢复点重入分类跟踪、instrument前后组件语义、模型特征/成员、同口径base对照、来源/资格不能扩张、未知帧FN、有限coast/reset、Demo真实D04基线/同步/race/SHA、预登记实验门。不能把已有颜色或测试数当效果。完整九会话评测正在串行运行，当前不得宣称实验完成。

报告可复现P1/P2错误（文件/行/触发/影响/最小修法）、任何代码与冻结假设不符，以及无需人工可继续的工程工作。最后写 REVIEW_COMPLETE 并给实际审查文件清单；无证据不要写PASS。中文回传。不修改任何文件。
