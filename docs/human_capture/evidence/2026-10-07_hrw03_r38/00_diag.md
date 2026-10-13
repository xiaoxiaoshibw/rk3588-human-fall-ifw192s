# R3.8 集中诊断与操作矩阵（实施前）

依据 R3.7 01–06，唯一验收矩阵 06 v1。初始全部 NOT_RUN。git/全文件（含 untracked）SHA 见 00_baseline.json。

| 操作/输入 | 实际入口与顺序 | 状态/消费者 | 检查 ID |
|---|---|---|---|
| startup/no artifact | load: exists→manifest→3 SHA→schema→matrix→bindings→gate | UNAVAILABLE；SAFE | T37-01/02,T38-09 |
| same-content reload / restart | load 全部重验；无全局缓存、无热切换 | 同状态同 artifact_id | T37-21,T38-11 |
| same-ID changed bytes / caller mutation | bytes SHA 与四类绑定；apply 再验证有限矩阵并复制点缓冲后提交 | REJECTED/STALE，失败不改云 | T37-03/07–13/19 |
| new artifact directory / new ID | 显式目录重新 load→VALIDATING→判定 | 不自动 latest | T37-09/18/21 |
| raw/wrong sid/registered frame | apply 先看 frame；只允许 leveled_session:source | ERR_FRAME_MISMATCH / DUPLICATE | T37-19,T38-10 |
| damaged/unsupported schema/profile | 安全结构验证先于访问嵌套对象；首失败定状态，安全可执行的后续错误收集 | REJECTED；SAFE | T37-02–06/12/13 |
| missing bound job / changed level bytes | 显式 job + transform_id + 3 SHA，禁止 mtime 顶替 | STALE；SAFE | T37-08/09,T38-08 |
| gate pass/warn/reject/missing | 03 完整快照→每项 band→盆地→聚合 | VALID/DEGRADED/REJECTED；非 VALID 输出 SAFE，DEGRADED 另记诊断 shadow | T37-14–18 |
| state != VALID→pipeline | 直接调用 P 同样输入/ctx；不把诊断 shadow 混为 SAFE | 全帧计数、clusters/tracks/events 完全相等 | T38-07–09 |

本轮不支持生产热切换（04 §1 输入载入期不可变）、浏览器/API 和设备入口，T39 明确 NOT_RUN。诊断 ppICP 的 identity/tls 与半集重拟合仅测指标，不替换冻结 B transform；跨方法差异只登记 notes。最终 B 处按 PP_SCHED 末级 0.08/0.60 收集对应点/JTJ，完整残差与 holdout 按 0.30；具体来源及不足必须如实记录，不能为 PASS 换解或调门。

已发现文档表述歧义：04 SAFE 的“条件 A”数值其实是 R3.6 的 reference 查询诊断，05 的 Branch P 是 online-only。本轮分别保留 P（生产现状）和 A（对账），不将两者等同。
