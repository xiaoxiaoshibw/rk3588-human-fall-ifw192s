# HF09真实浏览器第3轮

R2回滚/metadata/投影与207回归已提交，保留。根端独立project_snapshot_for_ros已PASS且从投影select仍可合法锁定。实际刷新IAB：初始9.2Hz/呈现9Hz/丢帧0，随后真实页面每3–4s仍Send buffer limit reached（10:50–10:52连续），候选/状态在degraded和fresh表之间可用，但原始50k点云仍带宽瓶颈。无需重测原30分钟。

1. 实施已授权备选：新增只读visualization点云话题，算法订阅/解码/候选/跟踪仍用全量/innolidar_points。只对显示包抽样（例如stride4/最大约12k点），字段与XYZ单位/端序/坐标不改，正确处理row_step/organized padding。缺帧/非法布局不伪造显示云；测试原消息/源header不被修改、抽样字节/组织行padding、低姿态仍完整参与原算法。
2. **ROS1 Header.seq发布会自动赋本topic序号**，不能简单复制原seq后宣称保持。使用真实wire header与完整源header的明确映射：保留source原seq/sec/nsec；发布抽样包后读取实际wire header并随candidate/state提供可选visualization topic+header+原/显示点数/stride。前端只在选中display topic与声明一致、完整header匹配且session/epoch/TTL通过时配框；`?points=/innolidar_points`诊断仍能用原source键。必须用实际ROS订阅探针对照wire header与映射，不伪改source seq/时间掩盖问题。或用能证明保持的标准方式，但不要依赖未经测试的假设。
3. 正式默认用轻量显示流；原页/原点云话题/driver不动。raw接收统计改准确名称“显示流”，算法input/处理率继续独立，不把显示Hz冒称原输入Hz。明确显示抽样数/原数，录制按钮/说明需注明当前显示流录制不等于原始全量bag。
4. UI呈现的rxMs应为frame.rxMs（原包在浏览器接收时刻），不能每次渲染重置为now掩盖年龄；可单独presentedAtMs计呈现间隔。显示“帧龄（接收后）”，不称端到端时延。hfFresh/pruneRawFrames拒绝负age，使用浏览器monotonic clock更合适；断流/断连/未知schema/旧epoch守卫保留。
5. 当前bundle manifest把manifest.sha256自身也放进find计算，内容不稳定。排除自身及pycache，start/profile校验清单再导入。新版本保留所有旧release；原冻结依赖哈希不变。再跑同树本地/板回归和实际版本回滚，无需无关C++重建。
6. profile lifecycle也记录精确脚本路径/输出路径的cmd元数据，拒绝误停且不启动重复写同文件的observer；旧已完成zombie只清本任务PID文件。Node已正确版本校验保持。

只处理这轮软件与可回退部署，新增topic必须仅可视化/只读，无控车/告警/自启；不改算法阈值/真实标签/地面参数。ROS/JS元数据映射、TTL、编码以及同原输入算法结果要有有效测试与真实stdout/SHA证据。完成第3轮SUBMITTED退出，Codex再实际浏览器长于1分钟复测带宽/框/断开，保存交付截图。实现方案取最小标准库/NumPy，别扩成框架。
