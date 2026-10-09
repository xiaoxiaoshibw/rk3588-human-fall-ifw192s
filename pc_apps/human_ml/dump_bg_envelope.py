# -*- coding: utf-8 -*-
"""dump_bg_envelope.py — 把空场模板背景差分包络导出为 JS 可直接用的 JSON.

产出到 <human_replay>/bg_envelope.json, 浏览器里 detect_ui.js 通过 /bg_envelope.json 拉取.

格式: { "grid_key(cell x*4096 + y)": z95_in_m, ... }  -- 与 PC 端 auto_person_label.py 同 key 编码.
"""
import json
import os
import sys

from auto_person_label import background_envelope

HERE = os.path.dirname(os.path.abspath(__file__))
REPLAY_DIR = os.path.join(os.path.dirname(os.path.dirname(HERE)), "pc_apps", "human_replay")


def main():
    cells = background_envelope(
        os.path.join(os.path.dirname(os.path.dirname(HERE)), "captures", "remote"))
    out = {str(k): round(v, 3) for k, v in cells.items()}
    target = os.path.join(REPLAY_DIR, "bg_envelope.json")
    with open(target, "w", encoding="utf-8") as fh:
        json.dump(out, fh, separators=(",", ":"))
    print("wrote", target, "cells:", len(out), "size:", os.path.getsize(target))


if __name__ == "__main__":
    main()
