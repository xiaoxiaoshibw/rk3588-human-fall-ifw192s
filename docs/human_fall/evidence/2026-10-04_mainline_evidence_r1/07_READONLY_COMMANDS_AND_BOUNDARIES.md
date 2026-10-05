# 实际只读取证与边界

本轮设备侧只读取证命令均使用：`ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 ldiar-wel`。原别名/密钥/host校验保持，未写ssh配置或存凭据。

| 步骤 | 实际远端命令/输入 | 原始exit/output |
|---|---|---|
| 01 | `hostname; docker ps --format "{{.Names}}|{{.Status}}"` | 01_board_inventory_exit=0；主机welcomtech，两已有容器Up33h |
| 02 | `docker exec -i slam-localization python3 -`，stdin为02_board_file_probe.py | exit0；指定原bag存在114550423bytes，ROSBAG V2，实际SHA等于metadata声明；非原件路径不存在 |
| 03 | 同上，stdin为03_read_bag_chain.py | exit0；只rosbag.Bag(...,'r')读指定原件、独立numpy26→28重建、首尾bagSHA一致；stderr有LZ4扩展不可用提醒，但本bag成功全量读取，不安装任何扩展 |
| 05 | 同上，stdin为05_recording_context_probe.py | exit0；只指定config与两个日志位置/同config目录文件名索引，没有递归设备扫描或更改 |

03输出canonical完整bytes SHA与本地bin实际一致，89frames、4372400points、dropped0。04初版检查bag_time_sec失败是本审计漏读既定`round(bag_time.to_sec(),6)`规则；04原exit1保留，修复为精确6位舍入后04b exit0。原header secs/nsecs始终按整数精确比较，无放宽数值精度门。读取/布局/XYZ证明不能倒推SDK录制外参或world-up。

timestamp独立测得float64→float32最大数值误差0.00781099998857826，源数值范围在03 JSON，单位未独立核验。冻结HR extractor注释“1s内<0.1µs”不能由这些数据支持；本轮不改原代码/格式，不将该注释沿用为precision证据。新的timestamp格式或解码器变更属于后续独立需求；当前frame header时间保持，不能把point timestamp量化当成header丢精度。

当前运行config六零、use_status=true，SHA bd428a1e9ed93a6b4b0951f2d3c88d368a4074231ce993d6c43761d24a2c8e71；mtime在8月不构成录制原件承诺。保留/var/log/inno_lidar.log同样六零，SHA32970556bb5fa8c73f51bb9c96e455941821f4acb35125036c5baece0ced3890，mtime 2026-10-02T09:33:51Z（录制窗口之后）。无同目录带日期config archive。该SDK日志没有录制进程/启动时间与bag的联合绑定，所以A05可软件PASS（如实列缺口），B02仍BLOCKED；不能靠文件mtime或当前零值推翻批准draft。

板端未启动任何topic、ROS采集、baseline、fall推理/验证、部署、服务重启或network/driver/config变更。只读取已存在的原bag/配置/日志；本次只读source recovery不改旧GL-I05“未执行设备阶段”的历史记录。
