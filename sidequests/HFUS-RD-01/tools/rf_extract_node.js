// rf_extract_node.js — 生产 rf_person.js 原样计算 51 维特征与概率。
// 输入: 单一 .npy 文件, int64 (N,) — 本批全部候选点数的累积和边界 (边界数=M+1, M=候选数) —— 不实际用;
//       真正的点数据为第二个 .npy (M,Nmax,4) float32。
// 简化协议: stdin 传 JSON {"file": npy路径, "counts": [n1,n2,...]}，
//          npy 存 (sumN,4) float32。node 端按 counts 切片。
"use strict";
const fs = require("fs"), path = require("path");
const RF = require(path.join(__dirname, "..", "..", "..", "pc_apps", "human_replay", "rf_person.js"));
RF.init(fs.readFileSync(path.join(__dirname, "..", "..", "..", "pc_apps", "human_replay", "rf_person_v1.json"), "utf8"));

function read_npy_f4(file) {
    const buf = fs.readFileSync(file);
    const hlen = buf.readUInt16LE(8);
    const header = buf.slice(10, 10 + hlen).toString();
    const m = header.match(/'descr':\s*'<f4'.*'shape':\s*\((\d+),\s*(\d+)\)/);
    if (!m) throw new Error("npy header fail: " + header);
    const rows = +m[1], cols = +m[2], start = 10 + hlen;
    const data = new Float32Array(rows * cols);
    for (let i = 0; i < rows * cols; i++) data[i] = buf.readFloatLE(start + i * 4);
    return { rows, cols, data };
}

const spec = JSON.parse(process.argv[2]);
const { rows, cols, data } = read_npy_f4(spec.file);
const features = [], probs = [];
let off = 0;
for (const n of spec.counts) {
    const frame = { n, x: new Float32Array(n), y: new Float32Array(n), z: new Float32Array(n) };
    const inten = new Float32Array(n);
    for (let i = 0; i < n; i++) {
        const o = (off + i) * cols;
        frame.x[i] = data[o]; frame.y[i] = data[o + 1];
        frame.z[i] = data[o + 2]; inten[i] = data[o + 3];
    }
    const fv = RF.extract(frame, inten);
    features.push(Array.from(fv));
    probs.push(RF.predict_person(fv));
    off += n;
}
process.stdout.write(JSON.stringify({ features, probs }));
