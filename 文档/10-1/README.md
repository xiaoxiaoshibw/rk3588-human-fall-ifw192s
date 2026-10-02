# 10-1 跌倒检测算法参考资料库

收集目的：为 `src/human_fall_detection/` 后续算法调整提供外部论文、开源实现和方法对照。
检索日期：2026-10-01。来源：arXiv API、GitHub API/搜索页人工核验；Semantic Scholar 当日限流(429)未覆盖。

与既有资料的关系：`文档/跌倒检测文献/`（PointNet++、ST-GCN，HF 早期收集）保持不动；本目录聚焦 **几何/时空方法、人体检测跟踪、跌倒判定**，更贴近当前 core/ 模块结构。

## 目录结构

```text
10-1/
├── README.md                  ← 本文件（索引 + 检索方法）
├── papers/                    ← 已下载 PDF（7 篇，全部核验通过）
├── github/                    ← 精选参考实现源码（zip 快照）
│   ├── hdl_people_tracking/     koide3，3D LiDAR 行人检测+跟踪（ROS+Eigen/PCL）
│   └── Lidar-Based-Fall-Detection/  Livox Mid-360 跌倒管线（数据+JK tuning+DGCNN-GRU）
├── notes/
│   ├── 方法对照.md             ← 按 core/ 模块逐一对照：我们 vs 文献 vs 可调算法
│   ├── 论文笔记.md             ← 每篇论文的要点摘录与"对项目可用性"判定
│   └── 数据集与评测.md         ← MM-Fi / MiliPoint / 融合跌倒数据集 + 评测指标口径
└── manifest.json              ← 全部条目元数据（标题/年份/来源/链接/本地路径）
```

## 快速结论（给后续调参看）

1. **conference/journal 级别直接做"3D LiDAR 跌倒检测"的已发表工作极少**；最接近的是毫米波点云（mmFall 系列）和深度相机。几何判定逻辑（质心下降速度 + 低姿态持续 + 主轴翻倒）跨传感器通用。
2. **人体检测/跟踪可借鉴成熟实现**：hdl_people_tracking（Haselich 分块聚类 + Kidono 29 特征 SVM + Munkres GNN + 恒速 KF），与我们的 `association.py`/`tracking.py` 同构，特征集可直接扩充进 `features.py`。
3. **DBSCAN 调参有现成实机数据**：Livox 项目网格搜索出 eps=0.2m / min_samples=10 表现最优，与我们 `perception.yaml` 的量级一致，可作为基准。
4. **毫米波 IMM 论文（2311.08755）验证了我们的状态机思路**（"先下降过程、后低姿态持续"），并给出环境无关参数化的方法学。
5. **节奏建议**：首版不引入学习模型（无标注、RK3588 无 NPU 推理管线、规则可解释）。先复用 Kidono 特征 + 已有规则；若后续要升级，候选次序：Kidono/Haselich 特征+SVM → 拉普拉斯谱 HAR → DGCNN-GRU（需数据集）。
