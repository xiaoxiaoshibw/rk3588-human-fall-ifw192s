# 联网研究阅读记录与复现边界

日期：2026-10-11。算法/数据/适用性结论见 [报告第8节](REPORT.md)。本文件记录证据来源与检索边界，避免把搜索到的项目当成已经跑过的实验。

## 检索范围

实际检索包含 `static indoor 3D LiDAR person detection github`、stationary people background、sparse human multi-frame、PointNet/PointNet++、PointPillars overhead indoor、LiDAR human pose LiveHPS/LiDARCap、KF association等组合，并核 DOI/作者仓库。优先作者代码和论文；聚合网页仅用于发现，不用于支持结论。

| 研究ID | 作者一手入口 | 本轮实际读取 / 资产核验 | 尚未核验 |
|---|---|---|---|
| R01 | [hdl_people_tracking](https://github.com/koide3/hdl_people_tracking) | repo tree/HEAD、nodelet、background_subtractor、Kidono分类源码；无模型return true已直接读到 | 本域权重/数据/运行；没有新编译ROS |
| R02 | [2026预印本](https://arxiv.org/html/2603.04938v1)、[作者repo](https://github.com/nilushacj/O-LiPeDeT-Overhead-LiDAR-Person-Detection-and-Tracking) | HTML实验分割、IoU门、逐模型距离表、预训练失败、pseudoID；真实PP/VoxelNeXt配置、train.py CUDA/XYZI | 数据实际下载/训练重现、长期静止实验、IFW域与板端延迟 |
| R03 | [PubMed原文记录](https://pubmed.ncbi.nlm.nih.gov/37430633/)、[真实repo](https://github.com/baberjunaid/LiDAR_Tracking_3D) | 正确DOI、作者摘要、Track_3D.cpp/package.xml；运动ROI初始化边界 | 完整外部数据实验、无运动冷启动证明、源码许可明确性 |
| R04 | [出版商](https://www.tandfonline.com/doi/full/10.1080/01691864.2022.2126732) | Crossref题名；出版商搜索返回第2节角度变化/背景代价、120s初始化及坐人/遮挡FP实验正文 | 直接页面曾403，未下载PDF、未核作者源代码/原数据；不称可直接复现 |
| R05 | [OctoMap官方文档](https://octomap.github.io/octomap/doc/index.html) | occupied/free/unknown语义、insertRay/search/castRay入口 | 本项目射线可见性模型、坐标/传感器原点标定；无需声称已集成octree |
| R06 | [UMOSMOTS作者repo](https://github.com/thkreutz/umosmots) | README/tree、MOTS_Datasets时间序列转换；固定传感器运动分割任务核清 | 本域结果、静止语义检测能力（任务并不提供此保证）、明确源码许可 |
| R07 | [PointNet](https://github.com/charlesq34/pointnet)、[PointNet++](https://github.com/charlesq34/pointnet2) | 论文任务/密度问题；PointNet++MSG及pointnet_util选定源码 | 原模型在IFW数据训练、框架移植、board/NPU |
| R08 | [PointPillars原论文](https://openaccess.thecvf.com/content_CVPR_2019/html/Lang_PointPillars_Fast_Encoders_for_Object_Detection_From_Point_Clouds_CVPR_2019_paper.html)、[OpenPCDet](https://github.com/open-mmlab/OpenPCDet) | 原任务/表示以及R02实际固定室内配置 | 原框架安装与本域微调；外部AP不用于本项目验收 |
| R09 | [RandLA-Net原repo](https://github.com/QingyongHu/RandLA-Net) | 原论文/仓库与当前lab历史阅读边界；点语义任务与候选分类区分 | 本轮未重新下载训练源码/数据/许可全部文本；移植前仍需核 |
| R10 | [XGBoost原论文](https://arxiv.org/abs/1603.02754) | 原论文摘要+本仓库训练/export实际实现和当前证据 | 外部通用ML benchmark不解释本项目家具泛化 |
| R11 | [SimpleTrack](https://github.com/tusen-ai/SimpleTrack)、[AB3DMOT](https://github.com/xinshuoweng/AB3DMOT) | SimpleTrack association.py有Hungarian/greedy具体实现；任务边界 | 本项目box/IDGT与KF关联结果；尚未运行shadow |
| R12 | [LiveHPS原文](https://arxiv.org/html/2402.17171v1)、[作者repo](https://github.com/4DVLab/LiveHPS) | HTML、models.py/test.py；单LiDAR推理、FreeMotion多模态训练真值、default CUDA/SMPL入口 | 本域人体crop、关节真值、实测精度、SMPL资产/NPU |
| R13 | [LiDARCap原文](https://arxiv.org/abs/2203.14698)、[LIP作者repo](https://github.com/4DVLab/LIP) | 论文任务与LIP惯性融合要求 | LiDARCap对应作者源码链接未确认，UNKNOWN；LIP不满足无穿戴IMU路线 |

## 冻结作者源码

详细文件SHA和raw URLs在 [manifest](research/manifest.json)、[supplement](research/supplement_manifest.json)。仅下载阅读，不执行。commit用于复核此次读到的行为，不代表承诺长期维护兼容。

| repo | 此次HEAD | GitHub API许可字段 |
|---|---|---|
| koide3/hdl_people_tracking | 2d125167ca2b0935b8075032b943edf11d996788 | BSD-2-Clause |
| nilushacj/O-LiPeDeT-Overhead-LiDAR-Person-Detection-and-Tracking | 275989ede2fd5ac2a02813f55bdfc8462f3f1d82 | MIT；第三方框架/数据另核 |
| baberjunaid/LiDAR_Tracking_3D | 226630992d7958ba28b653f35cef5839c7d31a8b | null，UNKNOWN |
| 4DVLab/LiveHPS | 31a518b348a15477f2577dd0649d2f8296ab320b | MIT代码；SMPL/数据另核 |
| charlesq34/pointnet2 | 42926632a3c33461aebfbee2d829098b30a23aaa | Other / NOASSERTION；不以API归类替代LICENSE文本 |
| thkreutz/umosmots | 28d4b840cf0218f2a7f6c51895c666955c23d5d0 | null，UNKNOWN |
| tusen-ai/SimpleTrack | 05c96bb7ed98fc179856f327544612a66c839b5e | MIT |

## 排除与更正

- 一次Sensors DOI初猜 `10.3390/s23104781`返回变压器故障论文。保留原lookup，但**不作为人体论文引用**；正确 `10.3390/s23104720`已独立Crossref+PubMed核，见补充manifest。
- 不能把2D LaserScan神经检测器直接等价为IFW192S 3D检测；2D时间编码只能作方法参照。本报告未把2D预训练权重列入实施路线。
- 不能把synthetic fall数据仓库标成真实跌倒数据。未找到并验证的数据不进入本项目证据链。
- 不能把移动点分割、运动ROI或固定传感器任务名当成静止人体冷启动保证。
- 网页访问失败、未发现源码/未下载数据均保留限制，没有以猜测链接补齐。

实际工程借鉴优先级：三态可见性和候选/轨迹契约 → 本域实际候选学习 → RAW上下文/BEV检测 → 经ID/人体crop验证的4D/姿态。参照论文阈值、GPU性能和AP均不能直接导入本项目验收。
