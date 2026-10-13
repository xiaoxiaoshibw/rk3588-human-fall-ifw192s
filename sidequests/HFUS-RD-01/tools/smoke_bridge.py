# -*- coding: utf-8 -*-
"""rf_extract_node.js 冒烟 + 与 python frame_feature 对拍（n=1 批次）。"""
import json
import os
import subprocess
import sys
import tempfile

import numpy as np

NODE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "rf_extract_node.js")


def run():
    rng = np.random.default_rng(0)
    a = rng.random((37, 4)).astype(np.float32) * 2
    b = rng.random((120, 4)).astype(np.float32) * 2
    cat = np.concatenate([a, b], axis=0)
    with tempfile.NamedTemporaryFile(suffix=".npy", delete=False) as tf:
        np.save(tf, cat)
        p = tf.name
    spec = json.dumps({"file": p.replace(os.sep, "/"), "counts": [37, 120]})
    r = subprocess.run(["node", NODE, spec], capture_output=True, text=True)
    os.unlink(p)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout)
    assert len(o["features"]) == 2 and len(o["features"][0]) == 51
    repo = os.path.abspath(os.path.join(os.path.dirname(NODE),
                                        "..", "..", ".."))
    sys.path.insert(0, os.path.join(repo, "pc_apps", "human_ml"))
    import frame_feature as ff
    py = ff.extract_features(a)
    js = np.array(o["features"][0])
    exact = [0, 5, 6, 7, 11, 12, 13, 23, 24, 25, 45, 46, 47, 48, 49]
    assert all(abs(py[i] - js[i]) < 1e-4 for i in exact), \
        [(i, py[i], js[i]) for i in exact if abs(py[i] - js[i]) >= 1e-4]
    d = np.abs(py - js)
    print("exact dims PASS")
    print("maxabs=%.2e; pca py=%s js=%s" % (
        d.max(), py[32:35].round(4), js[32:35].round(4)))
    print("axis_z py=%s js=%s (JS asc-order trap intentional)" % (
        py[37:40].round(4), js[37:40].round(4)))
    print("SMOKE PASS")


if __name__ == "__main__":
    run()
