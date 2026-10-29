# 特征分析

![八动作](../../../docs/human_capture/evidence/2026-10-15_hfus_markov_r01/run_r3/figures/eight_actions.png)

图件实际路径：docs/human_capture/evidence/2026-10-15_hfus_markov_r01/run_r3/figures/eight_actions.png及SVG。

高度/宽/深为2–98%分位跨度；最高最低是极值；质心是均值；volume为分位盒体积；density=点数/体积（近退化体积下限1e-6m³）；tilt为最大PCA轴与z的锐角，特征值接近时null；eigen_ratio为最大特征值/总值；low_fraction为z<0.6m比例。

垂速/水平速度/高度变化率/角速度分别由当前与上次有效测量差分除真实dt（m/s、deg/s）；缺失立即断差分，不能跨遮挡补速度。stable_frames是原型最大发射类连续帧数；missing_age_s为距最近测量秒。RF用真实强度及既有51维提取器；candidate_valid仅几何存在，completeness和association_confidence=null，因为无校准值。逐帧可增量计算；空间几何只依赖当前点，不依赖骨架。

可观察到高度与低位变化，但坐下/蹲下观测区间重叠，HMM的两个语义状态在此数据上不可独立验证。RF在这1934个已预筛候选上全为阳性，动态范围不足以研究真实闪烁；这也暴露先选候选再评RF的选择偏差。倾角反映可见点主轴，不保证身体轴；近退化/遮挡应UNKNOWN。特征是否真正有语义判别力需要逐帧人工标签，当前UNKNOWN；不以文件名给类别后做可分性准确率。范围数值见FEATURE_STATS.json。

图中多处垂速尖峰可能来自候选点可见分布/成员突变，例如083120开头和083254约17秒；不能视作已核实身体加速度。坐/蹲曲线跨度在本批次部分时段相近，当前没有按GT作独立类别分离实验。
