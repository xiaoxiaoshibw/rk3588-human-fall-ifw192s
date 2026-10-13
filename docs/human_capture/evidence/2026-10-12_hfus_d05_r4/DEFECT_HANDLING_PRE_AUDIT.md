# 实际独审缺陷处理（最终OpenCode前）

旧OPENCODE_SOURCE_01是中途审查，wrapper exit1，原child exit未保存；随后export exit0只能证明实际指定模型与完整文本，不能判最终独审PASS。保留旧日志。

| 缺陷 | 实际处理 | 状态 |
|---|---|---|
| 统计累计被当逐帧 | 新纯perf银行账明确PREFIX_CUMULATIVE_NOT_PER_FRAME，验证差值等于实际readmitted；不替换hook stats闭包对象 | PASS |
| 工具/HTML/Python不在加载JS manifest | R02 TOOLING_V1与当前R04 TOOLING_V1及SUMMARY真正加载源码分列；GT/AUDIT companion补全 | PASS |
| 未有银行前后快照 | R02/R03/R04所有会话RETENTION_BANK，计时外实际before/after；R03近距回退银行上下文另存 | PASS |
| Demo旧packet在加载时可被projection重绘、旧catch干扰新帧 | R03/R04 show开始清packet/pts，catch先检查token，跨会话shortcut退出旧请求；R02旧viewer缺陷保留，最终使用R04 | PASS源码；真浏览器结果另列 |
| auto来源当propagated，lost当运动预测 | 分列human/propagated/auto/UNKNOWN；coasting(last observed)，无运动外推声明 | PASS |
| SUMMARY无GT文件SHA字段 | 不改旧SUMMARY，CONSUMED_ASSETS_BASELINE_BINDING+POST_SHA_CHECK绑定AUDIT/输入/GT/manifest三轮before及真实after | PASS |
| 旧runner dead linkBase和分析unused timing | 不调用，不参与final；旧失败原样保留，R03/R04无dead linkBase | PASS说明 |
| fixed features用于最终候选诊断与实际gate可能不同 | R03raw_model_scope/classification_reason明确RECONSTRUCTED；实际inference gate_calls/raw/effective独立完整保存 | PASS |

未闭合：家具高分及bank自维持、远行/遮挡混簇、turn BG loss；资格不足阻模型晋级/连续身份/退出结论；R03 near five strict regressions确凿FAIL。H3仅合法登记A06参数与120有限参数反例，不宣称NaN等未登记配置支持。没有为了结束而降低验收。
