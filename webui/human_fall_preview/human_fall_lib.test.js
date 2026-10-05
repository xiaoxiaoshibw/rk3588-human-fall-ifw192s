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
/* ---- GL-04: explicit ground render / leveling / frustum / selection ---- */
function groundRenderSnap() {
  return {
    schema_version: 1, kind: "candidate_snapshot", session_id: "s", snapshot_id: "seq:1",
    time_epoch: 0,
    source: { seq: 1, stamp_secs: 10, stamp_nsecs: 0, frame_id: "innolidar" },
    units: { length: "m", angle: "rad" },
    coordinate: { source_frame: "innolidar", ground_derived_id: "gd-1", transform_status: "unknown" },
    calibration: { calibration_id: "cal-1", schema_version: 1, ground_status: "valid", ground_derived_id: "gd-1" },
    candidates: [{ candidate_id: "c0000", center_source_m: [3, 0, -0.5],
      bbox_source_min_m: [2.8, -0.2, -1], bbox_source_max_m: [3.2, 0.2, 0.5],
      range_m: { min: 3, median: 3.1, max: 3.3 }, point_count: 80,
      bbox_ground_from: "actual_points", bbox_ground_min_m: [0.1, -0.2, 0],
      bbox_ground_max_m: [1.1, 0.8, 1.2] }],
    ground_render: {
      schema_version: 1, kind: "ground_render", from_frame: "innolidar",
      to_frame: "ground_local", units: "m", calibration_id: "cal-1",
      geometry_schema_version: 1, ground_derived_id: "gd-1",
      R: [[1, 0, 0], [0, 1, 0], [0, 0, 1]], t: [0, 0, 1.5],
      support: { schema_version: 1, kind: "support_region", frame: "ground_local",
        ground_derived_id: "gd-1", polygon: [[0, 0], [1, 0], [1, 1], [0, 1]] }
    }
  };
}

test("validRotation accepts proper rotations and rejects scale/reflect/NaN", () => {
  assert.strictEqual(HF.validRotation([[1, 0, 0], [0, 1, 0], [0, 0, 1]]), true);
  assert.strictEqual(HF.validRotation([[0, -1, 0], [1, 0, 0], [0, 0, 1]]), true);
  assert.strictEqual(HF.validRotation([[2, 0, 0], [0, 1, 0], [0, 0, 1]]), false);
  assert.strictEqual(HF.validRotation([[1, 0, 0], [0, 1, 0], [0, 0, -1]]), false);
  assert.strictEqual(HF.validRotation([[NaN, 0, 0], [0, 1, 0], [0, 0, 1]]), false);
  assert.strictEqual(HF.validRotation([[1, 0], [0, 1]]), false);
});

