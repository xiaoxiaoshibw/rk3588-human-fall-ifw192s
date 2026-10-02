# 给 Claude Code：GL-02 R4，剩余入口与遮挡误判

工作目录`D:\Code\ldiar`。用户手动给Claude Code；只做本轮，不调用OpenCode，不启动GL03/部署/采集。执行者仅SUBMITTED/BLOCKED，Codex独立复审。

先读根AGENTS/CLAUDE、GL02工单/PLAN、冻结几何/交互契约、最新REVIEW_LOG与returns/GL-02.md R3；本轮权威要求：

- `docs/human_fall/evidence/2026-10-01_gl02_r3/CODEX_REVIEW.md`。
- 同目录`codex_r3_context_checks.py`及`55_codex_remaining_final_stderr.txt`，5方法5失败。原样复现，不删/改弱。
- GL02前轮参数/契约与`AI_PROMPT_GL02_CLAUDE_R3.md`持续边界；读取ponytail真实源或已验证副本。

**已经通过的部分保留**：R2七方法7/7、267全回归、R2静态6/6；完整artifact canonical/类型/整体平移正例/双向散点/latch/CLI不覆盖已有实现，不大重写。

## 必须完成的最小修复

1. 所有上下文输入路径统一校验、deepcopy解绑、原子构成同一canonical绑定；配套ground+derived局部更新须同步self.calibration及所有snapshot/state/monitor GDID/calibration_version，不能继续发旧ID。不要伪造support/来源证明，不改数学约定。尽量复用同一构造/绑定入口，避免每分支再写一套。
2. 有效上下文变化判据覆盖calibration_id/version与GDID；合法新标定版本即使几何ID未变，旧目标/位置/快照/请求/基线/动作历史资格也应失效。检查ground-only路径。旧事件/源seq/stamp/epoch保留；非法输入不部分更新。
3. capture_baseline请求在monitor未知/降级/锁存重标定时明确拒绝并回执，不先accepted再无限pending。已在进行/已有基线的不可用处理清楚；监测恢复是否可继续需遵守当前版本资格，不能自动继承已失效基线。普通辅助IMU degraded不能误伤；原始云显示和解除目标保留。
4. 90%原地面仍未动、10%单侧平整物体遮挡时不能锁存整片地面位移；仅off-support子集的同号/低离散不够。保留整体+0.1m连续平移正例、双向散点负例、稀疏unknown与持续失效锁存。可输出遮挡degraded/unknown，不放宽GL00门槛，不逐帧改变换或引入新库/新算法体系。阈值如需新合成约定，解释来源/限制并交审，不标物理实测。

旧自测中“10%杂点触发整片位移”的期望可按本轮语义修正，但保存旧证据与解释；本轮五方法/之前整体位移正例不改弱。配套局部入口现仍支持；不能靠取消入口来规避一致性，确需取消须明确调用链与兼容影响供审查。

## 验证与回传

- 原样运行R3 `codex_r3_context_checks.py`，5方法全部通过；R2 `codex_r2_integration_checks.py` 7方法、`static_probes.py`6方法保持；全相关回归报告实际数量。补至少一个新版本相同GDID下baseline/request资格与输入后原地修改反例、monitor坏时capture拒绝/已有pending处理反例。
- 记录branch/HEAD/git status、所有相关SHA/命令/真实退出码与冻结对照，确认没有其他写入者。证据新`evidence/<实际日期>_gl02_r4/`，原日志/原录制/旧产物/用户driver差异与Windows软链接不动，不commit/push/reset。
- 已授权板端若可达，可临时隔离副本跑Python3.8.10/NumPy1.17.4兼容回归、LF脚本/两端SHA/内外退出码；不可达如实NOT_RUN，不换主机/升级依赖/保存凭据。不动活动节点/driver/网络/自启/厂商库/UI。冻结default/geometry不动，candidate仅必要版本元数据，不能做GL03框或聚类。
- 雷达向下看，机器人总高1.4m、眼球垂直离地约1.1m；约26度仅截图粗估，候选距1.29～1.32m差未核验。真实地面/外参/IMU/confirmed仍BLOCKED/禁用。
- 向returns/GL-02.md追加“Claude Code GL02 R4”，逐项实现/检查/剩余限制，只SUBMITTED/BLOCKED；不写Codex PASS，不执行GL03。用户完成后回Codex说“复审GL02 R4”。
