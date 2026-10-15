# 当前交付入口

状态 **SUBMITTED / REVIEWED_WITH_FINDINGS / STOPPED**。独审完成，不代表验收通过；r04未全收口，无VALID registration。

- [最终报告](FINAL_REPORT.md)：三工单状态、r04逐ID、数值/分母、artifact三gate与集成结论。
- [唯一补充验收](ACCEPTANCE_V1.md) / [独审记录](INDEPENDENT_REVIEW.md)。原r04与V2表引用，不追改历史。
- [统一输入](UNIFIED_INPUT_MANIFEST.json) / [实际版本与完整复现命令](CURRENT_VERSION_MANIFEST.json)。
- [机器指标](metrics.json) / [逐帧背景结果](background_frame_results.jsonl) / [逐帧pointset结果](pointset_frame_results.jsonl)。
- [最小人工审阅队列](REVIEW_QUEUE.json)：31 POINT、155 ROW、9类窗口、HF164帧，全部PROPOSED/UNKNOWN。
- [对比图](AB_RETENTION_AND_UNKNOWN.png) / [HF困难帧](cap_20261013_094333_DIFFICULT_FRAMES.png) / [静立困难帧](cap_20261010_180557_DIFFICULT_FRAMES.png)。
- [当前真实浏览器](browser_final_verified/BROWSER_CHECK.json) / [审阅页截图](browser_final_verified/REVIEW_QUEUE_S8.png)。
- [相关测试命令与日志](TEST_RUNS.json) / [首次失败记录](RUN_LOG.md) / [首尾保护](PRESERVATION_CHECK.json)。

从D:/Code/ldiar运行现有页面（启动本机服务，不采集/部署）：

```powershell
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/server.py --port 8942
# http://127.0.0.1:8942/?sid=cap_20261010_180557&fi=10
python -B -W error sidequests/human_fusion_lab_next/real_fall/r04/server.py --port 8932
# http://127.0.0.1:8932/
```

8941旧服务未重启；源码为同一r01，新的队列需运行修复后server。console当前源码仍r02，不用旧桌面入口冒称已看r04。
