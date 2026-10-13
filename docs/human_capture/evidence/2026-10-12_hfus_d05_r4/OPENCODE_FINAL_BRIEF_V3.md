你是独立只读审核者。必须先完整读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md，回传实际路径。仓库 D:/Code/ldiar。禁止写任何文件/执行shell/启动评测/操作浏览器/修改GT模型或源。用 read/glob/grep/list。不要创建todo工具调用。审查后只输出中文报告，末尾精确写 REVIEW_COMPLETE。

当前用户授权主控唯一writer连续D05离线返工；不是D05a/D05b，禁止生产/部署/采集/Git写/驱动网络/ML。最多两个只读代理已有独立审核，不代替你。

首先完整读 docs/human_capture/evidence/2026-10-12_hfus_d05_r4/AUDIT_READY_REPORT.md、DEFECT_HANDLING_PRE_AUDIT.md、ACCEPTANCE_V1.md、PARITY_SUMMARY.json、PERFORMANCE_PURE.json、FULL_FAST_EXIT.json、PARITY_EXIT.json、PERFORMANCE_EXIT.json、CONSUMED_ASSETS_POST_SHA_CHECK.json、BOUNDARY_COMPARISON.json、BROWSER_OPERATIONS.json（当前Demo v2）；以及R02/R03两轮ACCEPTANCE_V1.md与R03 NEAR_REGRESSION_WINDOWS.json（可分块），R02 RESULTS_REVIEW_READY.md。不要把中途OpenCode或文件名称当完成证明。

重点源码 sidequests/human_fusion_lab_next/d05/r04/{hook_unknown_fast.js,hook_split.js,run.js,trace.js,verify_parity.py,perf_bank.js,demo_server.py,demo.html,audit_cli.py}，比较旧 d05/hook_unknown.js、R02 hook_split.js 与R03 hook_gate.js/run.js。读取核心rf_person.js feature布局相关范围。模型文件/原GT/raw captures只读，不必读取大points.bin/多GB全ledger；依据真实SHA/终端数据与逐帧parity结果审查。

确认：H1 GT-free密集核心互斥守恒、不放宽门；H2原模型不变、raw/effective/复算诊断与actual calls分列，家具诊断1/351→0/48却near184→179(accepted186→181)必须FAIL；H3在已登记minLocal=1,minRef=1,r=.6合法配置严格等价，9session2605帧实际重新运行，逐点/候选/轨迹同R02split，不通过引用旧ledger假冒实跑；纯perf九会话串行前5热身，p95门<50ms不改，Windows不冒充板端。缺独立已审负例/连续ID/退出/S9绑定，资格和生产BLOCKED。far仍32FN，occl61FN，家具ghost未解决，不能ACCEPTED。

确认最终Demo真正D04 baseline而非D03，读保存顺序ledger，不在seek续票；九会话/步进/拖动/播放暂停/重置/同步/实际删除恢复/实际检出与coasting last observation/unknown/来源/SHA门。检查异步stale packet/错误catch/shortcut的修复以及GT/AUDIT消费清单和实际before/after边界；.claude scheduled_tasks.lock消失必须单列，不能称全树不变。

按P1/P2/P3缺陷列具体位置、复现条件、是否阻本轮工程交付，区分算法剩余真实FAIL与代码缺陷；列三个冻结验收表状态建议和四类裁定，不自行ACCEPTED。若无阻断工程缺陷写明，但不可等同算法目标通过。必须完整读本brief，返回实际读取技能路径、审查范围和 REVIEW_COMPLETE。

补充：真实浏览器发现V1 session核验期间帧跳转会被show0覆盖，源/证据保留。当前最终Demo在r04/demo_v2/{demo.html,demo_server.py,README.md}，端口8915，需审查readySid及核验期间禁用控制、show守卫；TOOLING_SOURCES_V3与DEMO_INITIALIZATION_RACE.md。原8914为已保留旧版本。V1 brief未派发，实际审核只用本v2完整brief。

补充读 ACCEPTANCE_STATUS_REVIEW_READY.md 与 BASELINE_SCOPE_LIMITS.json（最终当前tracked missing=0、symlink=0），最终验收/return将在你的完整审核后追加，不把审查前NOT_RUN当作完工。