test("applyRigid maps source point through R/t", () => {
  assert.deepStrictEqual(HF.applyRigid([1, 2, 3], [[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 1.5]),
                         [1, 2, 4.5]);
  assert.deepStrictEqual(HF.applyRigid([1, 0, 0], [[0, -1, 0], [1, 0, 0], [0, 0, 1]], [5, 0, 0]),
                         [5, 1, 0]);
  assert.strictEqual(HF.applyRigid([1, 2, 3], [[2, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 0, 0]), null);
});

test("parseGroundRender: missing block is unavailable, never identity", () => {
  const s = groundRenderSnap();
  delete s.ground_render;
  const r = HF.parseGroundRender(s);
  assert.strictEqual(r.status, "unavailable");
  assert.strictEqual(r.R, null);
  assert.strictEqual(r.t, null);
});

test("parseGroundRender: valid+bound block is ready and carries support budget", () => {
  const r = HF.parseGroundRender(groundRenderSnap());
  assert.strictEqual(r.status, "ready");
  assert.strictEqual(r.ground_derived_id, "gd-1");
  assert.strictEqual(r.support.status, "ready");
  assert.strictEqual(r.support.polygon.count, 4);
  assert.deepStrictEqual(r.support.polygon.indices, [0, 1, 2, 3]);
});

test("parseGroundRender: unsupported/invalid/unbound are refused without a matrix", () => {
  let s = groundRenderSnap(); s.ground_render.schema_version = 2;
  assert.strictEqual(HF.parseGroundRender(s).status, "unsupported");
  s = groundRenderSnap(); s.ground_render.from_frame = "other_lidar";
  assert.strictEqual(HF.parseGroundRender(s).status, "invalid");
  s = groundRenderSnap(); s.ground_render.calibration_id = "cal-2";
  assert.strictEqual(HF.parseGroundRender(s).status, "unbound");
  s = groundRenderSnap(); s.ground_render.ground_derived_id = "gd-2";
  assert.strictEqual(HF.parseGroundRender(s).status, "unbound");
  s = groundRenderSnap(); s.ground_render.R = [[1, 0, 0], [0, 2, 0], [0, 0, 1]];
  assert.strictEqual(HF.parseGroundRender(s).status, "invalid");
  s = groundRenderSnap(); s.coordinate.ground_derived_id = "gd-other";
  assert.strictEqual(HF.parseGroundRender(s).status, "unbound");
});

test("parseSupport: frame mismatch is unavailable, binding and shape enforced", () => {
  assert.strictEqual(HF.parseSupport(null, "gd-1", "ground_local").status, "unavailable");
  assert.strictEqual(HF.parseSupport({ schema_version: 1, kind: "support_region", frame: "source_frame",
    ground_derived_id: "gd-1" }, "gd-1", "ground_local").status, "unavailable");
  assert.strictEqual(HF.parseSupport({ schema_version: 1, kind: "support_region", frame: "ground_local",
    ground_derived_id: "gd-x" }, "gd-1", "ground_local").status, "unbound");
  assert.strictEqual(HF.parseSupport({ schema_version: 1, kind: "support_region", frame: "ground_local",
    ground_derived_id: "gd-1", polygon: [[0, 0], [1, "x"]] }, "gd-1", "ground_local").status, "invalid");
});

test("supportBudget: 0/3/3000/3001/9000 points, budget and original indices", () => {
  const mk = (n) => Array.from({ length: n }, (_, i) => [i, i * 2]);
  assert.strictEqual(HF.supportBudget(mk(0), 3000).count, 0);
  assert.strictEqual(HF.supportBudget(mk(3), 3000).count, 3);
  assert.strictEqual(HF.supportBudget(mk(3), 3000).sampled, false);
  assert.strictEqual(HF.supportBudget(mk(3000), 3000).sampled, false);
  const b = HF.supportBudget(mk(3001), 3000);
  assert.strictEqual(b.count, 3000); assert.strictEqual(b.sampled, true);
  assert.strictEqual(b.total, 3001); assert.strictEqual(b.sampled_from, 3001);
  assert.ok(b.indices.every((i) => i >= 0 && i < 3001));
  const b2 = HF.supportBudget(mk(9000), 3000);
  assert.strictEqual(b2.count, 3000);
  assert.strictEqual(b2.indices[0], 0);
  assert.ok(b2.indices[b2.indices.length - 1] < 9000);
});

test("candidateBox: ground box requires actual_points, never source corners", () => {
  const s = groundRenderSnap();
  const c = s.candidates[0];
  assert.deepStrictEqual(HF.candidateBox(c, "source").min, [2.8, -0.2, -1]);
  assert.deepStrictEqual(HF.candidateBox(c, "ground").min, [0.1, -0.2, 0]);
  const legacy = Object.assign({}, c, { bbox_ground_from: "unavailable",
    bbox_ground_min_m: null, bbox_ground_max_m: null });
  assert.strictEqual(HF.candidateBox(legacy, "ground"), null);
});

test("snapshotIdentity/sameSnapshot: same seq+stamp different frame does not match", () => {
  const a = groundRenderSnap();
  const b = groundRenderSnap();
  assert.strictEqual(HF.sameSnapshot(a, b), true);
  b.source.frame_id = "foreign";
  assert.strictEqual(HF.sameSnapshot(a, b), false);
  const c = groundRenderSnap(); c.calibration.calibration_id = "cal-2";
  assert.strictEqual(HF.sameSnapshot(a, c), false);
  assert.strictEqual(HF.snapshotIdentity({}), null);
});

test("projectPoint/boxProjectRect: behind and near/far clipping discard the box", () => {
  const id = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1];
  const p = HF.projectPoint(0.5, -0.25, 0, id);
  assert.strictEqual(p.behind, false); assert.strictEqual(p.clipped, false);
  assert.strictEqual(HF.boxProjectRect(id, [-0.5, -0.5, -0.5], [0.5, 0.5, 0.5]).behind, false);
  // w<=0 (camera behind)
  assert.strictEqual(HF.projectPoint(1, 1, 1, [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0]).behind, true);
  // z beyond far plane -> clipped -> whole box discarded
  const far = HF.boxProjectRect(id, [-0.5, -0.5, 2], [0.5, 0.5, 3]);
  assert.strictEqual(far.behind, true); assert.strictEqual(far.rect, null);
});

test("validateSelection: rejects stale identity, stale age and unknown candidate", () => {
  const a = groundRenderSnap(), b = groundRenderSnap();
  assert.deepStrictEqual(HF.validateSelection(a, "c0000", b, 1000, 500, 2000),
                         { ok: true, reason: "ok" });
  b.source.frame_id = "foreign";
  assert.strictEqual(HF.validateSelection(a, "c0000", b, 1000, 500, 2000).reason, "stale_snapshot");
  assert.strictEqual(HF.validateSelection(a, "c0000", a, 5000, 500, 2000).reason, "stale_freshness");
  assert.strictEqual(HF.validateSelection(a, "c9999", a, 1000, 500, 2000).reason, "unknown_candidate");
});

test("snapshotMeta reports frame/units/calibration/geometry/ground status honestly", () => {
  const m = HF.snapshotMeta(groundRenderSnap());
  assert.strictEqual(m.frame, "innolidar");
  assert.strictEqual(m.units.length, "m");
  assert.strictEqual(m.calibration_id, "cal-1");
  assert.strictEqual(m.ground_status, "valid");
  assert.strictEqual(m.ground_derived_id, "gd-1");
  assert.strictEqual(m.physical.ground_physical_verified, false);
});

/* ---- GL-04 offline synthetic fixture (shared consumption path) ---- */
test("packRos1String round-trips through parseRos1String", () => {
  const text = JSON.stringify({ kind: "candidate_snapshot", a: 1, zh: "配平" });
  assert.strictEqual(HF.parseRos1String(HF.packRos1String(text)), text);
});

test("syntheticScenario: valid wire snapshot/state, frame-matched, explicit R/t", () => {
  ["normal", "tilted", "no_extrinsics"].forEach((name) => {
    const s = HF.syntheticScenario(name);
    assert.ok(s, name + " scenario exists");
    assert.strictEqual(HF.validSnapshot(s.snapshot), true, name + " snapshot valid");
    assert.strictEqual(HF.validState(s.state), true, name + " state valid");
    assert.deepStrictEqual(HF.headerFromPayload(s.cloud), { seq: 7, secs: 1000, nsecs: 0 });
    // the raw cloud frame must match the snapshot so the shared frame match works
    assert.ok(HF.frameKeys(HF.headerFromPayload(s.cloud), "/human_fall/display_points")
      .indexOf(HF.objectKeys(s.snapshot, "/human_fall/display_points")[0]) >= 0);
  });
  assert.strictEqual(HF.parseGroundRender(HF.syntheticScenario("normal").snapshot).status, "ready");
  assert.strictEqual(HF.parseGroundRender(HF.syntheticScenario("tilted").snapshot).status, "ready");
  const none = HF.syntheticScenario("no_extrinsics").snapshot;
  const rn = HF.parseGroundRender(none);
  assert.strictEqual(rn.status, "unavailable");
  assert.strictEqual(rn.R, null);
  assert.strictEqual(HF.candidateBox(none.candidates[0], "ground"), null);
  assert.strictEqual(HF.syntheticScenario("bogus"), null);
});

/* ---- GL-04 R2 additions (appended; R1 assertion text above is unchanged) ---- */
test("headerFrameFromPayload reads real frame_id and tolerates a short header", () => {
  const cloud = HF.encodePC2("innolidar", 1, 2, 3, [[0, 0, 0, 1]]);
  assert.strictEqual(HF.headerFrameFromPayload(cloud), "innolidar");
  assert.strictEqual(HF.headerFrameFromPayload(new Uint8Array(12)), null);
});

function authGroundSnap() {
  const s = groundRenderSnap();
  s.coordinate.ground = JSON.parse(JSON.stringify(s.ground_render));
  s.ground = { status: "valid", frame: "innolidar",
    support_polygon: [[0, 0, 0], [4, 0, 0], [4, 2, 0], [0, 2, 0]],
    support_polyline: [[0, 0, 0], [4, 2, 0]],
    support_frame: "ground_local", support_ground_derived_id: "gd-1", support_schema_version: 1 };
  delete s.ground_render;
  return s;
}
test("parseGroundRender consumes coordinate.ground + ground.support_polygon", () => {
  const r = HF.parseGroundRender(authGroundSnap());
  assert.strictEqual(r.status, "ready");
  assert.strictEqual(r.support.status, "ready");
  assert.strictEqual(r.support.polygon.count, 4);
});
test("parseGroundRender: identical alias ok, conflicting alias rejected", () => {
  const f = authGroundSnap();
  f.ground_render = JSON.parse(JSON.stringify(f.coordinate.ground));
  assert.strictEqual(HF.parseGroundRender(f).status, "ready");
  const c = authGroundSnap();
  c.ground_render = JSON.parse(JSON.stringify(c.coordinate.ground));
  c.ground_render.t[0] = 9;
  assert.strictEqual(HF.parseGroundRender(c).status, "invalid");
});
test("parseGroundRender: unknown/none ground and bad schema are unqualified", () => {
  let s = authGroundSnap(); s.calibration.ground_status = "none";
  assert.notStrictEqual(HF.parseGroundRender(s).status, "ready");
  s = authGroundSnap(); s.calibration.ground_status = "unknown"; s.ground.status = "unknown";
  assert.notStrictEqual(HF.parseGroundRender(s).status, "ready");
  s = authGroundSnap(); s.calibration.schema_version = 2; s.coordinate.ground.geometry_schema_version = 2;
  assert.strictEqual(HF.parseGroundRender(s).status, "unsupported");
});
test("snapshotIdentity includes transform content (same id, changed R/t differs)", () => {
  const a = groundRenderSnap(), b = groundRenderSnap();
  b.ground_render.t[0] = 5;
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(b));
  assert.strictEqual(HF.sameSnapshot(a, b), false);
});
test("observationQualified requires current candidate and available verifier", () => {
  const s = groundRenderSnap(), st = { sensor_quality: { ground_monitor: { status: "ok" }, ground_verifier_available: true } };
  assert.strictEqual(HF.observationQualified(s, st).ok, true);
  const empty = groundRenderSnap(); empty.candidates = [];
  assert.strictEqual(HF.observationQualified(empty, st).ok, false);
  assert.strictEqual(HF.observationQualified(s, { sensor_quality: { ground_verifier_available: false } }).ok, false);
  assert.strictEqual(HF.observationQualified(s, { sensor_quality: { ground_monitor: { status: "unknown" } } }).ok, false);
});

