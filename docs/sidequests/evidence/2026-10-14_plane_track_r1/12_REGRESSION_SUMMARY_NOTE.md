# 12_REGRESSION_SUMMARY.json 解析附注

- `12_reg_node_human_replay_lib.log`（utf-16）末行为 `all 45 tests passed` → **PASS（45 tests）**；
  该日志 v2 汇总里标 UNPARSED 只是我的解析正则没覆盖 "all N tests passed" 句式，不是测试失败。
- 该日志中的中文因 Node 输出 → PowerShell 管道编码为乱码，ASCII 结论行不受影响。
- 其它 12 份日志解析结论见 `12_REGRESSION_SUMMARY.json`；v1 汇总因按 utf8 读 utf-16 而全 UNPARSED，
  已改名保留为 `12_REGRESSION_SUMMARY_v1_encoding_ERROR.json`。
- 无新依赖：本轮只用了 Python 3.12 stdlib + NumPy 1.26.4 + Node 24.14.0；matplotlib 只在本机证据绘图中使用（已装）。
