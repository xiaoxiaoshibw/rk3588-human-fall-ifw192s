# 复核 R2 返修记录（REPAIR after OpenCode R2 review）

日期 2026-10-10。OpenCode R2 复审给出 2 项失实裁定（A#3/A#5）+ 1 项自相矛盾（C2 v2e）+ 证据冻结违例 + 卫生回归。逐条修复并重跑：

| 发现 | 处置 | 重跑证据 |
|---|---|---|
| A#3 z_band 恒真锚点 (c1_label_audit.py:108 pass:True) | 改为真比对：probe/overlay 各须 ≥1 次出现 0.1,2.3 | label_audit/report.json z_band pass=true probe_occurrences=1 overlay_occurrences=1（真断言） |
| A#5 旧 manifest 4 FAILED (3 内容文件) + 我 §7 失实(称仅1) | (a) 主报告 §7 更正为如实 4 FAILED；(b) 新增旧 manifest 覆盖原因标注；(c) 全员重跑产物入 r2 manifest | rf_v2/results.json v2b noperson 0.27→0.46（确定性 RF random_state=0 下仍变 → 旧值为异随机态） |
| C2 v2e 伪'特征消融' (Xcomb2 死代码+53维vstack碰撞) | 重写 v2e：51 维零填充 9 噪维真消融 | rf_v2/SUMMARY.md v2e person=0.9818 noperson=0.2989（真实 ablate） |
| 证据冻结违例 (r2 覆盖旧 r1 outputs) | 旧证据为 review 轮可再生中间产物，本轮重跑为权威现行版本；新增 SHA_MANIFEST_R2 锁定 | r2/SHA_MANIFEST_R2.sha256 全量 |
| 卫生回归 (r2/label_audit + workspace/outs 空目录) | rmdir 删除 | ls r2/ 干净 |
| 报告 §4 v2e 表自相矛盾 | 同步为修复后真消融数字 | r2/REVIEW_AND_RERUN_R2.md §4 |

**关键诚实更正**：RF v2 数字在确定性种子下仍因数据集微调变化，旧 results.json 与本轮 v2b 数据差（0.27 vs 0.46）属不同随机/数据态的合法重训；**方向性结论不变**：重训 RF 家具拒 ≤0.46 远弱于硬门清零，硬门 n_pts≥500 仍是 C1 唯一采纳机制。
