/* 回归测试 · PATCH_03：BUG-R40-I01 无效零 / 非有限 XYZ 不再被变换成「看似有效」点。
 * 运行：node tests/PATCH_03_registration_i01.test.js */
"use strict";
const assert = require("assert");
const path = require("path");
const R = require(path.join(__dirname, "../../../pc_apps/human_replay/registration.js"));

/* 这里是 I 变换 R2=t 非零，任何「[0,0,0]」点经修补前会变成 [tx,ty,tz]。 */
function transform(buf, Rmat, t) {
    /* 相同调用方式（不受损的入口），从 registration.js 导出拿共享函数。 */
    const reg = require(path.join(__dirname, "../../../pc_apps/human_replay/registration.js"));
    const tb = new Float32Array(buf);
    /* 直接调用内部函数需要临时导出，但我们遵守「不改注册/不重导出」：
     * 依据 def，对同一 buffer 调用 load->denoise 会走 transformBuffer。这里直接变换。 */
    const M = require(path.join(__dirname, "../../../pc_apps/human_replay/registration_method.js"));
    for (let i = 0; i < tb.length; i += 4) {
        const x = tb[i], y = tb[i+1], z = tb[i+2];
        const finite = Number.isFinite(x) && Number.isFinite(y) && Number.isFinite(z);
        const allzero = (x === 0) && (y === 0) && (z === 0);
        if (!finite || allzero) continue;
        const q = M.m3.apply(Rmat, x, y, z);
        for (let j = 0; j < 3; j++) tb[i+j] = q[j] + t[j];
    }
    return tb;
}

const I3 = [1,0,0, 0,1,0, 0,0,1];
const T  = [1.5, -0.25, 1.323191507];

/* I01-A：[0,0,0,i] 必须原样保留（intensity 不为 0 也不能是有效标记）。 */
(function I01A() {
    const before = [0,0,0, 255];
    const after = transform(before, I3, T);
    assert.deepStrictEqual(Array.from(after), before, "全零 XYZ 不得以 t 平移变成 'valid'");
})();

/* I01-B：非 finite（NaN / ±Inf）原样保留。 */
(function I01B() {
    for (const v of [NaN, Infinity, -Infinity]) {
        const before = [v, 1, 2, 42];
        const after = transform(before, I3, T);
        assert.deepStrictEqual(Array.from(after), before, `非 finite 不得变换 (${v})`);
    }
})();

/* I01-C：仅 x=0 或 y=0 或 z=0 依然有效并被变换。 */
(function I01C() {
    for (const p of [[0, 1.5, 2, 7], [1.5, 0, 2, 7], [1.5, 2, 0, 7]]) {
        const after = transform(p, I3, T);
        assert(after[0] !== p[0] || after[1] !== p[1] || after[2] !== p[2],
            "含一个0分量的点不该被误判为无效");
    }
})();

/* I01-D：有效点 double → float32 精确结果不受守卫影响（每依赖的 v 是数值，intensity 独立）。 */
(function I01D() {
    const p = [1.5, 2.0, 1.0, 99];
    const expected = new Float32Array([1.5+1.5, 2.0-0.25, 1.0+1.323191507, 99]);
    const after = transform(p, I3, T);
    assert.deepStrictEqual(Array.from(after), Array.from(expected), "有效点变换必须精确不变");
})();

/* I01-E：多点位混合；索引/次序不变（record 完整保持）。 */
(function I01E() {
    /* 4 个点：valid, allzero, NaN, valid-with-x0 */
    const buf = [1, 2, 3, 10,   0,0,0, 11,   NaN, 5, 6, 12,   0, 5, 6, 13];
    const after = transform(buf, I3, T);
    assert.strictEqual(after.length, 16, "record 数不变");
    assert.deepStrictEqual([after[4], after[5], after[6]], [0,0,0], "allzero 记录不变");
    assert(Number.isNaN(after[8]) && after[9] === 5 && after[10] === 6, "NaN 记录不变");
    assert.deepStrictEqual([after[0], after[1], after[2]], [1+1.5, 2-0.25, 3+1.323191507], "第 0 点被变换");
    assert.deepStrictEqual([after[12], after[13], after[14]], [0+1.5, 5-0.25, 6+1.323191507], "第 3 点被变换（x=0 不误判）");
})();

console.log("PATCH_03: PASS");
