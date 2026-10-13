# 实际审核命令及退出码

执行包装统一：`python -B -W error -X utf8 <本目录>/audit.py <name> <下列实际子命令>`。同名三件文件保存真实输出和退出码。

| 记录 | 实际子命令 | exit |
|---|---|---|
| data.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/data_audit.py` | 4294967295 |
| data2.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/data_audit.py` | 0 |
| edge.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/edge_audit.py` | 0 |
| final_integrity.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/audit.py integrity` | 0 |
| full_recompute.run | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/replay_audit.js` | 0 |
| gt_challenge.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/gt_challenge.py` | 0 |
| indices.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/index_audit.py` | 0 |
| negatives.run | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/negative_audit.js` | 1 |
| negatives2.run | `node --max-old-space-size=8192 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/negative_audit.js` | 0 |
| publish.run | `python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/publish.py` | 0 |
| registration.run | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/registration_check.js` | 0 |
| regression_pipe.run | `node pc_apps/human_replay/human_pipe_lib.test.js` | 0 |
| regression_replay.run | `node pc_apps/human_replay/human_replay_lib.test.js` | 0 |
| semantic.run | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/semantic.js` | 0 |
| tools.run | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/tool_audit.js` | 0 |
| votes_selfcheck.run | `node docs/human_capture/evidence/2026-10-08_hrsemshadow_r1/shadow.js selfcheck` | 0 |

基线实际命令：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrsemshadow_review_r1/audit.py baseline`，exit0；6056实际文件43,280,721,488字节。

初期只读探索命令包括 Get-Content（用户指定八组文件、相关源码/日志）、rg（源调用者/路径/记忆关键词）、git branch/rev-parse/status/diff、python版本与node --version。这些PowerShell读取调用exit0；第一次profile输出oh-my-posh/PSReadLine环境警告，随后用login=false。一次Windows rg通配目录参数报os error123，改用已核实路径；一次临时Python读取表达式产生unclosed-file ResourceWarning，未采用为审核证明，后续全部文件读取使用上下文管理器。

data初次扫描由审核者中止（精准核对自己的python子进程38480后Stop-Process），exit4294967295；理由是审核工具重复构建集合造成不必要耗时。仅优化本轮审核脚本，data2 exit0。

negatives初次exit1位于最后12样本的跨VM对象deepStrictEqual（结构/数值一致但原型不同）；初版保存为negative_audit_initial.js。改为规范化值哈希比较，不改算法/参数，negatives2 exit0；两次完整日志保留。

registration_check.js将临时夹具限定到本证据test_tmp；真实run23ID，T37-20不在自动suite。replay既有suite创建的两个os.tmpdir/hr03-*剪辑夹具由该suite自行移除，未保留或改变输入/生产文件。

最终发布/完整性命令也有独立run记录。最终发布只写本目录与append-only return；结束的完整性覆盖全部旧文件和旧return前缀。


收尾命令：`python -B -W error -X utf8 <本目录>/audit.py closeout python -B -W error -X utf8 <本目录>/closeout.py`，实际结果见closeout.run.json；仅汇总已有证据，不再执行目标功能。
