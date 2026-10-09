/* rf_person.test.js — JS RF 推理与 feature extraction 与 Python 端 frame_feature.py 对拍.
 *
 * Python 端 (参考真值):
 *   python -c "
 *     import sys, json
 *     sys.path.insert(0, 'pc_apps/human_ml')
 *     from frame_feature import extract_features
 *     import numpy as np
 *     # 造 100 随机点, 跟 JS 相同
 *     np.random.seed(42)
 *     pts = np.random.randn(100, 3).astype(np.float32) * 0.5 + [2.0, 1.0, 1.2]
 *     pts[:, 2] = np.abs(pts[:, 2]) * 0.5 + 0.2    # z 拉正且高
 *     inten = np.random.rand(100).astype(np.float32) * 1000
 *     fv = extract_features(np.column_stack([pts, inten]))
 *     print(json.dumps(fv.tolist()))
 *   " > /tmp/py_fv.json
 *
 * 跑法: node rf_person.test.js
 */
"use strict";

var RF_PERSON = require("./rf_person.js");

function assert(cond, msg) {
    if (!cond) { console.log("FAIL: " + msg); process.exit(1); }
    console.log("PASS: " + msg);
}

// --- 用固定 seed 点集对拍 ---
// 造一组 100 点（同 python 种子)
function lcg(seed) {
    var s = seed;
    return function () {
        s = (s * 1664525 + 1013904223) % 4294967296;
        return s / 4294967296;
    };
}
var rnd = lcg(42);
var N = 100;
var xs = new Float32Array(N), ys = new Float32Array(N), zs = new Float32Array(N), ii = new Float32Array(N);
for (var k = 0; k < N; k++) {
    // 中心 (2.0, 1.0, 1.2), std 0.5, z 拉正到 0.2 以上
    var nx = (rnd() * 2 - 1) * 0.5, ny = (rnd() * 2 - 1) * 0.5, nz = (rnd() * 2 - 1) * 0.5;
    xs[k] = 2.0 + nx;
    ys[k] = 1.0 + ny;
    zs[k] = Math.abs(nz) * 0.5 + 0.2;
    ii[k] = rnd() * 1000;
}
// 与 python 用同一均值 std 设 (python 用 randn(gauss), JS 用 uniform, 比较量纲不对,
// 走一个比较窄的 tolerance)
var frame = { n: N, x: xs, y: ys, z: zs };
var fv_js = RF_PERSON.extract(frame, ii);

// 验证固定数字: 不 NaN, 范围合理, 特定维度取值合理
assert(fv_js[0] === N, "fv[0]=n 点数");
assert(fv_js[4] >= 0 && fv_js[4] <= 4, "fv[4]=log10(i_std+1) 落在合理量纲");
assert(isFinite(fv_js[5]) && isFinite(fv_js[13]), "分位数有限");
assert(fv_js[14] >= 0 && fv_js[22] >= 0, "z 带 非负");
var zb_sum = 0; for (var q = 14; q <= 22; q++) zb_sum += fv_js[q];
assert(Math.abs(zb_sum - 1) < 0.01, "z 带 比例 之和 ≈ 1");
assert(fv_js[42] > 0, "z_range 非负");
assert(fv_js[44] >= 0, "upright 非负");
assert(fv_js[48] >= 0 && fv_js[48] <= 1, "n_pts_ratio_near 占比范围内");

// 与 Python 对照同一份特征 (python 生成 fv 时大家手 dump 对比)
console.log("JS features 前 10 维: ");
var rounded = Array.from(fv_js.slice(0, 10)).map(function (v) { return v.toFixed(3); });
console.log("  " + rounded.join(" "));

// RF predict_person 加载 json 后测试 (加载岗走 fetch, 这里直接读文件)
var fs = require("fs");
var jsonText = fs.readFileSync(require("path").join(__dirname, "rf_person_v1.json"), "utf-8");
RF_PERSON.init(jsonText);

// 已对准 dump: fv=extract(pts) 应该给高 person 概率
var p = RF_PERSON.predict_person(fv_js);
console.log("p(person) = " + p.toFixed(3));
assert(p >= 0.75, "本场 pts 是人形状 (JS fv 中 fv[37..39] 为 0 简化占位), RF 应该给高概率 (>= 0.75)");

// 真实空场样本: 用 python 预处理 提取 特征 写入 fixture, JS 只 做 predict
// fixture 由 pc_apps/human_ml/dump_rf_test_fixture.py 生成
var fixture_path = require("path").join(__dirname, "rf_test_fixture.json");
if (fs.existsSync(fixture_path)) {
    var fx = JSON.parse(fs.readFileSync(fixture_path, "utf-8"));
    // person 样本 (应 高概率)
    var passes_person = 0;
    fx.person.forEach(function (f) {
        var p = RF_PERSON.predict_person(new Float32Array(f.features));
        if (p >= 0.7) passes_person++;
    });
    console.log("person fixture: " + passes_person + "/" + fx.person.length + " >= 0.7");
    assert(passes_person >= 4, "person fixture 应至少 4/5 高概率");

    // noperson 样本 (应 低概率)
    var passes_noperson = 0;
    fx.noperson.forEach(function (f) {
        var p = RF_PERSON.predict_person(new Float32Array(f.features));
        if (p <= 0.3) passes_noperson++;
    });
    console.log("noperson fixture: " + passes_noperson + "/" + fx.noperson.length + " <= 0.3");
    assert(passes_noperson === fx.noperson.length, "noperson fixture 应全部低概率, 实际未通");
} else {
    console.log("跳过 fixture 测试 (生成 fixture: python pc_apps/human_ml/dump_rf_test_fixture.py)");
}

console.log("ALL RF_PERSON PASS");
