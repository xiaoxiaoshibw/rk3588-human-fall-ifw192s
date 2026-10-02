// HR-05 save_annotations 集成测试：起 Python 进程直测 _api_save_annotations
"use strict";
const { execFileSync } = require("child_process");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");

let n = 0;
function ok(name) { n++; console.log("ok", name); }

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "hr05-"));
const sid = "cap_20261002_999999";
const sdir = path.join(tmp, sid);
fs.mkdirSync(sdir, { recursive: true });
const frames = [
    { seq: 100, stamp_sec: 1, stamp_nanosec: 0, offset_points: 0, count_points: 2 },
    { seq: 101, stamp_sec: 2, stamp_nanosec: 0, offset_points: 2, count_points: 2 },
];
const meta = {
    format: "human_capture_session",
    format_version: 1,
    session_id: sid,
    created_iso: "2026-10-02T00:00:00Z",
    sensor: { model: "IFW192S", frame_id: "innolidar" },
    time_domain: "device_stamp_s_unanchored",
    duration_sec: 0.1,
    point_layout: { fields: ["x", "y", "z", "intensity"], stride_bytes: 16 },
    point_stride_bytes: 16,
    point_file: "points.bin",
    total_points: 4,
    frames: frames,
    human_annotations: [],
    extraction: { tool: "bag2session/0.1.0" },
};
fs.writeFileSync(path.join(sdir, "meta.json"), JSON.stringify(meta, null, 1));
fs.writeFileSync(path.join(sdir, "points.bin"), Buffer.alloc(4 * 16));

const pyFile = path.join(tmp, "t.py");
fs.writeFileSync(pyFile, `# -*- coding: utf-8 -*-
import sys, os, json, hashlib
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
sys.path.insert(0, "D:/Code/ldiar/pc_apps/human_replay")
import human_replay_lib as H
import config as C
C.DEST_ROOT = ${JSON.stringify(tmp)}

def mk(body):
    h = H.Handler.__new__(H.Handler)
    out = []
    h._body = lambda self=None: body
    h._json = lambda obj, code=200: out.append({"code": code, "obj": obj})
    return h, out

meta_path = os.path.join(C.DEST_ROOT, "${sid}", "meta.json")

# 1. 正常 save
anno = {
    "id": "ann_001", "source": "human", "label": "person",
    "frame_seq": 100, "stamp_sec": 1, "stamp_nanosec": 0,
    "box": {"center": [1, 2, 0.5], "size": [1, 1, 1.8], "yaw": 0},
    "created_iso": "2026-10-02T00:01:00Z", "tool": "human_replay/0.1", "frame_valid": True,
}
h, out = mk({"sid": "${sid}", "annotations": [anno]})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 200, out
assert out[0]["obj"]["ok"] is True
assert out[0]["obj"]["count"] == 1
sha_a = out[0]["obj"]["sha256"]
with open(meta_path) as fh:
    mm = json.load(fh)
assert mm["human_annotations"][0]["id"] == "ann_001"
print("PASS save ok, count=1, sha=%s" % sha_a[:16])

# 2. 幂等：再送同 body → 同 sha
h, out = mk({"sid": "${sid}", "annotations": [anno]})
H.Handler._api_save_annotations(h)
assert out[0]["obj"]["sha256"] == sha_a
print("PASS idempotent")

# 3. 冻结字段不变：对比保存前后
with open(meta_path) as fh:
    mm = json.load(fh)
assert mm["format"] == "human_capture_session"
assert mm["frames"][0]["seq"] == 100
assert mm["extraction"]["tool"] == "bag2session/0.1.0"
print("PASS frozen fields intact")

# 4. 并发：.tmp 存在 → 409
open(meta_path + ".tmp", "w").write("x")
h, out = mk({"sid": "${sid}", "annotations": [anno]})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 409
os.remove(meta_path + ".tmp")
print("PASS tmp exists -> 409")

# 5. 非法 sid
h, out = mk({"sid": "../bad", "annotations": []})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 400, out
print("PASS invalid sid -> 400")

# 6. 非法 box: size 负数
h, out = mk({"sid": "${sid}", "annotations": [
    {**anno, "box": {"center": [0,0,0], "size": [-1,1,1], "yaw": 0}}
]})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 400, out
print("PASS negative size -> 400")

# 7. 非法 box: center 超界
h, out = mk({"sid": "${sid}", "annotations": [
    {**anno, "box": {"center": [101,0,0], "size": [1,1,1], "yaw": 0}}
]})
H.Handler._api_save_annotations(h4 := h) if False else H.Handler._api_save_annotations(h)
assert out[0]["code"] == 400, out
print("PASS center超限 -> 400")

# 8. 非法 source
h, out = mk({"sid": "${sid}", "annotations": [
    {**anno, "source": "ai"}
]})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 400, out
print("PASS non-human source -> 400")

# 9. meta.json 不存在 → 404
h, out = mk({"sid": "cap_20261002_000000", "annotations": [anno]})
H.Handler._api_save_annotations(h)
assert out[0]["code"] == 404, out
print("PASS missing meta -> 404")

print("ALL PYTHON PASS")
`);

const out = execFileSync("python", [pyFile], { encoding: "utf-8" });
console.log(out);

// 验证磁盘 meta
const final_meta = JSON.parse(fs.readFileSync(path.join(sdir, "meta.json"), "utf-8"));
if (final_meta.human_annotations.length !== 1) throw new Error("annotations 长度 != 1");
ok("meta.json 更新且有 1 条 annotation");

const sha = crypto.createHash("sha256").update(fs.readFileSync(path.join(sdir, "meta.json"))).digest("hex");
console.log("meta sha =", sha.slice(0, 16));
ok("sha256 有值");

fs.rmSync(tmp, { recursive: true, force: true });
console.log("all " + n + " js-side checks passed");
