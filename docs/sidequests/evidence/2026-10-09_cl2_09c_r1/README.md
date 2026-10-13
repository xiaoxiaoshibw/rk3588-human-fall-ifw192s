# CL2-09C 离线等价性能优化

唯一验收表：[00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md) v1；最终结果以 FINAL_REPORT.md、verdict.json、10_evidence_manifest.json 为准。

baseline 是 CL2-09B candidate/floor_sheet.py 的冻结副本。candidate 是完整隔离运行目录，仅 floor_sheet.py 相对 09B 改动；frozen 是 09B 原始测试所用的更早基线，避免把其反例断言错误改为对 09B 的期望。生产、旧证据、原始 bin 均只读。

关键产物：02_fix.patch、candidate_version.json、test_equivalence.py、03_profile_03.json、04_benchmark.json、05_regression_03.stderr、06_session_final_binding.json、08_OPENCODE_REVIEW.md、09_CODEX_CROSS_REVIEW.md。原始执行失败和第一版源码/日志保留，不覆盖。

复现必须使用新的 revision 目录，不在此目录重复运行 exclusive 日志写入的脚本。准备运行目录后依次使用：

```
python -X utf8 -B -W error run_checks.py tests <新标签>
python -X utf8 -B -W error run_checks.py profile <新标签> <新profile.json>
python -X utf8 -B -W error run_checks.py benchmark
```

正式基准期间避免其他 CPU 密集任务。已有 HTTP 集成测试仅连接自身 127.0.0.1 临时服务并明确拒绝板端请求；如沙箱限制回环，保留失败并授权同一测试环境，不改断言。OpenCode CLI 用 run_opencode.py：process-local read whitelist，所有 shell/write/task/network 工具禁止；模型请求和 CLI 自身日志/DB 是其正常运行环境。实际模型由 session export 核查。

最坏时间仍可为 O(n⁴)，O(n²) 距离表内存。无搜索 cap、门控放宽、TLS 重拟合、生产接入、设备采集、B2/B3 或 CL2-10 自动推进。当前只交付本地离线证据。
