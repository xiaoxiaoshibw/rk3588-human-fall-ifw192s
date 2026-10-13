你是只读独立软件复审员。用户授权Codex返工HUMAN-UNIFY-R1，此轮writer已停止。你只能读文件、运行既有只读测试，不改任何源码、数据、配置、文档或证据，不commit/push/设备/部署/网络/采集；最终报告只返回到stdout，由编排者保存。本轮用opencode-go/deepseek-v4.1-flash、plan agent、default DB，不换模型/认证。

先读 docs/human_capture/README.md、docs/human_capture/HUMAN_UNIFY_R1_ACCEPTANCE.md（唯一v1）、docs/human_capture/evidence/2026-10-10_human_unify_review_r1/CODEX_REVIEW.md、docs/human_capture/evidence/2026-10-10_human_unify_rework_r2/SUBMISSION.md、pc_apps/human_core/README.md。适用技能 C:/Users/30680/.codex/skills/ponytail/SKILL.md。不可把旧证据的PASS或作者94测试替代验收。

逐ID R01-R08/S01/S02/Q01/D01复核。重点检查生产detect_overlay完整on_frame与core BASE_B真实语义；生产human_detect.js背景denoise与pipeline；RF闭包是否实例隔离；强度及raw索引；配平状态/R/T冲突；会话代际/报告/跳帧；实际实例配置；加载器short read/partial read与close；retained去重来源、过期且不自续命；统计accepted/rejected与current/ever是否准确。

执行 node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js。可执行test_baseline_parity.js（不加--out，只stdout，不覆盖现存证据），或读本轮parity_02.json/日志并独立核查其断言足以支持对拍。必要最小反例可用node -e，只stdout。不要跑runner去覆盖任何现有结果。性能读取perf_01真实日志/JSON，heap门不是总内存门。

审核本轮runs_01 9x5结果的JSON/CSV完整SHA、run_meta.source_sha256是否对应当前实现；核对AB_RESULTS术语没有伪造家具GT/recall，prf保持BLOCKED。S02结束SHA由编排者另做；若尚未存在保留为待最终复核，不把无法核定项报PASS。旧source/data/evidence冻结，不追改过去记录。

最后返回中文报告：实际读取路径/实际命令/exit结果/当前HEAD；逐ID PASS/FAIL/NOT_RUN/BLOCKED；缺陷必须给当前file:line、具体触发与最小返工；若无软件FAIL也只判本轮软件修复可提交复审，算法/生产资格仍BLOCKED、D01 NOT_RUN。不能编辑文件。新用户计划是自己重新录制，不能当本轮数据或GT到位。
