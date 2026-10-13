# Demo v1模型调用与原分数标签缺陷，v2另目录修复

真实浏览器v1远行f5已SHA_VERIFIED，原模型调用显示[]，实际上完整ledger.model_calls包含真实A/B模型调用。原页面继承gate_calls字段，R05不存在这个分类否决字段，空数组不能证明模型未调用。DEMO_V1_DISPLAY_DEFECT_DOM/DEMO_V1_FAR5_MODEL_DISPLAY_DEFECT保存原实物；v1源码/TOOLING_SOURCES_V1不覆盖。

另建demo_v2（8917）：改读model_calls，真实n/69D features/featureSHA/prob全部显示；pre-fusion PA独立概率与内部ID另列。最终candidate.prob是原融合输出分数，不冒称对合并成员集合重算；union_model_p标NOT_RECONSTRUCTED。没有修改模型、输入、算法、评分或已跑ledger。真实浏览器完成后再裁定R05-07。

旧8916仅历史缺陷Viewer，当前入口由新Demo v2 README引导。Source/tooling V2实际SHA另登记，运行中的v1服务保持原源码。
