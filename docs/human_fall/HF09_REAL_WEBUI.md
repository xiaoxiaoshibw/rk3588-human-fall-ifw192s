# 正式真实页面复测：带宽和源帧对齐

Codex实际IAB连接正式/human_fall/index.html，真实49143点：7.8Hz/9.4MBs、丢帧从32累计448；每3秒Send buffer limit reached，截图codex_real_before_transport.jpg；候选按钮偶尔出现，截图overlay一直等待匹配。现已断开释放订阅。不是synthetic80点时的通过。

这两项要与HF09_CODEX_R2一并闭合再最终回传：

1. ROS候选不应每帧给网页发送几万项point_indices等离线证据数组。纯算法/选择缓存和离线证据保留完整，网页ROS投影用新dict（不可原地pop污染缓存），只去掉网页不用的大索引数组，source/session/epoch/candidate_id/center/box/point_count/quality保持。先量实际JSON字节缩减和不改变原对象/同输入算法结果，更新ROS投影语义文档。不能以改算法丢弃人体点换带宽。
2. 现在只缓存候选快照、不缓存原点云，处理75ms+排队50ms后输出常落后最新点云一两帧。缓存最近8个原始点云payload及raw seq/sec/nsec/本地到达序号，显示最新可配已处理源帧，延迟标本地接收到呈现的年龄；不要把旧框画到最新raw场景。正常raw接收Hz统计与实际呈现Hz/跳帧明确分开；网络/断流/epoch/session切换清缓存，过期源帧隐藏框，不能持续保留旧状态绿色。无算法输出时仍可显示当前raw点云+unknown。
3. 不新建前端框架、不增加无界缓存、不改driver/桥服务参数。如果去索引后真实链路仍溢出，可新增仅可视化抽样流（算法完整原流，header严格保持用于同帧匹配，明确显示抽样与数量）。先回传具体测量结果，不通过虚改源seq/时间掩盖缺帧。
4. 有效JS缓存/不同stamp/跨epoch/过期边界测试与序列化不变检查；实际网页复测由Codex做。preview与正式共用同修复语义，保留原首页。R2代码bundle/回滚/原始测试日志要求仍执行。无需重录原30分钟统计，只另测消息/可视化效果。

请优先做最小必要改动，完成同session回传，不扩充新模型/身份/真实标签。
