# HF-03实现中独立复核：先修复再继续板测

Codex已定向暂停本次CLI worker，保留原session ses_f0cbba8e8ffeUVpsyHE7V6qdck，不是用户暂停任务。继续原工单，先修复以下三个独立已复现问题，再完成板上测试/真实bag分析和SUBMITTED回传。不要重做已完成阅读/基线记录，不改原72项冻结回归。此前地面符号在最新源码已修正：地面z=-1.5、朝上法向、平面n.p+d=0时d=+1.5，传感器高度=+d，两条符号检查已通过，保留。

独立脚本docs/human_fall/evidence/review_hf03_codex.py，当前5方法/3失败，日志evidence/2026-10-01_autonomous_hf03_r1/codex_initial_geometry_boundaries.txt；不得改/放宽此脚本。

1. P1：ground.py的np.linalg.svd默认full_matrices=True，为N点生成NxN的U，max_fit_points=50000时可消耗约20GB，不满足板上有界计算。必须使用full_matrices=False或更小的3x3协方差特征分解，检查其他新增SVD同类调用。修复前不得运行大点云拟合；补小数组拦截检查及实际较大数组的时间/内存合理性。
2. P2：地面held-out验证只有统计没有门控。训练平面z=-1.5、按同一随机切分将所有留出点改为z=-4时，holdout RMS=2.5m仍status=valid。使用有单位/合法范围的支持率与残差阈值判验证失败，兼顾场景内非地面离群点，不能简单把所有离群点RMS作为唯一限制。没有可用留出证据时明确未验证，不能默认为验证通过。保留失败原因/原始统计。
3. P2：build/validate_geometry_calibration允许status=valid、normal=[0,0,2]、offset=1.5这样的非单位法向进入产物。严格检查地面法向/offset/状态/帧/有效区域及验证信息的一致性；不要仅计算positive height就当结构正确。旋转记录的status也须与evidence一致，验证标记不得与unknown/synthetic记录矛盾。已知缺字段/错误类型返回明确校验错误，不用真实物理信息填空。范围内最小修复，不做通用schema框架。

常规配置参数同步检查有限值和合法范围（例如normal_up_min_z不可大于1，角度/支持率/留出比例有明确范围）。完成本地全部回归及原样独立5方法，再用相同哈希的板上隔离副本复跑、完成真实bag只读统计。单次SSH实测约26秒，bash工具给至少120秒；使用已设置的PowerShell7，不回退shell、不改用户全局配置。正式回传记录此早期失败与修复证据，合成/离线/现场验收分开；结束让Codex直接复审并继续下一阶段。
