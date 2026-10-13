# RESEARCH_SURVEY — 算法路线调研（HFUS-RD-01 交付 1）

调研日期 2026-10-12 · 调研对象：PCL 欧氏聚类 / DBSCAN / RF+XGBoost / PointNet /
PointNet++ / PointNeXt / RandLA-Net / Open3D-ML / 近年轻量点云分割。
三路并行检索 + 直接抓取官方文档与 GitHub 仓库页面，结论均带来源 URL。
本轮 WebSearch 持续 400 不可用，主题 H 的非一手文献覆盖受限，已在对应
位置明确标注"待验证"。

## 判定一览

| 方案 | 判定 | 一句话理由 |
|---|---|---|
| RF (sklearn) + 扩维特征 | **推荐**（主攻线） | sklearn 原生、秒级训练、Win CPU / RK3588 均可行；**必须 sigmoid 校准**（样本<1000） |
| XGBoost | **推荐**（平行基线） | Apache-2.0，Win/ARM64 wheel 齐；`scale_pos_weight` 只为 AUC 排序，若要校准概率须换 `max_delta_step` |
| PCL 欧氏聚类思想（KD-tree + 半径生长） | **推荐（作语义参考）** | 与非重复扫描密度不匹配的本质 = 固定 r；给出距离自适应扩展方向 |
| DBSCAN | **部分推荐（诊断层）** | 单一 eps 在非均匀密度下要么碎要么并；按距离分层 r 后可用 |
| PointNet vanilla (0.8M) | **待验证**（深度基线） | CPU 可训可推（PyTorch 2.12+cpu 本地验证）；用于判断深度学习是否值投 |
| PointNet++ (SSG/MSG) | **不推荐（当前簇密度下）** | FPS/ball-query 自定义算子 + 官方绑死 TF1.x+CUDA；百点级簇分组信息有限 |
| PointNeXt | **不推荐（近期）** | 官方明文要求 CUDA ops；PyTorch≥2.7+CUDA12.8+openpoints 依赖链过重；单人维护 |
| RandLA-Net 算法 | **推荐方向 / 实施待数据** | 1.24M 参数、单帧、输入规模恰好匹配 2-5w 点；SQN 0.1% 稀疏监督有先例 |
| RandLA-Net 官方 TF1.x 实现 | **不推荐** | Python3.5+TF1.11+CUDA9，Windows 编译问题多未决；**CC BY-NC-SA 4.0 非商业** |
| Open3D-ML 整体管线 | **不推荐（Windows）** | pip wheel 不带 PyTorch ops（issues #623/#424/#425/#659），需源码编译 |
| Open3D-ML 纯 PyTorch RandLA-Net 模型 | **推荐（剥出式）** | 纯 nn + sklearn KDTree（`# TODO: Replace with Open3D KNN` 注释自证）；MIT 许可 |
| S3DIS/SemanticKITTI 预训练权重直用 | **不推荐** | S3DIS 无 person 类 + 三重域差（扫描模式/视角/密度）；最多作骨干初始化 |
| Cylinder3D / SPVCNN / PVKD | **不推荐** | 全钉死 CUDA 稀疏卷积，CPU-only 不成立 |
| RK3588 NPU (RKNN) 点云 | **不押注** | rknn_model_zoo 无点云先例，算子匹配未知；按 CPU 推理做基线规划 |

## A. PCL Euclidean Cluster Extraction

- 官方教程：https://pcl.readthedocs.io/projects/tutorials/en/latest/cluster_extraction.html
- 核心：`pcl::EuclideanClusterExtraction<PointT>`，先 `KdTree`（FLANN/自
  实现）建树，再 BFS 半径生长：`setClusterTolerance(r)`、
  `setMinClusterSize / setMaxClusterSize`。复杂度 O(N log N)。
- 失效模式（本场景核心）：非重复扫描 LiDAR 的点密度随距离呈 ~1/r² 衰
  减，**固定 tolerance** 在近端过紧（同一人体因邻点间距超过 r 而碎成
  腿/躯/头多簇），远端过松（稀疏人点无法达到 min_cluster_size）。这本
  质上是 NA70 侧「5m 外人体点 25.4% BG 保留 + human_n_min=60 刚性」
  双重硬门失效的几何根源。
