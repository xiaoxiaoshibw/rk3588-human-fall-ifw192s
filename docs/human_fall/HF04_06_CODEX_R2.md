# HF04–06第2轮：闭合独立连续性与时序边界

继续原session ses_f0c87fac6ffeKE1MYpxoZMnwXa。第一轮146项两端回归通过，但Codex读取调用链后复现下列问题；当前evidence/review_hf04_06_codex.py共14方法/15失败断言（NAN/Inf两个子例），日志第1轮09–11。不要重盘点或降低独立断言。修复原功能和根因，保持原HF01–03的92项冻结测试/源码资产；HF04–06尚未冻结的valid fixtures可补必需schema/session/track/标定字段及显式测试选择参数，但不能删测试或降低断言来求通过。

## R1 / P1：丢流超时可重绑；预测重复积分

tracking.py在关联成功后才检查遮挡时长。最后实测t=100/receive10，10秒后另一个候选距5m，仍locked同track；已有occluded后迟到近候选也能跳过lost timeout。关联前按正确域检查距最后有效实测的超时/时钟质量，超过窗口lost并requires_reselection，不依赖每次丢帧都调用update([])。lost/ambiguous后继续拒绝自动重绑。

预测必须从最后实测位置/速度/时刻重算，不能把上一次预测再加“距最后实测的完整dt”。独立例：x0@100→x1@101，空帧101.5再空帧102，应x2而不是x2.5（均在1.5s预测窗口内）；时长从最后实测计，有限预测且非观测。单位/时钟域/负dt明确，不把异常dt钳0后继续配人。新增大小/合并风险检查时须保留合法站→卧尺度变化。

## R2 / P2：快照新鲜度与请求协议门控

selection.py允许快照receive=NAN/Inf、age<0的未来快照参与选择；请求schema_version999仍被执行。登记/请求时间和TTL必须有限、单调且同域；负age/过期/非法当前质量均拒绝，拒绝发生在状态修改前。所有动作校验schema_version=1和当前session/epoch/selection_version，不仅select；capture_baseline错误epoch99当前0也被接受。错误类型/未知版本返回明确拒绝，不通过int强转截断版本，不写NaN/Inf ack。

原幂等语义保持：同ID同内容不重复执行、冲突内容拒绝；旧会话/epoch命令不能变更当前目标。标定版本从板端快照/目标取得并与请求核对，不信客户端任意标定标记。采集基线起点取板端当前有效源时刻，不能信客户端任意source_stamp_s。无需通用schema框架或新依赖。

## R3 / P2：切人继承旧ready基线；人工确认绕过低姿态

select/release/epoch/失锁后旧目标ready基线仍保持ready。清除当前基线资格（可保留历史产物），新目标需重新采集；FeatureExtractor/FallStateMachine消费ready时核对session/track/epoch/标定/选择绑定，不接续另一人。正确幂等select重放不重复清当前新基线。

operator_confirmed=True会跳过所有height边界，完整贴地0.2m、max0.3m的平坦低姿态也可收成站姿ready。人工确认只记录操作者意图，不能绕过必要实测点数/高度跨度/姿态/稳定质量。允许低median但足够站姿竖向范围的合理视角，完整低卧例必须拒绝；现有低median正例可补齐真实成立的p90/max/跨度夹具，不伪造缺失测量。

## R4 / P1：静态基线差伪造下降；预测后重复事件

_classify将baseline_height-current_height达到门限直接当_descent_seen。当前进程启动已躺，即使height恒0.2、rate0，只要存有旧站姿基线，仍confirmed；初始低姿态0.35→0.15的小动作也可凭大基线差确认。下降幅度和速率必须由当前同目标连续有效实测历史提供，静态基线差只是姿态量，不是下降证据。初始化低姿态（包括有历史基线）保持low_posture_unclassified，不发事件。

一次confirmed后预测/质量中断令状态unknown，但保留_descent_seen/_low_since；重新看到同一低姿态又发第二事件。预测/质量断开不能填补连续低姿态时长/下降；保持已存事件，并且同一未恢复跌倒episode不重复计数。恢复后的真实新下降、重新选择另一目标的完整新证据才可新事件。默认线上mode_verified/allow_confirmed仍false，不能为测试开启真实模式。

## R5 / P2：重置标记永久粘住unknown

FeatureExtractor.history_reset_reason持久保留，FallStateMachine每帧把它当新重置，切人/epoch变化后再有正常观测永远unknown。区分一次性重置事件与持久诊断，重置清旧历史一次，随后连续新有效观测可重新得到upright和新的下降证据。不要为恢复而保留旧目标历史。

## R6 / P2：默认回放入口未经人工选人自动锁最大簇

ReplayPipeline默认首帧自动锁最大簇，与人工选择路线冲突。默认unselected；用显式initial candidate/position/operator request初始化。受控synthetic replay需要自动夹具时显式opt-in并标注测试来源，不能作为生产Node默认，不伪装人工确认。更新回放CLI参数与纯回放测试的有效初始选择，确定性/不自动重识别继续验证。

## 回传与下一阶段

运行原14方法独立脚本、全部回归及新增真正失效用例，两端相同哈希隔离复跑、记录内外退出码。同步INTERACTION_CONTRACT.md精确草案和例子（尚未冻结），追加HF04/05/06第2轮SUBMITTED，证据evidence/2026-10-01_autonomous_hf04_06_r2/。保留第1轮失败板测输出；若删除了派生stdout文件，实际失败信息仍在CLI JSON事件中，恢复到标明failed_attempt的日志便于审查，不抹掉CR/路径错误尝试。

修复完成退出让Codex直接复审，不要求用户转交，不自行ACCEPTED。无需部署/改雷达/网络/厂商库/自启/原始bag/用户资产；普通错误自行处理。Codex复审通过后立即推进ROS集成与WebUI。
