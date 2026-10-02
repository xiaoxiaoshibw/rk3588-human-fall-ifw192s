# 自主开发第2阶段：HF-04 → HF-05 → HF-06

此工单由Codex在HF-03软件复审后派发；当前预备文档不代表任务已启动。用户已授权持续自主开发，参见AUTONOMOUS_RUN.md。读取各原工单、当前core/calibration.py/ground.py及各回传、CONTRACT.md、WEBUI_SCOPE.md、DISPATCH.md与ponytail。纯点云几何路线独立推进，IMU设备语义和真实地面/安装验收仍单列未知，不伪造设备通过。

派发前提已完成：HF-03第2轮软件由Codex独立两端92项回归/6项边界复核PASS；消费已审 [GEOMETRY_CONTRACT.md](GEOMETRY_CONTRACT.md)。本轮用户授权已覆盖HF04–06，不因旧工单WAIT_DEPENDENCY或HF-02设备未知停下软件实现。

按04→05→06顺序实现兼容的纯模块和最小回放入口，不先开发UI/ROS节点；结束整个阶段后让Codex直接读取源码与回传复审。保留HF-01冻结工具/配置/契约、HF-02及已审HF-03资产；新增算法参数独立存放，不改冻结default.yaml。无新第三方框架、只有既有NumPy/标准库；Python3.8与NumPy1.17兼容。

运行工具注意：Codex为CLI单次运行设置shell为PowerShell7，用户全局配置未动。本机一次成功BatchMode SSH实测约26秒，不能用25秒工具超时推断连接不可用；SSH/板测工具给至少120秒，有界较长测试按实际需要设置。优先Python subprocess参数数组/stdin传脚本避免Windows→SSH→bash多层引号，远端/root/catkin_ws位于slam-localization容器内。

## HF-04候选

实现core/lidar_candidates.py，复用既有PointCloud2解码；使用已审几何API，明确输入/输出frame和单位。有界ROI/体素/连通簇提取、稳健中心和三维bbox、地面高度分位数、点数/范围、PCA主轴及退化标志、原始证据点索引。保留站立/蹲坐/低卧姿态，不能复用旧站立尺寸门限排除倒地。背景只由显式空场采集生成/冻结，绝不在线把静止目标学习进去；近地面/家具合并与不足点数明确质量/限制。

倾斜安装时高度按单位法向n.p+d计算，水平聚类/范围用地面切平面基底，不把原始雷达XY/Z默认当水平/重力轴。仍保留原始雷达系中心/bbox供原WebUI显示；地面覆盖检查使用点的地面投影，不用地面点的窄z范围拒绝站立人体。参考地面基底来源注明，不把它冒称实测世界外参。

候选快照包含schema/session/epoch/snapshot_id、raw seq/sec/nsec、frame/坐标定义、标定版本、有效质量和candidate_id；ID只在快照内有效，不冒称human识别或track。保留源坐标bbox供后续原WebUI叠加，参考坐标另有明确变换。缺地面时可输出未标定的雷达坐标候选，地面高度/跌倒观测不可用，不能假设地面z=0。

## HF-05锁定与请求

实现core/association.py、tracking.py及必要最小选择/基线纯接口。一人锁定使用有界匀速预测/距离门限，姿态尺寸突变不能直接换人；双候选近似、簇合并/拆分、交叉和丢失均明确ambiguous/occluded/lost，lost/ambiguous后不自动选择任何人。预测明确标记、不能增加跌倒证据。

请求只允许select/release/capture_baseline，绑定request_id、session/epoch/snapshot/candidate_id及selection_version；有限缓存/当前质量/单调TTL校验，旧快照、跨epoch、冲突或旧选择版本拒绝。重复相同ID和相同内容返回原回执，不重复执行；同ID不同内容拒绝。页面未来以板端回执为准。操作/epoch/丢失重置目标动作历史，已存事件不删除。

站姿基线从连续稳定有效实测观测采集，按秒和点数/位置/高度质量配置判断pending/ready/failed；拒绝初始卧姿、遮挡、预测和跨标定版本，失败不存假基线。基线包含独立版本/标定绑定、来源与阈值单位，不猜现场真实身高。必要时可显式人工站姿确认，但不能据此伪造真实标签。

## HF-06状态机

实现core/features.py、fall_state.py：状态按原工单七状态，所有持续时间基于单路合法源时序；confirmed必须有效站姿基线、同目标实测下降历史及持续低姿态证据。初始化已躺只能low_posture_unclassified，未选/质量失效/时钟重置/切目标清动作历史unknown。降质不撤销已有事件，恢复后才开始独立新事件，event_id去重。

模式验收门控必须明确：当前真实几何模式未经过人工标签验收，线上默认不允许confirmed，可提供suspected/观测/unknown。合成测试可显式启用已验收夹具以检查完整状态机，但不能把它当真机验收；不要实现一个默认永远confirmed的假演示。主动躺下与跌倒可能无法几何区分，如实标限制。

## 验证与交付

各模块留可失败的回归：贴地低卧、PCA退化、多目标/家具合并、跨epoch/陈旧选择、重复/冲突ID、预测不增加动作历史、不换人、站姿基线失败、初始低姿态、下降/低姿态/去重/恢复、切目标/丢流。固定种子回放两次一致，严格JSON无NaN/Inf。运行全部原测试，不删/降断言；本地和板上隔离环境完成纯函数检查。

提出docs/human_fall/INTERACTION_CONTRACT.md精确新增候选/请求/回执/state/event v1草案，含字段/枚举/时间域/幂等/版本/边界和样例；HF-01health/manifest保持冻结。Codex本阶段复审后再冻结新增实现契约，用于HF-07集成。

分别追加returns/HF-04.md、HF-05.md、HF-06.md，证据evidence/2026-10-01_autonomous_hf04_06_r1/，列每单完成/未完成、实际diff/测试/哈希、设备证据与合成分界。写SUBMITTED，不自行ACCEPTED，不要求用户转交。不部署、不重启雷达、不改网络/系统/厂商库、不覆盖旧bag、不保存凭据、不commit/push。用户常规授权内故障自行处理，完成后退出让Codex复审。
