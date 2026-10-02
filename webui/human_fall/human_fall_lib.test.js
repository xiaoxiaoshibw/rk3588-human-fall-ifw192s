/* Real JS unit checks for human_fall_lib.js (run: node human_fall_lib.test.js). */
"use strict";
const assert = require("assert");
const HF = require("./human_fall_lib.js");

let passed = 0;
function test(name, fn) {
  try { fn(); passed++; console.log("ok   " + name); }
  catch (err) { console.error("FAIL " + name + ": " + err.message); process.exitCode = 1; }
}

test("packClientMessage has opcode+channel+uint32 string length+utf8", () => {
  const text = '{"a":1}';
  const buf = HF.packClientMessage(1, text);
  const dv = new DataView(buf.buffer);
  assert.strictEqual(buf.length, 9 + Buffer.byteLength(text));
  assert.strictEqual(buf[0], 0x01);
  assert.strictEqual(dv.getUint32(1, true), 1);
  assert.strictEqual(dv.getUint32(5, true), Buffer.byteLength(text));
  assert.strictEqual(Buffer.from(buf.subarray(9)).toString("utf8"), text);
});
test("packClientMessage channel id is little endian", () => {
  const buf = HF.packClientMessage(0x01020304, "x");
  assert.deepStrictEqual(Array.from(buf.subarray(1, 5)), [0x04, 0x03, 0x02, 0x01]);
});

test("frameKey requires integer seq and finite stamps", () => {
  assert.strictEqual(HF.frameKey(5, 100, 250), "5@100.250");
  assert.strictEqual(HF.frameKey(null, 100, 0), null);
  assert.strictEqual(HF.frameKey(5, NaN, 0), null);
  assert.strictEqual(HF.frameKey(5, 100, undefined), null);
});
test("sourceKey matches only exact seq+sec+nsec", () => {
  const a = { seq: 5, stamp_secs: 100, stamp_nsecs: 250 };
  const b = { seq: 5, stamp_secs: 100, stamp_nsecs: 251 };
  const c = { seq: 6, stamp_secs: 100, stamp_nsecs: 250 };
  assert.strictEqual(HF.sourceKey(a), "5@100.250");
  assert.notStrictEqual(HF.sourceKey(a), HF.sourceKey(b));
  assert.notStrictEqual(HF.sourceKey(a), HF.sourceKey(c));
});

test("headerFromPayload reads seq/secs/nsecs LE", () => {
  const b = new Uint8Array(12);
  const dv = new DataView(b.buffer);
  dv.setUint32(0, 42, true); dv.setUint32(4, 1000, true); dv.setUint32(8, 500000000, true);
  assert.deepStrictEqual(HF.headerFromPayload(b), { seq: 42, secs: 1000, nsecs: 500000000 });
  assert.strictEqual(HF.headerFromPayload(new Uint8Array(4)), null);
});

test("parseRos1String honours uint32 length and rejects truncation", () => {
  const text = '{"hello":"world"}';
  const enc = new TextEncoder().encode(text);
  const buf = new Uint8Array(4 + enc.length);
  new DataView(buf.buffer).setUint32(0, enc.length, true);
  buf.set(enc, 4);
  assert.strictEqual(HF.parseRos1String(buf), text);
  assert.strictEqual(HF.parseRos1String(new Uint8Array([5, 0, 0, 0, 65])), null); // len 5 > 1 byte
});

test("validSnapshot rejects unknown schema and non-finite geometry", () => {
  const good = {
    schema_version: 1, kind: "candidate_snapshot", session_id: "s", snapshot_id: "seq:1",
    time_epoch: 0, source: { seq: 1, stamp_secs: 10, stamp_nsecs: 0, source_stamp_s: 10, frame_id: "innolidar" },
    candidates: [{ candidate_id: "c0000", center_source_m: [3, 0, -0.5],
      bbox_source_min_m: [2.8, -0.2, -1], bbox_source_max_m: [3.2, 0.2, 0.5],
      range_m: { min: 3, median: 3.1, max: 3.3 }, point_count: 80 }]
  };
  assert.strictEqual(HF.validSnapshot(good), true);
  assert.strictEqual(HF.validSnapshot(Object.assign({}, good, { schema_version: 999 })), false);
  const bad = JSON.parse(JSON.stringify(good));
  bad.candidates[0].center_source_m = [3, 0, null];
  assert.strictEqual(HF.validSnapshot(bad), false);
  const noSrc = JSON.parse(JSON.stringify(good));
  noSrc.source.seq = null;
  assert.strictEqual(HF.validSnapshot(noSrc), false);
});

