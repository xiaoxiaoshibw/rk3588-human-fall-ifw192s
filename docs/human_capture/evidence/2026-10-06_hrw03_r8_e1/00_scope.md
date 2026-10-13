# 00 · E-1 范围 / 非目标（SHADOW-ONLY）

- 日期：2026-10-06；writer：claude-k3（本会话）；ponytail full。
- **唯一目标**：把「203349 空场 reference 是否复制了 session-specific / movable state」从推测变成可量化证据。
- **非目标（沿用上一轮 attribution audit 已冻结的结论，不重复实验）**：
  1. B：registration residual 已知（最大贡献者，不本轮重新证明）；
  2. C：matcher geometry 独立小收益（~3–5%），不本轮动；
  3. D：connectivity shadow A/B 已证非主因（`NO_CHANGE`），不本轮动；
  4. 站点重发现：ROI、移动模式、subject phase 沿用上一轮（r7 §2）与既有 R3.0 时间线；
  5. production 任何修改：matcher / builder / radius / tier / connectivity / leveling / ICP 一行不改。
- **唯一变量** = temporal stability / cross-session persistence。
- 输入锁定：203349（102 帧）+ 223757（165 帧）各自既有 TLS job；registration = R3.2/11_r33 存档 + r7 CHECK PASS 的固定 ICP 解（不重新估计）。
- 输出四组量化：universe/站点残块/控制区/守恒+确定性；最终判 `E-CONFIRMED` 或 `E-NOT-CONFIRMED`。
- `.py` 扩展名说明：工单登记 Node 实现（实现语言 = Node 24，`node 03_e1_probe.py` 运行；Python 端无现成 loader/matcher 等价物）。