/* ---- GL-04 R3 additions (appended; older assertion text is unchanged) ---- */
test("parseGroundRender refuses unknown/non-metre transform units (C14/V03)", () => {
  let s = groundRenderSnap(); s.ground_render.units = "mm";
  assert.notStrictEqual(HF.parseGroundRender(s).status, "ready");
  s = groundRenderSnap(); delete s.ground_render.units;
  assert.notStrictEqual(HF.parseGroundRender(s).status, "ready");
});

test("explicit 3D support with null/NaN Z is invalid, never flattened (C13/V02)", () => {
  let s = authGroundSnap(); s.ground.support_polygon[0][2] = null;
  assert.notStrictEqual(HF.parseGroundRender(s).support.status, "ready");
  s = authGroundSnap(); s.ground.support_polygon[1][2] = NaN;
  assert.notStrictEqual(HF.parseGroundRender(s).support.status, "ready");
  // declared 2D support (x,y only) is still valid on the plane
  const flat = authGroundSnap(); flat.ground.support_polygon = [[0, 0], [1, 0], [1, 1]];
  assert.strictEqual(HF.parseGroundRender(flat).support.status, "ready");
});

function obsState(s) {
  return { session_id: s.session_id, time_epoch: s.time_epoch, snapshot_id: s.snapshot_id,
    source: JSON.parse(JSON.stringify(s.source)),
    calibration: JSON.parse(JSON.stringify(s.calibration)),
    ground_derived_id: s.coordinate.ground_derived_id,
    sensor_quality: { ground_monitor: { status: "ok" }, ground_verifier_available: true } };
}
test("observationQualified requires snapshot/state calibration binding (C04/C06/V06)", () => {
  const s = groundRenderSnap();
  assert.strictEqual(HF.observationQualified(s, obsState(s)).ok, true);
  const snapNew = groundRenderSnap(); snapNew.calibration.calibration_id = "cal-2";
  assert.strictEqual(HF.observationQualified(snapNew, obsState(s)).ok, false);
  const stateNew = obsState(s); stateNew.calibration.calibration_id = "cal-2";
  assert.strictEqual(HF.observationQualified(s, stateNew).ok, false);
  // a schema both sides share is still unsupported, not a supported binding
  const bad = groundRenderSnap(), badState = obsState(bad);
  bad.calibration.schema_version = 2; badState.calibration.schema_version = 2;
  assert.strictEqual(HF.observationQualified(bad, badState).ok, false);
});
test("observationQualified rejects source/session/snapshot_id mismatch (C04/C06)", () => {
  const s = groundRenderSnap();
  const foreign = obsState(s); foreign.source.frame_id = "foreign";
  assert.strictEqual(HF.observationQualified(s, foreign).ok, false);
  const otherSession = obsState(s); otherSession.session_id = "other";
  assert.strictEqual(HF.observationQualified(s, otherSession).ok, false);
  const otherSnap = obsState(s); otherSnap.snapshot_id = "seq:99";
  assert.strictEqual(HF.observationQualified(s, otherSnap).ok, false);
  // missing state-side fields still qualify (legacy/partial state tolerated)
  assert.strictEqual(HF.observationQualified(s, { session_id: s.session_id, time_epoch: s.time_epoch,
    sensor_quality: { ground_verifier_available: true } }).ok, true);
});

