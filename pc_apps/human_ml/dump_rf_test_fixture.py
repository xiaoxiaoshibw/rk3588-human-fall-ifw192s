# -*- coding: utf-8 -*-
"""dump_rf_test_fixture.py — 生成 JS 端 RF 推断回归对照 fixture.

输出 pc_apps/human_replay/rf_test_fixture.json:
  {"person": [{sid, frame, features}], "noperson": [...]}
"""
import json
import os

from frame_feature import extract_features
from session_load import iter_session_frames, iter_none_frames, REMOTE

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                   "pc_apps", "human_replay", "rf_test_fixture.json")


def take_n(gen, n):
    out = []
    for i, r in enumerate(gen):
        if i >= n:
            break
        out.append(r)
    return out


def main():
    fixture = {"person": [], "noperson": []}

    # 每 person 会话抽 2 帧
    for sid in ["cap_20261009_114817", "cap_20261009_121723", "cap_20261009_114641"]:
        sd = os.path.join(REMOTE, sid)
        for xyz_i, lab, name in take_n(iter_session_frames(sd), 2):
            fv = extract_features(xyz_i)
            fixture["person"].append({"sid": sid, "name": name, "features": fv.tolist()})

    # noperson: 空场模板 + 大房间空场
    for sid in ["cap_20261009_113611", "cap_20261004_203135", "cap_20261004_203349"]:
        sd = os.path.join(REMOTE, sid)
        for xyz_i, lab, name in take_n(iter_none_frames(sd), 3):
            fv = extract_features(xyz_i)
            fixture["noperson"].append({"sid": sid, "name": name, "features": fv.tolist()})

    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(fixture, fh, ensure_ascii=False)
    print("wrote", OUT, "person:", len(fixture["person"]), "noperson:", len(fixture["noperson"]))


if __name__ == "__main__":
    main()
