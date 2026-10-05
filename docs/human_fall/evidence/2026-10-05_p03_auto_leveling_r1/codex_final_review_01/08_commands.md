# 独立执行命令记录

所有命令均由 Codex 执行；不运行 archive 中的代码，不启动 Console，不写生产/测试源码。

| 命令 | 退出码 | 结果 |
|---|---|---|
| `git status --short` | 0 | 共享脏树，见 06_scope_status.txt；不归因既有差异为 P03 |
| `git branch --show-current` / `git rev-parse HEAD` | 0 / 0 | master / 3fc1338fc306444959433a41bdeaeefd705f58ec |
| `git diff --stat` | 128 | src/CMakeLists.txt Windows symlink 表示无法 hash；保留 06_scope_diff.txt；未修复链接 |
| `git diff --stat -- . ':!src/CMakeLists.txt'` | 0 | 完整可读范围快照 06_scope_diff_without_symlink.txt；不能显示 untracked，由 status/SHA 补足 |
| `python -B -c "import sys,numpy; ..."` | 0 | Python 3.12.10 / NumPy 1.26.4 / PyInstaller 6.21.0；环境盘点，不是板端性能验证 |
| `python -B -W error .../05_independent_checks.py before` | 0 | 4437 个 tracked/untracked/显式 ignored 文件记录；P03 13_SHA 全部匹配 |
| `python -B -W error .../05_independent_checks.py boundary` | 1 | 预期非零：范围门 FAIL；原始输出 07_boundary_checks.log，结构证据 07_boundary_checks.json |
| `python -B -W error .../05_independent_checks.py after` | 0 | P03提交与exe首尾不变；两项无关文献目录文件被外部修改，详见主报告 |
| 两套 Python unittest / Node 回归 / 独立算法反例 | N/A | NOT_RUN，范围硬门已命中 |

`...` 均为本报告同目录的绝对或仓库根相对路径。脚本只写本 evidence 子目录。