test("validState rejects unknown version and non-finite position", () => {
  const good = {
    schema_version: 1, kind: "target_state", session_id: "s", time_epoch: 0,
    fall_status: "upright", track_status: "locked", observability: "valid",
    position_source_m: [3, 0, -0.5], bbox_source_min_m: [2.8, -0.2, -1],
    bbox_source_max_m: [3.2, 0.2, 0.5], selection_version: 1,
    source: { seq: 1, stamp_secs: 10, stamp_nsecs: 0 }
  };
  assert.strictEqual(HF.validState(good), true);
  assert.strictEqual(HF.validState(Object.assign({}, good, { schema_version: 999 })), false);
  assert.strictEqual(HF.validState(Object.assign({}, good, { fall_status: "happy" })), false);
  assert.strictEqual(HF.validState(Object.assign({}, good, { position_source_m: [1, NaN, 2] })), false);
});

test("projectNdc + ndcToPixels handle DPR/viewport offsets", () => {
  const identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const ndc = HF.projectNdc(0.5, -0.25, 0, identity);
  assert.deepStrictEqual(ndc, { x: 0.5, y: -0.25, z: 0 });
  const px = HF.ndcToPixels(ndc, { width: 800, height: 600, left: 100, top: 50 },
                            { left: 40, top: 10 });
  assert.strictEqual(px.x, (0.75 * 800) + 60);
  assert.strictEqual(px.y, (0.625 * 600) + 40);
  assert.strictEqual(HF.projectNdc(1, 1, 1, [1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,0]), null);
});

test("boxRect / rectsIntersect handle missing corners", () => {
  const r = HF.boxRect([{ x: 10, y: 20 }, null, { x: 30, y: 40 }]);
  assert.deepStrictEqual(r, { x0: 10, y0: 20, x1: 30, y1: 40 });
  assert.strictEqual(HF.boxRect([null, null]), null);
  assert.strictEqual(HF.rectsIntersect(r, { x0: 0, y0: 0, x1: 15, y1: 25 }), true);
  assert.strictEqual(HF.rectsIntersect(r, { x0: 100, y0: 100, x1: 200, y1: 200 }), false);
});

test("normalizePrefix defaults and forces trailing slash", () => {
  assert.strictEqual(HF.normalizePrefix(null), "/human_fall/");
  assert.strictEqual(HF.normalizePrefix("/hf07_verify"), "/hf07_verify/");
  assert.strictEqual(HF.normalizePrefix("/human_fall/"), "/human_fall/");
});

test("cacheKey scopes a frame by its points topic", () => {
  assert.strictEqual(HF.cacheKey("/a/points", "5@1.2"), "/a/points|5@1.2");
  assert.notStrictEqual(HF.cacheKey("/a/points", "5@1.2"),
                        HF.cacheKey("/b/points", "5@1.2"));
});

test("same raw frame must still belong to current session and epoch", () => {
  const state = {session_id:"current", time_epoch:2};
  assert.strictEqual(HF.sameContext({session_id:"current", time_epoch:2}, state), true);
  assert.strictEqual(HF.sameContext({session_id:"old", time_epoch:2}, state), false);
  assert.strictEqual(HF.sameContext({session_id:"current", time_epoch:1}, state), false);
  assert.strictEqual(HF.sameContext({session_id:"current", time_epoch:-1}, state), false);
  assert.strictEqual(HF.sameContext(null, state), false);
});

