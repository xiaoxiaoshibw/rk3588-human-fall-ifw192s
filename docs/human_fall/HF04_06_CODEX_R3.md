# HF04–06第3轮：最后两个严格门控

原R1–R6的14独立方法已由Codex本地通过，156回归通过；感谢范围内修复。再次源代码核对发现两个未闭合路径，直接继续原session ses_f0c87fac6ffeKE1MYpxoZMnwXa，最小修复后推进ROS/UI。新独立脚本扩展到16方法、3失败断言，原14断言不变；日志第2轮12_codex_scope_clock_boundaries.txt。

1. features.baseline_applies遇到baseline或observation缺绑定字段时continue，所以仅 `{status:ready,height_m:{median:1.5}}` 对任何目标都有效。缺session/track/epoch/选择/代/标定绑定必须unknown/False，不能跳过核验；消费组件的自身session可作为当前上下文来源，但缺基线必要字段不得当成有效。把原HF04–06仍未冻结的合法fixture补齐真实成立的绑定，不降低断言；原HF01–03冻结92项不改。回放CLI的高度参数只可构造明确当前手动目标/受控fixture基线或报告未绑定，不生成无身份却ready的通用基线。
2. tracking._elapsed每次动态选receive/source，当前receive=NAN/Inf时回退源秒继续接受实测，破坏时钟质量门控。select时确定本目标时钟域，后续当前选定域无效就拒绝当前观测，保留上一合法实测基线（position_predicted或lost/unknown明确原因），不能改成另一域来制造有效。纯离线显式source域仍支持；合法恢复、负dt、间隔超时、预测锚点原例不破坏。原已有online选中receive10/source100，非法receive但source100.1时last_measured_source必须仍100，而不是消费新帧。

补两端原样16方法与全回归、同哈希隔离，记录source clock选择和基线严格条件的契约/迁移。保留前两轮回传，分别追加第3轮SUBMITTED；证据evidence/2026-10-01_autonomous_hf04_06_r3/。不要改独立脚本、不要削弱原14修复，不重做盘点。默认真实confirmed门控仍false，真实物理未验收不冒称通过。完成后结束，Codex复审并立即派发HF07/11。
