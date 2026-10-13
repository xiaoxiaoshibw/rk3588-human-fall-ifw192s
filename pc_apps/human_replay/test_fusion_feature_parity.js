/* test_fusion_feature_parity.js — HUMAN-UNIFY-FUSION-R1 F1 真实簇逐维对拍.
 *
 * 数据源: docs/human_capture/evidence/2026-10-10_human_unify_fusion_r1/parity_dataset.json
 *   (Python dump_parity_dataset.py 从新 9 会话真实导出: 483 候选簇 fv_py + 6 边界断面)
 *
 * 判定口径 (显式, 不写死“全维度同容差”——比值/百分比类维度会随簇尺度放大绝对误差):
 *   - 非 RF 使用维 (模型未消费, 只作统计): err ≤ --tol (默认 5e-3)
 *   - RF 使用维: err ≤ 100 ulp(scale), scale=max(|fv_py|, |该维树阈 min|, |max|, 1)
 *     — 任何树阈跨侧 (leaf path 不一致) 由 leaf_path 检查直接判 FAIL
 *   - 概率差 max 与 P95 报告; leaf path 全量 (100 树×N 簇) 必须 100% 一致
 *   - fv[37..39] az 并列: 报告 asc(历史契约) vs desc 两端差, 不单独判 FAIL
 *     (Python 端固定 eigh 原始列序输出, JS 稳定排序只能逼近;
 *      但 v1 模型未使用 37..39 维 — 见 rf_used_dims, 该近似不影响推理一致)
 *
 * 跑法: node test_fusion_feature_parity.js [--dataset <path>] [--tol 5e-3]
 */
"use strict";
var fs = require("fs"), path = require("path");
var RF = require("./rf_person.js");

function parseArgs() {
    var o = { dataset: path.join(__dirname, "..", "..", "docs", "human_capture", "evidence",
        "2026-10-10_human_unify_fusion_r1", "parity_dataset.json"), tol: 5e-3 };
    for (var i = 2; i < process.argv.length; i++) {
        if (process.argv[i] === "--dataset") o.dataset = process.argv[++i];
        else if (process.argv[i] === "--tol") o.tol = Number(process.argv[++i]);
        else throw new Error("未知参数 " + process.argv[i]);
    }
    return o;
}

function frameFromXyzi(xyzi) {
    return { n: xyzi.length,
        x: Float32Array.from(xyzi.map(function (p) { return p[0]; })),
        y: Float32Array.from(xyzi.map(function (p) { return p[1]; })),
        z: Float32Array.from(xyzi.map(function (p) { return p[2]; })),
        intensity: Float32Array.from(xyzi.map(function (p) { return p[3]; })) };
}

function leafPath(trees, fv) {
    return trees.map(function (t) {
        var node = 0;
        while (t.feature[node] !== -2) {
            node = fv[t.feature[node]] <= t.threshold[node] ? t.children_left[node] : t.children_right[node];
        }
        return node;
    });
}

