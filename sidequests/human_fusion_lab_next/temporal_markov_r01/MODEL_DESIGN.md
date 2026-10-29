# 模型与边界

冻结参数在run_r3/FROZEN_CONFIG.json，规则初始化、未拟合，冻结后不根据最终数据选择配置。

EMA以α=1-exp(-dt/τ)更新RF；投票为过去0.5秒有效观测；滞回0.65/0.4，RF阈值0.55；短保持0.4秒输出hold_prediction，缺失时baseline/ema/vote/hysteresis为null。MC用RF阈值先离散成PRESENT/MISSING/UNKNOWN再结合转移先验；连续特征观测分类器与转移矩阵分工明确，不声称MC能直接从点云识别姿态。

HMM：π为初始分布，A每0.1秒转移；实际dt用A^floor(dt/.1)乘(I*(1-f)+A*f)插值，非拟合连续生成矩阵。姿态发射使用z90与高度的高斯原型，快速运动提升TRANSITION似然，轴歧义/稀少点提高UNKNOWN。坐/蹲均是规则假设，不是学习得到的语义。Forward αt∝(αt-1 A(dt))⊙b(xt)，每步归一，似然有下限；缺失采用高UNKNOWN发射，不将无点当0高度。presence HMM另用RF连续似然。

Viterbi在log-domain执行δt(j)=log bj+max_i(δt-1(i)+log Aij)，回溯仅用于离线。逐sid+track的连续时间段分别解码，绝不跨reset；在线输出经前缀测试，不消费未来。离线可能增加而非减少切换。

HSMM用状态-起始时刻cohort后验；Weibull S_s(a)=exp(-(a/scale_s)^shape_s)，每步生存比S(a+dt)/S(a)，退出质量乘零对角exit矩阵后产生新cohort。秒持续时间用真实timestamp；最大持续30秒强制退出；每间隔细分≤0.02秒以允许多次renewal，右端点近似仍有误差，不宣称精确连续解。后验零质量明确拒绝。时间有限窗口内状态cohort开销受时长与帧率影响；不外推为板端内存结论。

事件HMM使用完全相同事件发射，几何分布平均驻留匹配Weibull均值，形成持续时间对照。HSMM状态NORMAL/POSSIBLE_FALL/POST_FALL/RECOVERY/UNKNOWN为假设。事件候选另需近期可靠高位、≥0.3m下降、≥0.5m/s、低位持续≥0.6秒和概率门；初始低位/慢降/缺失不能触发。主动快速躺下仍可能候选，不能确认跌倒。POST_FALL仅模型状态名字，无真实跌倒含义。

sid/track分隔缓存；时间倒退、>1秒间隔或显式reset清历史；缺失清下降armed和差分。上游复用同ID代表不同人且未通知的情况无法自动识别，此处ID串扰真实效果UNKNOWN。数学参数、转移图见config与figures/matrices.png。