- 对本项目适配难度：**低到中**。生产 XY 体素聚类（0.15m、8 邻接、
  min_voxels=3）已隐含 3D 欧氏近似；真 3D 欧氏替换是**语义升级**而不
  是收益来源——我们在 D2 实测：C1 vs C0 在同 BG 输出上 GT 覆盖率反而
  轻微下降（0.779 vs 0.795），见 CLUSTER_ABLATION.md。
- 许可：BSD-3-Clause；维护：活跃（PCL 1.15.x 2024 仍有提交）。
- 判定：**推荐（作参考语义层）**——不搬库，搬思想：候选生成时按
  「距离 → 局部点距」给自适应 r。

## B. DBSCAN / 自适应密度聚类

- 官方实现：sklearn `cluster.DBSCAN`（O(N²) 朴素、KDT/BallTree 加速
  O(N log N)）；文档：https://scikit-learn.org/stable/modules/clustering.html#dbscan
- HDBSCAN（层次变体，免 eps）：https://github.com/scikit-learn-contrib/hdbscan；
  pip 可装，支持 Windows py3.12 wheel。
- 失效模式：单一 `eps` + 单一 `min_samples` 对非均匀密度的等价约束
  与固定 r 的欧氏聚类相同（近密处把不相关点粘连；远疏处达不到
  min_samples）。
- 距离自适应变体（近年 LiDAR 文献常见做法）：按点到雷达距离 r_lidar
  缩放 eps：`eps(p) = eps0 + k * ||p||`，或按密度分层（近/中/远三段各
  自一套 (eps, min_samples)）。**本轮 WebSearch 不可用，"adaptive
  DBSCAN LiDAR" 一手论文未能直取 URL；按主流实现判断为 "工程可行，
  学术出处待补"**。
- 实测（D2 C2）：在 BG-kept 点（约 2k）上 `eps=0.30, min_samples=8`，
  帧均 22.8ms、GT 覆盖率与 C0 持平（0.7763 vs 0.7764），FP 簇 2627 vs
  C0 629 —— **DBSCAN 在 BG 输出之上没有收益**，但比 C0 慢 23 倍。
- 判定：**部分推荐**——按距离分层的 DBSCAN 可作诊断层；生产替代
  意义不大，因 BG 已把密点筛走了。

## C. RF / XGBoost

### C.1 手工结构特征（扩维建议集）

以 PCL normal-estimation 协方差方法（https://pcl.readthedocs.io/projects/
tutorials/en/master/normal_estimation_using_integral_images.html）+ sklearn
ensemble 实践（https://scikit-learn.org/stable/modules/ensemble.html）为
源，长期通用的点云簇特征：
- 协方差/PCA 特征值派生（λ1≥λ2≥λ3）：Linearity / Planarity /
  Scattering / Omnivariance / Anisotropy / Eigenentropy / 曲率变化
- 截面（XY 平面特征值比、最大弦半径）
- 高度带占比 + 层数（本仓已有 9 带）
- 局部密度（kNN 平均距离，k=8）
- 强度统计 + 距雷达距离 + 方位角
- **Hackel 2016 ISPRS 特征集（multi-scale eigenvalue features）原文 URL
  本轮未直取，标记为"经典来源，待补 URL"；但特征族已被多家复用，按
  类别列入是安全的**。

适配难度 **低**：15–600 点稳定 PCA 可行（>=10 点即可）；点少时特征
噪声大，需要组合而非依赖单一特征。

### C.2 类别不平衡 + 校准 + 消融

- `RandomForestClassifier(class_weight='balanced_subsample')`：
  https://scikit-learn.org/stable/modules/ensemble.html
- XGBoost `scale_pos_weight` 只优化 AUC；要校准概率用 `max_delta_step`
  + Platt：https://xgboost.readthedocs.io/en/stable/parameter.html
- sklearn `CalibratedClassifierCV(method='sigmoid')`：**样本 <1000 必须
  用 sigmoid，isotonic 会过拟合**：
  https://scikit-learn.org/stable/modules/generated/sklearn.calibration.CalibratedClassifierCV.html
- 消融**不要用** `feature_importances_`（MDI 偏好高基数特征且只在训
  练集上）；用 `permutation_importance` 在留出集做：
  https://scikit-learn.org/stable/modules/ensemble.html (1.11.2.5)
- 困难负样本挖掘无统一权威标准；工程做法：迭代 train → 在验证集家
  具误报上追加 → 重训。本轮无可引用一手 URL，标"待验证"。

