# STEP0 冻结尝试 1

实际命令：`python -X utf8 -B -W error docs/sidequests/evidence/2026-10-09_cl2_10_r1/prepare.py`，退出 1。尚未写出 00_baseline.json，尚未数值实验。

工具原始错误：FileNotFoundError，D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/1705fddaa8794a3fa716e69ecf5ee8a4/domain.npz 不存在。正常会话的隔离 overlay 仅含 report/manifest，不能假设含 domain。受影响复制立即停止。

只读检查在传统聚类原作业目录找到该 domain，历史 manifest 明确 domain_sha256。修正只限 prepare：使用原作业域前必须匹配冻结 manifest；已写入的本轮副本只核 SHA 后复用，不覆盖。原证据和原资产均不修改。此记录是观察到的准备失败说明，完整命令/错误已在本聊天工具输出中；不冒充捕获了当时不存在的 stdout/stderr 文件。
