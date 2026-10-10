# -*- coding: utf-8 -*-
"""HR-xx PC 端共用常量。无第三方依赖，单测与脚本直接 import。"""

import os
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))

BOARD_URL = "http://192.168.31.58:8766"       # 捕获控制面（无鉴权，CORS *）

# 数据落盘根目录（D1）：D1 冻结为 D:\Code\ldiar\captures\remote\
DEST_ROOT = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "captures", "remote")

POLL_INTERVAL_S = 15.0
HTTP_TIMEOUT_S = 8.0     # 控制面 JSON

# 数据面流式下载的 socket 超时：单次读间隙上限。限速在板端（capture_server
# download_limit_kbit，默认 70000 Kbit/s ≈ 70Mbit，给 100M 链路实时预览留 30%）；
# 正常 256KB/30ms 一来，60s 没有字节才判死。scp 时代的 3600s 是总时长上限，
# HTTP 流式不需要总时长上限，只防僵死。
DOWNLOAD_TIMEOUT_S = 60.0

# 落盘前置门槛：剩余空间 < 会话大小 + 256MB slack 就本轮放弃
SPACE_SLACK_BYTES = 256 * 1024 * 1024


def free_bytes(path):
    return shutil.disk_usage(path).free