### C.3 安装/许可/平台

- sklearn：BSD-3；持续维护；Win/Linux/ARM64 全 wheel。
- XGBoost：Apache-2.0（https://raw.githubusercontent.com/dmlc/xgboost/
  master/LICENSE）；PyPI 最新 3.4.1（2026-08-15），Windows x86-64
  wheel 48.9MB / ARM64 2.1MB；`xgboost-cpu` 可单独装；CPU 默认
  `tree_method='hist'`，数百样本×百维×百树秒级。
- **RK3588**：xgboost 直接装 ARM64 wheel 可行；也可经 treelite /
  onnx 导出；RF 可复用我们已做过的 joblib→json 推理路径。
- **判定：两者均推荐**。

## D. PointNet / PointNet++

### D.1 论文与基线

- PointNet (CVPR 2017)：https://arxiv.org/abs/1612.00593 — 对称函数保
  证置换不变；vanilla 0.8M 参数 / 148M FLOPs/样本；50% 删点仅降
  2.4-3.8%。
- PointNet++ (NeurIPS 2017)：https://arxiv.org/abs/1706.02413 — SA 层
  （FPS + ball query + mini-PointNet）；SSG 8.7MB / GTX1080 batch8
  82.4ms / FLOPs 未直接报。

### D.2 输入/输出与重采样

- 恒输入 N×3（可+法向）；N 固定（1024/512）。点数不足时重复采样或
  上采样；超出随机下采 / FPS。
- 对 NA70 15–600 点簇：上采到 256 已带来 2-17× 重复点；重复采样
  **不制造新信息**，模型实际看 ≤600 独立点。

### D.3 预训练权重迁移风险

- ModelNet40 是 40 类完整 CAD 网格采样的 1024 点均匀稠密云；
- NA70 是固定式 Livox 非重复扫描的稀疏立面点云；
- 论文报告的 90.7-91.9% ModelNet40 精度**不代表**人 vs 家具表现；
- **判定：必须从头训练 + 自采数据，不得"加载 ModelNet 权重直接推理"**。

### D.4 实现

- 官方 PointNet (charlesq34/pointnet)：MIT，TF1.x+Py2.7，2017-2018
  停更。https://github.com/charlesq34/pointnet
- 官方 PointNet2 (charlesq34/pointnet2)：MIT，需自编译 tf_ops CUDA
  kernels，纯 CPU 不可行。https://github.com/charlesq34/pointnet2
- 第三方 PyTorch（yanx27/Pointnet_Pointnet2_pytorch）：MIT，
  `--use_cpu` 明确支持；基于 PyTorch 1.6 + Py3.7，新版兼容需自验；
  **事实标准**。https://github.com/yanx27/Pointnet_Pointnet2_pytorch

### D.5 Windows CPU 训练 + RK3588 推理

- PyTorch Windows CPU wheel：`pip install torch --index-url
  https://download.pytorch.org/whl/cpu`（官方说明，本轮 torch 2.12.0+cpu
  已实装验证）。
- PointNet vanilla 在 CPU 上"小时级"训 736 样本×15 epoch（量级估算，
  实测见 CLASSIFIER_ABLATION.md）。
- PointNet++ CPU 训练**不推荐**：ball query + FPS 在 CPU 慢 1-2 数量级；
  且 RKNN 不支持这些自定义算子。
- **RK3588 NPU**：PointNet vanilla 的 Conv1d+maxpool 属标准算子，
  量化可上；PointNet++ 分组算子需 CPU fallback，不推。

### D.6 判定

- PointNet vanilla (0.8M)：**待验证**——作为"深度学习是否值得"的
  最小成本实验；
- PointNet 完整版：**待验证**；
- PointNet++ (SSG/MSG)：**不推荐**当前；
- 预训练直迁：**不推荐**。

## E. PointNeXt

- 论文：https://arxiv.org/abs/2206.04670 （NeurIPS 2022）· 仓库：
  https://github.com/guochengqian/PointNeXt · PyPI: `pointnext_official`
- 核心：PointNet++ 训练策略升级（增广 + 优化器）+ 倒残差瓶颈 +
  可分离 MLP 缩放；ScanObjectNN 87.7%；S3DIS mIoU 74.9。
- 维护：**2026 仍在维护**（Blackwell sm_120 安装脚本更新、PyPI 包
  新增）；单人/小团队主导，长期 SLA 无。
