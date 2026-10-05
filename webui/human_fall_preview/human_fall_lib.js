/* HF-11 preview pure helpers (browser + Node).
 *
 * Kept free of DOM/THREE/WebSocket so the exact wire packing, frame keying,
 * payload/schema validation and projection math can be unit-tested with the
 * existing Node runtime. The browser layer (human_fall.js) loads this as
 * ``window.HF``; the Node checks/probes use ``require()``.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) { module.exports = factory(); }
  else { root.HF = factory(); }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";

  var FALL = ["unknown", "upright", "descending", "low_posture_unclassified",
              "suspected", "confirmed", "recovering"];
  var TRACK = ["unselected", "locked", "occluded", "ambiguous", "lost"];
  var OBS = ["valid", "degraded", "invalid"];
  var HARD_FALL = ["confirmed"];

  function isNum(v) { return typeof v === "number" && isFinite(v); }
  function isInt(v) { return isNum(v) && Math.floor(v) === v; }
  function isTriple(v) { return Array.isArray(v) && v.length === 3 && v.every(isNum); }
  function isEnum(value, list) { return list.indexOf(value) >= 0; }

  // A source frame is only usable for alignment when it carries a real seq and
  // both stamp seconds and nanoseconds (a bare seq would let a reboot or a
  // repeated seq overlay a wrong frame).
  function frameKey(seq, secs, nsecs) {
    if (!isInt(seq) || seq < 0 || seq > 4294967295 ||
        !isInt(secs) || secs < 0 || secs > 4294967295 ||
        !isInt(nsecs) || nsecs < 0 || nsecs >= 1000000000 ||
        (secs === 0 && nsecs === 0)) return null;
    return seq + "@" + secs + "." + nsecs;
  }
  function sourceKey(source) {
    if (!source || typeof source !== "object") return null;
    return frameKey(source.seq, source.stamp_secs, source.stamp_nsecs);
  }
  function presentedKey(frame) {
    if (!frame || typeof frame !== "object") return null;
    return frameKey(frame.seq, frame.secs, frame.nsecs);
  }
  // Raw ROS1 Header prefix: uint32 seq, uint32 stamp.secs, uint32 stamp.nsecs.
  function headerFromPayload(u8) {
    if (!u8 || u8.byteLength < 12) return null;
    var dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    return { seq: dv.getUint32(0, true), secs: dv.getUint32(4, true),
             nsecs: dv.getUint32(8, true) };
  }
  // Real frame_id of a raw PointCloud2 payload: it follows the 12-byte header
  // as a std_msgs string (uint32 length + UTF-8). Returns null when the payload
  // is truncated (a synthetic harness may send only the 12-byte header), so the
  // caller can skip the frame check rather than reject a valid short frame.
  function headerFrameFromPayload(u8) {
    if (!u8 || u8.byteLength < 16) return null;
    try {
      var dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
      var len = dv.getUint32(12, true);
      if (len <= 0 || 16 + len > u8.byteLength) return null;
      return new TextDecoder().decode(u8.subarray(16, 16 + len));
    } catch (e) { return null; }
  }
  // std_msgs/String ros1 wire format: uint32 length + UTF-8 bytes.
  function parseRos1String(u8) {
    if (!u8 || u8.byteLength < 4) return null;
    var dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
    var len = dv.getUint32(0, true);
    if (len > u8.byteLength - 4) return null;
    return new TextDecoder().decode(u8.subarray(4, 4 + len));
  }
  // Client message data wire format: opcode 0x01 + channel id u32 LE + payload.
  // The payload for ros1 std_msgs/String is uint32 LE length + UTF-8 JSON, so
  // the whole frame is 1 + 4 + 4 + utf8 length (the 4-byte string length is
  // mandatory; omitting it makes the bridge fail to deserialize).
  function packClientMessage(channelId, text) {
    var enc = new TextEncoder().encode(text);
    var buf = new Uint8Array(9 + enc.length);
    var dv = new DataView(buf.buffer);
    buf[0] = 0x01;
    dv.setUint32(1, channelId, true);
    dv.setUint32(5, enc.length, true);
    buf.set(enc, 9);
    return buf;
  }
  // Inverse of parseRos1String: uint32 LE length + UTF-8 (used by the offline
  // synthetic entry to feed the exact same message path as the board bridge).
  function packRos1String(text) {
    var enc = new TextEncoder().encode(String(text));
    var buf = new Uint8Array(4 + enc.length);
    new DataView(buf.buffer).setUint32(0, enc.length, true);
    buf.set(enc, 4);
    return buf;
  }

  function validCandidate(c) {
    if (!c || typeof c !== "object") return false;
    if (typeof c.candidate_id !== "string" || !c.candidate_id) return false;
    if (!isTriple(c.center_source_m)) return false;
    if (!isTriple(c.bbox_source_min_m) || !isTriple(c.bbox_source_max_m)) return false;
    if (c.range_m != null &&
        !(isNum(c.range_m.min) && isNum(c.range_m.median) && isNum(c.range_m.max))) return false;
    if (!isInt(c.point_count) || c.point_count < 0) return false;
    return true;
  }
  function validSnapshot(m) {
    if (!m || typeof m !== "object") return false;
    if (m.schema_version !== 1 || m.kind !== "candidate_snapshot") return false;
    if (typeof m.session_id !== "string" || !m.session_id) return false;
    if (typeof m.snapshot_id !== "string" || !m.snapshot_id) return false;
    if (!isInt(m.time_epoch)) return false;
    if (sourceKey(m.source) === null) return false;
    if (!Array.isArray(m.candidates)) return false;
    for (var i = 0; i < m.candidates.length; i++) if (!validCandidate(m.candidates[i])) return false;
    return true;
  }
  function validState(m) {
    if (!m || typeof m !== "object") return false;
    if (m.schema_version !== 1 || m.kind !== "target_state") return false;
    if (typeof m.session_id !== "string" || !m.session_id) return false;
    if (!isInt(m.time_epoch)) return false;
    if (!isEnum(m.fall_status, FALL)) return false;
    if (!isEnum(m.track_status, TRACK)) return false;
    if (!isEnum(m.observability, OBS)) return false;
    if (m.position_source_m != null && !isTriple(m.position_source_m)) return false;
    if (m.bbox_source_min_m != null && !isTriple(m.bbox_source_min_m)) return false;
    if (m.bbox_source_max_m != null && !isTriple(m.bbox_source_max_m)) return false;
    if (m.selection_version != null && !isInt(m.selection_version)) return false;
    if (m.source != null && sourceKey(m.source) === null &&
        m.source.seq != null) return false;
    return true;
  }
  function validAck(m) {
    return !!m && typeof m === "object" && m.schema_version === 1 &&
      m.kind === "selection_ack" && typeof m.request_id === "string" &&
      typeof m.accepted === "boolean";
  }
  function validEvent(m) {
    return !!m && typeof m === "object" && m.schema_version === 1 &&
      m.kind === "fall_event" && typeof m.event_id === "string" &&
      isEnum(m.fall_status, FALL);
  }

  // Column-major 4x4 (THREE .elements) projection with perspective divide.
  function projectNdc(x, y, z, e) {
    var cx = e[0] * x + e[4] * y + e[8] * z + e[12];
    var cy = e[1] * x + e[5] * y + e[9] * z + e[13];
    var cz = e[2] * x + e[6] * y + e[10] * z + e[14];
    var cw = e[3] * x + e[7] * y + e[11] * z + e[15];
    if (!isNum(cw) || Math.abs(cw) < 1e-12) return null;
    return { x: cx / cw, y: cy / cw, z: cz / cw };
  }
  // NDC -> canvas pixels using the canvas client rect and the viewport origin,
  // so DPR/viewport changes are handled by the caller's rect (CSS pixels).
  function ndcToPixels(ndc, rect, view) {
    if (!ndc || !rect) return null;
    var vx = view ? view.left : 0, vy = view ? view.top : 0;
    return { x: (ndc.x * 0.5 + 0.5) * rect.width + (rect.left - vx),
             y: (-ndc.y * 0.5 + 0.5) * rect.height + (rect.top - vy) };
  }
  function boxRect(points) {
    var x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity, any = false;
    for (var i = 0; i < points.length; i++) {
      var p = points[i];
      if (!p) continue;
      any = true;
      if (p.x < x0) x0 = p.x; if (p.x > x1) x1 = p.x;
      if (p.y < y0) y0 = p.y; if (p.y > y1) y1 = p.y;
    }
    return any ? { x0: x0, y0: y0, x1: x1, y1: y1 } : null;
  }
  function rectsIntersect(a, b) {
    return !!a && !!b && a.x1 >= b.x0 && a.x0 <= b.x1 && a.y1 >= b.y0 && a.y0 <= b.y1;
  }
  // Cache keys are scoped by the points topic as well as the frame key, so two
  // point-cloud sources sharing a frame_id can never alias one entry.
  function cacheKey(pointsTopic, key) {
    return (pointsTopic || "") + "|" + (key || "");
  }
  function normalizePrefix(prefix) {
    if (!prefix || typeof prefix !== "string") return "/human_fall/";
    return prefix.charAt(prefix.length - 1) === "/" ? prefix : prefix + "/";
  }
  function sameContext(a, b) {
    return !!(a && b && typeof a.session_id === "string" && a.session_id &&
      a.session_id === b.session_id && isInt(a.time_epoch) &&
      a.time_epoch >= 0 && a.time_epoch === b.time_epoch);
  }
  // A display-stream frame is identified by its topic and its wire header seq +
  // stamp (rospy assigns the seq per topic, so the source seq cannot be copied).
  function displayKey(topic, wireSeq, secs, nsecs) {
    if (typeof topic !== "string" || !topic) return null;
    if (!isInt(wireSeq) || wireSeq < 0) return null;
    if (!isInt(secs) || secs < 0 || secs > 4294967295) return null;
    if (!isInt(nsecs) || nsecs < 0 || nsecs >= 1000000000) return null;
    return "D|" + topic + "|" + wireSeq + "@" + secs + "." + nsecs;
  }
  // Key of a candidate/state's optional visualization mapping. The display
  // cloud preserves the source stamp, so the wire seq + source stamp identifies
  // the matching display frame.
  function visualizationKey(viz) {
    if (!viz || typeof viz !== "object") return null;
    var src = viz.source;
    if (!src || typeof src !== "object") return null;
    return displayKey(viz.topic, viz.wire_seq, src.stamp_secs, src.stamp_nsecs);
  }
  // Both possible keys for a raw cloud header: source-frame key (used with
  // ?points=/innolidar_points) and display key (used with the sampled stream).
  function frameKeys(header, topic) {
    var keys = [];
    if (!header) return keys;
    var sk = frameKey(header.seq, header.secs, header.nsecs);
    if (sk) keys.push("S|" + sk);
    var dk = displayKey(topic, header.seq, header.secs, header.nsecs);
    if (dk) keys.push(dk);
    return keys;
  }
  // Match keys for a candidate/state against the topic the page is actually
  // subscribed to. With a visualization mapping the choice is explicit and
  // isolated: selecting the mapping's source_topic yields only the source key,
  // selecting its display topic yields only the display key AND requires the
  // mapping's source header to equal the object's own source header, and any
  // other topic (or a mismatched source) yields no keys -- an S/D pair can
  // never both match and bypass the mapping. Without a mapping, legacy/synthetic
  // source frames still match by source key.
  function objectKeys(obj, selectedTopic) {
    if (!obj || typeof obj !== "object") return [];
    var viz = obj.visualization;
    if (viz && typeof viz === "object" && typeof viz.topic === "string" && viz.topic) {
      if (selectedTopic === viz.source_topic) {
        var sk = sourceKey(obj.source);
        return sk ? ["S|" + sk] : [];
      }
      if (selectedTopic === viz.topic) {
        var src = viz.source;
        var parent = obj.source;
        if (!src || typeof src !== "object" || !parent ||
            parent.seq !== src.seq ||
            parent.stamp_secs !== src.stamp_secs ||
            parent.stamp_nsecs !== src.stamp_nsecs) return [];
        var dk = visualizationKey(viz);
        return dk ? [dk] : [];
      }
      return [];
    }
    var legacy = sourceKey(obj.source);
    return legacy ? ["S|" + legacy] : [];
  }
  // Keep only raw frames received within ttlMs (bounded cache pruning). A
  // negative age (clock jump / stale rxMs) is rejected, never treated as fresh.
  function pruneRawFrames(frames, now, ttlMs) {
    var keep = [];
    for (var i = 0; i < (frames || []).length; i++) {
      var f = frames[i];
      if (isNum(f.rxMs) && isNum(now) && (now - f.rxMs) >= 0 &&
          (now - f.rxMs) <= ttlMs) keep.push(f);
    }
    return keep;
  }
  // Choose which cached raw frame to render. frames are oldest-first with
  // strictly increasing order; presented is {order, rxMs} or null; match(key)
  // reports whether processed output exists for that raw frame. Selection is
  // forward-only and never draws old boxes on a newer scene. When no newer
  // frame has output, fall back to the newest raw after fallbackMs so a stalled
  // algorithm still shows the live cloud (with unknown state).
  function nextPresentedFrame(frames, presented, match, now, fallbackMs) {
    if (!frames || !frames.length) return null;
    var newest = frames[frames.length - 1];
    if (!presented || !isInt(presented.order)) return newest;
    for (var i = frames.length - 1; i >= 0; i--) {
      var f = frames[i];
      if (f.order <= presented.order) break;
      if (typeof match === "function" && match(f)) return f;
    }
    var wait = isNum(fallbackMs) ? fallbackMs : 800;
    if (newest.order > presented.order && isNum(presented.rxMs) &&
        isNum(now) && (now - presented.rxMs) >= wait) return newest;
    return null;
  }

  /* ================= GL-04 explicit ground render / leveling ==================
   * Single documented consumption entry for the optional synthetic rendering
   * extension (snapshot.ground_render). Production build_snapshot does not emit
   * this block, so the browser must never derive R/t from ``normal``/``offset_m``,
   * never treat a missing block as identity, and never fabricate a support region
   * from the decorative grid. Modes only change which coordinate array is drawn;
   * candidate ids / requests stay bound to the original snapshot. */
  var GROUND_LOCAL_FRAME = "ground_local";
  var SUPPORT_MAX_POINTS = 3000;

  // 3x3 row-major rotation must be finite and orthonormal with det +1; a scaled
  // or reflected matrix would silently distort the scene (no identity fallback).
  function validRotation(R) {
    if (!Array.isArray(R) || R.length !== 3) return false;
    for (var i = 0; i < 3; i++) if (!isTriple(R[i])) return false;
    function dot(a, b) { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
    for (var r = 0; r < 3; r++) if (Math.abs(dot(R[r], R[r]) - 1) > 1e-4) return false;
    if (Math.abs(dot(R[0], R[1])) > 1e-4) return false;
    if (Math.abs(dot(R[0], R[2])) > 1e-4) return false;
    if (Math.abs(dot(R[1], R[2])) > 1e-4) return false;
    var det = R[0][0] * (R[1][1] * R[2][2] - R[1][2] * R[2][1]) -
              R[0][1] * (R[1][0] * R[2][2] - R[1][2] * R[2][0]) +
              R[0][2] * (R[1][0] * R[2][1] - R[1][1] * R[2][0]);
    return Math.abs(det - 1) <= 1e-4;
  }
  function applyRigid(p, R, t) {
    if (!isTriple(p) || !validRotation(R) || !isTriple(t)) return null;
    return [
      R[0][0] * p[0] + R[0][1] * p[1] + R[0][2] * p[2] + t[0],
      R[1][0] * p[0] + R[1][1] * p[1] + R[1][2] * p[2] + t[1],
      R[2][0] * p[0] + R[2][1] * p[1] + R[2][2] * p[2] + t[2]
    ];
  }
  function _badGround(status, reason) {
    return { status: status, reason: reason, R: null, t: null, from_frame: null,
             to_frame: null, calibration_id: null, ground_derived_id: null,
             support: { status: "unavailable", reason: "no_transform" } };
  }
  function _flatArray(m) { return Array.isArray(m) ? m.map(_flatArray).join(",") : String(m); }
  // Canonical content of a versioned ground block, used both for the legacy
  // alias conflict check (root cause 1) and for the selection identity (V05).
  function groundTransformKey(block) {
    if (!block || typeof block !== "object") return "";
    return [block.kind, block.schema_version, block.from_frame, block.to_frame,
            block.units, block.calibration_id,
            block.ground_derived_id, block.geometry_schema_version,
            _flatArray(block.R), _flatArray(block.t)].join("|");
  }
  // An explicit top-level source length unit other than metres makes every
  // source/ground length downstream unquantified: it can never be shown as a
  // metre measurement nor feed a metre transform/support layer (V03/C14). A
  // missing unit is legacy/partial and stays tolerated.
  function _sourceUnitsUnsupported(snapshot) {
    var u = snapshot && snapshot.units;
    return !!(u && typeof u === "object" && u.length != null && u.length !== "m");
  }
  function _parseGroundBlock(block, snapshot, support) {
    if (block === undefined || block === null) return _badGround("unavailable", "no_ground_block");
    if (typeof block !== "object") return _badGround("invalid", "not_object");
    if (_sourceUnitsUnsupported(snapshot)) return _badGround("invalid", "source_units");
    if (block.kind != null && block.kind !== "ground_render" &&
        block.kind !== "coordinate_ground") return _badGround("invalid", "kind");
    if (block.schema_version !== 1) return _badGround("unsupported", "schema_version");
    var src = snapshot.source || {};
    if (typeof block.from_frame !== "string" || !block.from_frame ||
        block.from_frame !== src.frame_id) return _badGround("invalid", "from_frame_mismatch");
    // A snapshot whose declared coordinate.source_frame contradicts its own
    // source.frame_id is not a current known coordinate (V05/C05).
    var scf = snapshot.coordinate && snapshot.coordinate.source_frame;
    if (scf != null && src.frame_id != null && scf !== src.frame_id)
      return _badGround("invalid", "coordinate_source_frame_mismatch");
    if (block.to_frame !== GROUND_LOCAL_FRAME) return _badGround("invalid", "to_frame");
    // An explicit transform must declare metric units: an unknown or non-metre
    // length (e.g. mm) would silently scale the scene, so it is never shown as
    // ready and never labelled as "m" (V03/C14).
    if (block.units !== "m") return _badGround("invalid", "units");
    if (!validRotation(block.R) || !isTriple(block.t)) return _badGround("invalid", "rotation_translation");
    var cal = snapshot.calibration || {}, coord = snapshot.coordinate || {};
    if (cal.schema_version !== 1) return _badGround("unsupported", "calibration_schema");
    if (typeof block.calibration_id !== "string" || !block.calibration_id ||
        block.calibration_id !== cal.calibration_id) return _badGround("unbound", "calibration_id");
    if (typeof block.ground_derived_id !== "string" || !block.ground_derived_id ||
        block.ground_derived_id !== coord.ground_derived_id ||
        (cal.ground_derived_id != null && cal.ground_derived_id !== block.ground_derived_id))
      return _badGround("unbound", "ground_derived_id");
    if (block.geometry_schema_version != null &&
        block.geometry_schema_version !== cal.schema_version)
      return _badGround("unbound", "geometry_schema_version");
    // Ground status is part of the qualification: a valid transform under an
    // unknown/none ground must not be presented as a leveled current frame.
    var gstatus = cal.ground_status != null ? cal.ground_status
      : (snapshot.ground && snapshot.ground.status != null ? snapshot.ground.status : "unknown");
    if (gstatus !== "valid")
      return { status: "unqualified", reason: "ground_status_" + gstatus, R: null, t: null,
               from_frame: null, to_frame: null, calibration_id: null, ground_derived_id: null,
               support: { status: "unavailable", reason: "ground_status_" + gstatus } };
    return { status: "ready", reason: "ok", R: block.R, t: block.t,
             from_frame: block.from_frame, to_frame: block.to_frame,
             calibration_id: block.calibration_id, ground_derived_id: block.ground_derived_id,
             units: block.units != null ? block.units : null, support: support };
  }
  // Support is consumed from snapshot.ground.support_polygon/support_polyline
  // (the user-requested location) with its frame/units/version binding declared
  // inline; the legacy block.support is only a fallback for the R1 alias.
  function _normalizedSupport(snapshot, block) {
    var g = snapshot.ground;
    if (g && typeof g === "object" &&
        (g.support_polygon != null || g.support_polyline != null)) {
      return parseSupport({
        schema_version: g.support_schema_version != null ? g.support_schema_version : 1,
        kind: g.support_kind || "support_region",
        frame: g.support_frame != null ? g.support_frame : block.to_frame,
        ground_derived_id: g.support_ground_derived_id != null
          ? g.support_ground_derived_id : block.ground_derived_id,
        units: g.support_units != null ? g.support_units : block.units,
        polygon: g.support_polygon != null ? g.support_polygon : null,
        polyline: g.support_polyline != null ? g.support_polyline : null
      }, block.ground_derived_id, block.to_frame);
    }
    return parseSupport(block.support, block.ground_derived_id, block.to_frame);
  }
  function parseGroundRender(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return _badGround("invalid", "no_snapshot");
    var coord = snapshot.coordinate || {};
    var authoritative = coord.ground, legacy = snapshot.ground_render, block;
    if (authoritative != null && legacy != null) {
      if (groundTransformKey(authoritative) !== groundTransformKey(legacy))
        return _badGround("invalid", "conflicting_ground_sources");
      block = authoritative;
    } else {
      block = authoritative != null ? authoritative : legacy;
    }
    var base = _parseGroundBlock(block, snapshot, null);
    if (base.status !== "ready") return base;
    base.support = _normalizedSupport(snapshot, block);
    return base;
  }
  // Uniform subsample that preserves the original index of every kept point and
  // reports its provenance (total + sampled_from) so a consumer can tell a full
  // support region from a budgeted sample.
  function supportBudget(points, maxPoints) {
    if (!Array.isArray(points)) return null;
    var total = points.length;
    var budget = isInt(maxPoints) && maxPoints > 0 ? maxPoints : SUPPORT_MAX_POINTS;
    var kept = [], indices = [], i;
    if (total <= budget) {
      for (i = 0; i < total; i++) { kept.push(points[i]); indices.push(i); }
    } else {
      var step = total / budget;
      for (i = 0; i < budget; i++) { var idx = Math.floor(i * step); kept.push(points[idx]); indices.push(idx); }
    }
    return { points: kept, indices: indices, total: total, sampled_from: total,
             sampled: total > budget, count: kept.length };
  }
  function validSupportPoints(list) {
    if (!Array.isArray(list)) return null;
    for (var i = 0; i < list.length; i++) {
      var p = list[i];
      if (!Array.isArray(p) || p.length < 2 || !isNum(p[0]) || !isNum(p[1])) return null;
      // A declared 2D ground_local support may use the plane; an explicit third
      // component is a 3D coordinate and must be a finite number. A null/NaN Z
      // is unknown, never a point to flatten onto the plane (V02/C13).
      if (p.length >= 3 && !isNum(p[2])) return null;
    }
    return list;
  }
  function parseSupport(support, groundDerivedId, frame) {
    var want = frame || GROUND_LOCAL_FRAME;
    if (!support || typeof support !== "object") return { status: "unavailable", reason: "no_support" };
    if (support.schema_version !== 1 || support.kind !== "support_region")
      return { status: "invalid", reason: "support_schema" };
    // An explicit non-metre support unit can never be drawn as a metre layer; a
    // missing unit is legacy/partial and stays tolerated (V02/C13/C14).
    if (support.units != null && support.units !== "m")
      return { status: "invalid", reason: "support_units" };
    if (support.ground_derived_id !== groundDerivedId)
      return { status: "unbound", reason: "support_ground_derived_id" };
    if (support.frame !== want)
      return { status: "unavailable", reason: "frame_not_provided", frame: support.frame };
    var poly = support.polygon != null ? validSupportPoints(support.polygon) : null;
    var line = support.polyline != null ? validSupportPoints(support.polyline) : null;
    if (support.polygon != null && !poly) return { status: "invalid", reason: "polygon_points" };
    if (support.polyline != null && !line) return { status: "invalid", reason: "polyline_points" };
    return { status: "ready", frame: support.frame,
             polygon: poly ? supportBudget(poly, SUPPORT_MAX_POINTS) : null,
             polyline: line ? supportBudget(line, SUPPORT_MAX_POINTS) : null };
  }
  // Ground boxes may only be the explicitly published actual-point AABB; a source
  // AABB must never be turned into a ground box by transforming two corners.
  function sourceCandidateBox(c) {
    if (!c || !isTriple(c.bbox_source_min_m) || !isTriple(c.bbox_source_max_m)) return null;
    return { min: c.bbox_source_min_m, max: c.bbox_source_max_m };
  }
  function groundCandidateBox(c) {
    if (!c || c.bbox_ground_from !== "actual_points") return null;
    if (!isTriple(c.bbox_ground_min_m) || !isTriple(c.bbox_ground_max_m)) return null;
    return { min: c.bbox_ground_min_m, max: c.bbox_ground_max_m };
  }
  function candidateBox(c, mode) {
    return mode === "ground" ? groundCandidateBox(c) : sourceCandidateBox(c);
  }
  function candidateSignature(c) {
    if (!c || typeof c !== "object") return "";
    var parts = [c.candidate_id,
      (c.center_source_m || []).join(","),
      (c.center_ground_m || []).join(","),
      (c.bbox_source_min_m || []).join(","),
      (c.bbox_source_max_m || []).join(","), c.point_count];
    if (c.bbox_ground_from === "actual_points") {
      parts.push("g", (c.bbox_ground_min_m || []).join(","),
                 (c.bbox_ground_max_m || []).join(","));
    }
    return parts.join("|");
  }
  // A selectable snapshot identity binds session/epoch/snapshot/source/calibration/
  // geometry; two frames that share seq+stamp but differ in frame/label do not match.
  function snapshotIdentity(s) {
    if (!s || typeof s !== "object") return null;
    var sk = sourceKey(s.source);
    if (!sk) return null;
    var cal = s.calibration || {}, coord = s.coordinate || {};
    // frame_id is part of the identity: the same seq+stamp published under a
    // foreign frame must not be treated as the same frame (V05).
    var frame = s.source && s.source.frame_id != null ? s.source.frame_id : "";
    // The full render transform content is part of the identity: a same seq+stamp
    // snapshot whose R/t changed must not let a cached selection through (V05).
    var block = coord.ground != null ? coord.ground : s.ground_render;
    // coordinate.source_frame is part of the identity too: an in-place change of
    // the declared source frame must invalidate an old rendered choice (V05/C11).
    var coordFrame = coord.source_frame != null ? coord.source_frame : "";
    // The declared top-level source length unit is part of the identity: an
    // in-place change of `units.length` must invalidate a cached choice (V05).
    var unitsLength = (s.units && typeof s.units === "object" && s.units.length != null)
      ? s.units.length : "";
    return [s.session_id, s.time_epoch, s.snapshot_id, sk, frame, coordFrame,
            s.schema_version, unitsLength,
            cal.calibration_id, cal.schema_version, cal.ground_status,
            coord.ground_derived_id, coord.transform_status,
            groundTransformKey(block)].join("|");
  }
  function sameSnapshot(a, b) {
    var ia = snapshotIdentity(a), ib = snapshotIdentity(b);
    return ia !== null && ia === ib;
  }
  // Binding consistency shared by the observation and selection consumers. The
  // identity fields (session/epoch/snapshot/source frame) must agree when both
  // sides carry them. Calibration id and ground-derived id are compared as full
  // nullable values: once the state declares one, a null on either side is a
  // version mismatch -- even if only one side is missing -- but a state that
  // omits the field entirely (legacy/partial) is tolerated so the original
  // source mode is never dead-locked (V05/V06/C01).
  var _normBind = function (v) { return v == null ? null : v; };
  function _bindingMismatch(snapshot, state) {
    if (snapshot.session_id != null && state.session_id != null &&
        snapshot.session_id !== state.session_id) return "session_mismatch";
    if (isInt(snapshot.time_epoch) && isInt(state.time_epoch) &&
        snapshot.time_epoch !== state.time_epoch) return "epoch_mismatch";
    if (snapshot.snapshot_id != null && state.snapshot_id != null &&
        snapshot.snapshot_id !== state.snapshot_id) return "snapshot_id_mismatch";
    var ss = snapshot.source, ts = state.source;
    if (ss && ts) {
      var ssk = sourceKey(ss), tsk = sourceKey(ts);
      if (ssk !== null && tsk !== null && ssk !== tsk) return "source_frame_mismatch";
      if (ss.frame_id != null && ts.frame_id != null && ss.frame_id !== ts.frame_id)
        return "source_frame_mismatch";
    }
    var cal = snapshot.calibration || {}, tcal = state.calibration || {};
    var coord = snapshot.coordinate || {};
    var sgd = coord.ground_derived_id != null ? coord.ground_derived_id
      : (cal.ground_derived_id != null ? cal.ground_derived_id : null);
    // A state that declares a calibration binding (real kind=target_state) must
    // agree with the snapshot on every nullable field: both null/absent is a
    // legal legacy match, but a known value against a null/undefined counterpart
    // is a version mismatch -- even when only one side is missing (V05/V06/C05).
    // A state that omits the whole binding (legacy/partial pure-function input)
    // keeps the old tolerance so source-only never dead-locks (V09/C01).
    if (state.calibration != null || state.ground_derived_id !== undefined) {
      if (_normBind(cal.calibration_id) !== _normBind(tcal.calibration_id))
        return "calibration_id_mismatch";
      if (_normBind(cal.schema_version) !== _normBind(tcal.schema_version))
        return "schema_mismatch";
      if (_normBind(sgd) !== _normBind(state.ground_derived_id))
        return "ground_derived_id_mismatch";
    } else {
      if (tcal.calibration_id !== undefined && cal.calibration_id !== tcal.calibration_id)
        return "calibration_id_mismatch";
      if (state.ground_derived_id !== undefined && sgd !== state.ground_derived_id)
        return "ground_derived_id_mismatch";
    }
    return null;
  }
  // A current target observation additionally requires a supported calibration
  // schema, a valid ground and an available verifier. A ready baseline or a
  // fresh state alone never substitutes for a current candidate observation;
  // unknown sensors must show unknown/null (V06/C04/C06/C10).
  function observationQualified(snapshot, state) {
    if (!snapshot || typeof snapshot !== "object") return { ok: false, reason: "no_snapshot" };
    if (!Array.isArray(snapshot.candidates) || !snapshot.candidates.length)
      return { ok: false, reason: "no_candidate" };
    if (!state || typeof state !== "object") return { ok: false, reason: "no_state" };
    if (_sourceUnitsUnsupported(snapshot)) return { ok: false, reason: "source_units" };
    var cal = snapshot.calibration || {}, tcal = state.calibration || {};
    if (cal.schema_version !== 1 ||
        (tcal.schema_version != null && tcal.schema_version !== 1))
      return { ok: false, reason: "unsupported_schema" };
    var bm = _bindingMismatch(snapshot, state);
    if (bm) return { ok: false, reason: bm };
    var gstatus = cal.ground_status != null ? cal.ground_status
      : (snapshot.ground && snapshot.ground.status != null ? snapshot.ground.status : "unknown");
    if (gstatus !== "valid") return { ok: false, reason: "ground_" + gstatus };
    var sq = state.sensor_quality;
    if (sq && typeof sq === "object") {
      if (sq.ground_verifier_available === false)
        return { ok: false, reason: "verifier_unavailable" };
      var gm = sq.ground_monitor;
      if (gm && typeof gm === "object" && gm.status != null && gm.status !== "ok")
        return { ok: false, reason: "ground_monitor_" + gm.status };
    }
    return { ok: true, reason: "ok" };
  }
  // The operator's *current selection context* is a different consumer from an
  // existing target's physical observation: a fresh source selection -- even a
  // legacy calibration-less/source-only one -- must not require an existing
  // target or a valid ground. An explicitly wrong schema or a mismatched
  // binding is still refused (V09/C01/C04/C06).
  function selectionContextQualified(snapshot, state) {
    if (!snapshot || typeof snapshot !== "object") return { ok: false, reason: "no_snapshot" };
    if (!Array.isArray(snapshot.candidates) || !snapshot.candidates.length)
      return { ok: false, reason: "no_candidate" };
    if (!state || typeof state !== "object") return { ok: false, reason: "no_state" };
    // A wrong explicit source unit makes every source length unquantified, so a
    // fresh list/click/drag choice in that frame can never be accepted (V03/C14).
    if (_sourceUnitsUnsupported(snapshot)) return { ok: false, reason: "source_units" };
    var cal = snapshot.calibration || {}, tcal = state.calibration || {};
    if (cal.schema_version != null && cal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    if (tcal.schema_version != null && tcal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    var bm = _bindingMismatch(snapshot, state);
    if (bm) return { ok: false, reason: bm };
    return { ok: true, reason: "ok" };
  }
  // Source-mode current measurement qualification. The raw source frame has no
  // leveled ground, so a legacy/source-only target is a valid current actual
  // observation as long as the binding agrees and no verifier says the stream is
  // unusable. An explicit unsupported schema is still refused; ground status and
  // verifier availability are only demanded in ground mode (V09/C01/C08).
  function sourceAlignmentQualified(snapshot, state) {
    if (!snapshot || typeof snapshot !== "object") return { ok: false, reason: "no_snapshot" };
    if (!Array.isArray(snapshot.candidates) || !snapshot.candidates.length)
      return { ok: false, reason: "no_candidate" };
    if (!state || typeof state !== "object") return { ok: false, reason: "no_state" };
    if (_sourceUnitsUnsupported(snapshot)) return { ok: false, reason: "source_units" };
    var cal = snapshot.calibration || {}, tcal = state.calibration || {};
    if (cal.schema_version != null && cal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    if (tcal.schema_version != null && tcal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    var bm = _bindingMismatch(snapshot, state);
    if (bm) return { ok: false, reason: bm };
    var sq = state.sensor_quality;
    if (sq && typeof sq === "object") {
      if (sq.ground_verifier_available === false)
        return { ok: false, reason: "verifier_unavailable" };
      var gm = sq.ground_monitor;
      if (gm && typeof gm === "object" && gm.status != null && gm.status !== "ok")
        return { ok: false, reason: "ground_monitor_" + gm.status };
    }
    return { ok: true, reason: "ok" };
  }
  // An explicit negative actual-observation flag means the target's pose is not
  // a current actual measurement, so it may never endorse a physical fall even
  // if the values are otherwise present. An omitted flag stays legacy-tolerant
  // (V07/C08).
  function actualObservationQualified(c) {
    if (!c || typeof c !== "object") return { ok: false, reason: "no_state" };
    if (c.bbox_observed === false) return { ok: false, reason: "bbox_not_observed" };
    if (c.position_source_from != null && c.position_source_from !== "actual_points")
      return { ok: false, reason: "position_source_" + c.position_source_from };
    return { ok: true, reason: "ok" };
  }
  // Position-source provenance only (no bbox flag): an explicit non-actual source
  // means the source XYZ/centre is NOT a current actual measurement, so it must
  // not be shown as the current position nor labelled measured. An omitted/null
  // value stays legacy-tolerant and actual_points is a real measurement; this is
  // deliberately narrower than actualObservationQualified so a bbox-only negative
  // flag never erases a legal actual_points raw centre (V07/V09/C08).
  function sourcePositionQualified(c) {
    if (!c || typeof c !== "object") return { ok: false, reason: "no_state" };
    if (c.position_source_from != null && c.position_source_from !== "actual_points")
      return { ok: false, reason: "position_source_" + c.position_source_from };
    return { ok: true, reason: "ok" };
  }
  // A prediction box is an independent diagnostic: it does not need a non-empty
  // candidate list, but it still requires a fresh, correctly bound snapshot in
  // supported units. It is never a current position/fall observation (V07/C08).
  function predictionDiagnosticQualified(snapshot, state) {
    if (!state || typeof state !== "object" || state.position_predicted !== true)
      return { ok: false, reason: "not_predicted" };
    if (!snapshot || typeof snapshot !== "object") return { ok: false, reason: "no_snapshot" };
    if (_sourceUnitsUnsupported(snapshot)) return { ok: false, reason: "source_units" };
    var cal = snapshot.calibration || {}, tcal = state.calibration || {};
    if (cal.schema_version != null && cal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    if (tcal.schema_version != null && tcal.schema_version !== 1)
      return { ok: false, reason: "unsupported_schema" };
    var bm = _bindingMismatch(snapshot, state);
    if (bm) return { ok: false, reason: bm };
    return { ok: true, reason: "ok" };
  }
  function snapshotMeta(s) {
    if (!s || typeof s !== "object") return null;
    var cal = s.calibration || {}, coord = s.coordinate || {}, gr = s.ground || {},
        ver = s.verification || {};
    var src = s.source || {};
    return {
      frame: s.source ? s.source.frame_id : null,
      source_frame: s.source ? s.source.frame_id : null,
      seq: src.seq != null ? src.seq : null,
      stamp_s: (src.stamp_secs != null)
        ? (src.stamp_secs + (src.stamp_nsecs || 0) / 1e9) : null,
      units: s.units || null,
      schema_version: s.schema_version,
      calibration_id: cal.calibration_id != null ? cal.calibration_id : null,
      calibration_schema: cal.schema_version != null ? cal.schema_version : null,
      ground_status: cal.ground_status != null ? cal.ground_status
        : (gr.status != null ? gr.status : "unknown"),
      ground_derived_id: coord.ground_derived_id != null ? coord.ground_derived_id
        : (cal.ground_derived_id != null ? cal.ground_derived_id : null),
      transform_status: coord.transform_status != null ? coord.transform_status : "unknown",
      // Geometry schema of the explicit transform, reported separately from the
      // calibration/snapshot schema so the three versions are never conflated
      // (V03/C03).
      geometry_schema: (coord.ground && coord.ground.geometry_schema_version != null)
        ? coord.ground.geometry_schema_version
        : (coord.geometry_schema_version != null ? coord.geometry_schema_version : null),
      horizontal_basis: coord.horizontal_basis != null ? coord.horizontal_basis : null,
      ground_frame: coord.ground_frame != null ? coord.ground_frame : null,
      physical: {
        ground_physical_verified: ver.ground_physical_verified === true,
        extrinsics_verified: ver.extrinsics_verified === true,
        imu_alignment_verified: ver.imu_alignment_verified === true
      }
    };
  }
  // Clip-space projection. w<=0 means behind the camera; ndc.z outside [-1,1]
  // means outside the near/far planes. Both are treated as unusable corners.
  function projectPoint(x, y, z, e) {
    if (!e) return { behind: true, clipped: true };
    var cx = e[0] * x + e[4] * y + e[8] * z + e[12];
    var cy = e[1] * x + e[5] * y + e[9] * z + e[13];
    var cz = e[2] * x + e[6] * y + e[10] * z + e[14];
    var cw = e[3] * x + e[7] * y + e[11] * z + e[15];
    if (!isNum(cw) || cw <= 1e-9) return { behind: true, clipped: true };
    var ndc = { x: cx / cw, y: cy / cw, z: cz / cw };
    if (!isNum(ndc.x) || !isNum(ndc.y) || !isNum(ndc.z)) return { behind: true, clipped: true };
    return { x: ndc.x, y: ndc.y, z: ndc.z, behind: false,
             clipped: ndc.z < -1 || ndc.z > 1 };
  }
  // Project all 8 box corners through the current camera matrix and return the
  // min/max pixel rect. Any behind/clipped corner discards the whole box so a
  // partially visible box can never draw a false full-screen rectangle.
  function boxProjectRect(mvp, min, max) {
    if (!mvp || !isTriple(min) || !isTriple(max)) return { rect: null, behind: true, reason: "invalid" };
    var pts = [], xs = [min[0], max[0]], ys = [min[1], max[1]], zs = [min[2], max[2]];
    for (var a = 0; a < 2; a++) for (var b = 0; b < 2; b++) for (var d = 0; d < 2; d++) {
      var p = projectPoint(xs[a], ys[b], zs[d], mvp);
      if (!p || p.behind || p.clipped)
        return { rect: null, behind: true, reason: p && p.clipped ? "clipped" : "behind" };
      pts.push(p);
    }
    return { rect: boxRect(pts), behind: false, reason: "ok" };
  }
  // Re-validate the exact snapshot+candidate at submit time. The captured render
  // closure must never be trusted: the currently presented snapshot must be the
  // same identity and still fresh, and the candidate must still exist in it.
  function validateSelection(snapshot, candidateId, currentSnapshot, nowMs, rxMs, ttlMs) {
    if (!snapshot || !currentSnapshot || !sameSnapshot(snapshot, currentSnapshot))
      return { ok: false, reason: "stale_snapshot" };
    if (!(isNum(nowMs) && isNum(rxMs) && (nowMs - rxMs) >= 0 && (nowMs - rxMs) <= ttlMs))
      return { ok: false, reason: "stale_freshness" };
    var list = snapshot.candidates || [];
    for (var i = 0; i < list.length; i++)
      if (list[i] && list[i].candidate_id === candidateId) return { ok: true, reason: "ok" };
    return { ok: false, reason: "unknown_candidate" };
  }

  /* ---- offline synthetic fixture (shared by the browser entry + Node tests) ----
   * Pure: it only builds a ros1 PointCloud2 byte array and the matching
   * candidate_snapshot/target_state JSON objects. The explicit R/t and support
   * are declared in the snapshot; nothing here connects to a board. */
  function rotX(deg) {
    var r = deg * Math.PI / 180, c = Math.cos(r), s = Math.sin(r);
    return [[1, 0, 0], [0, c, -s], [0, s, c]];
  }
  function encodePC2(frameId, seq, secs, nsecs, points) {
    var parts = [], total = 0;
    function push(u8) { parts.push(u8); total += u8.length; }
    function str(s) { var b = new TextEncoder().encode(s), l = new Uint8Array(4);
      new DataView(l.buffer).setUint32(0, b.length, true); push(l); push(b); }
    function u32(v) { var b = new Uint8Array(4); new DataView(b.buffer).setUint32(0, v >>> 0, true); push(b); }
    function u8(v) { push(new Uint8Array([v & 255])); }
    function f32(v) { var b = new Uint8Array(4); new DataView(b.buffer).setFloat32(0, v, true); push(b); }
    u32(seq); u32(secs); u32(nsecs); str(frameId);
    u32(1); u32(points.length);
    var fields = [["x", 0], ["y", 4], ["z", 8], ["intensity", 12]], f;
    u32(fields.length);
    for (f = 0; f < fields.length; f++) { str(fields[f][0]); u32(fields[f][1]); u8(7); u32(1); }
    u8(0); u32(16); u32(points.length * 16); u32(points.length * 16);
    for (var i = 0; i < points.length; i++) {
      f32(points[i][0]); f32(points[i][1]); f32(points[i][2]); f32(points[i][3]);
    }
    u8(1);
    var out = new Uint8Array(total), off = 0;
    for (var p = 0; p < parts.length; p++) { out.set(parts[p], off); off += parts[p].length; }
    return out;
  }
  function syntheticScenario(name) {
    var seq = 7, secs = 1000, nsecs = 0, frame = "innolidar";
    var R = null, t = null, calId = "syn-cal-1", gdId = "syn-gd-1";
    if (name === "normal") { R = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]; t = [0, 0, 1.5]; }
    else if (name === "tilted") { R = rotX(12); t = [0, 0, 1.5]; }
    else if (name === "no_extrinsics") { R = null; t = null; }
    else return null;
    function toSource(p) {
      if (!R) return p.slice();
      var d = [p[0] - t[0], p[1] - t[1], p[2] - t[2]];
      return [R[0][0] * d[0] + R[1][0] * d[1] + R[2][0] * d[2],
              R[0][1] * d[0] + R[1][1] * d[1] + R[2][1] * d[2],
              R[0][2] * d[0] + R[1][2] * d[1] + R[2][2] * d[2]];
    }
    var groundG = [], personG = [], i, j, z;
    for (i = -2; i <= 2; i += 0.5) for (j = -2; j <= 2; j += 0.5) groundG.push([i, j, 0]);
    for (z = 0; z <= 1.6; z += 0.2) for (var dx = -0.15; dx <= 0.16; dx += 0.15) personG.push([3 + dx, 0.1, z]);
    var xyz = [], k;
    for (k = 0; k < groundG.length; k++) { var sg = toSource(groundG[k]); xyz.push([sg[0], sg[1], sg[2], 10]); }
    for (k = 0; k < personG.length; k++) { var sp = toSource(personG[k]); xyz.push([sp[0], sp[1], sp[2], 200]); }
    var cloud = encodePC2(frame, seq, secs, nsecs, xyz);
    function bbox(list) {
      var lo = [Infinity, Infinity, Infinity], hi = [-Infinity, -Infinity, -Infinity], c = [0, 0, 0];
      for (var a = 0; a < list.length; a++) for (var q = 0; q < 3; q++) {
        if (list[a][q] < lo[q]) lo[q] = list[a][q];
        if (list[a][q] > hi[q]) hi[q] = list[a][q];
        c[q] += list[a][q];
      }
      for (var q2 = 0; q2 < 3; q2++) c[q2] /= list.length;
      return { lo: lo, hi: hi, c: c };
    }
    var pb = bbox(personG), center = toSource(pb.c);
    var dist = Math.sqrt(center[0] * center[0] + center[1] * center[1] + center[2] * center[2]);
    var snapshot = {
      schema_version: 1, kind: "candidate_snapshot", session_id: "syn", snapshot_id: "seq:" + seq,
      time_epoch: 0,
      source: { seq: seq, stamp_secs: secs, stamp_nsecs: nsecs, source_stamp_s: secs + nsecs / 1e9, frame_id: frame },
      units: { length: "m", angle: "rad" },
      coordinate: { source_frame: frame, reference_frame: null,
        horizontal_basis: R ? "ground_tangent" : "raw_xy_uncalibrated",
        ground_relative_available: !!R, ground_frame: R ? "ground_local" : null,
        transform_status: "unknown", ground_derived_id: R ? gdId : null },
      calibration: { calibration_id: calId, schema_version: 1,
        ground_status: R ? "valid" : "invalid", ground_derived_id: R ? gdId : null },
      ground: R ? { status: "valid", frame: frame, normal: null, offset_m: null, sensor_height_m: null } : null,
      settings: {}, quality: { ground_valid: !!R, candidate_count: 1, input_point_count: xyz.length },
      candidates: [{
        candidate_id: "c0000", semantic: "unknown", point_count: personG.length,
        center_source_m: center, center_ground_m: R ? pb.c : null,
        bbox_source_min_m: toSource(pb.lo), bbox_source_max_m: toSource(pb.hi),
        bbox_ground_min_m: R ? pb.lo : null, bbox_ground_max_m: R ? pb.hi : null,
        bbox_ground_from: R ? "actual_points" : "unavailable",
        range_m: { min: dist, median: dist, max: dist },
        axis: { ambiguous: false }, quality: { sufficient_points: true }
      }],
      verification: { ground_physical_verified: false, extrinsics_verified: false, imu_alignment_verified: false },
      ground_render: R ? {
        schema_version: 1, kind: "ground_render", from_frame: frame, to_frame: "ground_local",
        units: "m", calibration_id: calId, geometry_schema_version: 1, ground_derived_id: gdId,
        R: R, t: t,
        support: { schema_version: 1, kind: "support_region", frame: "ground_local",
          ground_derived_id: gdId, polygon: [[-2, -2], [2, -2], [2, 2], [-2, 2]] }
      } : null,
      note: "synthetic/offline GL-04 fixture"
    };
    var smin = toSource(pb.lo), smax = toSource(pb.hi);
    var state = {
      schema_version: 1, kind: "target_state", session_id: "syn", time_epoch: 0,
      track_id: "t0001", track_status: "locked", fall_status: "upright", observability: "valid",
      position_source_m: center, position_predicted: false,
      bbox_source_min_m: [Math.min(smin[0], smax[0]), Math.min(smin[1], smax[1]), Math.min(smin[2], smax[2])],
      bbox_source_max_m: [Math.max(smin[0], smax[0]), Math.max(smin[1], smax[1]), Math.max(smin[2], smax[2])],
      bbox_ground_min_m: R ? pb.lo : null, bbox_ground_max_m: R ? pb.hi : null,
      bbox_ground_from: R ? "actual_points" : "unavailable",
      range_m: { median: dist }, selection_version: 1,
      source: { seq: seq, stamp_secs: secs, stamp_nsecs: nsecs, frame_id: frame },
      calibration: { calibration_id: calId, ground_status: R ? "valid" : "invalid" },
      baseline: { status: "ready" }, event_persistence: { degraded: false, persisted_count: 0 },
      visualization: null
    };
    return { cloud: cloud, snapshot: snapshot, state: state,
             logTimeNs: BigInt(secs) * 1000000000n + BigInt(nsecs) };
  }

  var API = {
    FALL: FALL, TRACK: TRACK, OBS: OBS, HARD_FALL: HARD_FALL,
    isNum: isNum, isInt: isInt, isTriple: isTriple, isEnum: isEnum,
    frameKey: frameKey, sourceKey: sourceKey, presentedKey: presentedKey,
    headerFromPayload: headerFromPayload, headerFrameFromPayload: headerFrameFromPayload,
    parseRos1String: parseRos1String,
    packClientMessage: packClientMessage, packRos1String: packRos1String,
    validCandidate: validCandidate, validSnapshot: validSnapshot,
    validState: validState, validAck: validAck, validEvent: validEvent,
    projectNdc: projectNdc, ndcToPixels: ndcToPixels,
    boxRect: boxRect, rectsIntersect: rectsIntersect,
    cacheKey: cacheKey, normalizePrefix: normalizePrefix, sameContext: sameContext,
    pruneRawFrames: pruneRawFrames, nextPresentedFrame: nextPresentedFrame,
    displayKey: displayKey, visualizationKey: visualizationKey,
    frameKeys: frameKeys, objectKeys: objectKeys,
    GROUND_LOCAL_FRAME: GROUND_LOCAL_FRAME, SUPPORT_MAX_POINTS: SUPPORT_MAX_POINTS,
    validRotation: validRotation, applyRigid: applyRigid,
    parseGroundRender: parseGroundRender, parseSupport: parseSupport,
    supportBudget: supportBudget, sourceCandidateBox: sourceCandidateBox,
    groundCandidateBox: groundCandidateBox, candidateBox: candidateBox,
    candidateSignature: candidateSignature, snapshotIdentity: snapshotIdentity,
    sameSnapshot: sameSnapshot, snapshotMeta: snapshotMeta,
    groundTransformKey: groundTransformKey, observationQualified: observationQualified,
    selectionContextQualified: selectionContextQualified,
    sourceAlignmentQualified: sourceAlignmentQualified,
    actualObservationQualified: actualObservationQualified,
    sourcePositionQualified: sourcePositionQualified,
    predictionDiagnosticQualified: predictionDiagnosticQualified,
    projectPoint: projectPoint, boxProjectRect: boxProjectRect,
    validateSelection: validateSelection, encodePC2: encodePC2
  };
  // The offline scenario generator builds geometry and wire bytes, so it is a
  // Node evidence helper only. The browser branch must never expose or execute
  // it -- the browser entry loads a precomputed static JSON fixture instead.
  if (typeof module === "object" && module.exports) API.syntheticScenario = syntheticScenario;
  return API;
});
