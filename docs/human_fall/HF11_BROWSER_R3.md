# 真实浏览器第3轮修复（链路已通，关闭三个实际缺陷）

继续session ses_f0c1d2e43ffeMDoXiXAHqpVYqQ。Codex已在真实浏览器预览连接、解除、点候选选人、采基线，ROS回执链路实际通过；合成明确标识。当前活动页/驱动未替换，不重盘点/不放松校验。

1. URL points=/hf07_verify/points时，仍订阅/innolidar_points以及synthetic points，两条输入混到同一个原renderer/pcPrevSeq/FPS/drops。DOM实测渲染80点却11.2MB/s和丢帧数4,929,859,347，反复Send buffer limit reached。诊断选择points参数时替换默认点云订阅（保留原IMU/device），只显示/计数/缓存选定点云来源；源帧缓存必须带pointstopic而非仅header同frame_id。不要增大无界buffer掩盖；实际预览应无两来源互相污染。
2. 解除已收到release接受、track_id=null/unselected，但state仍输出上一目标position_source_m=3,..、range=3.07，UI仍标实测。清理/隐藏无锁定目标的当前pos/range/bbox/预测表述，当前状态不要用_last_candidate替代新目标；历史事件保留，不伪装实时位置。补pure runtime release后再输入有效cloud的断言，字段应null，UI“--/未选目标”。
3. 现实际verify配置只ground_path（validated standalone ground），calibration_version一直None。浏览器capture完成ready后长时间fall_status仍unknown，是新严格baseline绑定缺标定版本（不是应该放松守卫）。为独立ground配置建立稳定的“数值参数版本”：从验证后的ground内容/源文件hash得非空版本，可用build_geometry_calibration生成candidate记录、reference=null、所有physical verification=false；明确只是参数标识，不代表外参/地面物理已验收。对直接FallNodeCore地面-only构造也定义同等版本或明确要求提供calibration（生产/测试接口一致）。补standalone ground→capture ready→连续standing upright的正例，不向基线补假物理证明。

Source/default/offline流程也保持正常，原175回归及18/5独立边界不破坏，新语义同步；真实confirmed仍false。修完更新隔离node/合成demo/preview并明确保留供Codex继续浏览器复核，不杀原服务。脚本只操作自己确切test节点，不用泛pkill误杀活动未来node。记录回传第3轮、源码/环境/原驱动与首页hash、真实URL及检查。

另：用户已授权正常可回退部署，独立通过后Codex将直接推广生产新节点/页面，不再搬运；现在仍只preview。不要用静态grep代替测试或声称未知schema路径通过，保留前2轮实际失败。
