# HF09部署前时钟边界

当前Codex源码复审发现三个组合边界，先修再测，不改算法/阈值：

1. human_fall_node.build_core把mode.replay=true标clock_domain=message_time，但所有ROS回调/worker实际传time.monotonic。ROS节点（含rosbag play）接收新鲜度始终monotonic；离线fall_replay独立显式source/message时钟不改。要么拒绝不支持的配置，要么明确ROS始终monotonic并修文档，不伪标消息时钟。
2. worker的now在解码/整个core.process前取。计算完成后应再次读取同机monotonic，若当前帧receive已超过cloud_stale，应只输出当前stale/unknown状态，不发布过期候选/旧正常状态/新警报。选人snapshot的生成时刻和当前新鲜度不要靠处理前时钟绿化；保留真实处理耗时统计。
3. on_request在core._lock等待前采receive_s，handle_request会等长计算后用旧时间。请求处理需在取得互斥锁后再取当前monotonic并校验；不要在等待/锁后仍把到达时刻冒充now。用明确公开小方法/ROS适配函数即可，避免泛重构。

补真实可注入时钟/慢计算/锁等待边界检查，不只grep存在。既有186/独立5+18+4/网页14都保留。普通软件问题用户已授权自行处理。

上述闭合后尽早启动30分钟真实点云有限统计，同时其他部署/回放/文档可继续。正式无地面保持unknown，原driver和首页不改；精确停止自己测试进程，保留备份与回退脚本。

## 追加：Codex独立watchdog实测5方法3失败

脚本evidence/review_hf09_codex.py，原日志codex_watchdog_initial.txt。ROS builder和请求锁后取时钟已PASS；剩下真正失败：status_state在必需cloud_stale时仍fall_status=upright，并把旧position/range/bbox标实测；首次无帧fall_status=None而非unknown。这也使你新增计算结束后status_state分支仍发布旧绿色状态。

请修status_state缺帧/非法/过期的公共输出为unknown、隐藏当前位置/range/bbox与实测声明；nested fall_state/target_features一致不可observable=true，并保留已存历史事件。不得放松本独立断言；输入恢复要重新按合法实测更新，不用持续timer来制造下降证据。无需改候选算法/阈值。补回归并跑本5方法，再继续HF09。
