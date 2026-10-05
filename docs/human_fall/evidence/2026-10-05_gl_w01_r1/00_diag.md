# 写前诊断 / GL-W01

根因：human_replay_lib.py 只有静态/meta/bin/标注/板端代理路由，缺本地配平任务；console.html/replay没有计算入口。P02 estimator脚本有顶层输出断言，不能普通import旧证据；其三个纯函数数学移入新工作台适配器并注明来源，不修改旧证据。

范围：pc_apps/human_replay新增leveling页面/JS、本地leveling服务与三个纯估计器、检查；human_replay_lib.py添加本地路由；console.html增加卡片；index.html回放页增加链接；Console.spec显式numpy打包。不改src生产数学、webui、录制、旧证据。唯一writer Codex，ponytail实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。

| 操作 | 入口/赋值与检查 | 保留/失效 | 验收 |
|---|---|---|---|
| startup/no session | local session route / UI initial disabled | no job/results | W01/W06 |
| same content reload | source SHA both files then UI load | old browser results cleared; jobs immutable | W01/W06 |
| same ID new content | expected hashes vs actual before/after fit/export | reject, no ready result | W06 |
| new session/ROI/config | UI generation counter before fetch, clear previous report | late response discarded; old disk outputs retained | W01/W02/W06 |
| caller mutation | validate_config owned normalized copy, server job immutable input | cannot mutate inflight config | W06 |
| foreign frame/units/schema | strict meta contiguous offsets/28B/XYZ/innolidar/version, source fingerprint | error state, no export | W02/W06 |
| overlap/nonfinite/line/missing ROI | frozen union membership / quality | reject or explicit FAIL; no silent trim | W02/W03 |
| insufficient/empty holdout | deterministic 3 distinct excluded frame ordinals | reject/invalid estimator; never train on holdout | W03 |
| run/concurrent run/failure | one nonblocking global job lock, queued/running/ready/failed | second409; failed no artifact route | W06 |
| local download/result preview | job+method+artifact whitelist, ready check, resolved inside unique root | immutable new data only | W05/W06 |
| source modified during fit/export | fresh end SHA before commit/ready | fail all exports; hidden incomplete dir retained for diagnosis | W05/W06 |
| TLS/SVD agree RANSAC disagrees | full same-domain pairwise + numerical LS check | no majority recommendation; individual geometry results retained | W04 |

静态离线任务不持有上一帧accepted/EMA或生产消费者，所以AGL freeze/recovery/timeout状态裁剪为明确不适用；本单不实现GL-A～I，也不把其计划状态改PASS。3帧留出为当前会话事前冻结诊断，不是未曝光物理ground truth。输出标注框不搬入新坐标系，保存原标注为source_annotations并清空human_annotations，避免旋转框被误消费。
