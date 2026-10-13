# S9 外部改写观察（非本轮写入）

最初只读观察：manifest V1 e2e `ac52ca94c253...`，V2 annotator-1 `9f4f7b0706347c0d8106ea6ab30a100f0c4d2966dea88d5ebd4ea9f62c045424`，35对象、18标帧，P1=18/P2=17。V2 session_sha256.points=64个a、缺meta；与实际会话不绑定，已经BLOCKED。

训练01读取8会话后，S9 manifest变为仅V1 e2e：`d6cee828bae91eafbde30bba0c67f252381238c231cab6687cd60e8c0f337356`，冻结时间2026-10-10T14:40:48Z。GT_V2.json不再存在；draft与history亦变为测试占位。训练01 exit1（原始日志保留），未产生模型。

Codex没有运行freeze/标注器e2e测试，没有写入或删除gt_store文件。不推断具体外部操作者。新消费者记录NO_USABLE_NON_E2E_VERSION，并继续其余独立会话，不将e2e V1计入训练或指标；S9全帧算法运行仍可完成。
