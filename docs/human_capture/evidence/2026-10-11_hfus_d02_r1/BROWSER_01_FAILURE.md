# 真实浏览器检查第一次失败（保留）

命令：`node sidequests/human_fusion_lab_next/review/check_browser.js docs/human_capture/evidence/2026-10-11_hfus_d02_r1/package_01 docs/human_capture/evidence/2026-10-11_hfus_d02_r1/browser_01`

实际 exit=1：`Error: browser startup`，检查脚本未收到本地9235的Chrome调试endpoint，未载入页面。目录中仅启动profile目录；未当作浏览器功能通过。使用headless/隐藏进程、独立本轮profile，没有接管现有Chrome/旧profile。

包的Node源码/输入/输出SHA和映射复核独立exit0；它不能替代真实浏览器检查。下一次验证使用新browser_02目录并保留本次失败。