- 依赖：Python 3.12 + uv + PyTorch ≥2.7 + CUDA 12.8 + openpoints 子
  模块 + wandb；训练/评测必须自编译自定义 CUDA/C++ ops（nvcc +
  g++<14）。
- 官方 README 原文：**"PyPI packages are importable without compiling
  CUDA extensions. Full training/evaluation still requires the custom
  CUDA/C++ ops"** —— 可 import，但训不了、评测不了。
- 许可：代码 MIT；论文 CC BY-NC-SA 4.0。
- 对 NA70：适配难度**高**（簇点数远低于设计规模；无 GPU 训练机）；
  Windows 无独显 CPU 训练**不推荐**；RK3588 NPU **不推荐**。
- **判定：不推荐（近期）**。降级用法：未来簇密度 ≥2k 点 + 拿到 GPU
  训练机时，只借鉴其增广/optimizer 配方，不引入 openpoints 栈。

## F. RandLA-Net

- 论文：https://arxiv.org/abs/1911.11236 （CVPR 2020 Oral / TPAMI 2021）
- 仓库：https://github.com/QingyongHu/RandLA-Net
- 核心：随机采样 + 局部特征聚合（LocSE K=16 + 注意力池化 + 膨胀残
  差），参数量 1.24M（RangeNet++ 的 1/40）。输入单帧 N×d，输出 N×
  n_class；SemanticKITTI seq-08（4071 帧 4 亿点）在 RTX 2080Ti 上 185
  秒 = 22 FPS（GPU 数字）。
- 逐点标注需求：全监督逐点；同组后续 SQN（ECCV 2022,
  https://arxiv.org/abs/2104.04891, https://github.com/QingyongHu/SQN）
  证明 RandLA-Net 骨干 + **0.1% 稀疏标注**可近全监督——直接回答
  "需要多少标注"：二元人/非人远易于 13 类，0.1% 级稀疏标注（每帧随
  机几十点）是已被验证的下限方向。
- **官方实现依赖（关键结论）**：
  - 最后一次提交 2021-07-02，实质停更 5 年，189 个 open issues。
  - 环境钉死 **Python 3.5 + TensorFlow 1.11 + CUDA 9.0 + cuDNN 7.4.1 /
    Ubuntu 16.04**。
  - 需编译 `utils/nearest_neighbors`（Cython CPU）+ `utils/cpp_wrappers`
    （C++/pybind11 CPU）—— 不是 CUDA op，但需 C++ 工具链。
  - Windows CPU-only **实质阻断**（TF1.x 无 Win py3.8+ 支持 + issues
    #267/#166/#220/#254/#191/#66 大量 Windows 编译失败未解决 +
    open3d 旧版 `from open3d import linux` 平台绑定）。
  - **许可：CC BY-NC-SA 4.0（非商业 + 相同方式共享）**——一票否决项
    若项目有商业可能；衍生模型权重按 SA 需同许可发布。
- **S3DIS 预训练权重直用风险**：S3DIS 是 Matterport 全景稠密扫描
  （带 RGB），**无 person 类**；域差在扫描模式/视角/密度三维度都极
  大。**判定：不推荐直迁**，最多作骨干初始化候选。
- **Open3D-ML 纯 PyTorch 复刻**：https://github.com/isl-org/Open3D-ML/
  blob/main/ml3d/torch/models/randlanet.py —— **纯 nn 模块 + sklearn
  KDTree**，代码内注释 `# TODO: Replace with Open3D KNN` 自证不用
  Open3D 编译 op。许可 MIT。这是**剥出式绕开官方许可与 TF 栈**的路
  线。
- Open3D-ML 整体在 Windows 的 pip 安装下**不能跑 ml3d 管线**（官方
  wheel 不带 PyTorch ops，issues #623/#424/#425/#659）。
- **Windows CPU 训练/推理**：剥出模型文件 + 自写 200 行数据管线可
  行；CPU 帧率无公开数据，需自测（D4 探针：cKDTree K=16 对 16k
  点 104ms / 40960 点 392ms；这是 RandLA-Net 的 CPU 主要开销）。
- **RK3588**：板端 Python 3.8 / NumPy 1.17 锁死，Open3D-ML 不兼容；
  需 ONNX 导出或纯 NumPy 推理重写（1.24M 参数矩阵乘可行，KNN 需
  自写 KD-tree）。RKNN model zoo 无点云先例，**不押注 NPU**。