test("nextPresentedFrame picks newest raw with output, forward-only", () => {
  const frames = [
    { order: 1, key: "1@1.0", rxMs: 0 },
    { order: 2, key: "2@1.1", rxMs: 0 },
    { order: 3, key: "3@1.2", rxMs: 0 },
  ];
  // no presented frame yet -> newest raw
  assert.strictEqual(HF.nextPresentedFrame(frames, null, () => false, 100, 800).order, 3);
  // presented at 1; only frame 2 has output -> 2 (newest with output, not 3)
  assert.strictEqual(
    HF.nextPresentedFrame(frames, { order: 1, rxMs: 0 }, (fr) => fr.key === "2@1.1", 100, 800).order, 2);
  // no newer output and not yet fallback: keep current (null)
  assert.strictEqual(
    HF.nextPresentedFrame(frames, { order: 2, rxMs: 100 }, () => false, 200, 800), null);
  // fallback to newest raw after fallbackMs so the live cloud still shows
  assert.strictEqual(
    HF.nextPresentedFrame(frames, { order: 2, rxMs: 0 }, () => false, 900, 800).order, 3);
  // never move backward
  assert.strictEqual(
    HF.nextPresentedFrame(frames, { order: 3, rxMs: 0 }, () => true, 900, 800), null);
});

test("pruneRawFrames drops stale frames, preserves order, rejects negative age", () => {
  const frames = [{ order: 1, rxMs: 5000 }, { order: 2, rxMs: 1500 },
                  { order: 3, rxMs: 1900 }, { order: 4, rxMs: 2100 }];
  // now=2000 ttl=1000: 1500/1900 kept; 5000 (future, age<0) and 2100 (>now) rejected
  assert.deepStrictEqual(HF.pruneRawFrames(frames, 2000, 1000).map((f) => f.order), [2, 3]);
  assert.deepStrictEqual(HF.pruneRawFrames([], 2000, 1000), []);
});

test("displayKey/visualizationKey/frameKeys wire mapping", () => {
  assert.strictEqual(HF.displayKey("/t", 7, 100, 5), "D|/t|7@100.5");
  assert.strictEqual(HF.displayKey("/t", -1, 100, 5), null);
  assert.strictEqual(HF.displayKey("/t", 7, 100, 1000000000), null);
  assert.strictEqual(HF.displayKey("", 7, 100, 5), null);
  const viz = { topic: "/t", wire_seq: 7, source: { seq: 99, stamp_secs: 100, stamp_nsecs: 5 } };
  assert.strictEqual(HF.visualizationKey(viz), "D|/t|7@100.5");
  const fk = HF.frameKeys({ seq: 7, secs: 100, nsecs: 5 }, "/t");
  assert.ok(fk.indexOf("S|7@100.5") >= 0);
  assert.ok(fk.indexOf("D|/t|7@100.5") >= 0);
});

test("objectKeys isolates selected display/source topic and rejects mismatches", () => {
  const src = { seq: 99, stamp_secs: 100, stamp_nsecs: 5 };
  const viz = { topic: "/human_fall/display_points", source_topic: "/innolidar_points",
               wire_seq: 7, source: src };
  const obj = { source: src, visualization: viz };
  assert.deepStrictEqual(HF.objectKeys(obj, "/human_fall/display_points"),
                         [HF.visualizationKey(viz)]);
  assert.deepStrictEqual(HF.objectKeys(obj, "/innolidar_points"), ["S|99@100.5"]);
  assert.deepStrictEqual(HF.objectKeys(obj, "/other/display_points"), []);
  // parent source disagrees with the mapping source -> no display key
  const mismatch = { source: { seq: 99, stamp_secs: 100, stamp_nsecs: 6 },
                     visualization: viz };
  assert.deepStrictEqual(HF.objectKeys(mismatch, "/human_fall/display_points"), []);
  // no mapping -> legacy/synthetic source key only
  assert.deepStrictEqual(
    HF.objectKeys({ source: { seq: 1, stamp_secs: 2, stamp_nsecs: 3 } }, "/any"),
    ["S|1@2.3"]);
});

test("raw ROS header frame rejects invalid ranges and fractions", () => {
  assert.strictEqual(HF.frameKey(1, 0, 0), null);
  assert.strictEqual(HF.frameKey(-1, 1, 0), null);
  assert.strictEqual(HF.frameKey(1, 1.5, 0), null);
  assert.strictEqual(HF.frameKey(1, 1, 1000000000), null);
  assert.strictEqual(HF.frameKey(1, 0, 1), "1@0.1");
});
console.log("HF lib checks: " + passed + " passed");