/* ---- GL-04 R4 additions (appended; older assertion text is unchanged) ---- */
test("observationQualified compares full nullable ground-derived binding (C05/V06)", () => {
  const s = groundRenderSnap();
  const one = JSON.parse(JSON.stringify(s));
  one.coordinate.ground_derived_id = null; one.calibration.ground_derived_id = null;
  // one-sided missing: snapshot null while the state declares a known GDID
  const stKnown = obsState(s); stKnown.ground_derived_id = "gd-1";
  assert.strictEqual(HF.observationQualified(one, stKnown).ok, false);
  // explicit both-null legacy binding still matches
  const stNull = obsState(s); stNull.ground_derived_id = null;
  assert.strictEqual(HF.observationQualified(one, stNull).ok, true);
  // a state that omits the field entirely is tolerated (legacy/partial)
  const stMissing = obsState(s); delete stMissing.ground_derived_id;
  assert.strictEqual(HF.observationQualified(one, stMissing).ok, true);
});

test("selectionContextQualified separates selection from physical observation (V09/C01)", () => {
  const s = groundRenderSnap();
  assert.strictEqual(HF.selectionContextQualified(s, obsState(s)).ok, true);
  // legacy calibration-less / ground-less source-only context is still selectable
  const legacy = JSON.parse(JSON.stringify(s));
  legacy.calibration = { calibration_id: null, schema_version: null, ground_status: "unknown", ground_derived_id: null };
  legacy.coordinate = { source_frame: "innolidar", ground_relative_available: false, ground_derived_id: null };
  delete legacy.ground_render;
  const lst = obsState(s);
  lst.calibration = JSON.parse(JSON.stringify(legacy.calibration));
  lst.coordinate = JSON.parse(JSON.stringify(legacy.coordinate));
  lst.ground_derived_id = null;
  lst.sensor_quality = { ground_valid: false };
  assert.strictEqual(HF.selectionContextQualified(legacy, lst).ok, true);
  // an explicitly unsupported schema is still refused
  const bad = JSON.parse(JSON.stringify(s)); bad.calibration.schema_version = 2;
  assert.strictEqual(HF.selectionContextQualified(bad, obsState(s)).ok, false);
  // a mismatched calibration id is still refused
  const other = JSON.parse(JSON.stringify(s)); other.calibration.calibration_id = "cal-2";
  assert.strictEqual(HF.selectionContextQualified(other, obsState(s)).ok, false);
  // missing state-side calibration fields are tolerated for legacy/partial state
  assert.strictEqual(HF.selectionContextQualified(s,
    { session_id: s.session_id, time_epoch: s.time_epoch }).ok, true);
});

