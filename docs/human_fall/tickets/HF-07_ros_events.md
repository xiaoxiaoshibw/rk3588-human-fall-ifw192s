# HF-07 ROS1 节点、事件与启动集成
执行：OpenCode DeepSeek v4.1 Flash。依赖：HF-01～06。状态：WAIT_DEPENDENCY。

先读 ../DISPATCH.md 并读取 ponytail SKILL.md。保留旧人体跟随接口，不接运动控制。

## 工作与代码
- scripts/human_fall_node.py：ROS 只负责消息接收/配置/结果发布；调用纯计算模块，输入缓存有界，点云计算不要阻塞所有传感器回调。处理异常后仍输出明确 invalid/unknown，不吞错误。
- 发布 /human_fall/state 与 /human_fall/event 的冻结 JSON；publish allow_nan=False。无效距离/姿态输出 null，质量原因有 reason_codes。
- 按 [WEBUI_SCOPE.md](../WEBUI_SCOPE.md) 和后续冻结 schema 发布候选/三维包围盒、实际位置与标定版本、源帧关联信息、选择/基线回执；将 RK3588 算法结果提供给现有 Foxglove/WebUI。确认 bridge 可见对应话题和类型；新写入通道只接受选择/标定操作，不改变 health/manifest 冻结版本或车辆控制边界。
- 检查 UI 断开时算法独立运行，页面重连取得当前板端锁定/基线/跌倒状态；旧请求、跨 session/epoch 的框与迟到回执不改变当前目标。精确 state/event 与新增选择接口须在本单集成前审查，不能把草案当已经冻结。
- 事件 JSONL 本地记录，状态健康按配置频率发布；证据关联既有 session bag/点云索引，不新建视频录制框架。事件不能因节点异常重启被静默重播成新事件，定义 session/event 去重策略。
- launch/human_fall.launch 与 config/default.yaml：点云/IMU/设备状态话题、标定路径、超时/阈值、算法模式和输出目录均可配；没有模型文件要求。必需点云/地面标定缺失启动失败或明确等待，辅助 IMU 失效按模式报告，不返回正常“无人”。
- 完成最小 package 安装/import；catkin_install_python 与纯模块安装正确，从不同 cwd 启动不依赖 scripts 临时 sys.path。文档写真实设备/容器启动命令与回放步骤。

## 验收
ROS1 真机或 Linux 回放启动，检测缺点云/地面标定、非法 PointCloud2、计算异常、磁盘写失败、辅助 IMU 失效、超时、节点重启；有限队列/事件去重/关闭行为合理。旧 unittest 继续通过，/human_follow/state 内容不变，无 /cmd_vel 等控制发布。回放用有效消息时间，watchdog 区分回放暂停与实机丢流；必要时使用 replay 标志，不关掉所有失效检查。

输出样例须能与原点云源帧及 track_id 对应；模拟网页选择/标定请求、回执丢失/重发与重连，确认算法只在 RK3588 运行。真实浏览器界面由 HF-11 联调，不能只以 ROS 话题存在宣称网页最终交付完成。

## 回传
启动命令、包构建/安装验证、topic 样例、健康/事件日志、returns/HF-07.md。
