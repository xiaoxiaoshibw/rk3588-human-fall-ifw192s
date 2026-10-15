# -*- coding: utf-8 -*-
"""HR-xx PC 端共用常量。无第三方依赖，单测与脚本直接 import。"""

import os
import re
import shutil

_HERE = os.path.dirname(os.path.abspath(__file__))

# 会话 sid/目录名白名单（PC/板/各插件共用一份；原先 4 份 cap_[0-9_] 窄正则的根）。
# 字母/数字/下划线/连字符，1..100 长；无点/斜杠/空格 → 天然防路径穿越与隐藏目录。
# 2026-10-12 放宽：synth_*、cap_*_clip_* 等非纯 cap_[0-9_] 命名同样可列/可载/可标，
# 与 leveling.py 原有宽度和 session_selection.js S12 的 clip 支持对齐。
SID_RE = re.compile(r"^[A-Za-z0-9_\-]{1,100}$")

# 板端协同部署模式（2026-10-10 用户授权：GT 标注台部署到 3588、所有人共标、
# 标注结果落板可拉回 PC）。直接设环境变量运行即为板端模式，
# PC 侧缺省路径全部不变（单板单开关，不做双实例）。
BOARD_MODE = os.environ.get("HUMAN_REPLAY_BOARD_MODE") == "1"

BOARD_URL = "http://192.168.31.58:8766"       # 捕获控制面（无鉴权，CORS *）

# 数据落盘根目录（D1）：PC 侧冻结为 D:\Code\ldiar\captures\remote\；
# 板端模式直接复用采集 staging /mnt/captures/captures_remote（
# capture_server 出的 <sid>/{meta.json,points.bin} 同构，GT 在数据原地标注，
# 无需任何搬运）。FETCH_DIR 留作板端覆盖钩子，默认=None→用 DEST_ROOT。
# DEST_ROOT 覆盖: HR_DEST_ROOT 独立生效（板端 deploy 脚本设它；
# 测试隔离也用）。不显式设时回 BOARD_MODE 默认（板=staging, PC=D1 原始路径）。
_pc_default = os.path.join(os.path.dirname(os.path.dirname(_HERE)), "captures", "remote")
_board_default = "/mnt/captures/captures_remote"
DEST_ROOT = os.environ.get("HR_DEST_ROOT") or (_board_default if BOARD_MODE else _pc_default)
FETCH_DIR = os.environ.get("HR_FETCH_DIR") or None

POLL_INTERVAL_S = 15.0
HTTP_TIMEOUT_S = 8.0     # 控制面 JSON

# 数据面流式下载的 socket 超时：单次读间隙上限。限速在板端（capture_server
# download_limit_kbit，2026-10-14 起 800000 Kbit/s ≈ 100MB/s，旧值 70000 是
# 百兆/无线时代给实时预览留余量用的）；
# 正常 256KB/30ms 一来，60s 没有字节才判死。scp 时代的 3600s 是总时长上限，
# HTTP 流式不需要总时长上限，只防僵死。
DOWNLOAD_TIMEOUT_S = 60.0

# 落盘前置门槛：剩余空间 < 会话大小 + 256MB slack 就本轮放弃
SPACE_SLACK_BYTES = 256 * 1024 * 1024


def free_bytes(path):
    return shutil.disk_usage(path).free
