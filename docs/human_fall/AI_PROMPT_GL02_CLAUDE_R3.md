# 给 Claude Code：GL-02 R3 返工（用户手动）

工作目录`D:\Code\ldiar`。本轮只修GL02软件，用户手动派发；不要调用OpenCode或派后续任务，不启动GL03、不部署/采集。你只写SUBMITTED/BLOCKED回传，Codex独立复审后才放行。

先读根AGENTS/CLAUDE、GL02工单、PLAN、几何/交互契约、最新REVIEW_LOG、`returns/GL-02.md`的Claude R2，以及：

- `evidence/2026-10-01_gl02_r2/CODEX_REVIEW.md`（本轮权威复审，含七项失败及测试契约说明）。
- 同目录`codex_r2_integration_checks.py`、`54_codex_integration_final_stderr.txt`。原样复现七方法七失败，不改弱、不跳过。
- `AI_PROMPT_GL02_CLAUDE_REWORK.md`的范围/现场/设备边界及GL00/GL01已通过审查，不重复已闭合工作。
- `C:\Users\30680\.codex\skills\ponytail\SKILL.md`或GL02 R1哈希验证副本，写明来源。

记录开工branch/HEAD/git status与相关SHA，确认单实现写入者。用户driver改动、Windows软链接、未跟踪资产保留，不reset/commit/push。证据用新`evidence/<实际日期>_gl02_r3/`，旧日志/产物不覆盖。

按CODEX_REVIEW最小修复：

1. 完整artifact加载要同步真实被使用的ground/derived/calibration/id/监测；启动和reload同验证，先校验后原子更新，复制/绑定输入防事后原地修改。裸不完整块须拒绝或隔离未激活预览，不能与旧ground/旧GDID混用。不得以旧父随后更新为理由绕开一致性，不伪造新support证据。
2. ground monitor degraded/unknown/recalibration失效必须阻断相关离地特征、基线采样、跌倒历史/新事件，公开位置/框/嵌套状态同步unknown。保留源点云和历史事件；普通辅助IMU degraded不应被误伤。核查handle_request/status_state/_feed_baseline及所有消费入口，不仅改标签。
3. 一致整体位移与双向散点/家具遮挡区分；保留+0.1m整体连续变化正例，双向散点不能同样报地面位移。不要放宽GL00门槛或逐帧更新固定变换，不引入新库/新算法体系。报告支持质量、变化证据与暂不能区分的限制。
4. 已达到recalibration_required的旧版本保持失效，直到显式新有效版本；断流只清当前连续观测，不能抹掉既有标定失效。持续帧计数如沿用仍明确为合成设计值，不称物理时长；watchdog无新frame的路径同样检查。
5. nested schema严格int；新派生块R/t/n/参考轴等在numpy转换前逐项拒bool/非数字/非有限。源sha需合法hex并在存在parent.input hash时一致，来源/创建时间按fixture与实际输入如实记录，不静默把真实缺来源标synthetic。不改冻结health/manifest与旧validator原义。
6. CLI新版本的已有输出/diagnostics保护使用独占创建或等效原子策略，失败不能覆盖历史；证明至少一条真实冲突反例。

R1旧六方法的裸块测试与完整上下文一致性存在不足：若选择拒绝裸不完整更新，按CODEX_REVIEW“测试契约说明”在新证据目录保存副本，以完整匹配新artifact验证清位置，保留旧脚本与历史结果。**本轮七方法保持原样**（其裸块测试允许安全拒绝）。不得为满足单条旧测试再破坏父/派生一致性。

验收：本轮七方法全部通过；262起的全相关回归（报告实际新数量）；数学/合法切换/无效切换原子性/监测正常与散点负例/失效保持/无效特征与基线/CLI冲突分列日志。已授权板端可达时用临时隔离副本Python3.8.10/NumPy1.17.4兼容验证（只隔离测试，非部署/采集），LF脚本、记录内外退出码及两端SHA；不可达记录真实失败和NOT_RUN，不升级依赖/换主机/保存凭据。

允许GL02相关calibration/ground/必要runtime及最小选择/基线失效入口、CLI/独立配置/测试；lidar_candidates限版本元数据，不做GL03框或分割。冻结default/geometry、driver/UI/厂商库/网络/自启不动。雷达向下看；机器人总高1.4m，眼球垂直离地约1.1m；约26度仅截图粗估，约1.29～1.32m候选差未解决。真实地面/外参/IMU/confirmed不升级。

向`returns/GL-02.md`追加“Claude Code GL02 R3”，列逐项修改/关键函数/命令/真实退出码/SHA/原失败及剩余限制；只SUBMITTED/BLOCKED。完成后用户回Codex说“复审GL02 R3”，无需搬运长回传。
