# CL2-09B：ROI选择器假拒绝离线修复

当前交付以FINAL_REPORT.md、verdict.json和最终manifest为准；这里只说明运行方式与资产边界。

用户明确同意继续CL2-09B离线修复，保留门控、不部署。唯一验收表[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1。Codex唯一writer；实际读取ponytail：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

- `frozen/`：来自CL2-08 `D:/Code/cl208audit` 的只读源码复制，SHA绑定原来源。
- `candidate/`：完整隔离runtime副本，仅floor_sheet.py与frozen不同，variant=cl209b_feasible_roi_v1；不接运行程序。
- `02_fix.patch`：可审查的单文件源码补丁，本轮没有应用到原生产树。
- `test_selector.py`：已知小/大候选反例、完整oracle、旧成功逐字dict、拒绝/边界/确定性/不修改caller及Python3.8语法。
- `03_session121647.json`：原bin/frozen平面重建11 clean cells；原/新结果精确相同、四区不变；旧TLS P95失败保持，不重新估计TLS或导出。
- `04_benchmark.json`：实测5/25/60/100候选、完全共线及失败有可行项；最坏O(n4)代价公开，板端性能NOT_RUN。
- `candidate_regression*.stderr`及command.json：所有执行尝试保留；第五轮完整32项PASS，-W error；初期缺fixture/沙箱限制没有通过改断言掩盖。
- `05_opencode_raw_output*.stdout/.stderr`、权限/模型/完整session export：真实CLI独立审计，首轮不可读BLOCKED保留，不能以exit0当完成。
- `09_integrity.json`：关键输入/历史/原源码守护；main并发范围外变动仅作上下文，不回滚也不冒称全主树冻结。

复跑需要新的证据revision：本目录脚本输出采用exclusive，不能覆盖原文件。数值回归命令为 `python -X utf8 -B -W error run_tests.py <新日志标签>`；首次准备复制冻结源，所有fixture只在证据内临时目录，HTTP项只连自己的127.0.0.1服务；需要相应沙箱许可。`run_logged.py session_probe/benchmark/check_integrity`记录完整argv/exit/stdout/stderr。OpenCode仅read、逐文件project-relative白名单，不接板端、无shell/写入/子任务权限。

根因和修复范围见07_AUTHOR_ANALYSIS.md；独立审计与Codex裁决分别保存，不改模型原话。不以selector修复替代TLS放行：121647有效TLS仍BLOCKED。无部署、采集、提交、合并、B2/B3或新阶段自动执行。
