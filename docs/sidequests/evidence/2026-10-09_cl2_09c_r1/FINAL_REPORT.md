# CL2-09C 离线等价性能优化提交

2026-10-09 Asia/Shanghai。**SUBMITTED / STOPPED；C01–C09 自验 PASS；尚不具备生产接入资格。** 设备/物理/B2/B3 NOT_RUN，121647 有效 TLS BLOCKED、物理成因 UNKNOWN。唯一验收表 v1 为 [00_SCOPE_AND_ACCEPTANCE.md](00_SCOPE_AND_ACCEPTANCE.md)。

只交付新隔离 [candidate/floor_sheet.py](candidate/floor_sheet.py) 与 [02_fix.patch](02_fix.patch)，variant `cl209c_exact_roi_search_v1`。冻结 09B 完整实现作 oracle。通过距离表、原序间距剪枝和首对共线关系复用去掉重复工作；原成功路径、describe/SVD/门控及稳定并列规则未改变。无 cap、超时判无解、近似阈值或质量标准降低。详细证明及第一版记录见 [07_AUTHOR_ANALYSIS.md](07_AUTHOR_ANALYSIS.md)。

## 实际性能

| 候选数 | 路径 | 09B 中位秒 | 09C 中位秒 | 加速倍数 |
|---:|---|---:|---:|---:|
| 25 | 失败兜底有解 | 0.1560 | 0.0218 | 7.15 |
| 25 | 非共线无解 | 0.1615 | 0.0484 | 3.34 |
| 60 | 失败兜底有解 | 4.1200 | 0.5629 | 7.32 |
| 60 | 非共线无解 | 4.2839 | 0.7817 | 5.48 |
| 100 | 失败兜底有解 | 43.0306 | 2.8357 | 15.17 |
| 100 | 非共线无解 | 42.7000 | 4.7025 | 9.08 |


每格为同输入、同本机环境、基线/候选交替三次无插桩调用的中位数，所有轮次完整 dict 精确相同；原始样本和环境/源码 SHA 见 [04_benchmark.json](04_benchmark.json)。完全共线快速拒绝亦已测量。首样本不是冷 OS/BLAS 进程；范围/时序抖动公开，不把相对加速当板端保证。最坏仍 O(n⁴)，内存 O(n²)，生产时延验收 NOT_RUN。

[03_profile_03.json](03_profile_03.json) 分别记录排序、枚举 next、hypot、min、np.all、SVD；含插桩开销且存在 inclusive 项，不相加或当真实基准。SVD 数值输入与执行保持原样，不声称减少 SVD 次数。

## 等价、门控与审计

41 项（35 冻结 + 6 新差分）最终 -B -W error 全过。新检查以 09B 穷举完整 dict 为 oracle，覆盖小/大、无解、重复、并列、反序、平移、边界和 caller ownership。命令/exit0/最终源码 SHA 在 [05_regression_03_command.json](05_regression_03_command.json)，具名日志在 [05_regression_03.stderr](05_regression_03.stderr)。原沙箱 socket 失败保留；没有降断言。本机 Python3.12.10/NumPy1.26.4，Python3.8 语法通过；板端运行 NOT_RUN。

原 121647 bin 只读重建 11 个 clean cells，09B/09C/原四 ROI 完全相同；最终绑定见 [06_session_final_binding.json](06_session_final_binding.json)。ordinal72/ROI2 P95=0.05029186936019117m，50mm 门控仍 FAIL、有效 TLS BLOCKED。未重新拟合 TLS、导出替代真实输入或判定物理成因。

真实 OpenCode CLI 1.18.35 / `opencode-go/deepseek-v4.1-flash` / session `ses_edf09e4a0ffe2L1WVp04Yusuw5`，只读白名单，其他工具 deny。独审 [08_OPENCODE_REVIEW.md](08_OPENCODE_REVIEW.md)；作者交叉裁决 [09_CODEX_CROSS_REVIEW.md](09_CODEX_CROSS_REVIEW.md)。原 IO/argv/有效权限/完整 export 均保留；审计员没有亲自重跑数值/SHA，UNKNOWN 边界保留，不伪称双份执行。

## 逐项验收与完整性

| ID | 状态 | 证据与限制 |
|---|---|---|
| C01 | PASS | 主树全文件含 untracked/ignored SHA 库存；09B 164 项 manifest 及冻结资产起止核验 |
| C02 | PASS | 60 候选分项插桩，min inclusive、循环残余和计数开销明确披露 |
| C03 | PASS | 距离复用、原叉积几何剪枝；原成功/describe/SVD/门控不变；无 cap |
| C04 | PASS | 09B 完整枚举 full-dict 差分；正式基准每轮 exact dict 相同 |
| C05 | PASS | 35 冻结 + 6 新差分 = 41 项 -W error；最终 03 回归 exit0；板端 NOT_RUN |
| C06 | PASS | 本机 25/60/100 无插桩三次交替基准；生产时延验收 NOT_RUN |
| C07 | PASS | 真实 bin 重建 11 clean cells；最终源码再次绑定；ROI 不变，TLS 仍 BLOCKED |
| C08 | PASS | 真实只读指定 CLI 模型/有效权限/IO/session export；作者核验与审计 UNKNOWN 区分 |
| C09 | PASS | 旧资产不变，append-only 本工单 return、最终 manifest 逐 SHA 复算 |
| E01 | BLOCKED | 无生产接入、CL2-10、发布或部署授权 |
| D01 | NOT_RUN | 无设备/物理/采集/B2/B3；121647 有效 TLS BLOCKED |


09B 164 项 manifest 已复算；375 个历史/源码/输入守护起止相同。主树含 untracked/ignored 的起止库存和 13 个范围外上下文变化记录在 01_baseline.json / 09_integrity.json，不回滚或归因。原生产 floor_sheet.py、历史证据及真实输入未由本轮修改。ponytail 实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。无新依赖。

本工单 return 已 append-only 写入 docs/sidequests/returns/CL2-09C.md；不回填 CLUSTER-01 或 09B。最终字节由 final_integrity.json、[10_evidence_manifest.json](10_evidence_manifest.json) 绑定。当前停止点是隔离离线交付；不自动开启 CL2-10、生产接入、发布、部署、采集、B2/B3 或 commit/push。
