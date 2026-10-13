# 完整性与工作树边界

开始基线 [baseline_before.json](baseline_before.json)，结束基线和漂移将由最后一次采样记录。审计文件只新增于本目录，另新增 `docs/human_capture/returns/HUMAN-FUSION-DIAG.md`。不修用户并行修改、不回滚已有变化。

输入和18个冻结副本的结束SHA核验见 `final_integrity.json`；这是完整性检查，不是重复人体检测或新的语义审核。当前GT SHA资格与输入字节不变是不同概念：S9资格不合格不能因结束哈希相同而PASS。

新执行：data_audit（9会话读取/索引/RAW支撑）、S6 stage probe（476 ticks）、missing-reference单变量A/B（1600 ticks）；历史18个Demo结果仅重算，没有本轮九会话浏览器测试。外部源码只下载阅读，没有外部训练/运行。

research_supplement第一次exit1为新输出子目录尚未创建，保留原日志；补建自己证据子目录后r2 exit0。初猜错误DOI返回无关论文，原lookup保留且在研究记录排除。没有把这些失败改写成初次成功。

设备/物理/采集/部署、关节GT、真实跌倒与泛化、有效S9双人身份仍NOT_RUN/BLOCKED/UNKNOWN。

## 结束核验结果

- [结束基线](baseline_after.json) / [漂移](baseline_delta.json)：HEAD未变；9,644路径；26已有文件内容变化、2元数据变化、56新增路径，其中本轮仅新增回传1个，55个其他审计目录外新产物。结束读取无unstable路径。不能证明整树冻结，**A01整体BLOCKED**；本轮没有修改这些外部文件。
- [final_integrity.json](final_integrity.json)：36输入SHA全部不变，18原副本和对应live源不变，初次96本地链接全部存在。S9资格仍BLOCKED。
- 漂移主要包含18份既有V2结果JSON、V3背景研究和CC骨架适配；只读复核后18份V2candidate/track数字全部与原重算相同。旧结果文件内容冻结不得宣称PASS。
- 补充冻结33份晚到输入，SHA见 [late_snapshot_manifest.json](late_snapshot_manifest.json)。[late_review.json](late_review.json) / [日志](late_readonly_review.log) exit0：859条固定候选PointNet中心化A/B推理、608条B家具XGB复评分；没有训练/replay/browser。PointNet遗漏中心化已定位，B家具FP595/TN13已复核；V3逐层文档与实际JSON冲突详见报告12节。
- 此后只编辑本轮报告/任务书/完整性记录并追加本回传；没有把这些自身交付写入当成并行生产变化。采样后的全树未来变化不作保证。

最终文档检查：[final_document_check.json](final_document_check.json) / [日志](final_document_check.log)，exit0；126本地链接有效、51冻结副本不变。完成版REPORT SHA256：`94196f0f007d9b24414c165eb7527ba4fc8e767faf8c5de1c9d08c935078760e`。验收表v1 SHA保持不变。完整性自验不会解除整树漂移或语义/物理BLOCKED。