- **数据量**：参照 S3DIS 单 Area（千万点）+ SQN 0.1% 稀疏先例，
  保守估计需**数百到一千帧**覆盖各姿态/位置/遮挡的 NA70 自采帧 +
  稀疏点标——但属工程外推，无文献直接背书。**跨域 ML 在本仓库
  已有先例一票否决（HR-08 记忆），自采数据是前提**。
- **逐点→实例**：官方/复刻都不提供实例分离后处理；标准做法是
  "人"点集做欧氏连通/DBSCAN（即 D2 已实测的 C1/C2 算法，帧级
  4.3-22.8ms）。
- **判定：算法推荐进入下一阶段，但实施前必须过 DATA_BLOCKED**：
  九会话 97% 以上非人点无 reviewed 标签，逐点监督不可获得；最小
  标注清单见 DATA_AUDIT.md §5。

## G. Open3D-ML

- 仓库：https://github.com/isl-org/Open3D-ML · 2.4k★
- 维护：活跃（2026-08 Intel XPU、2026-02 PyTorch 2.10 适配）。
- 模型：分割 RandLA-Net / KPConv / SparseConvUnet / PointTransformer；
  检测 PointPillars / PointRCNN。
- 许可：MIT。
- Windows 可用性：**存在已知阻断**（pip wheel 不带 PyTorch ops，
  issues #623/#424/#425/#659），官方建议源码编译
  `BUILD_PYTORCH_OPS`。
- Python 要求 ≥3.10（open3d 0.20）；与 RK3588 板端 Py3.8 不兼容。
- **判定：整体管线不推荐（Windows）；剥出其中纯 PyTorch 模型文件推
  荐**。

## H. 近年轻量分割边缘部署（2023-2026）

本轮 WebSearch 持续 HTTP 400 不可用，主题 H 覆盖面受限，以下结论仅
基于直接核实的项目一手页面；**"近年无成熟 CPU 边缘点云分割方案"是
覆盖受限下的方向性判断，不是穷举结论**。

- Cylinder3D（CVPR2021, https://github.com/xinge008/Cylinder3D）：
  spconv 1.2.1 + CUDA 10.2 钉死，**无 CPU 路径**；Apache-2.0。
- SPVCNN/torchsparse（MIT Han Lab）：GPU 稀疏卷积库，CUDA 根本前
  提。https://github.com/mit-han-lab/torchsparse
- PVKD（CVPR2022, https://github.com/cardwing/Codes-for-PVKD）：仍钉
  spconv 1.2.1 + CUDA 10.2，2022-11 后停更；MIT。
- RK3588 NPU：RKNN-Toolkit2 支持（Python 3.6-3.12，
  https://github.com/airockchip/rknn-toolkit2），但 rknn_model_zoo 全
  部是图像/音频/文本模型，**无任何点云/3D 参考实现**（
  https://github.com/airockchip/rknn_model_zoo）。
- **判定：Cylinder3D/SPVCNN/PVKD 均不推荐**；RK3588 NPU **待验证
  /不押注**，按 CPU 推理做基线规划。

## 与本仓数据的桥接

- 对"分类器是否是损失源"的诚实回答需要 oracle 实验，本轮实测：
  已接受候选中 GT 覆盖率 `cov>=0.5` 的 510 个 reviewed 对象，
  **0 个**因 RF 单独被拒——分类器在已交付候选上没有独立损失；但
  在家具 FP 上概率 p50=0.83（S1 644 个无 GT 候选 58% 过 0.55 门
  限），说明分类器的主要问题在**负类整洁率**，不在正例召回。这与
  调研结论（RF 未校准 + 负例池不足）完全对齐。
- 扩维特征消融建议见 C.1；本轮新增 18 维（线性/平面/散射度 + 截面
  + 局部密度 + 层数 + 峰度 + 距离方位 + 强度跨度）在 D3 实测（详
  见 CLASSIFIER_ABLATION.md）。

## 本轮未覆盖（明示）

- WebSearch 不可用期间，未能直取：Hackel 2016 ISPRS 论文原文、
  Livox Mid-360 非重复扫描人体检测专项论文、2024-2026 边缘点云分
  割综述。以上相关结论均按"待验证"处理，不进入推荐依据。
- 所有 RK3588 CPU/NPU 耗时均为量级估算，**未实测**，部署前必须
  真机 profile。
