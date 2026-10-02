# 自主开发第3阶段：HF-07 ROS1集成 → HF-11现有WebUI

用户已授权持续开发及普通可回退联调。先读AUTONOMOUS_RUN.md、AGENTS.md、DISPATCH.md、CONTRACT.md、GEOMETRY_CONTRACT.md、INTERACTION_CONTRACT.md最新冻结范围、WEBUI_SCOPE.md、HF07/HF11原工单、当前模块和回传，使用ponytail。HF04–06软件已由Codex独立两端158回归/18边界复审；Codex最后将prediction_age_s改为自最后实测计，并独立两端复跑，消费当前源码不回退旧版本。

按07→11串行完成实际软件和Linux/浏览器可验证的链路，不依赖未知IMU物理值。保持HF01冻结脚本/default.yaml/CONTRACT和HF03几何语义/测试、C++不改。算法只在RK3588，网页仅交互/显示，无cmd_vel或电机/外部通知。不引入ROSBridge/MQTT/新网站/模型库；优先现有Foxglove clientPublish，只有实际不可用才增加最小必要请求通道。

## HF-07节点、安装、数据失效

实现scripts/human_fall_node.py及最小可复用纯处理器/状态builder，独立node配置/launch、core安装规则、COLCON_IGNORE等ROS1发现边界。源码/安装从不同cwd运行实测，不靠临时sys.path才能正常import，不运行会改写原manifest的顶层build脚本。仅Linux隔离catkin验证，不重建/部署活动驱动。

点云回调记真实接收时钟并放有界最新队列，处理不阻塞所有回调；用单写计算worker，请求/epoch/状态提交保持完整锁保护。网络丢流/非法stamp/layout/缺地面/时钟复位/设备运动或背景异常有明确invalid/unknown，辅助IMU未知不阻断独立几何记录。默认无有效地面/基线应进入等待而非假正常；原点云仍可显示，低卧候选不能因旧尺寸门限消失。纯模块新增严格基线绑定字段在每次观测/采样都填齐真实当前上下文。

生产默认不自动选人，绝不用回放fixture_auto初选逻辑代替请求。所有请求有schema/session/epoch/版本/当前质量/源快照/目标绑定；源时钟仅时序、在线TTL使用monotonic；replay独立message时间域并标记暂停/重开，不关闭质量检查。特别检查：旧快照中人已消失而最新快照为空时拒绝选择，即使旧快照还在TTL内；可唯一连续匹配旧候选到当前候选时才接受，不能仅凭缓存位置锁已消失人。切标定/目标/epoch不得继承基线/动作证据。

按INTERACTION契约发布候选、合并target_state、event、selection_ack；严格JSON禁止NaN/Inf、源frame/seq/sec/nsec/snapshot/epoch可回溯，位置/框标source/reference，网页源框用source bbox。距离基于雷达源坐标/可见簇，不能用平移后世界坐标范数冒称雷达距离。相同事件只发一次、事件JSONL本地持久记录、重启不静默重播为新事件；磁盘失败明确降级，不假装事件保存成功。有限recent_events让重连取历史，不重发所有旧事件当新事件。

必须运行原158回归/18独立边界及新增节点/请求/重启/写失败/队列/暂停测试。板上用新隔离工作区和验证话题（如/human_fall_verify/*），可启动新测试节点/生成明确synthetic PointCloud2做协议链路测试，标明synthetic而非真实人体；验证后清理自己创建的进程。默认真实mode_verified/allow_confirmed=false，测试完整状态机仅明确fixture配置/话题；不得为演示开启真实confirmed。

## HF-11真实页面源码与预览

重新读取板上/root/catkin_ws/webui实际文件，记录哈希/备份，再纳入本地webui/；保留用户最近页面修改、Three.js/OrbitControls许可与点云/IMU/设备状态原功能，不从旧证据snapshot覆盖。实查运行bridge serverInfo能力、advertise/publish接受与ROS请求/回执，无参数capabilities不代表不支持。

实现候选/选择拖框/重叠候选确认/解除/采集站姿基线、自动框与点云中心XYZ/距离/坐标、地面与基线有效性、跌倒状态/历史事件。选择发板端ID和当时源帧、等待正确request_id/session/epoch/selection_version回执再锁定显示；重连不重放旧选择，旧回执不能回滚新状态。普通模式保留视角旋转，选人拖框时正确隔离OrbitControls；按canvas client rect处理视角/缩放/DPR。

同屏原点云与框必须按seq+raw秒字段/源快照对齐，用有界帧缓存；不要把旧框叠到新场景当新测量。epoch/session切换清缓存，超过TTL灰显/隐藏；断流/未知schema/非有限位置/后端错误显示unknown，不默认绿色/upright。预测明确标记并使用正确最后实测年龄。位置label是可见点云中心，不是解剖质心/人体身高；真实未标定坐标标雷达innolidar，不贴世界坐标。confirmed红/疑似黄/unknown灰并有文字，事件历史不因降质/恢复消失。

HTTP私网部署的浏览器不能假设crypto.randomUUID可用，生成唯一request_id用可用原生API/兼容fallback。读取真实Three.js版本，点云与三维框/投影共用同一source→scene映射，保留原渲染坐标约定。页面不放业务实现细节、无多余弹窗。

先将新页面放新预览子目录（原8090服务可服务/root/catkin_ws/webui/human_fall_preview/...），不要覆盖活动index.html；测试节点/预览页面可对接验证命名空间或live输入，记录访问URL和话题。算法安装/正式页面替换在Codex复审后进行；用户已授权可回退部署，不再需要人工搬运，但本轮结束先给Codex可验证的预览。

## 交付

分别追加returns/HF-07.md与HF-11.md，证据evidence/2026-10-01_autonomous_hf07_11_r1/。列实际diff/源码与环境哈希/包构建安装/启动停止/话题与请求回执/测试/预览URL/未验证项，写SUBMITTED后退出。先在部署文档写准确部署/回滚/配置/ground/基线步骤和默认门控；不自行ACCEPTED，不假装真人人体/真实跌倒验收通过。保留所有失败尝试，普通问题自行修复；不改网络/系统/厂商库/雷达自启，不覆盖原bag，不保存凭据，不commit/push。
