# B1 — 实时人体锁定 (stand/noperson) 演示计划

> 状态： **DRAFT**（已获用户原则同意走最短路径的第一步； 等计划评审后定开工）
> 承接： [CAPTURE_BATCH2_PLAN.md](CAPTURE_BATCH2_PLAN.md) 之后； HR-09 v1 模型 (`ML/models/rf_person_v1.joblib`) 已在仓
> 唯一验收表： 本文 §五 即 B1 验收表； 不变更 W03/W04 冻结边界， 不替代 HR-SEM-SHADOW, 不进生产管线。

## 一、目标一句话

在浏览器里开一个实时页， 点云来源是板上真实的雷达， 页面里每帧把**人**用红框/颜色单独锁出来，
持续跟踪（track_id 身份稳定）, 轨迹尾迹可视化——**只解决「人在哪/动没动」, 不做姿态也不做跌倒**。

## 二、为什么在浏览器里做 (而不是板端 ROS 节点)

| 维度 | 浏览器里做 | 板端 ROS 节点里做 (HF-11 的路线) |
|---|---|---|
| 实时数据接入 | 已有： `webui/human_fall/index.html` 直连板端 **foxglove-bridge WebSocket v1**, 已解码 `sensor_msgs/PointCloud2` (XYZI, 小端） | 需要新写 C++/Python 订阅器和发布器 |
| 计算在哪 | 浏览器 JS 里 (Three.js + TypedArray) | RK3588 上跑 HF-11 状态机 |
| 延迟 | 端侧走 WS， 帧延迟 ~100-300ms, HF-11 实测呈现层滞后 1 帧——**这个量级对「锁定演示」足够** | 板端更近， 但你要在现场看演示效果时反正也是开浏览器 |
| 计算负载 | 浏览器本机 (PC/手机） 跑 JS, 不占 RK3588 CPU | 占板端 CPU, 需要考虑与 HF-11 的资源争抢 |
| 改动面 | 新加一个 web 页 (`webui/human_detect/`) + 一个轻量 JS 侧机器学习推理器， 不插手 HF/生产 | 必须进 `src/human_fall_detection/`, 走 release + rollback, 风险面大 |

**结论**: B1「实时锁定」在浏览器里跑， 板端只照旧推流； 后续 v2 动作化、 v3 跌倒接入， 才往板端 ROS 迁。

## 三、架构与数据流 (复用已通的路)

```
板端 inno_lidar_ros → /innolidar_points (sensor_msgs/PointCloud2, XYZI)
   │
   ▼ foxglove-bridge (已有, ws://<board-ip>:9090, inno_webui 页验证过)
PC/手机浏览器 webui/human_detect/index.html
   │
   ├─ JS 解码 PointCloud2 (复用 human_fall.html 已实现的解析层)
   ├─ 帧预处理: 用空场模板 leveled R/T 把每帧归一到 z=0 (R/T 已注册, 把矩阵硬编码进 JS, 零运行时求逆)
   ├─ 背景差分: 静态背景 5cm 网格 95 分位包络 (从 rf_person_v1.joblib + ai_labels.json 一次性
   │              导出成一份 JS 常量数组, 直接嵌入页面, 不用 joblib)
   ├─ 候选簇: 桌状 DBSCAN 粗聚类 (eps 0.3m, min 30 点), 每簇求质心 + 占据高度带
   ├─ 人/非人判定: 簇 51 维特征 → 每簇喂 rf_person_v1 (导出为纯数值 joblib2json 快照 < 1MB JSON,
   │              JS 里 100 棵树线性投票, 无外依赖)
   ├─ 时序跟踪: 每帧「人簇」与上一帧 track 最近邻关联 (欧氏距离 + 卡尔曼位置预测)
   │            未命中 > 1s → track 销毁； 出框又回来的按新 track
   └─ 渲染: Three.js 顶视图+主视图, 「人簇」用红框 + track_id + 尾迹
```

**关键决策**:
- 不板端化 (B1 阶段), board 只照旧跑 inno_lidar_ros
- 不动现有 HR-W03/HF-11/管线任何文件； 网页是纯诊断/演示, 无控制命令
- v1 RF 导出成 JSON 后, 浏览器零依赖——一个 <script src="rf.json"> 就 loaded

## 四、要做的工件

| 类别 | 工件 | 所在 |
|---|---|---|
| 配置/模型 | `rf_person_v1.json.gz` (或 .json) | `webui/human_detect/` 内嵌/静态文件 |
| 前端页 | `webui/human_detect/{index.html,detect.js,detect_lib.js,detect_lib.test.js}` | 新目录, 结构对齐 `human_capture/` |
| 数据源 | 不变， 照旧走 foxglove-bridge:9090 | 现有 |
| 文档 | 本计划 + 返回 `returns/human_detect_b1.md` | docs |
| 测试 | lib 层 node 测试 ≥ 20 例； 模型导出与 Python 端对齐校验 1 例 | `webui/human_detect/` |
| 工程 | `open_webui.bat` 增加一个快捷方式 (可选) | `webui/` |

## 五、B1 验收 (唯一验收表)

| ID | 条目 | 通过标准 |
|---|---|---|
| B1-R1 | 实时性 | 呈现帧率 ≥ 5 Hz (板端 10Hz 推流， 允许丢一半); 帧龄 < 1s |
| B1-R2 | 锁定准确率 | 浴室空场 5 分钟不进人： 页面 0 个锁定框； 站人静止 30s: 全程有框且 track_id 不变 |
| B1-R3 | 多目标 | 两个静止人相距 ≥ 1.5m: 有两个独立 track_id, 且帧间不交换 |
| B1-R4 | 走动跟踪 | 人横向走过去 (~3m 距离）: track_id 单程保持 （允许 1s 内的临时断档， 自动恢复要同 id; 超过就当新 track) |
| B1-R5 | 视觉合理性 | 人不在框内 ↔ 物理吻合 (人蹲下/出框时框消失， 不持久挽留） |
| B1-R6 | 安全 | 页面 0 写操作： 不发任何命令话题， bathroom 检测不向前推理， 跌倒状态机不启动 |
| B1-R7 | 自测通过 | node lib 测试 ≥ 20 例 PASS; 模型导出 SHA vs Python 端对齐 (至少抽 3 个特征向量两边一致) |

任何一条不过 → 不 B2, 不关单， 只把现状挂上； 跟 B1 范事急， 数据不不足以支撑后续动作时值再调。

## 六、非目标 (本单不做)

- ❌ 姿态分类 (walk/sit/squat/lying/fall) — 那是 B2
- ❌ 跌倒状态机 — 绝不在 B1 启动
- ❌ 板端部署/打包/容器化 — B1 是纯网页 + 静态文件
- ❌ 多人跟踪密集优化 (交叉、遮挡) — 有就是 bonus, 不卡验收
- ❌ 模型再训练 — 用 HR-09 v1 现成 joblib, 不动

## 七、风险与边界 (显式)

| 风险 | 量级 | 对策 |
|---|---|---|
| 浏览器算力不够 (JS RF 100 棵树 + 每帧 50k 点） | 中 | 帧抽稀 (10Hz → 每 2 帧处理 1 次)、每帧点数抽稀到 ~20k 处理 (保留密度足够） |
| 跨房间泛化差 （第一批数据在 10m 房间录的， 浴室只有 2-3m) | **高** | 人侧： 体侧特征主要靠形状不主要靠绝对位置， 风险中； noperson 侧： 浴室必须重新采一个空场模板配平 (不补不行）, 页面上增加一个「空场模板重新打点」的入口或者换浴室模板 |
| 坐标对齐 | 低 | 直接用 leveled R/T 硬编码常量， 每帧只做矩阵乘 |
| rad person v1 是 ROI 输入， 不能整帧 | 低 | 锁定链路本来就是「先簇再做特征」, RF 只喂簇内点， 一致 |

## 八、计划工时 (估计， 供参考)

- R1 (条件和数据通路复查 + 设计文档）: 0.5 天
- R2 (web 页框架 + 点云解码 + 跟踪器 lib): 1.5 天
- R3 (RF json 导出工具 + JS 推断器 + 测试）: 1 天
- R4 (背景差分 + leveled 变换 + 联调）: 1 天
- R5 (验收 B1-R1..R7 + 返回记录）: 0.5 天

**合计约 4.5 天** 纯我侧工作量。如果你的联调环境受限， R1 后可以随时改派方向。

## 九、依赖 (& 卡点)

- 板端已有 foxglove-bridge :9090 且在跑 （实测在 `human_fall/index.html` 用过） — **不需要板端任何新改**
- PC/浏览器能连通板子 (不要求互联网）
- HR-09 v1 RF 模型已存档： `ML/models/rf_person_v1.joblib` (188k) → 导 JSON
- 浴室空场模板 (第二批补采） 上传后， 替换页面里的背景包络即可， 不咬牙再训一个新模型

—— 计划到此， 等你评审， 你通过后我写开工单 （不动生产、不触碰 freeze/human_fall)。
