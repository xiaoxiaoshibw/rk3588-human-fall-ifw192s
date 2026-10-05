"""P02 classical estimators, local offline adapters (no ROS or file access)."""
from .tls import estimate as tls
from .svd import estimate as svd
from .ransac import estimate as ransac

ESTIMATORS = {"tls": tls, "svd": svd, "ransac": ransac}
