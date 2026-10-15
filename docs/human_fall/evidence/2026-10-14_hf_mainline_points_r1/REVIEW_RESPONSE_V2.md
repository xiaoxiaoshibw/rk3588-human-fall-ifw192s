# 独审发现回应 v2

原OPENCODE_REVIEW_02.md/jsonl原样保留，结论REVIEW_WITH_FINDINGS；本文件是作者回应，不代写审者结论。

- P2-1：FEEDBACK_DIVERGENCE逐1966帧完整NPZ集合核对，feedback原FG锚点相对R1分歧0，最终成员相对combined分歧0。单独tracker执行属实，但该数据上是零分歧退化臂，没有独立效果信息；不能称独立前景证据。
- P2-2：护栏是读取首轮完整回归（含80历史帧）后选择的拟合式后处理过滤器。0.85/0.12m/30°来自旧R3/R2常数，非本轮诊断统计推导。PR04/05明确后验护栏内及REUSED_REGRESSION，不能作为独立泛化证据，不再借PASS淡化选择偏倚。
- P2-3：VERIFICATION_TIMELINE将保留产物SHA、观察到的mtime、缺源检测时间绑定；PR05/07a是历史保存证据，早于FINAL_SOURCE_AVAILABILITY，当前不可复跑。mtime不是独立可信时间戳，限制保留。
- P3-1：S8_HUMAN_REFERENCE_BINDING绑定已审GT SHA/源SHA、523个既有输出SHA和逐帧reference源行集合SHA、53帧57045分母、GT对象PERSON身份/帧/压缩索引数量与既有human_reference.npz SHA。所有派生输出匹配初始快照。原始文件当前缺失，不能重新证明valid_raw紧凑索引到原始记录的映射；该限制显式保留，未伪造原始映射重放。
- P3-2：BROWSER_FINAL_SOURCE.json为空，原因是读取折叠区域innerText；OPENCODE_REVIEW_01.md为空是CLI启动参数失败。均保留为失败工件，不再用作成功证据。实际浏览器点击源行见BROWSER_FINAL_SOURCE_V2/BROWSER_FINAL_ADDITIONAL、截图BROWSER_FINAL_RECOVERED；真实审核原文见02。

最终FINAL_INPUT_BINDING_CHECK：原始快照captures/remote下1778文件全部当前缺失（其中主链18），跨仓11个依赖SHA仍相等。当前复跑BLOCKED，不归因、不替代原录制；冻结输出和原始验证证据保留。算法和冻结配置未改，本轮仅追加溯源统计和限定交付表述。
