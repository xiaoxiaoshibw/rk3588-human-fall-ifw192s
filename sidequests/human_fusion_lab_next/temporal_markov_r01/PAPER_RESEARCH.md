# 已核实论文与开源参考

2026-10-15，由只读论文子代理按paper-lookup技能核查Crossref、作者稿、机构网页和作者仓库。未用论文指标替代本项目测量；板端可行性是工程推断，非实测。

|方法|正式引用|传感器/特征/时序/骨架|代码与本项目边界|
|---|---|---|---|
|RGB-D HMM跌倒|Dubois & Charpillet, Automatic Fall Detection System with a RGB-D Camera using a Hidden Markov Model, ICOST 2013，[DOI](https://doi.org/10.1007/978-3-642-39470-6_33)，[Inria书目](https://radar.inria.fr/rapportsactivite/RA2013/maia/bibliography.html)|Kinect深度背景减除，质心、垂速、离散程度→HMM，无关节骨架|此次未找到作者确认代码，不等于确认不存在；几何观测路线最接近，但深度相机点密度/背景不同，发射与阈值不可照搬。小HMM可NumPy实现。|
|S-HSMM活动与异常|Duong, Bui, Phung & Venkatesh, Activity Recognition and Abnormality Detection with the Switching Hidden Semi-Markov Model, CVPR 2005，[DOI](https://doi.org/10.1109/CVPR.2005.61)，[SRI作者全文](https://www.sri.com/wp-content/uploads/2021/12/1132.pdf)|四顶角摄像头跟踪，厨房网格位置序列，两层S-HSMM，持续时间，无骨架|[作者代码页](https://www.dinhphung.com/index.php?n=Main.Code)确列MATLAB CxHSMM及本论文；包未实际运行。原论文不是跌倒效果验证，只支持显式持续时间建模依据。小有限时长HSMM可研究移植。|
|LiDAR多人TCN|Luo, Poslad & Bodanese, Temporal Convolutional Networks for Multiperson Activity Recognition Using a 2-D LIDAR, IEEE IoT Journal 2020，[DOI](https://doi.org/10.1109/JIOT.2020.2984544)，[大学接收稿](https://qmro.qmul.ac.uk/xmlui/bitstream/123456789/63962/2/Bodanese%20Temporal%20convolutional%20networks%202020%20Accepted.pdf)|2D LiDAR聚类、人/非人判别、Kalman轨迹窗口，TCN/LSTM/HMM比较，无骨架|未核实专属作者代码；通用TCN仓库不能冒充本论文实现。平面轨迹活动不是3D姿态坍塌；小TCN可后续对照，当前板端依赖栈不直接支持原训练实现。|
|通用轻量时序对照|Bai, Kolter & Koltun, An Empirical Evaluation of Generic Convolutional and Recurrent Networks for Sequence Modeling, 2018，[arXiv](https://arxiv.org/abs/1803.01271)|因果膨胀TCN，通用序列，无传感器/骨架假设|[官方locuslab/TCN](https://github.com/locuslab/TCN)有实际实现。可用同几何特征作后续小TCN对照，需要可信标签与训练授权，未在本轮训练。|
|LiDAR谱特征HAR|Sharifipour等, LiDAR-based Human Activity Recognition through Laplacian Spectral Analysis, 2025预印本，[作者稿](https://arxiv.org/html/2509.23255v1)|MM-Fi Ouster OS1 32线10Hz；点图Laplacian谱，滑窗统计+SVM/RF，无骨架|[作者仓库](https://github.com/Arritmic/oulu-pointcloud-har)当前仅README/LICENSE，写Code coming soon，应记代码尚未发布。分类器轻量不等于图构造/谱分解适合RK；传感器与本项目分布不同。|
|复杂点云动作捕捉背景|Li等, LiDARCap: Long-range Marker-less 3D Human Motion Capture with LiDAR Point Clouds, CVPR 2022，[作者预印本](https://arxiv.org/abs/2203.14698)|PointNet++编码、时序聚合、逆运动学/SMPL；推理输入LiDAR，学习/输出涉及人体姿态与身体模型|[作者仓库](https://github.com/jingyi-zhang/LiDARCap)有训练/评估代码，依赖PyTorch、PointNet++扩展、SMPL，非本轮NumPy小模型或当前板端直接方案；目标不是跌倒分类。|

文献支持做公平比较，不支持预设HMM/HSMM胜出。当前优先原基线+可解释滤波，补GT后比较小HMM/HSMM；如观测非高斯、长上下文必要且标签足够，再用同特征小TCN或GRU。贝叶斯滤波可低成本融合存在概率，但不能把家具持久置信纠正为人体。当前不下载权重/数据、不改模型、不引入训练服务。
