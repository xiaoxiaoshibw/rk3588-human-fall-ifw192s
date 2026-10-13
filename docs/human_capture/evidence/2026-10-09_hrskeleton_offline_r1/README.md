# HR-SKELETON-OFFLINE r1 交付入口

SUBMITTED / BLOCKED；12项工具自验PASS，6项真人效果/GT项BLOCKED，未ACCEPTED。真实GT=0（用户回复无）。本轮不是再次规划：已提供可运行可信绑定、完整簇审阅、5–7区域节点数学原型、独立时序和完整120行运行证据。

- [完整复审/六类结果](REVIEW.md)、[SKO-01～18](ACCEPTANCE.md)、[实际命令](COMMANDS.md)。
- [人工任务](GT_TASKS.md)、[全部待审成员](gt_pending.json)、[120行索引](frame_index.csv)。
- [契约](CONTRACT.md)、[输入](input_manifest.json)、[划分](split_manifest.json)、[参数v1](prototype_params_v1.json)、[最终源码冻结](freeze_r3.json)。
- [最终normalized](pass5/normalized_frames.jsonl)、[raw](pass5/nodes_raw.jsonl)、[filtered](pass5/nodes_filtered.jsonl)、[真实指标/缺口](pass5/metrics.json)。真实normalized为null/BLOCKED_GT；合成正例见synthetic_fixture.json/synthetic_output.json，不计真人。
- [独立复算](independent_audit_final.json)、[完整性](05_integrity.md)、[交付SHA](delivery_manifest.json)。

从仓库根启动审阅：

```powershell
python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/serve_review.py
```

打开 http://127.0.0.1:8883/review.html ；当前测试服务已停止，Ctrl+C关闭。参数frame为固定分支行索引，ci为完整簇编号；例frame=0&ci=1是开发112的一个待审簇，不预设PERSON。页面显示完整点、原row/摘要、raw/filtered与UNKNOWN；矩形选择节点参考区域，填实际reviewer/标签/连续身份后导出sidecar。

测试命令（已运行，复跑必须使用新输出日志名/目录，不能覆盖旧产物）：

```powershell
python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/test_skeleton.py -v
node docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/bind_inputs.js validate <实际人工sidecar路径>
```

后续运行真实数据必须有最小B门及新证据轮授权，复制工具到新rN后重新核输入/冻结；绝不把合成或ROI改为human。不启动HR-07/08/09、W06/W07/ML或生产。

![已核验的完整簇审阅](browser_review_final.jpg)
