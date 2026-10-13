# R05 独审缺陷处理（原源/原账不覆盖）

独审01 child15472/export0，指定实际模型核验PASS；完整REVIEW_COMPLETE。独立代理也只读核对23已加载九会话与model/工具SHA、计数一致。

- P1-A：新增PARITY_SUMMARY_V2明确field_parity=true / ledger_byte_parity=false及全部22比较字段、新增bank_events诊断与非比较字段范围。原ledger/SUMMARY/FRAME_PARITY/验证源不改，运行与分类/点/状态字段精确相等不等整文件字节相等。独审写21个，实际fields列表22，按实际列表为准。
- P2-B：保持原fail-fast不变式throw。无独立FG证明却写bank表示实验实现资格失效，不允许忽略后继续修正锚点。exit1/partial ledger将按软件/反例失败保留、不能归环境，不能进入FINAL。本次不触发且两套完整exit0。当前即弃保守银行播种优于把无证明更新当可用；不改变原成功运行的代码版本。
- P2-C：原实验rf51_threshold确为.55，硬编码断言没有影响本轮真实结果；明确范围仅该冻结配置。下一轮新分析从实际config读取阈值，旧源/结果保留。模型参数变化须新版本，不能用本轮脚本证明任意参数资格。
- P2-D：raw秒TTL标签遗漏保持已知限制；v2派生同时按帧/秒TTL补证，完整BANK_*_V2 exit0，不称原raw已修。
- P2-E：当前验证器仅读取真实DOM，不访问隐藏packet。先读取UIframe，再三窗头部f/t与原meta逐项一致，所有23行独立代理重复核实。正则\bf(\d+)\b不会匹配final（f后非数字）；本轮实际无误，任意新文案需新版本验证。低风险加固不重写当前验证源/重新生成浏览器证据。
- P2-F：Demo README第5行已明确control导航从精确parity派生；server场景case.variant映射，当前control真实22字段逐帧相等。引用PARITY_SUMMARY_V2，未冒充新control收益，下一轮若control变更必须重新实跑或新索引。
- 只读代理发现人工包175804 f233–243越界：会话239帧最大238；新MINIMAL_HUMAN_REVIEW_V2裁为233–238，原包保留。机器CASE_INDEX本就min(len-1)，原结果不改。
- 边界/性能：BOUNDARY_AND_PERFORMANCE_SUPPLEMENT纠正brief01/AUDIT_READY全机无竞争含义；主控串行不证明全机无竞争，42外部新增与当前外部评测进程真实列出，不干预。性能实际FAIL，环境资格另BLOCKED；不归咎未证明原因。

后续收口新报告/return/TOOLING_V4/结束增量尚待补审实际完成，不能用旧R04或只读代理代替指定OpenCode。
