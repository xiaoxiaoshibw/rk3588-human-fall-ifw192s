"""AGL-A 三估计器薄适配器（同一 PointDomain；无质量/仲裁/时间逻辑）。

每个适配器只做：配置与 domain 校验 → 单一数值核 → 统一 PlaneEstimate 记录。
数值语义与冻结 GL-01/离线工作台一致；等权输入时与 P02 结果逐位同值。
"""
from .tls import estimate_tls
from .svd import estimate_svd
from .ransac import estimate_ransac

ESTIMATORS = {"tls": estimate_tls, "svd": estimate_svd, "ransac": estimate_ransac}
