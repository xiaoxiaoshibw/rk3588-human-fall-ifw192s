# GL-02 Claude R3独立复审 / 2026-10-01

结论：**软件REWORK，GL03不放行；板端兼容NOT_RUN；真实物理BLOCKED。** 用户继续手动给Claude Code，Codex未启动实现CLI。

已闭合R2七方法：Codex原样复跑7/7 exit0（51_*）；全回归267/267 exit0（50_*）；R2静态6/6 exit0（52_*）。裸不完整块显式拒绝符合最新契约，R1旧裸块位置用例的5/6结果是保留的历史口径，不因此否定已修复部分；完整有效上下文清位置由新回归覆盖。

沿其他受支持入口复查，新增上下文4方法4失败（53_*），补单侧遮挡后最终5方法5失败、exit1（55_*）。此前成功和本轮失败全部保留，未改弱原七方法。

## 剩余五项

1. **配套ground+derived局部更新发布旧GDID（P1）**：apply_ground_context(ground=flat_ground(1.4),ground_derived=trusted_block(1.4))虽替换self.ground/self.ground_derived，却未替换self.calibration。下一帧snapshot.calibration.ground_derived_id仍gd_653bd8b4ce2c119d，而实际monitor/runtime ID为gd_f19f31ed2caa8a66。新地面正确但版本与消费者仍错配。所有入口统一构成完整canonical上下文并发布相同ID，不能只有完整artifact路径正确。
2. **配套局部更新仍持有caller字典（P1）**：上述路径resolved_ground=ground/resolved_block=block直接赋值。调用后caller把offset或t改99，core值同步变99，绕过加载验证。完整artifact路径的deepcopy没有覆盖此入口；所有可接受输入先校验/解绑再提交。
3. **calibration_id变化但GDID相同未失效旧资格（P1）**：合法新artifact v2含同一GDID，apply后旧track位置[1,0,.2]和旧版本目标仍保留。changed只比较GDID；需以calibration_version与GDID等实际有效上下文版本判断，清基线、快照、请求/轨迹资格和相关缓存。ground-only无GD路径也需同类检查，不能读旧版本历史继续工作。
4. **monitor不可用仍接受capture_baseline（P1）**：synthetic人体簇导致ground monitor不可用，process输出已invalid，但handle_request的_required_input_reason只查cloud freshness，选择后capture_baseline仍accepted并把collector置pending。持续不可用时_feed_baseline一直跳过，pending可无限停留。基线请求入口须按当前地面监测资格拒绝/回执，不只阻断后续feed；旧pending/ready资格的失效策略明确，解除目标/原始可视化等行为保留。
5. **10%单侧遮挡误锁存整体地面位移（P2）**：360点原地面仍Z=0，40点物体Z=.3；支持率.9>=.8，10帧后仍recalibration_required。_coherence只看off-support子集，单侧平整物体自然同号/低离散，不能证明整片地面变了。该样本可暂时degraded/unknown，但不以局部遮挡锁死旧标定；保留整个可信地面+0.1m连续平移正例和双向散点负例，不放宽GL00门槛。

反例脚本：codex_r3_context_checks.py，最终输出55_codex_remaining_final_stderr.txt。五项均独立实跑，不是建议性的猜测。

范围对照54_*：整体GL02改动仅calibration/ground/runtime/CLI及R1既有candidate版本元数据，冻结配置/driver/UI保留；当前ground SHA956786ba…1893、runtime18e64b2d…834b匹配R3回传。板端未跑的网络失败保留，不冒称设备PASS；本轮不因软件已失败而反复联网/部署。

R4限定为剩余入口一致性和监测遮挡误判，不重做已审数学/严格类型/CLI独占创建。允许把旧自测中“10%off-plane==整片位移”的期望更新成局部遮挡不可证明位移，保存原失败与解释；不得改弱本轮五方法或此前整体位移正例。若选择取消配套局部更新API，先说明其调用链与兼容影响，不能用直接删除/拒绝该入口逃过当前仍公开支持的上下文一致性需求。

手动下一步：AI_PROMPT_GL02_CLAUDE_R4.md，提交后由Codex复审。
