# 深度学习与公开人体数据扩展（2026-10-22）

用户要求转入深度学习并寻找更大公开数据。本轮实际完成官方来源/可下载性核查、LaserAct核心包下载核验、MoMo点云样本解码及首版深度网络5折训练。没有部署、采集或设备操作；旧RF模型与历史证据保留。

## 数据选择与实际取得

所有“论文/官网规模”均与“本轮实际取得”分开。不同数据集的数字动作ID不共享语义，不能直接合并。相同动作的同步多传感器视图不增加独立人员数，点数/帧数也不等同于独立动作片段。

| 数据源 | 官方规模口径 | 对本项目的用途 | 当前可用性与限制 |
|---|---|---|---|
| [ACTIVE，ICCV2025](https://wangzy01.github.io/ACTIVE/index.html) | 80人、30类、46,868实例，真实LiDAR+RGB | 优先的大规模真实LiDAR动作预训练/微调 | 官方HF点云包7,263,397,797B；文件请求401，需用户账号申请并同意联系信息共享/科研条款。本轮没有代填资料、接受条款或发送邮件。官方GitHub的active.list已取得：46,868个唯一名称/80个人员ID/30个动作ID，帧条目911,387、每片1–317帧。不是全部片段已下载。 |
| [HmPEAR，ACMMM2024](https://openreview.net/pdf?id=hgRElsBV6v) | 25人、10场景、40类、约6,000动作片段、300k总帧，其中250k姿态标注 | 同时学习人体形状、动作和姿态 | 作者下载页当前超时，未取得数据，不能将论文规模写成已经入库。 |
| [LaserAct v1.1](https://raphaelmemmesheimer.github.io/laseract/) | 9人、49类、2,341段，4种LiDAR同步 | 多传感器迁移、背景与人体裁剪对照，含脚本化Falling/Lying | 核心包7,342,080B已下载，与作者SHA完全相符；实际CSV为2,341段/49类/9人，官方人员隔离train1,430段/5人、test911段/4人。Falling30、Stumbling50、Lying53。公开点云CC BY-NC4.0，RGB/IR另行受控；项目页称论文仍在审稿。 |
| [FreeMotion / LiveHPS，CVPR2024](https://4dvlab.github.io/project_page/LiveHPS.html) | 论文表格报告578k帧 | 人体点云/姿态表征预训练 | 官方代码目前链接的是Indoor子集，含点云和SMPL标注；不能声称已经拿到整个578k。动作类别标签与可下载子集实际规模未核实，不把姿态帧升级为动作/跌倒真值。 |
| [NTU RGB+D120](https://github.com/shahroudy/NTURGB-D) | 106人、120类、114,480片段，约8M帧（论文口径） | 大规模骨架/深度动作预训练，再向真实LiDAR迁移 | Kinect深度/骨架数据，非原生LiDAR。官方提供下载入口，骨架有535个缺失/不完整样本清单；后续须保留坏样本审计，不能把跨模态收益当IFW192S效果。 |
| [LiDARHuman26M / LiDARCap](https://github.com/jingyi-zhang/LiDARCap) | 13人、184,048帧、26,414,383点、20类日常动作（论文描述） | LiDAR人体姿态编码器预训练 | “26M”是点数，不是2,600万帧；动作分类标签可用性仍需实际盘点。官方模型/SMPL资源有各自条件，不把代码许可当数据许可。 |
| [MoMo / PePNet](https://github.com/Shark0-0/PePNet)，[作者数据仓](https://modelscope.cn/datasets/shark3/momo) | 专用点云包8,418,786,100B；完整人数/片段数尚未核实 | 候选真实点云动作数据，先核对标签/来源再扩大训练 | 已取得作者数据仓文件清单、大小与SHA，验证Range，取得专用包前8MiB及完整第一条点云序列。完整数据尚未下载，不报未经核实的样本总量。 |

ACTIVE是当前最明确的大规模真实LiDAR动作候选；官方代码2026-02说明曾修正错误切分，应使用当前57人训练/23人测试配置，并另从训练人员内划验证集，避免每轮以测试集选epoch。访问申请是该数据源的外部条件，不阻断其它公开数据核查和现有本地训练。

NTU120可扩展动作先验，但需要跨模态迁移；HmPEAR优先解决直接LiDAR HAR监督问题；FreeMotion/LiDARHuman26M适合姿态表征，不与动作标签直接拼接。LaserAct动作片段更多，但仅9人，不能把增加片段误写为人员多样性大幅提高。以上排序是本轮工程判断，不是已验证的模型收益。

## LaserAct核验与部分文件

- `data/downloads/deep_lidar_20261022/laseract_core.tar`：7,342,080B，作者SHA `89a5dd0a9ddd78911ada257999298efd23b1355734a28d9cf28d1bc7e5edd90c`。5275个tar成员清单、labels/splits/calibration/datasheet/license保留在新证据中，没有执行包内代码或向已有数据根解包。
- 官方人体裁剪是RGB Mask R-CNN和深度投影派生的机器标注；姿态也为模型预测/深度提升，不能作为独立人体关节真值。作者明确记载地面动作因相机视场存在缺失：11条完全没有人体云、22条Velodyne覆盖不足半数，多数为Lying，部分为Falling。后续不能为了分数丢掉这些困难样本。
- `laseract_person.tar`完整包4,602,081,280B传输慢，本轮停止并保留部分文件，见LASERACT_PARTIAL.json。它是预分配的未完成文件，完整作者SHA未通过，**不得作为完整数据包打开或参与训练**；没有删、移、改名或覆盖。后续如重下使用新路径，当前实现不宣称可验证续传。

## MoMo发现的混包问题与正确来源

作者数据仓可公开访问的文件元数据指出：

- `momo.zip`：3,127,376,920B，发布SHA `296a0e9f323696165bdb5fa7a0f95eda5c47392818c0cb4e8a48f2e4c11e6c78`。
- **专用点云** `momo_spike_pc.tar.gz`：8,418,786,100B，发布SHA `30e25881de513b8ffdebb4a0b5f60b1b949cf7ff1d9d0b28c3b17ca0fa4f4135`。
- 姿态包 `momo_HMR_spike_pose.tar.gz`：147,857,487B，发布SHA `a788f86e36a080fdde6bb2f234b359362fe09b40ace0de2353e69f904fb12261`，不需要它才能读取XYZ；HMR输出不当独立姿态GT。

Range读取momo.zip中央目录后发现2,223个成员混有`.history`、嵌套Git对象、HmPEAR的train_pc、NTU样例、姿态输出、视频和代码，不能按名称直接算作MoMo训练集。因此在发现后停止该混合包下载，保留部分文件、目录与REJECTED_WORKSPACE.json，未执行任何内含代码，也未把重复样例或其它数据集混入训练。后续全量盘点入口主动拒绝这个ZIP。

专用点云包前8MiB的HTTP响应精确匹配`bytes 0-8388607/8418786100`，前缀和完整首成员保留。首条为`data2/dengzc/momo_spike_pc/P029S001A006R014.pkl`，通过受限NumPy反序列化：20帧、50,214点、每帧1,852–3,487点、全部有限float64 XYZ。成员SHA `ab97e6d52cea743acbdfed6da9bdb8b8f29dcc6dc56b72ebfa237e87b64d3fbb`。首成员完整不等于整个gzip通过CRC或完整作者SHA；完整归档校验仍UNKNOWN。

没有将该A006映射成MM-Fi的A06，也未执行原作者的随机补点或测试集选型逻辑。首样本仅20帧，说明新数据适配要支持变长有效帧/掩码或明确的时间窗口；不能把不足30帧的序列大批排除后仍报全数据成绩。数据仓卡片是默认模板，完整类别名、坐标单位/轴、时间戳和数据级许可仍需核实。

## 已实现并运行的深度基线

`ML/src/train_deep_lidar.py`：PyTorch实现逐点共享MLP（3→16→32）+点维mean/max池化+4层64通道因果TCN（kernel3、dilation1/2/4/8）+27类分类头，共52,283参数。LayerNorm只在同一时刻的通道内操作，不用跨时间BatchNorm；卷积只左侧补零，窗口位置归一化仅参考第一可用帧。模型支持变长T，但本次MM-Fi训练仍使用30个连续帧。

为完成CPU训练/核对闭环，当前每帧固定64个由源路径SHA种子抽取的原始行，不使用关节GT或作者人体裁剪。点采样缓存包含E01全部270序列/80,190帧、7,290个30帧窗口。沿用原RF5折人员划分，每折8人/216序列/5,832窗口训练，2人/54序列/1,458窗口留出；同人全部窗口同折。

固定seed42、AdamW lr0.001、weight_decay0.01、batch32、梯度clip5、每折10epoch，使用最后固定epoch，不按留出分数选最佳轮。完整保存全部50个epoch、5份权重、人员/序列划分、逐窗口概率、混淆矩阵和序列聚合。

| E01人员5折 | 窗口accuracy | 窗口macro-F1 | 序列聚合accuracy | 序列聚合macro-F1 |
|---|---:|---:|---:|---:|
| 首版小型因果PointNet-TCN | 24.10% | 0.2190 | 31.85% | 0.2771 |
| 原RF30帧基线 | 63.28% | 0.6265 | 65.93% | 0.6518 |

本轮深度基线尚未优于RF：64点采样、全场景背景、固定10epoch和小网络共同改变，不能把差异全归为模型家族优劣。末轮各折训练在线准确率仍低，不能据此声称收敛，更不能只换深度模型就承诺解决数据不足。下一轮重点为增加可靠独立数据、人体点集对照、更多点数/训练预算和新独立环境。

本机实际环境：Python3.12、NumPy1.26.4、PyTorch2.14.1+cpu，torch.cuda.is_available=False，AMD集成显示适配器。无CUDA训练，本轮未安装包、下载权重、改驱动/网络、租用云算力或将PyTorch塞进板端。正式较大训练优先使用已有可用GPU资源；当前CPU入口可复现，不把硬件条件当数据查找前提。

E02本轮未读取/训练/再次预测；鉴于此前已经观察过其错误并用于后续研究判断，新路线应将其保留为开发参考，不再称为全新独立验证。E03/E04仍未参与本轮，后续须在新配置/权重冻结后才作独立测试。

## 测试、回放与复现

- 12项ML测试全部`-B -W error`通过：因果性在train/eval模式均逐值验证、点排列/平移、有限梯度/损失下降、重载、非法值、20帧变长输入、受限NumPy读取及拒绝可执行GLOBAL。
- 从原始E01 ZIP重新解码5条留出人员深蹲序列：1,485帧、135个窗口，源路径抽样重建、5份对应留出模型重放，类别一致、概率误差≤1e-6；不是IFW192S原始检测/跟踪整链或板端测试。
- 新模型`ML/models/deep_lidar_20261022_v1/`，证据`docs/evidence/2026-10-22_deep_lidar_sources/`；新源数据目录`data/downloads/deep_lidar_20261022/`。部分归档明确标为不可用，旧RF模型与数据未改。
- `discovery.log`、ACCESS/ADDITIONAL_ACCESS/SECONDARY保留超时/401/405；辅助CSV核对首次有未关闭文件ResourceWarning，改用read_text+StringIO重跑；一次终端打印emoji产生GBK编码异常，改为结构化JSON写文件，均不影响训练子进程。失败与不完整下载没有删除。

```powershell
# 在仓库根目录；所有输出和模型路径均需换成新的目录。
python -B -W error ML/src/train_deep_lidar.py prepare --input data/downloads/public_lidar_20261022/E01_lidar_gt.zip --output docs/evidence/deep_repeat/cache
python -B -W error ML/src/train_deep_lidar.py train --input docs/evidence/deep_repeat/cache/points64.npz --output docs/evidence/deep_repeat/mmfi_deep --models ML/models/deep_repeat --epochs 10 --folds 5
python -B -W error ML/src/replay_deep_public_lidar.py --evidence docs/evidence/deep_repeat --models ML/models/deep_repeat
python -B -W error -m unittest discover -s ML/src -p 'test*lidar.py' -v
```

完整MoMo点云归档在取得并核对上述作者SHA后，才可用`audit_momo.py --archive <专用tar.gz> --sha256 <作者SHA> --output <新目录>`盘点全量；当前只验证首样本，没有将尚未取得的全数据写入训练完成数。
