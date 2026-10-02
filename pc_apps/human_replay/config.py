# -*- coding: utf-8 -*-
"""HR-xx PC 端共用常量。无第三方依赖，单测与脚本直接 import。"""

import os
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))

BOARD_URL = "http://192.168.3.125:8766"       # 捕获控制面（无鉴权，CORS *）
SSH_TARGET = "ldiar-wel"                       # ~/.ssh/config alias（免密 key）

# 数据落盘根目录（D1）：D1 冻结为 D:\Code\ldiar\captures\remote\
DEST_ROOT = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "captures", "remote")

POLL_INTERVAL_S = 15.0
HTTP_TIMEOUT_S = 8.0
SSH_TIMEOUT_S = 30.0
SCP_TIMEOUT_S = 3600.0

# 预留 30% 链路给实时预览（README §6）：100M 链路 → scp -l 70000 ≈ 70Mbit/s
SCP_LIMIT_KBIT = 70000

# 落盘前置门槛：剩余空间 < 会话大小 + 256MB slack 就本轮放弃
SPACE_SLACK_BYTES = 256 * 1024 * 1024


def free_bytes(path):
    return shutil.disk_usage(path).free
