/* test_session_contract.js — SESSION 契约回归（HUMAN-FUSION-UNIFY-R1 / STEP 1）。
 * 镜像 master session_selection.test.js 的 S01–S12 语义，叠加 fusion_lab 的 SHA 守卫特化。
 * 运行：node test_session_contract.js   （exit 0 = 全绿）
 */
"use strict";
const assert = require("node:assert/strict");
const A = require("./session_adapter.js");
const old = "cap_20261002_223757", mid = "cap_20261009_181716", latest = "cap_20261010_180751";
let tests = 0;
function test(name, fn) { fn(); console.log("PASS " + name); tests++; }
const rows = [{ sid: old, frames: 2, local: true }, { sid: mid, frames: 3, local: true }, { sid: latest, frames: 126, local: true }];

test("S01 default latest with reversed/shuffled input", () => {
    for (const list of [rows, rows.slice().reverse(), [rows[1], rows[2], rows[0]]])
        assert.equal(A.choose(list, null).sid, latest);
});
test("S02 valid explicit old sid respected", () => assert.equal(A.choose(rows, old).sid, old));
test("S03 unavailable/invalid/empty explicit sid visible safe fallback", () => {
    for (const sid of ["cap_20261010_235959", "../x", "", "<img onerror=x>"]) {
        const p = A.choose(rows, sid);
        assert.equal(p.sid, latest); assert.match(p.message, /回退/);
    }
    /* 无查询 (null/undefined) = 非显式：默认最新且无回退提示。 */
    assert.equal(A.choose(rows, null).message, "");
    assert.equal(A.choose(rows, undefined).sid, latest);
});
test("S04 incomplete/remote/error/empty rows excluded", () => {
    const list = rows.concat([{ sid: "cap_20261010_000000", frames: 0 },
        { sid: "cap_20261010_010000", frames: 1, local: false },
        { sid: "cap_20261010_020000", frames: 1, error: "bad meta" }]);
    assert.equal(A.choose(list, null).sid, latest);
});
test("S05 empty list finishes with clear notice", () => {
    const p = A.choose([], null); assert.equal(p.sid, ""); assert.match(p.message, /没有有效可用会话/);
});
test("S06 deterministic desc sorting and dedup", () => {
    const list = rows.concat([{ sid: mid, frames: 999 }]);
    assert.deepEqual(A.choose(list, null).list.map(s => s.sid), [latest, mid, old]);
});
test("S12 legal clip suffix respected, unsafe suffix rejected", () => {
    const sid = "cap_20261002_165321_clip_1989287-1989294";
    assert.equal(A.choose(rows.concat([{ sid, frames: 2, local: true }]), sid).sid, sid);
    for (const bad of [sid + "/file", sid + "..", sid + " ", sid + "_".repeat(100)]) {
        assert.equal(A.choose(rows, bad).sid, latest); assert.match(A.choose(rows, bad).message, /回退/);
    }
});
/* fusion_lab 特化：SHA 守卫。 */
test("F01 sha-mismatched session excluded from default but browsable if explicit", () => {
    const list = rows.map(r => ({ ...r, sha_idem: true }));
    list[2].sha_idem = false; /* latest 损坏 */
    const p = A.choose(list, null);
    assert.equal(p.default_sid, mid);                 /* 默认降级到次新 sha 一致者 */
    assert.equal(p.sid, mid);
    assert.deepEqual(p.sha_mismatch_sids, [latest]);  /* 暴露给前端 */
    assert.equal(A.choose(list, latest).sid, latest); /* 显式仍尊重（研究需浏览边界帧）*/
});
test("F02 all sha-mismatch falls back to raw list head, clearly non-eligible", () => {
    const list = rows.map(r => ({ ...r, sha_idem: false }));
    const p = A.choose(list, null);
    assert.equal(p.default_sid, latest);              /* 兜底仍给出最新可浏览，但全员 sha 失败已暴露 */
    assert.deepEqual(p.sha_mismatch_sids, [latest, "cap_20261009_181716", old]);
});
console.log(tests + " session contract tests passed");
