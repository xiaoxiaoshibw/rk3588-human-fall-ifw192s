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

  return {
    FALL: FALL, TRACK: TRACK, OBS: OBS, HARD_FALL: HARD_FALL,
    isNum: isNum, isInt: isInt, isTriple: isTriple, isEnum: isEnum,
    frameKey: frameKey, sourceKey: sourceKey, presentedKey: presentedKey,
    headerFromPayload: headerFromPayload, parseRos1String: parseRos1String,
    packClientMessage: packClientMessage,
    validCandidate: validCandidate, validSnapshot: validSnapshot,
    validState: validState, validAck: validAck, validEvent: validEvent,
    projectNdc: projectNdc, ndcToPixels: ndcToPixels,
    boxRect: boxRect, rectsIntersect: rectsIntersect,
    cacheKey: cacheKey, normalizePrefix: normalizePrefix, sameContext: sameContext,
    pruneRawFrames: pruneRawFrames, nextPresentedFrame: nextPresentedFrame,
    displayKey: displayKey, visualizationKey: visualizationKey,
    frameKeys: frameKeys, objectKeys: objectKeys
  };
});
