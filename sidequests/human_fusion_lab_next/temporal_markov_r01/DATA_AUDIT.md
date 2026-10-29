# 数据审计

master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；脏工作树完整记录BASELINE_STATUS.txt，相关tracked/untracked源SHA见BASELINE.json。只读复用上一轮E0 G0，1934动作+90独立空场，非未见泛化集。18原meta/points重核，6072份JSON/NPZ逐文件对旧INDEX验证。R2完整提取，R3特征字节复用和新时序结果分开记录。

原始字段根据实际meta.point_layout及human_replay_lib既有契约，只消费XYZ@0/4/8和intensity@12，小端float32、stride28。其余字节不解释。offset/count全连续、总长匹配、时间严格单调。时间是设备未锚定秒，不把bag walltime作设备时间。中位9.64655Hz，dt约0.103665s，速度使用每轨迹真实相邻dt；空场只取mod3=2留帧，因此实际观察间隔约0.311s。

当前labels目录0文件；LABEL_MANIFEST重读：282核心和66第二人未审核，trusted_K=0。九源human_annotations=0；动作名不是标签。E1正式训练仍未解除，未训练、未调参选胜者。所有P/R/F1、混淆矩阵、Macro F1、真实事件P/R与延迟均BLOCKED/UNKNOWN。

人体点集稳定性只能描述：1934帧都有候选，90空场无候选，几何轴歧义2帧；候选纯度/完整性与关联置信度未知，不把selected_count稳定当真人证据。旧action_output包含历史来源和RF占位0，本轮不拿占位作基线；输入来自可SHA核对的最新E0。原131958背景原源缺失是历史边界，本轮消费E0已冻结数值产物，不宣称重新验证其物理标定或原场景。

输入全索引：run_r3/INPUT_MANIFEST.json、FEATURE_REUSE.json；保留来源meta/points、每帧源seq/offset/count、候选成员SHA、轨迹ID。各会话既有dev/final角色原样保留，但全体早已开发暴露；本轮纯规则机制研究，不作泛化验证或使用最终集选择阈值。
