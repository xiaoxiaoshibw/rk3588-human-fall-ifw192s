# GL-02 Claude Code R2独立复审 / 2026-10-01

结论：**软件REWORK；设备兼容NOT_RUN；真实地面/物理BLOCKED；GL03不放行。** 后续仍由用户手动交Claude Code，Codex不自动派工。

独立验证：262回归exit0（50_*）、原R1六方法exit0（51_*）；新增集成五方法五失败（52_*），补类型检查后最终七方法七失败、exit1（54_*）。原失败/成功都保留。SHA核对当前源码与R2回传一致，工作树driver差异/软链接保留，未改算法/部署。

## 已闭合部分

原布尔版本True、自动AABB信任、同ID坏t拒绝、位置清除及完整父/派生构造器一致性等R1六反例已通过。严格计数、CLI选项依赖与存在性拒绝已补。源码冻结范围对照见53_codex_changes_from_pre_gl02.txt；R1原有lidar_candidates元数据修改计入整体GL02，不误计成R2新改。

## 未闭合：按实际反例返工

1. **监测失效仍发布实测位置（P1）**：真实调用process→select→process（synthetic站立簇）产生ground_valid=false、observability=degraded，position_source_m仍为[1,0,-.45]。_mask_unobservable仅在invalid调用；features/_feed_baseline/fall仍消费旧ground候选。因此“实际位置/基线门控已闭合”自述不成立。监测失效须在源头使离地特征、基线采样、跌倒历史/新事件不可用，并同步公开位置/框/嵌套状态；不要把辅助IMU的普通degraded误当本功能失效。
2. **完整标定加载后仍用旧地面（P1）**：apply_ground_context(calibration=new_artifact)中new_ground默认为None，self.ground不从artifact.ground更新；artifact与derived d=1.4，但实际候选计算仍用self.ground d=1.2。必须校验并原子切换实际消费的ground/derived/calibration/版本/监测，重启/启动路径同样核对。
3. **裸derived切换留下不一致有效上下文（P1）**：裸新d=1.4只换self.ground_derived；self.ground和self.calibration仍是旧d=1.2/旧GDID，snapshot读取旧calibration发布ID。这不是“旧父随后再来”的安全原子加载。可要求完整匹配上下文并拒绝裸不完整更新，或仅把裸块置为隔离未激活预览、清旧有效ground/calibration且不得发布错配版本。禁止编造新父support验证证据。
4. **散点误报整体变化（P2）**：可信ROI内一半点高度+0.1、一半-0.1，连续10帧仍recalibration_required。代码仅看p95>.05，没有符号一致性/离散程度/覆盖证据；“散点破坏”分支在support<.8且p95<=.05时也几乎不可达。保留整体一致平移正例，散点/遮挡应unknown/degraded，不能把家具回波冒充地面位移；不放宽旧门槛。
5. **失效要求未保持（P2）**：整体位移5次达到recalibration_required后，下一帧恢复旧平面，立即ok。要求重标定应保持到显式新有效版本，不靠一帧自动恢复，断流清连续证据与“已经失效的标定”是两种状态。
6. **版本类型仍不严格（P2）**：schema_version=1.0通过；只排除了bool，未限定int。必须严格整数版本（旧health/manifest语义不变）。
7. **混合布尔矩阵仍可加载（P2）**：identity R[0][0]=True、重算内容ID后，validate_ground_derived通过；旧_numeric_array转换会把bool变1。新派生块数组必须在转换前逐项拒绝bool/非数字，保留旧冻结validator兼容。

最终反例脚本codex_r2_integration_checks.py覆盖以上七方法，原样执行，54_*是可信失败结果。额外源码待核（非独立失败计数）：watchdog断流时是否清monitor连续证据；source.sha256当前只查长度而非hex/与parent.input一致；build默认补synthetic_fixture来源/created_at允许None，须按合成夹具与真实输入区分，不能声称“缺来源全部拒绝”；CLI仍exists后save_json，独占创建/失败不覆盖策略待核。

## 测试契约说明

R1“换标定清位置”反例曾用裸块d变化只检验清位置；R2据此允许裸块绕旧父一致性。六方法通过不足以证明新上下文正确。R3若选择拒绝裸不完整更新，允许在新的证据目录保存R1脚本副本，把该方法改用完整匹配父/派生artifact，再验证位置清除；原R1脚本/证据不改。须说明这是补全有效上下文条件，不允许放宽本轮七方法或略过一致性。

板端兼容仍NOT_RUN（Claude报告SSH超时；本轮不因软件已失败而反复联网），不以本地通过升级设备。机器人总高1.4m/雷达眼球垂直约1.1m/向下看有效；源原点偏移及约1.29～1.32m候选距差保留，物理标志false。

下一步：用户手动交AI_PROMPT_GL02_CLAUDE_R3.md。修复后Codex复审，不进GL03。