/* ---- GL-04 R5 additions (appended; older assertion text is unchanged) ---- */
test("observationQualified rejects known-vs-missing/null binding both ways (C05/V06)", () => {
  const s = groundRenderSnap();
  // known snapshot GDID, state omits the field entirely -> mismatch
  const stMissing = obsState(s); delete stMissing.ground_derived_id;
  assert.strictEqual(HF.observationQualified(s, stMissing).ok, false);
  // known snapshot schema, state declares calibration with null schema -> mismatch
  const stNullSchema = obsState(s); stNullSchema.calibration.schema_version = null;
  assert.strictEqual(HF.observationQualified(s, stNullSchema).ok, false);
  // both null/absent is still a legal legacy match
  const one = JSON.parse(JSON.stringify(s));
  one.coordinate.ground_derived_id = null; one.calibration.ground_derived_id = null;
  const stNull = obsState(s); stNull.ground_derived_id = null;
  assert.strictEqual(HF.observationQualified(one, stNull).ok, true);
  delete stNull.ground_derived_id;
  assert.strictEqual(HF.observationQualified(one, stNull).ok, true);
});

test("sourceAlignmentQualified accepts legacy source-only, gates verifier/schema (C01/C08/V09)", () => {
  const s = groundRenderSnap();
  const legacy = JSON.parse(JSON.stringify(s));
  legacy.calibration = { calibration_id: null, schema_version: null, ground_status: "unknown", ground_derived_id: null };
  legacy.coordinate = { source_frame: "innolidar", ground_relative_available: false, ground_derived_id: null };
  delete legacy.ground_render;
  const lst = { session_id: legacy.session_id, time_epoch: legacy.time_epoch,
    source: JSON.parse(JSON.stringify(legacy.source)),
    calibration: JSON.parse(JSON.stringify(legacy.calibration)),
    coordinate: JSON.parse(JSON.stringify(legacy.coordinate)),
    ground_derived_id: null, sensor_quality: { ground_valid: false } };
  // ground mode still refuses the calibration-less input, source mode accepts it
  assert.strictEqual(HF.observationQualified(legacy, lst).ok, false);
  assert.strictEqual(HF.sourceAlignmentQualified(legacy, lst).ok, true);
  // explicit unsupported schema refused on either side
  const bad = JSON.parse(JSON.stringify(legacy)); bad.calibration.schema_version = 2;
  assert.strictEqual(HF.sourceAlignmentQualified(bad, lst).ok, false);
  // an explicitly unavailable verifier clears the current source observation
  const nost = JSON.parse(JSON.stringify(lst)); nost.sensor_quality = { ground_verifier_available: false };
  assert.strictEqual(HF.sourceAlignmentQualified(legacy, nost).ok, false);
  // a known snapshot binding with a missing state GDID is refused
  const known = groundRenderSnap();
  const km = obsState(known); delete km.ground_derived_id;
  assert.strictEqual(HF.sourceAlignmentQualified(known, km).ok, false);
});

