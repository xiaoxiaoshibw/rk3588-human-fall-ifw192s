# 跌倒检测参考文献

整理日期：2026-09-30。已纳入当前项目文档；用户要求论文正文与补充材料。下载文件均经过 PDF 签名、页数、首页题名与 SHA256 检查。

| 文献 | 本地文件 | 来源与状态 |
|---|---|---|
| Charles R. Qi 等，2017，PointNet++: Deep Hierarchical Feature Learning on Point Sets in a Metric Space | [正文与补充合并版](Qi_2017_PointNet++_正文与补充.pdf) | [arXiv](https://arxiv.org/abs/1706.02413)，14页，补充内容从第11页开始 |
| PointNet++ 独立补充材料 | [Supplementary Material](Qi_2017_PointNet++_独立补充材料.pdf) | [NeurIPS 官方论文页](https://proceedings.neurips.cc/paper_files/paper/2017/hash/d8bf84be3800d12f74d8b05e9b89836f-Abstract.html)，官方补充ZIP内的PDF，5页 |
| Sijie Yan 等，2018，Spatial Temporal Graph Convolutional Networks for Skeleton-Based Action Recognition | [ST-GCN 正文](Yan_2018_ST-GCN.pdf) | [arXiv](https://arxiv.org/abs/1801.07455)，10页；检查AAAI论文页、arXiv与作者仓库，未发现独立补充附件 |
| Jiaqi Lai, Mohammad Yavari, Peter Vee Sin Lee, David C. Ackland，2026，Three-Dimensional human motion analysis using LiDAR technology: A systematic review（Journal of Biomechanics 卷202，文章号113292） | [正文](Lai_2026_LiDAR人体运动分析综述.pdf) | DOI：10.1016/j.jbiomech.2026.113292；[官方入口](https://www.sciencedirect.com/science/article/pii/S0021929026001478)。hybrid OA（CC BY 4.0）；自动下载受阻，2026-10-02 由用户经浏览器手动取得正文（19页），补充材料未随正文获得、待查 |

文件哈希、相对路径与核验结果见 [文件清单](manifest.json)。源文件使用复制方式纳入，下载目录原文件保留。

## 实验方案原文与项目适用范围

[06_跌倒检测_实验方案与必读文献.md](06_跌倒检测_实验方案与必读文献.md) 为用户提供的参考原文，逐字节保留。文中依赖的01–05资料和两份综述PDF没有随本次材料提供，不代表已纳入或已全部核验。

可参考困难负例类别、按人员/场次/场景划分数据、时序观测与评测设计。当前项目仍按 [开发计划](../../docs/human_fall/README.md)、[冻结契约](../../docs/human_fall/CONTRACT.md) 与 [WebUI范围](../../docs/human_fall/WEBUI_SCOPE.md) 执行：RK3588、现有ROS1、人工选人与连续跟踪、几何时序跌倒基线、WebUI显示。

采用参考原文时注意：

- LIP 的四个IMU佩戴在人体上，不能用雷达内置IMU替代。内置IMU用于设备运动/重力线索，核验未通过时融合禁用。[LIP原论文](https://arxiv.org/abs/2205.15410)
- ST-GCN使用骨架关节点及图连接；PointNet++的全局特征不能直接作为已有骨架节点。[ST-GCN原论文](https://ojs.aaai.org/index.php/aaai/article/view/12328)
- 文中的硬件替换、ROS2安装、模型训练和外部通知是参考方案，不是本项目新增执行工单。
- 95%召回、500ms告警、30ms推理等数字没有在当前RK3588项目实测，不能当作验收成绩；计算耗时、事件确认时间与网页显示延迟分别测量。

HF-02 当前为软件REWORK/设备BLOCKED，具体修复见 [返工要求](../../docs/human_fall/HF-02_REWORK_PROMPT.md)。文献归档不改变工单验收状态。
