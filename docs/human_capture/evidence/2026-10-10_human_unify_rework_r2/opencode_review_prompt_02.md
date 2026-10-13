只读补充独审HUMAN-UNIFY-R1 R2。指定opencode-go/deepseek-v4.1-flash、plan、default DB；不改任何源码/数据/配置/文档/证据，不设备/部署/采集/网络/commit/push，不启动其他agent。最终只stdout中文报告。

读README当前授权、docs/human_capture/HUMAN_UNIFY_R1_ACCEPTANCE.md唯一v1、docs/human_capture/evidence/2026-10-10_human_unify_rework_r2/OPENCODE_REVIEW_01.md及SUBMISSION_POST_GUARD.md、pc_apps/human_core/{engine,data_loader,runner,test_rework,test_baseline_parity,test_perf}.js。加载C:/Users/30680/.codex/skills/ponytail/SKILL.md。

第一独审R01–R08无软件FAIL；并发外部RF写入导致S02BLOCKED，这个事实保留。现在writer在核心内追加来源守卫：不缓存可变源码、globalThis隔离、实际读取字节SHA、mode前后/跨mode实现和输入守卫、对拍/perf起始末尾SHA。审查这些是否正确、是否破坏原修复；执行run_all_tests.js核对96项。可用stdout-only node -e最小反例，禁止写文件。矩阵和对拍由编排者新轮运行，不要自己重跑长矩阵。新数据用户尚未交付，算法/生产资格BLOCKED。

核对submitted_source_sha_02.json当前core SHA。若final runs_03/parity_04/perf_02尚未完整，留NOT_RUN或待核定，不能预判PASS。S02原基线RF变化不能洗成全树PASS，但可确认当前core范围未发生未授权改动。

返回实际读路径/命令/退出码/真实模型、对新加固逐点PASS/FAIL/BLOCKED、任何缺陷file:line与触发条件，和本轮软件修复是否仍无FAIL。不给总体ACCEPTED，不编辑文件。