test("snapshotIdentity covers coordinate.source_frame and transform units (C11/V05)", () => {
  const a = groundRenderSnap();
  const b = groundRenderSnap(); b.coordinate.source_frame = "foreign";
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(b));
  const c = groundRenderSnap(); c.ground_render.units = "mm";
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(c));
});

test("parseGroundRender refuses a coordinate/source frame contradiction (V05/C05)", () => {
  const bad = groundRenderSnap(); bad.coordinate.source_frame = "foreign";
  assert.notStrictEqual(HF.parseGroundRender(bad).status, "ready");
  assert.strictEqual(HF.parseGroundRender(groundRenderSnap()).status, "ready");
});

test("parseGroundRender refuses an explicit non-metre source units.length (V03/C14)", () => {
  const s = groundRenderSnap();
  s.units.length = "mm";
  assert.notStrictEqual(HF.parseGroundRender(s).status, "ready");
  const legacy = groundRenderSnap();
  delete legacy.units.length;
  assert.strictEqual(HF.parseGroundRender(legacy).status, "ready");
});

test("parseSupport refuses explicit non-metre support_units, tolerates legacy (V02/C13/C14)", () => {
  const block = groundRenderSnap().ground_render;
  const bad = JSON.parse(JSON.stringify(block.support)); bad.units = "mm";
  assert.notStrictEqual(HF.parseSupport(bad, "gd-1", "ground_local").status, "ready");
  const legacy = JSON.parse(JSON.stringify(block.support));
  assert.strictEqual(HF.parseSupport(legacy, "gd-1", "ground_local").status, "ready");
});

