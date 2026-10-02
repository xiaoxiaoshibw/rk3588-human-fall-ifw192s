# GL-02 R1 Codex独立复审：REWORK / 2026-10-01

用户在本轮执行中明确后续任务改为手动交给Claude Code。现有GL02 OpenCode轮次已exit0并收取回传，不自动派GL02返工或GL03；下一步是Claude Code手动执行GL02 R2返工，完成后由Codex复审。

Codex独立262全回归exit0（41_*），但codex_gl02_boundaries.py 6方法6失败（40_*），软件仍REWORK；真实物理/真实来源BLOCKED。GL00 R4/GL01 R4已通过的软件范围不重做。当前数学变换基础已实现且旧回归保持，但不能据测试总数放行生命周期/监测。

具体问题：

1. 整片可信地面平移0.10m连续10次，监测始终degraded，没有要求重标定。旧平面支持率<.8即阻断“连续变化”的计数，真实整体偏移反而走不到失效分支；原自测只提高约10%点的p95，不能证明整片地面变化检测。修复需保留质量不足unknown与可信一致变化的区别，不放宽GL00残差门槛或逐帧改变换。
2. 未确认的自动source AABB边界被当成可信地面，报告ok。源valid_region角点变换只是几何外包范围，不是地面身份/覆盖真值；需要明确独立可信ROI来源，缺失时unknown。测试的trusted/evidence字段为复审探针，不强制实现字段名；语义不得改弱。
3. apply_ground_context换ID后只清基线/快照，tracker.position_m等旧位置仍保留；功能声称positions已失效但实际未清。旧选择/请求缓存、特征历史、_last_candidate/_last_state等消费入口也需核查，源seq/stamp/epoch保留。
4. 同ID损坏标定（t=99m）可被apply_ground_context接受，且先修改self.calibration。启动/reload应先完整校验，再原子切换；同ID不能跳过校验。坏输入不得保留旧绿色有效状态，具体拒绝/失效策略与日志明确。
5. parent ground d=1.4和ground_derived d=1.2同时进入同产物仍可通过；各块独立合法不代表互相一致。父ground/source frame/n/d/源hash等必须一致，constrained数据也须严格validator。
6. 嵌套schema_version=True等于1被接受，版本必须严格整数；同时核查新数字/数组字段中mixed bool及R/t/单位/frame/source/created_at/quality的完整性。

附加静态待核：GroundMonitor持续性参数可用浮点再int截断；未知帧/断流时旧监测结果/连续证据需失效；recalibration_required须真实影响观测有效性/位置/基线，不只作为quality装饰字段。derived source AABB不能声称完整地面支持覆盖。CLI --ground-derived旧路径选项不得静默忽略；输出拒绝前不得覆盖diagnostics，必要新产物使用独占创建。

R1更改lidar_candidates.py仅添加ground_derived_id绑定，属于本单兼容元数据接入，未做GL03框/聚类修改。geometry/default与driver/UI未动；冻结状态仍须以基线SHA核对。板端隔离NOT_RUN是本轮未执行，不是缺部署/采集授权；既有权限允许隔离纯函数兼容测试，部署与采集仍不执行。

手动任务完整提示词：../../AI_PROMPT_GL02_CLAUDE_REWORK.md。执行者仅SUBMITTED/BLOCKED，Codex独立复审后才改PASS，不启动后续单。