function main() {
    var o = parseArgs();
    var ds = JSON.parse(fs.readFileSync(o.dataset, "utf8"));
    var model = JSON.parse(fs.readFileSync(path.join(__dirname, "rf_person_v1.json"), "utf8"));
    RF.init(JSON.stringify(model));
    var trees = model.trees;

    /* RF 实际使用维 + 每维阈值范围 (scale) */
    var used = new Array(ds.feat_dim).fill(false);
    var thMin = new Array(ds.feat_dim).fill(Infinity), thMax = new Array(ds.feat_dim).fill(-Infinity);
    trees.forEach(function (t) {
        t.feature.forEach(function (f, i) {
            if (f >= 0) { used[f] = true; if (t.threshold[i] < thMin[f]) thMin[f] = t.threshold[i]; if (t.threshold[i] > thMax[f]) thMax[f] = t.threshold[i]; }
        });
    });
    var EPS_F32 = 1.1920928955078125e-7;
    function rfTol(d, fvpy) {
        if (!used[d]) return null;
        return 100 * EPS_F32 * Math.max(Math.abs(fvpy), Math.abs(thMin[d] === Infinity ? 0 : thMin[d]), Math.abs(thMax[d] === -Infinity ? 0 : thMax[d]), 1.0);
    }

    var items = ds.clusters.map(function (c) {
        return { tag: c.sid + "#f" + c.frame + "/c" + c.cluster, xyzi: c.xyzi, fv_py: c.fv_py };
    }).concat(ds.edge_cases.map(function (e) {
        return { tag: "edge:" + e.name, xyzi: e.xyzi, fv_py: e.fv_py };
    }));

    var dimMaxAbs = new Array(ds.feat_dim).fill(0), dimSumAbs = new Array(ds.feat_dim).fill(0);
    var dimMaxRel = new Array(ds.feat_dim).fill(0);
    var failures = [], probDiffs = [], azDiffs = [];
    var leafMismatch = 0, leafMismatchSamples = [];
    var globalMaxAbs = 0, globalMaxAt = null;
    items.forEach(function (it) {
        var fr = frameFromXyzi(it.xyzi);
        var fv_js = RF.extract(fr, fr.intensity);
        for (var d = 0; d < ds.feat_dim; d++) {
            var err = Math.abs(fv_js[d] - it.fv_py[d]);
            dimMaxAbs[d] = Math.max(dimMaxAbs[d], err);
            dimSumAbs[d] += err;
            if (err > globalMaxAbs) { globalMaxAbs = err; globalMaxAt = it.tag + " fv[" + d + "]=" + ds.feat_names[d]; }
            var bt = rfTol(d, it.fv_py[d]);
            if (bt !== null) dimMaxRel[d] = Math.max(dimMaxRel[d], err / bt);
            if (d >= 37 && d <= 39) azDiffs.push(err);
            if (bt === null) {
                if (err > o.tol) failures.push({ tag: it.tag, dim: d, name: ds.feat_names[d], kind: "non_rf_dim_err", err: err, tol: o.tol, js: fv_js[d], py: it.fv_py[d] });
            } else if (err > bt) {
                failures.push({ tag: it.tag, dim: d, name: ds.feat_names[d], kind: "rf_dim_over_100ulp", err: err, tol_100ulp: bt, js: fv_js[d], py: it.fv_py[d] });
            }
        }
        var p_js = RF.predict_person(fv_js), p_py = RF.predict_person(Float32Array.from(it.fv_py));
        probDiffs.push(Math.abs(p_js - p_py));
        var lpj = leafPath(trees, fv_js), lpp = leafPath(trees, Float32Array.from(it.fv_py));
        var same = lpj.every(function (v, i) { return v === lpp[i]; });
        if (!same) { leafMismatch++; if (leafMismatchSamples.length < 10) leafMismatchSamples.push(it.tag); }
    });

    var n = items.length;
    var pd = probDiffs.slice().sort(function (a, b) { return a - b; });
    var az = azDiffs.slice().sort(function (a, b) { return a - b; });
    var report = {
        schema: "fusion_parity_result/v1",
        dataset: path.relative(process.cwd(), o.dataset).replace(/\\/g, "/"),
        non_rf_tol: o.tol,
        n_items: n,
        rf_used_dims: used.map(function (u, i) { return u ? i : null; }).filter(function (v) { return v !== null; }),
        global_max_abs_err: { value: +globalMaxAbs.toPrecision(6), at: globalMaxAt },
        per_dim: ds.feat_names.map(function (nm, i) {
            return { dim: i, name: nm, rf_used: used[i],
                max_abs_err: +dimMaxAbs[i].toPrecision(4), mean_abs_err: +(dimSumAbs[i] / n).toPrecision(4),
                max_rel_100ulp: used[i] ? +dimMaxRel[i].toPrecision(4) : null,
                rf_thresh_range: used[i] ? [thMin[i], thMax[i]] : null };
        }),
        prob_diff: { max: +pd[pd.length - 1].toPrecision(4), p95: +pd[Math.floor(pd.length * 0.95)].toPrecision(4), mean: +(probDiffs.reduce(function (a, b) { return a + b; }, 0) / n).toPrecision(4) },
        leaf_path: { mismatch_items: leafMismatch, total: n, match_rate: (n - leafMismatch) / n, samples: leafMismatchSamples },
        az_37_39_max_abs_err: az.length ? +az[az.length - 1].toPrecision(4) : 0,
        failures_over_tol: { count: failures.length, head: failures.slice(0, 30) },
    };
    console.log(JSON.stringify(report, null, 1));
    var pass = failures.length === 0 && leafMismatch === 0;
    console.log(pass ? ("PARITY PASS (" + n + " items, leaf 100%)") : ("PARITY FAIL (" + failures.length + " items over tol, " + leafMismatch + " leaf mismatches)"));
    process.exit(pass ? 0 : 1);
}

main();