test("snapshotIdentity covers units.length/ground kind+schema, candidateSignature covers center_ground_m (V05/C11)", () => {
  const a = groundRenderSnap();
  const b = groundRenderSnap(); b.units.length = "mm";
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(b));
  const c = groundRenderSnap(); c.ground_render.kind = "other";
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(c));
  const d = groundRenderSnap(); d.ground_render.schema_version = 2;
  assert.notStrictEqual(HF.snapshotIdentity(a), HF.snapshotIdentity(d));
  const cand = { candidate_id: "c0000", center_ground_m: [1, 2, 3], bbox_ground_from: "actual_points",
    bbox_ground_min_m: [0, 0, 0], bbox_ground_max_m: [1, 1, 1], point_count: 5 };
  const cand2 = JSON.parse(JSON.stringify(cand)); cand2.center_ground_m[0] = 99;
  assert.notStrictEqual(HF.candidateSignature(cand), HF.candidateSignature(cand2));
});

test("actualObservationQualified rejects explicit negative actual-observation flags (V07/C08)", () => {
  assert.strictEqual(HF.actualObservationQualified({}).ok, true);
  assert.strictEqual(HF.actualObservationQualified({ bbox_observed: false }).ok, false);
  assert.strictEqual(HF.actualObservationQualified({ position_source_from: "actual_points" }).ok, true);
  assert.strictEqual(HF.actualObservationQualified({ position_source_from: "unavailable" }).ok, false);
  assert.strictEqual(HF.actualObservationQualified({ position_source_from: "predicted" }).ok, false);
});

test("predictionDiagnosticQualified needs prediction+binding but not candidates (V07/C08)", () => {
  const snap = groundRenderSnap();
  const st = { session_id: snap.session_id, time_epoch: snap.time_epoch, snapshot_id: snap.snapshot_id,
    source: JSON.parse(JSON.stringify(snap.source)),
    calibration: JSON.parse(JSON.stringify(snap.calibration)),
    ground_derived_id: snap.coordinate.ground_derived_id, position_predicted: true };
  assert.strictEqual(HF.predictionDiagnosticQualified(snap, st).ok, true);
  assert.strictEqual(HF.predictionDiagnosticQualified(snap, Object.assign({}, st, { position_predicted: false })).ok, false);
  const bad = groundRenderSnap(); bad.units.length = "mm";
  assert.strictEqual(HF.predictionDiagnosticQualified(bad, st).ok, false);
  assert.strictEqual(HF.predictionDiagnosticQualified(null, st).ok, false);
});

test("selectionContextQualified refuses explicit wrong source units, tolerates legacy (V03/V09/C14)", () => {
  const snap = groundRenderSnap();
  const st = { session_id: snap.session_id, time_epoch: snap.time_epoch, snapshot_id: snap.snapshot_id,
    source: JSON.parse(JSON.stringify(snap.source)),
    calibration: JSON.parse(JSON.stringify(snap.calibration)),
    ground_derived_id: snap.coordinate.ground_derived_id };
  assert.strictEqual(HF.selectionContextQualified(snap, st).ok, true);
  const bad = groundRenderSnap(); bad.units.length = "mm";
  assert.strictEqual(HF.selectionContextQualified(bad, st).ok, false);
  const legacy = groundRenderSnap(); delete legacy.units.length;
  assert.strictEqual(HF.selectionContextQualified(legacy, st).ok, true);
});

test("sourcePositionQualified gates only explicit non-actual provenance (V07/V09/C08)", () => {
  assert.strictEqual(HF.sourcePositionQualified({}).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: null }).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: "actual_points" }).ok, true);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: "unavailable" }).ok, false);
  assert.strictEqual(HF.sourcePositionQualified({ position_source_from: "predicted" }).ok, false);
  assert.strictEqual(HF.sourcePositionQualified({ bbox_observed: false }).ok, true);
});

console.log("HF lib checks: " + passed + " passed");
