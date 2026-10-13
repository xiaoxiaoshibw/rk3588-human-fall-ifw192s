# 第一轮：统一事实与结论资格

2026-10-11；本轮用户授权为规划与 OpenCode 审核，不是实现授权。

已读 AGENTS.md、HF WORKFLOW、HC README、RETURN_TEMPLATE、ponytail，以及 CC SUMMARY、V3 REPORT_FINAL、诊断 REPORT 全文/CLAUDE_TASKBOOK。只读核对实际 runtime、tracker、engine、背景函数、PointNet 评测与冻结 JSON。

| 原总结/旧计划说法 | 当前归一裁定 | 处理 |
|---|---|---|
| 接下来采用 unique 为默认 | V2 fixedDetector 已在每次 tick/segment reset 强制 Unique；V1 裸入口和生产未统一 | 已完成的 V2 不重做；默认入口迁移另单 |
| 确认票违反很多 | CC 三轮纠正后真实 votes 违反=0 | 不安排无证据的投票修复 |
| geometry mismatch 98.7% | 当前 CC 同口径 6520 候选 mismatch=0；内部仍先运行 RF tracker | 显示同步已修；纯几何状态语义另列限制 |
| V3-B 已修检测 | V3 super.frame 先出 V2 检测，A/B/C 只生成 masks | 背景点级收益与全链 NOT_RUN 分开 |
| f128 的15点没有入簇，所以60点门是唯一根因 | 实际 covered_by_clusters=15、orphan=0，有191/374点混合簇 | 对 B 重做真实簇成员/纯度/score/关联账本；不套 A 链解释 |
| V3 XGB 家具全拒证明泛化或仅记忆位置 | B 608家具候选 FP595；只证明候选域脆弱，位置记忆不是唯一原因 | 固定点集与去代理消融；新家具泛化 UNKNOWN |
| PointNet heldout 全中或影子几乎全失效 | V3漏中心化；正确预处理 test58/65、stress39/58；val/test/stress无负例 | 修研究评测消费者，停止据旧表选型 |
| V3 near31335、S65062 GT点分母 | 实际 JSON near286822、S627268 | 原记录只读；新归一表使用 JSON 分母 |
| 已确认候选点等于真人点 | 骨架 adapter 只有 CONFIRMED_HUMAN，gt_present 未核候选相交 | 保留粗区域代理，不升级真人/关节精度 |
| 人体算法无姿态/跌倒实现 | ROS HF 有 fall_state；lab pose_history 未有效填充 | 实现存在性与本轮未接通/未物理验证分开 |

当前快照：master / 026e06303f60ed1bbe4ddc4d037836db68da6d27；12412 个文件，包括 ignored/untracked，零读取错误、零读取中漂移；.git 内部除外，不遍历目录符号链接。详见 BASELINE_BEFORE.json。SHA 相同的比较对象是本轮工作树基线，不是干净 HEAD 内容。

决策：先统一计分与来源，然后隔离接通 BG-B；以真实最终输出验收。S9 草稿不提升 GT；本轮不运行会覆盖旧 results/models/GT 的复跑入口。
