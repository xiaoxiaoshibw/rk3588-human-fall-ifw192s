/* HF-11 preview layer for the existing IFW192S point-cloud page.
 *
 * Renders candidate / target boxes, drag-to-select, stance baseline, fall
 * status and event history on top of the untouched original renderer. All
 * algorithm output comes from the RK3588 node over the existing
 * foxglove_bridge; the browser only renders and sends operator selection/
 * baseline requests using the bridge's clientPublish capability (no vehicle
 * control, no external service).
 *
 * Wire/帧/校验规则 (see docs/human_fall/HF11_WIRE_FRAME_FIXES.md):
 *  - a client ros1 std_msgs/String payload is uint32 LE length + UTF-8 JSON,
 *    after opcode 1 + channel id (packed by HF.packClientMessage);
 *  - a box is overlaid only when the candidate/state source frame exactly
 *    matches the currently presented cloud frame (seq + secs + nsecs), never
 *    on a bare seq match or with no presented frame;
 *  - every inbound payload is schema/kind/finiteness validated; invalid or
 *    unknown data shows unknown and hides the affected box/label but never
 *    deletes already-stored events;
 *  - a late state never rolls back a newer selection_version/epoch.
 *
 * Namespace is configurable for the on-board verification link:
 *   ?prefix=/hf07_verify/&points=/hf07_verify/points
 * defaulting to /human_fall/ + /innolidar_points (production).
 */
(function () {
  "use strict";
  var HF = window.HF;

  var params = new URLSearchParams(location.search);
  var PREFIX = HF.normalizePrefix(params.get("prefix"));
  // The main script reads the same ?points= and subscribes to exactly one cloud
  // source, so the verify cloud never mixes with /innolidar_points.
  var POINTS_TOPIC = (typeof HF_POINTS_TOPIC !== "undefined")
    ? HF_POINTS_TOPIC : (params.get("points") || "/innolidar_points");
  var CAND_TOPIC = PREFIX + "candidates";
  var STATE_TOPIC = PREFIX + "state";
  var EVENT_TOPIC = PREFIX + "event";
  var ACK_TOPIC = PREFIX + "selection_ack";
  var REQ_TOPIC = PREFIX + "selection_request";

  [CAND_TOPIC, STATE_TOPIC, EVENT_TOPIC, ACK_TOPIC].forEach(function (t) {
    if (TOPICS.indexOf(t) < 0) TOPICS.push(t);
  });

  var hf = {
    capabilities: [], serverInfo: null, channelReady: false, channelId: 1,
    lastState: null, lastStateRxMs: 0, presented: null, candidates: new Map(),
    events: [], eventIds: {}, pending: {}, selectMode: false, drag: null,
    order: { session: null, epoch: null, sel: null }, retiredSessions: [],
    rawFrames: [], rawOrder: 0, rawCount: 0, presentCount: 0, presentMarks: [],
    // GL-04: coordinate mode + explicit ground render (source fallback default).
    coordMode: (params.get("mode") === "ground") ? "ground" : "source",
    groundRender: HF.parseGroundRender(null), lastMeta: null,
    synthetic: params.get("synthetic"), syntheticScene: null,
    // Honest performance: actual renderer.render count/monotonic window + DPR.
    renderCount: 0, renderMarks: [], lastDpr: null,
    // Qualification transition guard for one-shot GPU invalidation.
    wasObserved: false
  };
  window.__hf = hf;

  // Monotonic where available: ages/rates must not jump with the wall clock.
  function hfNow() {
    return (window.performance && typeof window.performance.now === "function")
      ? window.performance.now() : Date.now();
  }
  function hfLog(msg, level) { log(msg, level); }
  function hfSetText(id, text, cls) {
    var el = $(id); if (!el) return;
    el.textContent = text; el.className = cls || "";
  }
  function hfFresh(ts) { return ts > 0 && (hfNow() - ts) < 2000; }
  function hfNewRequestId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      try { return window.crypto.randomUUID(); } catch (e) { /* fall through */ }
    }
    return "r-" + hfNow().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  /* ---- raw frame cache + output-matched presentation ----
   * The algorithm output lags the newest raw cloud by ~1 frame (decode+compute
   * plus queue). Rendering the newest raw frame would therefore never align with
   * the candidate/state boxes. Instead the last RAW_CACHE raw payloads are kept
   * and the newest one that already has a matching processed output is presented
   * (forward-only, with a bounded fallback to the newest raw when no output
   * arrives, so a stalled algorithm still shows the live cloud + unknown). */
  var HF_RAW_CACHE = 8, HF_RAW_TTL_MS = 2000, HF_PRESENT_FALLBACK_MS = 800;
  function hfOutputForFrame(frame) {
    var keys = frame.keys || [];
    for (var i = 0; i < keys.length; i++) {
      var entry = hf.candidates.get(keys[i]);
      if (entry && hfFresh(entry.rxMs) && hf.lastState &&
          HF.sameContext(entry.snap, hf.lastState)) return true;
      var s = hf.lastState;
      if (s && hfFresh(hf.lastStateRxMs) &&
          HF.objectKeys(s, POINTS_TOPIC).indexOf(keys[i]) >= 0) return true;
    }
    return false;
  }
  function hfUpdateStreamStats() {
    var elPres = $("pcPresHz"), elSkip = $("pcSkip"), elAge = $("pcAge"),
        now = hfNow();
    while (hf.presentMarks.length && now - hf.presentMarks[0] > 1000) hf.presentMarks.shift();
    if (elPres) elPres.textContent = hf.presentMarks.length.toFixed(1);
    if (elSkip) elSkip.textContent = Math.max(0, hf.rawCount - hf.presentCount);
    if (elAge) {
      var age = hf.presented ? now - hf.presented.rxMs : null;
      elAge.textContent = (age != null && age >= 0) ? (age / 1000).toFixed(2) : "--";
    }
  }
  function hfPresentFrame(frame) {
    // rxMs is the ORIGINAL packet's browser receive time (frame age); it must
    // not be reset here or the displayed age would be hidden. presentedAtMs is
    // the separate presentation instant (render interval).
    hf.presented = { seq: frame.header.seq, secs: frame.header.secs,
                     nsecs: frame.header.nsecs, keys: frame.keys,
                     frameId: frame.frameId != null ? frame.frameId : null,
                     rxMs: frame.rxMs, presentedAtMs: hfNow(), order: frame.order };
    hf.presentCount += 1;
    hf.presentMarks.push(hfNow());
    if (hf.presentMarks.length > 256) hf.presentMarks.shift();
    if (typeof renderPoints === "function") renderPoints(frame.logTimeNs, frame.payload);
    hfUpdateStreamStats();
    // Metadata/transform may only come from the entry that is actually presented.
    hfSyncCurrentSnapshot();
  }
  function hfAdvancePresent() {
    hf.rawFrames = HF.pruneRawFrames(hf.rawFrames, hfNow(), HF_RAW_TTL_MS);
    var next = HF.nextPresentedFrame(hf.rawFrames, hf.presented, hfOutputForFrame,
                                     hfNow(), HF_PRESENT_FALLBACK_MS);
    if (next) hfPresentFrame(next);
  }
  function hfOnRawFrame(logTimeNs, payload) {
    // Raw receive stats are counted for every message; only the chosen frame is
    // rendered (renderPoints) so raw Hz, presented Hz and skipped frames differ.
    if (typeof recordPointsStats === "function") recordPointsStats(logTimeNs, payload);
    hf.rawCount += 1;
    var header = HF.headerFromPayload(payload);
    var keys = header ? HF.frameKeys(header, POINTS_TOPIC) : [];
    if (keys.length) {
      hf.rawOrder += 1;
      hf.rawFrames.push({ keys: keys, order: hf.rawOrder, header: header,
                          frameId: HF.headerFrameFromPayload(payload),
                          logTimeNs: logTimeNs, payload: payload, rxMs: hfNow() });
      while (hf.rawFrames.length > HF_RAW_CACHE) hf.rawFrames.shift();
      hfAdvancePresent();
    }
    hfUpdateStreamStats();
  }

  /* ---- serverInfo capabilities + selection request channel ---- */
  var hfOrigOnJson = FoxgloveClient.prototype.onJson;
  FoxgloveClient.prototype.onJson = function (m) {
    if (m && m.op === "serverInfo") {
      hf.serverInfo = m; hf.capabilities = m.capabilities || []; hfRenderCap();
    }
    return hfOrigOnJson.call(this, m);
  };
  function hfRenderCap() {
    var ok = !!(client && client.ws && client.ws.readyState === 1) &&
      hf.capabilities.indexOf("clientPublish") >= 0;
    hfSetText("hfCap", (ok ? "可用" : "不可用") + " · " + CAND_TOPIC.split("/").slice(0, -1).join("/") + "/",
              ok ? "hf-ok" : "hf-cert");
  }
  function hfTickConnection() {
    var live = !!(client && client.live);
    if (!live) { hf.channelReady = false; return; }
    if (!hf.channelReady && hf.capabilities.indexOf("clientPublish") >= 0) {
      client.send({ op: "advertise", channels: [{
        id: hf.channelId, topic: REQ_TOPIC, encoding: "ros1",
        schemaName: "std_msgs/String", schema: "string data\n",
        schemaEncoding: "ros1msg" }] });
      hf.channelReady = true;
      hfLog("HF: 已声明选择请求通道 " + REQ_TOPIC);
    }
  }
  function hfSendRequest(body) {
    if (!(client && client.live)) { hfLog("HF: 未连接，无法发送选择请求", 1); return null; }
    if (!hf.channelReady) { hfLog("HF: 请求通道不可用（bridge 未确认 clientPublish）", 2); return null; }
    body.schema_version = 1;
    body.request_id = hfNewRequestId();
    var frame = HF.packClientMessage(hf.channelId, JSON.stringify(body));
    client.ws.send(frame);
    hf.pending[body.request_id] = { action: body.action, t: hfNow() };
    hfLog("HF: 发送 " + body.action + " " + (body.candidate_id || body.track_id || ""));
    return body.request_id;
  }
  function hfSelectionVersion() {
    var s = hf.lastState;
    return (s && HF.isInt(s.selection_version)) ? s.selection_version : 0;
  }
  function hfSendSelect(snapshot, candidateId) {
    if (!snapshot) return;
    hfSendRequest({ action: "select", session_id: snapshot.session_id,
      time_epoch: snapshot.time_epoch, snapshot_id: snapshot.snapshot_id,
      candidate_id: candidateId, selection_version: hfSelectionVersion() });
  }
  function hfSendRelease() {
    var s = hf.lastState;
    if (!s || !s.track_id) { hfLog("HF: 当前没有已锁定目标", 1); return; }
    hfSendRequest({ action: "release", session_id: s.session_id, time_epoch: s.time_epoch,
      track_id: s.track_id, selection_version: hfSelectionVersion() });
  }
  function hfSendCapture() {
    var s = hf.lastState;
    if (!s || !s.track_id) { hfLog("HF: 请先选人再采集基线", 1); return; }
    hfSendRequest({ action: "capture_baseline", session_id: s.session_id,
      time_epoch: s.time_epoch, track_id: s.track_id,
      selection_version: hfSelectionVersion(), operator_confirmed: true });
  }

  /* ---- context reset on session/epoch change ---- */
  function hfResetContext(reason) {
    hf.candidates.clear();
    hf.pending = {};
    // A session/epoch/connection change must drop the raw frame cache too, so a
    // frame from the old context can never be presented against new output.
    hf.rawFrames = [];
    hf.presented = null;
    hf.rawCount = 0;
    hf.presentCount = 0;
    hf.presentMarks = [];
    if (hfBoxes.cand) { for (var k in hfBoxes.cand) hfBoxes.cand[k].line.visible = false; }
    if (hfBoxes.target) hfBoxes.target.line.visible = false;
    // The old snapshot's explicit ground render must not outlive its context.
    hf.lastMeta = null;
    hf.groundRender = HF.parseGroundRender(null);
    if (hf.coordMode === "ground") hf.coordMode = "source";
    hf.wasObserved = false;
    hfApplyModeToBuffers();
    hfDrawSupport();
    dirty3d = true;
    hfRenderPanel();
    hfLog("HF: 上下文重置（" + reason + "），清候选/框/待选/原始缓存", 1);
  }

  /* ---- inbound topic handling ---- */
  function hfOnMessage(topic, payload) {
    if (topic === CAND_TOPIC) {
      var text = HF.parseRos1String(payload);
      var c = text ? hfParse(text) : null;
      if (!HF.validSnapshot(c)) {
        hfLog("HF: 候选快照 schema/字段非法，显示 unknown", 1);
        hfResetContext("invalid_snapshot"); hfInvalidateState(); hfRenderCandidates(); return;
      }
      // Store a snapshot under every key it can be matched by (source-frame key
      // and/or display mapping key); the presented raw frame looks itself up.
      // A future/foreign snapshot is cached but never allowed to rewrite the
      // current frame: the derived metadata/transform is only synced from the
      // entry that the currently presented raw frame matches (V01/V03/V06).
      var keys = HF.objectKeys(c, POINTS_TOPIC);
      if (!keys.length) { hfLog("HF: 候选快照无可用源键，忽略", 1); return; }
      var entry = { snap: c, rxMs: hfNow() };
      for (var ki = 0; ki < keys.length; ki++) hf.candidates.set(keys[ki], entry);
      while (hf.candidates.size > 16) { hf.candidates.delete(hf.candidates.keys().next().value); }
      hfAdvancePresent();      // output arrived: present the matching raw frame
      hfSyncCurrentSnapshot(); // only the current presented entry may drive render
      // The first qualified pair (state + candidate) must show the same readout/
      // transform/box immediately, without waiting for the next message (C02).
      hfRenderState();
      hfRenderCandidates();
    } else if (topic === STATE_TOPIC) {
      var st = hfDecode(payload);
      if (!HF.validState(st)) { hfLog("HF: 状态 schema/字段非法，显示 unknown", 1); hfInvalidateState(); return; }
      if (!hfAcceptState(st)) return;
      hf.lastState = st; hf.lastStateRxMs = hfNow();
      hfMergeRecentEvents(st.recent_events); hfRenderState();
      hfAdvancePresent();      // output arrived: present the matching raw frame
    } else if (topic === EVENT_TOPIC) {
      var ev = hfDecode(payload);
      if (ev && HF.validEvent(ev)) hfAddEvent(ev, true);
    } else if (topic === ACK_TOPIC) {
      var ack = hfDecode(payload);
      if (ack && HF.validAck(ack)) hfOnAck(ack);
    }
  }
  function hfDecode(payload) {
    var text = HF.parseRos1String(payload);
    if (!text) return null;
    try { return JSON.parse(text); }
    catch (e) { hfLog("HF JSON 解析失败: " + e.message, 1); return null; }
  }
  function hfParse(text) {
    try { return JSON.parse(text); }
    catch (e) { hfLog("HF JSON 解析失败: " + e.message, 1); return null; }
  }
  function hfAcceptState(m) {
    if (hf.order.session !== null && hf.order.session !== m.session_id) {
      if (hf.retiredSessions.indexOf(m.session_id) >= 0) return false;
      hf.retiredSessions.push(hf.order.session);
      if (hf.retiredSessions.length > 8) hf.retiredSessions.shift();
      hfResetContext("session_changed"); hf.order = { session: m.session_id, epoch: null, sel: null };
    }
    if (hf.order.epoch !== null) {
      if (m.time_epoch < hf.order.epoch) return false;
      if (m.time_epoch > hf.order.epoch) { hfResetContext("time_epoch_changed"); hf.order.sel = null; }
      else if (HF.isInt(m.selection_version) && HF.isInt(hf.order.sel) &&
               m.selection_version < hf.order.sel) return false;
    }
    hf.order.session = m.session_id;
    hf.order.epoch = m.time_epoch;
    if (HF.isInt(m.selection_version)) hf.order.sel = m.selection_version;
    return true;
  }
  function hfInvalidateState() {
    hf.lastState = null;
    hfSetText("hfTrack", "--"); hfSetText("hfFall", "unknown", "hf-unk");
    hfSetText("hfObs", "unknown", "hf-unk"); hfSetText("hfPos", "--");
    hfSetText("hfRange", "--"); hfSetText("hfCoord", "--"); hfSetText("hfBaseline", "--");
    hfSetText("hfPred", "--"); hfSetText("hfPersist", "--");
    if (hfBoxes.target) hfBoxes.target.line.visible = false;
  }
  window.hfConnectionState = function (open) {
    hf.channelReady = false;
    hf.capabilities = [];
    hf.presented = null;
    hfResetContext(open ? "connected" : "disconnected");
    hf.order = { session: null, epoch: null, sel: null };
    hf.retiredSessions = [];
    hfInvalidateState();
    hfRenderCap();
    hfRenderCandidates();
  };

  var hfOrigHandle = handleMessage;
  handleMessage = function (topic, logTimeNs, payload) {
    if (topic === CAND_TOPIC || topic === STATE_TOPIC ||
        topic === EVENT_TOPIC || topic === ACK_TOPIC) {
      hfOnMessage(topic, payload); return;
    }
    // The points topic is intercepted: cache the raw frame and render only the
    // newest frame that has matching output (stats/render split in the page).
    if (topic === POINTS_TOPIC) { hfOnRawFrame(logTimeNs, payload); return; }
    hfOrigHandle(topic, logTimeNs, payload);
  };

  function hfOnAck(a) {
    delete hf.pending[a.request_id];
    var tag = a.accepted ? "接受" : "拒绝";
    hfLog("HF 回执 " + a.action + " " + tag +
      (a.reason ? " [" + a.reason + "]" : "") +
      (a.idempotent_replay ? " (重复回执)" : ""), a.accepted ? 0 : 1);
    if (a.action === "capture_baseline" && a.baseline) {
      hfLog("HF 基线 " + a.baseline.status +
        (a.baseline.reason ? " (" + a.baseline.reason + ")" : ""));
    }
    /* 迟到的旧回执只记日志，不改变显示（显示以板端 state 为准）。 */
  }

  /* ---- events ---- */
  function hfAddEvent(ev, live) {
    if (!ev || !ev.event_id || hf.eventIds[ev.event_id]) return;
    hf.eventIds[ev.event_id] = true;
    hf.events.unshift(ev);
    if (hf.events.length > 50) hf.events.length = 50;
    hfRenderEvents();
    if (live) hfLog("HF 新事件: " + ev.fall_status + " " + ev.event_id);
  }
  function hfMergeRecentEvents(list) {
    if (!Array.isArray(list)) return;
    for (var i = 0; i < list.length; i++) if (HF.validEvent(list[i])) hfAddEvent(list[i], false);
  }
  function hfRenderEvents() {
    var el = $("hfEvents"); if (!el) return;
    el.textContent = "";
    for (var i = 0; i < hf.events.length; i++) {
      var ev = hf.events[i], d = document.createElement("div");
      var t = HF.isNum(ev.start_source_s) ? Number(ev.start_source_s).toFixed(2) + "s" : "--";
      d.textContent = t + "  " + (ev.track_id || "?") + "  " + (ev.fall_status || "?") +
        "  " + ((ev.reason_codes || []).join(","));
      el.appendChild(d);
    }
  }

  /* ---- state / candidates text ---- */
  var FALL_CLASS = { confirmed: "hf-cert", suspected: "hf-susp", recovering: "hf-susp",
    descending: "hf-susp", low_posture_unclassified: "hf-susp", unknown: "hf-unk",
    upright: "hf-ok" };
  function hfFallHex(status) {
    if (status === "confirmed") return "#e05252";
    if (status === "suspected" || status === "descending" ||
        status === "low_posture_unclassified" || status === "recovering") return "#e8b23c";
    if (status === "upright") return "#3ad07a";
    return "#8fa0b8";
  }
  function hfFallColor(status) { return parseInt(hfFallHex(status).slice(1), 16); }
  // A qualification transition (fresh observation -> lost) must invalidate every
  // layer at once: DOM readouts, overlay and the cached GPU canvas (boxes,
  // support region, ground transform) plus a real dirty3d so the stale leveled
  // scene disappears. Called only on the transition, never per RAF (V06/C09).
  function hfInvalidatePresentation(reason) {
    if (hfBoxes.cand) for (var k in hfBoxes.cand) hfBoxes.cand[k].line.visible = false;
    if (hfBoxes.target) hfBoxes.target.line.visible = false;
    hfClearSupport();
    hf.lastMeta = null;
    hf.groundRender = HF.parseGroundRender(null);
    if (hf.coordMode === "ground") hf.coordMode = "source";
    hfApplyModeToBuffers();
    hfDrawSupport();
    dirty3d = true;
    hfLog("HF: 观测资格失效（" + reason + "），清框/支持层/配平并重绘", 1);
  }
  // Presentation qualification (snapshot + binding + verifier) is tracked
  // separately from the target's own detail: losing the target's current
  // geometry only blanks its readout (hfStateAligned), while losing the
  // presentation itself must tear down the cached GPU ground scene.
  function hfPresentationQualified() {
    var snap = hfCurrentCandidateSnapshot();
    return !!snap && HF.observationQualified(snap, hf.lastState).ok;
  }
  function hfRefreshObservation() {
    var ok = hfPresentationQualified();
    if (hf.wasObserved && !ok) hfInvalidatePresentation("observation_lost");
    hf.wasObserved = ok;
  }
  function hfRenderState() {
    hfRefreshObservation();
    // The position row must name the frame its value actually comes from; a
    // ground_local value is never labelled as source (V03/C03).
    hfSetText("hfPosLabel", hf.coordMode === "ground" ? "位置 ground_local (m)" : "位置 source (m)");
    var s = hf.lastState;
    if (!s || !hfFresh(hf.lastStateRxMs)) {
      hfSetText("hfTrack", "--"); hfSetText("hfFall", "unknown", "hf-unk");
      hfSetText("hfObs", "unknown", "hf-unk"); hfSetText("hfPos", "--");
      hfSetText("hfRange", "--"); hfSetText("hfCoord", "--"); hfSetText("hfBaseline", "--");
      hfSetText("hfPred", "--"); hfSetText("hfPersist", "--");
      var elS0 = $("pcSample"); if (elS0) elS0.textContent = "--";
      return;
    }
    // A retained baseline qualification is shown even when the current frame is
    // not aligned; it must not be replaced by, or endorse, a stale observation.
    var b = s.baseline || {};
    hfSetText("hfBaseline", b.status ? (b.status + (b.reason ? " (" + b.reason + ")" : "")) : "--",
      b.status === "ready" ? "hf-ok" : "hf-unk");
    if (!hfStateAligned()) {
      hfSetText("hfTrack", (s.track_id || "未选目标") + " / 未对齐当前帧");
      hfSetText("hfFall", "unknown", "hf-unk");
      hfSetText("hfObs", "unknown", "hf-unk");
      hfSetText("hfPos", "--"); hfSetText("hfRange", "--"); hfSetText("hfCoord", "--");
      hfSetText("hfPred", s.position_predicted
        ? ("预测 age=" + (HF.isNum(s.prediction_age_s) ? s.prediction_age_s.toFixed(2) : "?") + "s")
        : "-- / 无对齐观测", s.position_predicted ? "hf-susp" : "hf-unk");
      var ep0 = s.event_persistence || {};
      hfSetText("hfPersist", ep0.degraded ? ("降级: " + (ep0.reason || "写失败"))
        : ("ok (" + (ep0.persisted_count || 0) + ")"), ep0.degraded ? "hf-cert" : "hf-ok");
      var elS1 = $("pcSample"); if (elS1) elS1.textContent = "--";
      return;
    }
    var viz = s.visualization;
    var elS = $("pcSample");
    if (elS) elS.textContent = (viz && HF.isInt(viz.display_points) &&
      HF.isInt(viz.original_points))
      ? (viz.display_points + "/" + viz.original_points + " s" + viz.stride) : "--";
    hfSetText("hfTrack", (s.track_id || "未选目标") + " / " + (s.track_status || "--"));
    // The raw source measurement may be current while the physical fall state is
    // not: without a qualified physical observation the fall row is unknown (C10).
    var physical = hfPhysicalObserved();
    var fs = physical ? (s.fall_status || "unknown") : "unknown";
    hfSetText("hfFall", fs, FALL_CLASS[fs] || "hf-unk");
    hfSetText("hfObs", s.observability || "unknown",
      s.observability === "valid" ? "hf-ok" : (s.observability === "invalid" ? "hf-cert" : "hf-susp"));
    var groundMode = hf.coordMode === "ground";
    var pos = null;
    if (groundMode) {
      if (HF.isTriple(s.position_ground_m)) pos = s.position_ground_m;
      else if (HF.isTriple(s.center_ground_m)) pos = s.center_ground_m;
    } else if (HF.isTriple(s.position_source_m) && hfSourcePositionQualified()) {
      pos = s.position_source_m;
    }
    // A predicted pose is a diagnostic, not a current actual measurement: it is
    // shown on the prediction row, never as the "current position" value (C08).
    if (s.position_predicted) pos = null;
    hfSetText("hfPos", pos ? pos.map(function (v) { return v.toFixed(2); }).join(", ") : "--");
    hfSetText("hfRange", (s.range_m && HF.isNum(s.range_m.median)) ? s.range_m.median.toFixed(2) : "--");
    var cal = s.calibration || {};
    var srcFrame = (s.source && s.source.frame_id) ||
      (hf.lastMeta && hf.lastMeta.source_frame) || "?";
    var calTxt = "标定 " + (cal.calibration_id != null ? cal.calibration_id : "未提供") +
      " · 地面 " + (cal.ground_status || "unknown");
    if (groundMode) {
      hfSetText("hfCoord", "配平 " + HF.GROUND_LOCAL_FRAME + "（源 " + srcFrame + "）· " + calTxt);
    } else {
      hfSetText("hfCoord", "可见点云中心 · 雷达坐标 " + srcFrame + "（未标定世界坐标）· " + calTxt);
    }
    var hasMeasuredPos = !!(s.track_id && HF.isTriple(s.position_source_m) && hfSourcePositionQualified());
    hfSetText("hfPred", !s.track_id ? "-- / 未选目标" : s.position_predicted ?
      ("预测 age=" + (HF.isNum(s.prediction_age_s) ? s.prediction_age_s.toFixed(2) : "?") + "s")
      : (hasMeasuredPos ? "实测" : "无有效观测"),
      !s.track_id ? "hf-unk" : s.position_predicted ? "hf-susp" : (hasMeasuredPos ? "hf-ok" : "hf-unk"));
    var ep = s.event_persistence || {};
    hfSetText("hfPersist", ep.degraded ? ("降级: " + (ep.reason || "写失败"))
      : ("ok (" + (ep.persisted_count || 0) + ")"), ep.degraded ? "hf-cert" : "hf-ok");
  }
  function hfCurrentCandidateEntry() {
    if (!hf.presented || !hfFresh(hf.presented.rxMs) ||
        !hfFresh(hf.lastStateRxMs)) return null;
    var keys = hf.presented.keys || [];
    for (var i = 0; i < keys.length; i++) {
      var entry = hf.candidates.get(keys[i]);
      if (entry && hfFresh(entry.rxMs) && HF.sameContext(entry.snap, hf.lastState)) {
        // The raw header must carry the same spatial frame as the snapshot: the
        // same seq+stamp under a foreign frame is a different frame (V05/V06).
        if (hf.presented.frameId != null && entry.snap.source &&
            entry.snap.source.frame_id != null &&
            hf.presented.frameId !== entry.snap.source.frame_id) continue;
        return entry;
      }
    }
    return null;
  }
  function hfCurrentCandidateSnapshot() {
    var entry = hfCurrentCandidateEntry();
    return entry ? entry.snap : null;
  }
  function hfCandidateFrom(snap, id) {
    var list = (snap && snap.candidates) || [];
    for (var i = 0; i < list.length; i++)
      if (list[i] && list[i].candidate_id === id) return list[i];
    return null;
  }
  // A current *actual* target is a live locked track, never a prediction and never
  // a lost/occluded/ambiguous/unselected retained pose. An omitted track_status is
  // treated as legacy-locked so source-only frames stay usable (V07/C08).
  function hfCurrentActual(s) {
    if (!s || !s.track_id || s.position_predicted) return false;
    return s.track_status == null || s.track_status === "locked";
  }
  // Physical fall/colour endorsement is a distinct gate from a raw source
  // measurement: it needs the presented snapshot to be physically observed
  // (ground + verifier) AND a current actual target with no explicit negative
  // actual-observation flag (V06/V07/C08/C10).
  function hfPhysicalObserved() {
    var s = hf.lastState;
    if (!s || !hfStateAligned() || !hfCurrentActual(s)) return false;
    var snap = hfCurrentCandidateSnapshot();
    if (!snap) return false;
    return HF.observationQualified(snap, s).ok && HF.actualObservationQualified(s).ok;
  }
  // A source position readout is only a current actual measurement when its own
  // explicit provenance says so; a negative source flag proves the value is not
  // the current position even if the triple is otherwise present. Shared by the
  // position row and the measured label; missing/null stays legacy (V07/V09/C08).
  function hfSourcePositionQualified() {
    return HF.sourcePositionQualified(hf.lastState).ok;
  }
  // The current target's own explicit geometry for the active mode. Presence of
  // stale state fields is never proof: the state's published target position/
  // centre and AABB must match exactly one current snapshot candidate's own
  // published fields in that mode. 0 matches (target absent, only unrelated
  // candidates) or >1 matches (ambiguous) is unknown, with no position -- never
  // a first/nearest pick, no tracking, no client-side geometry (V07/C07).
  function hfTripleEq(a, b) {
    if (!HF.isTriple(a) || !HF.isTriple(b)) return false;
    for (var i = 0; i < 3; i++) if (Math.abs(a[i] - b[i]) > 1e-6) return false;
    return true;
  }
  function hfTargetGeometryPresent() {
    var s = hf.lastState;
    if (!s) return false;
    var snap = hfCurrentCandidateSnapshot();
    if (!snap) return false;
    var list = snap.candidates || [];
    var ground = hf.coordMode === "ground";
    if (ground) {
      // A retained ground pose from a lost/ambiguous/unselected (or predicted)
      // track must never be shown as the current target, even if its ground
      // fields still match a live candidate (V07/C08).
      if (!hfCurrentActual(s)) return false;
      var wantGC = HF.isTriple(s.center_ground_m);
      var wantGB = s.bbox_ground_from === "actual_points" &&
        HF.isTriple(s.bbox_ground_min_m) && HF.isTriple(s.bbox_ground_max_m);
      if (!wantGC && !wantGB) return false;
      var gHits = 0;
      for (var i = 0; i < list.length; i++) {
        var c = list[i];
        if (wantGC && !hfTripleEq(c.center_ground_m, s.center_ground_m)) continue;
        if (wantGB && !(c.bbox_ground_from === "actual_points" &&
            hfTripleEq(c.bbox_ground_min_m, s.bbox_ground_min_m) &&
            hfTripleEq(c.bbox_ground_max_m, s.bbox_ground_max_m))) continue;
        gHits++;
      }
      return gHits === 1;
    }
    // An explicit prediction is not a current actual candidate and carries its
    // own trusted pose; it is never re-matched to a candidate (C08).
    if (s.position_predicted && HF.isTriple(s.position_source_m)) return true;
    // Any other non-current status (lost/ambiguous/unselected) rejects a retained
    // source pose as current, regardless of a stale candidate match (C08).
    if (!hfCurrentActual(s)) return false;
    var wantSC = HF.isTriple(s.position_source_m);
    var wantSB = HF.isTriple(s.bbox_source_min_m) && HF.isTriple(s.bbox_source_max_m);
    if (!wantSC && !wantSB) return false;
    var sHits = 0;
    for (var j = 0; j < list.length; j++) {
      var c2 = list[j];
      if (wantSC && !hfTripleEq(c2.center_source_m, s.position_source_m)) continue;
      if (wantSB && !(hfTripleEq(c2.bbox_source_min_m, s.bbox_source_min_m) &&
          hfTripleEq(c2.bbox_source_max_m, s.bbox_source_max_m))) continue;
      sHits++;
    }
    return sHits === 1;
  }
  // Derived state (frame/units/calibration/geometry/ground status + explicit
  // transform + support) may only come from the entry the currently presented
  // raw frame resolves to; a future/foreign snapshot never rewrites it.
  function hfSyncCurrentSnapshot() {
    var snap = hfCurrentCandidateSnapshot();
    if (snap) {
      hf.lastMeta = HF.snapshotMeta(snap);
      hf.groundRender = HF.parseGroundRender(snap);
    } else {
      hf.lastMeta = null;
      hf.groundRender = HF.parseGroundRender(null);
    }
    if (hf.coordMode === "ground" && hf.groundRender.status !== "ready") {
      hfLog("HF: 地面变换不再有效（" + hf.groundRender.status + "），回退原始坐标", 1);
      hf.coordMode = "source";
    }
    hfApplyModeToBuffers();
    hfDrawSupport();
    hfRenderPanel();
  }
  // True only when a fresh state is aligned to the presented cloud frame AND the
  // presented snapshot still carries a qualified current candidate observation
  // (candidate present + valid ground + available verifier). A ready baseline or
  // a matching state alone never endorses a stale/absent observation.
  function hfStateAligned() {
    var s = hf.lastState;
    if (!s || !hfFresh(hf.lastStateRxMs)) return false;
    if (!hf.presented || !hfFresh(hf.presented.rxMs)) return false;
    var snap = hfCurrentCandidateSnapshot();
    if (!snap) return false;
    // The physical observation gate differs by mode: ground mode needs the
    // leveled transform + verifier, while source mode accepts a legacy
    // source-only actual target as long as the binding agrees (V09/C01/C08).
    var q = (hf.coordMode === "ground") ? HF.observationQualified(snap, s)
      : HF.sourceAlignmentQualified(snap, s);
    if (!q.ok) return false;
    if (!hfTargetGeometryPresent()) return false;
    if (s.source && snap.source &&
        s.source.frame_id != null && snap.source.frame_id != null &&
        s.source.frame_id !== snap.source.frame_id) return false;
    if (hf.presented.frameId != null && snap.source && snap.source.frame_id != null &&
        hf.presented.frameId !== snap.source.frame_id) return false;
    var pk = hf.presented.keys || [], sk = HF.objectKeys(s, POINTS_TOPIC);
    for (var i = 0; i < pk.length; i++) if (sk.indexOf(pk[i]) >= 0) return true;
    return false;
  }
  function hfRenderCandidates() {
    var el = $("hfCands"); if (!el) return;
    el.textContent = "";
    var snap = hfCurrentCandidateSnapshot();
    if (!snap) {
      var d = document.createElement("div");
      d.textContent = hf.presented ? "候选与当前点云帧未匹配（等待匹配/已过期）" : "尚未收到点云帧";
      d.style.color = "var(--dim)"; el.appendChild(d); return;
    }
    var list = snap.candidates || [];
    if (!list.length) {
      var d2 = document.createElement("div");
      d2.textContent = "当前帧无候选";
      d2.style.color = "var(--dim)"; el.appendChild(d2); return;
    }
    for (var i = 0; i < list.length; i++) {
      (function (c) {
        var btn = document.createElement("button");
        btn.type = "button";
        btn.style.display = "block";
        btn.style.width = "100%";
        btn.style.textAlign = "left";
        btn.style.margin = "2px 0";
        // The row reads in the active mode: ground mode shows the candidate's
        // own ground_local centre (or "?" when absent), never the source value
        // mislabelled -- and vice versa. No candidate geometry is derived here.
        var center = hf.coordMode === "ground" ? c.center_ground_m : c.center_source_m;
        var frameTag = hf.coordMode === "ground" ? "ground" : "source";
        var cm = HF.isTriple(center) ? center.map(function (v) { return v.toFixed(2); }).join(",") : "?";
        var rm = (c.range_m && HF.isNum(c.range_m.median)) ? c.range_m.median.toFixed(2) : "?";
        btn.textContent = c.candidate_id + "  (" + cm + ") " + frameTag + "  d=" + rm + "  pts=" + c.point_count;
        // Immutable render token: capture identity + candidate content now, so a
        // later same-ID content change / in-place mutation cannot reuse the click.
        var token = { identity: HF.snapshotIdentity(snap),
                      signature: HF.candidateSignature(c) };
        btn.onclick = function () { hfSelectCandidate(snap, c.candidate_id, token); };
        el.appendChild(btn);
      })(list[i]);
    }
  }

  /* ================= GL-04 coordinate mode / leveling / support =============
   * Modes only choose which coordinate array is drawn. Source points and ids are
   * never mutated: the source frame is cached and the displayed buffer is either
   * the source copy (source mode) or the explicit-versioned ground render of it
   * (ground mode). Ground mode is refused unless the authoritative
   * snapshot.coordinate.ground (legacy snapshot.ground_render alias) is ready and
   * version-bound; a missing block never becomes an identity map. */
  function hfGroundReady() {
    return hf.coordMode === "ground" && hf.groundRender &&
           hf.groundRender.status === "ready";
  }
  function hfActiveGroundFrame() {
    return hfGroundReady() ? HF.GROUND_LOCAL_FRAME
      : (hf.lastMeta && hf.lastMeta.frame) || "source_frame";
  }
  // Submit-time re-validation: the captured render closure must never be
  // trusted. Re-resolve the current fresh entry and compare the immutable render
  // token (snapshot identity incl. transform content + candidate signature); a
  // same-ID changed snapshot, foreign frame, or caller in-place mutation is
  // rejected. The original snapshot_id/candidate_id is submitted (not the
  // client-leveled id). Single guard shared by list click and drag (M04/M06).
  function hfSelectCandidate(closedSnap, candidateId, renderToken) {
    hfUpdateMvp();
    var entry = hfCurrentCandidateEntry();
    if (!entry) { hfLog("HF: 无当前对齐候选快照，拒绝旧快照选择", 2); return; }
    var cur = hfCandidateFrom(entry.snap, candidateId);
    if (!cur) { hfLog("HF: 当前快照已无该候选，拒绝选择", 2); return; }
    var capturedIdentity = renderToken ? renderToken.identity : HF.snapshotIdentity(closedSnap);
    var capturedSignature = renderToken ? renderToken.signature
      : HF.candidateSignature(hfCandidateFrom(closedSnap, candidateId));
    if (capturedIdentity === null || capturedIdentity !== HF.snapshotIdentity(entry.snap)) {
      hfLog("HF: 快照 identity/坐标系已变化，拒绝旧选择", 2); return;
    }
    if (capturedSignature !== HF.candidateSignature(cur)) {
      hfLog("HF: 候选内容已变化，拒绝旧选择", 2); return;
    }
    // The selection context is validated separately from an existing target's
    // physical observation: a fresh source select only needs the current binding
    // to agree, not a valid ground/verifier or an existing target (V09/C01).
    var q = HF.selectionContextQualified(entry.snap, hf.lastState);
    if (!q.ok) { hfLog("HF: 当前选择context失效(" + q.reason + ")，拒绝选择", 2); return; }
    hfSendSelect(entry.snap, candidateId);
  }

  /* ---- source cache + mode rendering ---- */
  var hfSourcePositions = new Float32Array(0), hfSourceCount = 0;
  function hfApplyModeToBuffers() {
    if (no3d || !geo || !hfSourceCount) return;
    var n = hfSourceCount, need = n * 3;
    if (hfGroundReady()) {
      var R = hf.groundRender.R, t = hf.groundRender.t;
      for (var i = 0; i < n; i++) {
        var b = i * 3, x = hfSourcePositions[b], y = hfSourcePositions[b + 1],
            z = hfSourcePositions[b + 2];
        positions[b]     = R[0][0] * x + R[0][1] * y + R[0][2] * z + t[0];
        positions[b + 1] = R[1][0] * x + R[1][1] * y + R[1][2] * z + t[1];
        positions[b + 2] = R[2][0] * x + R[2][1] * y + R[2][2] * z + t[2];
      }
    } else {
      positions.set(hfSourcePositions.subarray(0, need), 0);
    }
    if (geo.attributes && geo.attributes.position) geo.attributes.position.needsUpdate = true;
    dirty3d = true;
  }
  function hfCaptureSourceAndApplyMode() {
    if (no3d || !geo) return;
    var n = geo.drawRange ? geo.drawRange.count : 0;
    if (!(n > 0)) { hfSourceCount = 0; return; }
    var need = n * 3;
    if (hfSourcePositions.length < need) {
      hfSourcePositions = new Float32Array(Math.max(need, hfSourcePositions.length * 2, 4096));
    }
    hfSourcePositions.set(positions.subarray(0, need), 0);
    hfSourceCount = n;
    hfApplyModeToBuffers();
  }
  var hfOrigRenderPoints = renderPoints;
  renderPoints = function (logTimeNs, payload) {
    if (hfOrigRenderPoints) hfOrigRenderPoints(logTimeNs, payload);
    hfCaptureSourceAndApplyMode();
  };

  /* ---- support layer (independent, budgeted, never derived from the grid) ---- */
  var hfSupportGroup = null;
  function hfClearSupport() {
    if (!hfSupportGroup) return;
    for (var i = hfSupportGroup.children.length - 1; i >= 0; i--) {
      var o = hfSupportGroup.children[i];
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
      hfSupportGroup.remove(o);
    }
  }
  function hfMakeSupportLine(points, closed, color) {
    var verts = [], i;
    for (i = 0; i < points.length; i++) {
      var z = HF.isNum(points[i][2]) ? points[i][2] : 0;
      verts.push(points[i][0], points[i][1], z);
    }
    var g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.Float32BufferAttribute(verts, 3));
    var m = new THREE.LineBasicMaterial({ color: color, transparent: true, opacity: 0.85 });
    // LineLoop closes the polygon without adding a duplicate vertex, so the
    // ≤3000-point budget and the source indices stay exact.
    var line = closed ? new THREE.LineLoop(g, m) : new THREE.Line(g, m);
    line.frustumCulled = false;
    return line;
  }
  function hfDrawSupport() {
    hfClearSupport();
    if (no3d || !scene || !hfGroundReady()) return;
    var sup = hf.groundRender.support;
    if (!sup || sup.status !== "ready") return;
    if (!hfSupportGroup) { hfSupportGroup = new THREE.Group(); scene.add(hfSupportGroup); }
    if (sup.polygon) hfSupportGroup.add(hfMakeSupportLine(sup.polygon.points, true, 0x4ad0c0));
    if (sup.polyline) hfSupportGroup.add(hfMakeSupportLine(sup.polyline.points, false, 0x4a90d0));
  }

  /* ---- leveling panel ---- */
  // FPS is the real renderer.render count over the last monotonic second (not
  // the presented-cloud Hz). queue_dropped only comes from a real snapshot/state
  // field, otherwise it is explicitly unknown -- pcSkip ("未呈现") keeps its
  // original meaning and is never passed off as queue drops. Connection shows
  // the true online/offline (or synthetic/offline) state.
  function hfUpdatePerfPanel() {
    var now = hfNow();
    while (hf.renderMarks.length && now - hf.renderMarks[0] > 1000) hf.renderMarks.shift();
    var fps = hf.renderMarks.length;
    var snap = hfCurrentCandidateSnapshot();
    // queue_dropped is the real publisher counter in state.performance; a
    // present-but-disabled/invalid block is unknown, never a fabricated 0, and
    // never overridden by the older compatibility fields (V08/C15).
    var perf = hf.lastState && hf.lastState.performance;
    var q;
    if (perf != null) {
      q = (perf.kind === "performance" && perf.schema_version === 1 &&
           perf.enabled === true && HF.isInt(perf.queue_dropped))
        ? perf.queue_dropped : "unknown";
    } else if (snap && snap.quality && HF.isInt(snap.quality.queue_dropped)) {
      q = snap.quality.queue_dropped;
    } else if (hf.lastState && HF.isInt(hf.lastState.queue_dropped)) {
      q = hf.lastState.queue_dropped;
    } else if (hf.lastState && hf.lastState.sensor_quality &&
               HF.isInt(hf.lastState.sensor_quality.queue_dropped)) {
      q = hf.lastState.sensor_quality.queue_dropped;
    } else {
      q = "unknown";
    }
    var conn = hf.synthetic ? "synthetic/offline" : ((client && client.live) ? "在线" : "断开");
    hfSetText("gPerf", fps + " render-fps · queue_dropped " + q + " · " + conn,
      (hf.synthetic || (client && client.live)) ? "hf-ok" : "hf-unk");
  }
  function hfRenderPanel() {
    hfSetText("gMode", hf.coordMode === "ground" ? "ground_local（俯瞰 +Z 向下）" : "原始 source");
    var gb = $("hfModeGround");
    var tag = $("hfLevelTag");
    if (gb) gb.disabled = (hf.groundRender.status !== "ready");
    if (tag) {
      if (hf.coordMode === "ground") tag.textContent = "配平预览（未地面核验）";
      else tag.textContent = hf.groundRender.status === "ready"
        ? "配平可用（显式版本化 R/t，未地面核验）"
        : "配平不可用：" + hf.groundRender.status + " · " + hf.groundRender.reason;
    }
    var m = hf.lastMeta;
    if (!m) {
      ["gFrame", "gFrames", "gCal", "gGeom", "gGround", "gRender", "gSupport", "gPhys"].forEach(function (id) {
        hfSetText(id, "--");
      });
      hfUpdatePerfPanel();
      return;
    }
    hfSetText("gFrame", (m.source_frame || m.frame || "?") +
      (m.seq != null ? " #" + m.seq : "") +
      (m.stamp_s != null ? "@" + Number(m.stamp_s).toFixed(3) : "") +
      " · " + (m.units && m.units.length ? m.units.length : "?"));
    hfSetText("gFrames", (m.source_frame || "?") + " → " +
      (hf.coordMode === "ground" ? HF.GROUND_LOCAL_FRAME : "source"));
    hfSetText("gCal", (m.calibration_id != null ? m.calibration_id : "未提供") +
      " / 标定schema " + (m.calibration_schema != null ? m.calibration_schema : "?") +
      " / 快照schema " + (m.schema_version != null ? m.schema_version : "?"));
    hfSetText("gGeom", (m.horizontal_basis || "?") + " / " + (m.transform_status || "unknown") +
      " / 几何schema " + (m.geometry_schema != null ? m.geometry_schema : "?"));
    hfSetText("gGround", (m.ground_status || "unknown") +
      (m.ground_derived_id ? " · " + m.ground_derived_id : " · 无GDID"));
    var gr = hf.groundRender;
    hfSetText("gRender", gr.status === "ready"
      ? "可用（显式版本化 R/t）" : "不可用（" + gr.status + ":" + gr.reason + "）",
      gr.status === "ready" ? "hf-ok" : "hf-unk");
    var sup = gr.status === "ready" ? gr.support : null;
    if (sup && sup.status === "ready") {
      var pn = sup.polygon ? (sup.polygon.count + "/" + sup.polygon.total + "pt") : null;
      var ln = sup.polyline ? (sup.polyline.count + "/" + sup.polyline.total + "pt") : null;
      hfSetText("gSupport", (pn || ln) ? ((pn || "-") + " 面 / " + (ln || "-") + " 线") : "空",
        "hf-ok");
    } else {
      hfSetText("gSupport", "未提供", "hf-unk");
    }
    hfSetText("gPhys", "地面核验=" + (m.physical.ground_physical_verified ? "是" : "否") +
      " 外参=" + (m.physical.extrinsics_verified ? "是" : "否") +
      " IMU=" + (m.physical.imu_alignment_verified ? "是" : "否"), "hf-unk");
    hfUpdatePerfPanel();
  }
  function hfSetMode(mode) {
    if (mode === "ground" && (!hf.groundRender || hf.groundRender.status !== "ready")) {
      hfLog("HF: 无显式有效地面变换，配平不可用，保持原始坐标", 1);
      mode = "source";
    }
    hf.coordMode = mode;
    hfApplyModeToBuffers();
    hfDrawSupport();
    hfRenderPanel();
  }
  function hfOverhead() {
    if (no3d || !camera || !controls) return;
    var t = controls.target;
    camera.up.set(0, 1, 0);
    camera.position.set(t.x, t.y, t.z + 12);
    camera.lookAt(t.x, t.y, t.z);
    controls.update();
    dirty3d = true;
    hfLog("HF: 俯瞰 ground_local（+Z 向下，参考网格≠已核验地面）");
  }

  /* ---- offline synthetic entry (?synthetic=normal|tilted|no_extrinsics) ----
   * The browser never builds scenario geometry or wire bytes. It only fetches a
   * precomputed static JSON fixture (this round's r6 evidence) whose sample
   * frame / points / candidate fields are already fixed, then feeds the exact
   * same parse / frame-match / render path. It never connects to the board and
   * never sends a request. Override the URL with ?fixture=<url>. */
  function hfBase64ToBytes(b64) {
    var bin = atob(b64), out = new Uint8Array(bin.length);
    for (var i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
    return out;
  }
  function hfStartSynthetic(name) {
    var known = ["normal", "tilted", "no_extrinsics"];
    if (known.indexOf(name) < 0) {
      hfLog("HF: 未知 synthetic 场景 " + name + "（可选 normal/tilted/no_extrinsics）", 2); return;
    }
    var url = params.get("fixture") ||
      ("../../docs/human_fall/evidence/2026-10-03_gl04_r6/fixtures/" + name + ".json");
    hfLog("HF: synthetic/offline 加载静态fixture " + url + "（浏览器只消费字段，不构造几何）");
    if (typeof fetch !== "function") { hfLog("HF: 环境无 fetch，synthetic 不可用", 2); return; }
    fetch(url).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (fx) {
      hf.syntheticScene = { cloud: hfBase64ToBytes(fx.cloud_b64),
        snapshot: fx.snapshot, state: fx.state, logTimeNs: fx.logTimeNs };
      hfLog("HF: synthetic/offline 场景 " + name + " 就绪（不连接板端、不发真实请求）");
      function push() {
        if (!hf.syntheticScene) return;
        var s = hf.syntheticScene;
        hfOnRawFrame(s.logTimeNs, s.cloud);
        hfOnMessage(CAND_TOPIC, HF.packRos1String(JSON.stringify(s.snapshot)));
        hfOnMessage(STATE_TOPIC, HF.packRos1String(JSON.stringify(s.state)));
        hfUpdatePerfPanel();
      }
      push();
      setInterval(push, 1000);
    }).catch(function (e) {
      hfLog("HF: synthetic fixture 加载失败 " + url + " (" + e.message + ")", 2);
    });
  }

  /* ---- 3D boxes（对象池：复用 LineSegments，消失的候选超龄后移除并 dispose，防 scene 无限增长） ---- */
  var HF_BOX_MAX = 20;          /* 活框上限（远多于实际候选数，仅为保险） */
  var HF_BOX_STALE_MS = 2000;   /* 候选消失后保留这么久再删（容忍短暂漏帧） */
  var hfBoxes = { cand: {}, target: null }, hfBoxGroup = null;
  if (!no3d && scene) { hfBoxGroup = new THREE.Group(); scene.add(hfBoxGroup); }
  function hfBoxGeometry() {
    var g = new THREE.BufferGeometry();
    var c = [[0,0,0],[1,0,0],[1,1,0],[0,1,0],[0,0,1],[1,0,1],[1,1,1],[0,1,1]];
    var e = [[0,1],[1,2],[2,3],[3,0],[4,5],[5,6],[6,7],[7,4],[0,4],[1,5],[2,6],[3,7]];
    var v = [];
    for (var i = 0; i < e.length; i++) {
      var a = c[e[i][0]], b = c[e[i][1]];
      v.push(a[0],a[1],a[2], b[0],b[1],b[2]);
    }
    g.setAttribute("position", new THREE.Float32BufferAttribute(v, 3));
    return g;
  }
  function hfMakeBox() {
    var mat = new THREE.LineBasicMaterial({ color: 0xffd24a });
    var line = new THREE.LineSegments(hfBoxGeometry(), mat);
    line.frustumCulled = false;
    if (hfBoxGroup) hfBoxGroup.add(line);
    return { line: line, mat: mat, lastSeen: hfNow() };
  }
  function hfDropBox(id) {
    var b = hfBoxes.cand[id];
    if (!b) return;
    if (hfBoxGroup) hfBoxGroup.remove(b.line);
    b.line.geometry.dispose();
    b.mat.dispose();
    delete hfBoxes.cand[id];
  }
  /* 每帧清理：超龄的隐藏框真正移出 scene；同时兜底总量上限（删最老的）。 */
  function hfPruneBoxes(now) {
    var ids = Object.keys(hfBoxes.cand), i, b;
    for (i = 0; i < ids.length; i++) {
      b = hfBoxes.cand[ids[i]];
      if (!b.line.visible && (now - b.lastSeen) > HF_BOX_STALE_MS) hfDropBox(ids[i]);
    }
    ids = Object.keys(hfBoxes.cand);
    while (ids.length > HF_BOX_MAX) {
      var oldest = ids[0];
      for (i = 1; i < ids.length; i++) {
        if (hfBoxes.cand[ids[i]].lastSeen < hfBoxes.cand[oldest].lastSeen) oldest = ids[i];
      }
      hfDropBox(oldest);
      ids = Object.keys(hfBoxes.cand);
    }
  }
  function hfPlace(box, min, max, color) {
    box.mat.color.setHex(color);
    box.line.visible = true;
    box.line.position.set(min[0], min[1], min[2]);
    box.line.scale.set(Math.max(max[0] - min[0], 1e-3), Math.max(max[1] - min[1], 1e-3),
                       Math.max(max[2] - min[2], 1e-3));
  }

  /* ---- overlay projection / drawing ---- */
  var hfOv = $("hfOverlay"), hfCtx = hfOv ? hfOv.getContext("2d") : null;
  var hfMvp = (!no3d && typeof THREE !== "undefined") ? new THREE.Matrix4() : null;
  var hfMvpElements = null;
  function hfResizeOverlay() {
    if (!hfOv) return;
    var v = $("view3d"), dpr = Math.min(devicePixelRatio, 2);
    hfOv.width = Math.max(2, Math.round(v.clientWidth * dpr));
    hfOv.height = Math.max(2, Math.round(v.clientHeight * dpr));
    hfCtx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  window.addEventListener("resize", hfResizeOverlay);
  // Project all 8 corners through the CURRENT camera matrix; any behind/near/far
  // clipped corner discards the whole rectangle (no false box, no red screen).
  function hfBoxRect(min, max) {
    if (hfMvpElements === null) return { rect: null, behind: true, reason: "no_camera" };
    var res = HF.boxProjectRect(hfMvpElements, min, max);
    if (res.behind || !res.rect) return res;
    var rect = renderer.domElement.getBoundingClientRect();
    var view = $("view3d").getBoundingClientRect();
    var p0 = HF.ndcToPixels({ x: res.rect.x0, y: res.rect.y0 }, rect, view);
    var p1 = HF.ndcToPixels({ x: res.rect.x1, y: res.rect.y1 }, rect, view);
    return { x0: Math.min(p0.x, p1.x), x1: Math.max(p0.x, p1.x),
             y0: Math.min(p0.y, p1.y), y1: Math.max(p0.y, p1.y), behind: false };
  }
  function hfStrokeRect(r, color, width) {
    hfCtx.strokeStyle = color; hfCtx.lineWidth = width;
    hfCtx.strokeRect(r.x0, r.y0, Math.max(1, r.x1 - r.x0), Math.max(1, r.y1 - r.y0));
  }
  function hfLabel(x, y, text, color) {
    hfCtx.fillStyle = color; hfCtx.font = "11px 'Segoe UI',sans-serif";
    hfCtx.fillText(text, x, Math.max(11, y - 3));
  }

  // Refresh the camera matrix so a rotation/zoom that happened on the last frame
  // is projected with the current view, including right before a selection.
  function hfUpdateMvp() {
    if (no3d || !camera || !hfMvp) return;
    camera.updateMatrixWorld();
    hfMvp.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
    hfMvpElements = hfMvp.elements;
  }

  /* ---- frame loop ---- */
  function hfFrame() {
    requestAnimationFrame(hfFrame);
    hfTickConnection();
    if (no3d || !hfCtx) return;
    // DPR-only changes do not fire a resize event, so keep both overlay backing
    // dimensions AND the renderer pixel ratio in sync here (V04). The rect
    // conversion below already uses CSS pixels.
    var vEl = $("view3d"), dprNow = Math.min(devicePixelRatio, 2) * (window.__renderScale || 1.0);
    var wantW = Math.max(2, Math.round(vEl.clientWidth * dprNow));
    var wantH = Math.max(2, Math.round(vEl.clientHeight * dprNow));
    if (hfOv && (Math.abs(hfOv.width - wantW) > 0.5 || Math.abs(hfOv.height - wantH) > 0.5))
      hfResizeOverlay();
    if (hf.lastDpr !== dprNow) {
      hf.lastDpr = dprNow;
      if (renderer && typeof renderer.setPixelRatio === "function") renderer.setPixelRatio(dprNow);
      if (typeof resize3d === "function") resize3d();
    }
    hfUpdateMvp();
    var snap = hfCurrentCandidateSnapshot();
    var boxes = [];
    var liveIds = {};
    if (snap) {
      for (var i = 0; i < snap.candidates.length; i++) {
        var c = snap.candidates[i];
        liveIds[c.candidate_id] = true;
        // Boxes consume the explicitly published AABB for the active coordinate
        // mode; a ground box is never built from the source corners.
        var bb = HF.candidateBox(c, hf.coordMode);
        if (!bb) { if (hfBoxes.cand[c.candidate_id]) hfBoxes.cand[c.candidate_id].line.visible = false; continue; }
        if (!hfBoxes.cand[c.candidate_id]) hfBoxes.cand[c.candidate_id] = hfMakeBox();
        hfBoxes.cand[c.candidate_id].lastSeen = hfNow();
        hfPlace(hfBoxes.cand[c.candidate_id], bb.min, bb.max, 0xffd24a);
        var rm = (c.range_m && HF.isNum(c.range_m.median)) ? c.range_m.median.toFixed(2) : "?";
        boxes.push({ min: bb.min, max: bb.max,
                     label: c.candidate_id + " d=" + rm, color: "#ffd24a" });
      }
    }
    for (var id in hfBoxes.cand) if (!liveIds[id]) hfBoxes.cand[id].line.visible = false;
    hfPruneBoxes(hfNow());

    var target = null;
    var s = hf.lastState, stateMatches = hfStateAligned();
    var sbb = stateMatches ? HF.candidateBox(s, hf.coordMode) : null;
    if (sbb) {
      if (!hfBoxes.target) hfBoxes.target = hfMakeBox();
      var pred = !!s.position_predicted;
      var physical = hfPhysicalObserved();
      var fallHex = pred ? "#6b7a90" : (physical ? hfFallHex(s.fall_status) : "#8fa0b8");
      var fallTxt = physical ? (s.fall_status || "") : "unknown";
      hfPlace(hfBoxes.target, sbb.min, sbb.max, parseInt(fallHex.slice(1), 16));
      target = { min: sbb.min, max: sbb.max,
        label: (s.track_id || "目标") + " " + fallTxt + (pred ? " 预测" : ""),
        color: fallHex };
    } else if (hfBoxes.target) { hfBoxes.target.line.visible = false; }

    // A prediction is an independent diagnostic: even with no current candidate
    // (e.g. occluded), a fresh, correctly bound snapshot in supported units keeps
    // its grey prediction box/age while current position/fall stay unknown (C08).
    if (!target && !stateMatches && s && hfFresh(hf.lastStateRxMs) &&
        HF.predictionDiagnosticQualified(snap, s).ok) {
      var pbb = HF.candidateBox(s, hf.coordMode);
      if (pbb) {
        if (!hfBoxes.target) hfBoxes.target = hfMakeBox();
        hfPlace(hfBoxes.target, pbb.min, pbb.max, 0x6b7a90);
        target = { min: pbb.min, max: pbb.max,
          label: (s.track_id || "目标") + " unknown 预测", color: "#6b7a90" };
      }
    }

    hfDrawOverlay(boxes, target, snap);
  }
  function hfDrawOverlay(boxes, target, snap) {
    var v = $("view3d");
    hfCtx.clearRect(0, 0, v.clientWidth, v.clientHeight);
    for (var i = 0; i < boxes.length; i++) {
      var r = hfBoxRect(boxes[i].min, boxes[i].max);
      if (!r || r.behind) continue;
      hfStrokeRect(r, boxes[i].color, 1); hfLabel(r.x0, r.y0, boxes[i].label, boxes[i].color);
    }
    if (target) {
      var rt = hfBoxRect(target.min, target.max);
      if (rt && !rt.behind) { hfStrokeRect(rt, target.color, 2); hfLabel(rt.x0, rt.y0, target.label, target.color); }
    }
    if (hf.drag) {
      hfCtx.strokeStyle = "#3ad07a"; hfCtx.lineWidth = 1; hfCtx.setLineDash([4, 3]);
      hfCtx.strokeRect(hf.drag.x0, hf.drag.y0, hf.drag.x1 - hf.drag.x0, hf.drag.y1 - hf.drag.y0);
      hfCtx.setLineDash([]);
    }
    if (!snap) {
      hfCtx.fillStyle = "#6b7a90"; hfCtx.font = "12px sans-serif";
      hfCtx.fillText(hf.presented ? "候选/目标与当前点云帧等待匹配" : "等待点云帧", 12, v.clientHeight - 24);
    }
  }

  /* ---- select mode + drag (isolated from OrbitControls) ---- */
  function hfSetSelectMode(on) {
    hf.selectMode = !!on;
    var btn = $("hfSelectMode");
    if (btn) btn.textContent = "选人模式：" + (hf.selectMode ? "开" : "关");
    $("view3d").classList.toggle("selecting", hf.selectMode);
  }
  function hfFinishDrag(drag) {
    var rx0 = Math.min(drag.x0, drag.x1), rx1 = Math.max(drag.x0, drag.x1);
    var ry0 = Math.min(drag.y0, drag.y1), ry1 = Math.max(drag.y0, drag.y1);
    if ((rx1 - rx0) < 6 || (ry1 - ry0) < 6) { hfLog("HF: 拖框太小，忽略", 1); return; }
    var snap = hfCurrentCandidateSnapshot();
    if (!snap) { hfLog("HF: 当前帧无对齐候选，拒绝选择（不锁已消失的人）", 2); return; }
    hfUpdateMvp();
    var box = { x0: rx0, y0: ry0, x1: rx1, y1: ry1 }, hits = [];
    for (var i = 0; i < (snap.candidates || []).length; i++) {
      var c = snap.candidates[i];
      // Hit-test the current coordinate mode's actual AABB through the current
      // camera (8 corners), then submit through the same select guard as clicks.
      var bb = HF.candidateBox(c, hf.coordMode);
      if (!bb) continue;
      var r = hfBoxRect(bb.min, bb.max);
      if (r && !r.behind && HF.rectsIntersect(r, box)) hits.push(c);
    }
    if (!hits.length) { hfLog("HF: 拖框未命中候选", 1); return; }
    if (hits.length === 1) {
      hfSelectCandidate(snap, hits[0].candidate_id,
        { identity: HF.snapshotIdentity(snap), signature: HF.candidateSignature(hits[0]) });
      return;
    }
    hfLog("HF: 命中 " + hits.length + " 个候选，请在右侧列表点选确认（防前后重叠误选）", 1);
  }
  $("hfSelectMode").onclick = function () { hfSetSelectMode(!hf.selectMode); };
  $("hfCapture").onclick = hfSendCapture;
  $("hfRelease").onclick = hfSendRelease;

  var hfView = $("view3d");
  function hfLocal(ev) { var r = hfView.getBoundingClientRect();
    return { x: ev.clientX - r.left, y: ev.clientY - r.top }; }
  hfView.addEventListener("pointerdown", function (ev) {
    if (!hf.selectMode) return;
    ev.stopPropagation(); ev.preventDefault();
    var p = hfLocal(ev);
    hf.drag = { x0: p.x, y0: p.y, x1: p.x, y1: p.y };
    if (controls) controls.enabled = false;
    var target = ev.target;
    if (target && target.setPointerCapture) { try { target.setPointerCapture(ev.pointerId); } catch (e) {} }
  }, true);
  hfView.addEventListener("pointermove", function (ev) {
    if (!hf.drag) return;
    ev.stopPropagation();
    var p = hfLocal(ev); hf.drag.x1 = p.x; hf.drag.y1 = p.y;
  }, true);
  hfView.addEventListener("pointerup", function (ev) {
    if (!hf.drag) return;
    ev.stopPropagation();
    var p = hfLocal(ev); hf.drag.x1 = p.x; hf.drag.y1 = p.y;
    var drag = hf.drag; hf.drag = null;
    if (controls) controls.enabled = true;
    hfFinishDrag(drag);
  }, true);

  /* ---- init ---- */
  var banner = $("hfBanner");
  if (banner) {
    var synthetic = PREFIX.indexOf("verify") >= 0 || POINTS_TOPIC.indexOf("verify") >= 0;
    banner.textContent = "HF-11 预览 · " + PREFIX + " · " +
      (synthetic ? "合成/验证输入（非真实人体）" : "几何模式") + " · 未验收不产生 confirmed";
  }
  if ($("hfModeSource")) $("hfModeSource").onclick = function () { hfSetMode("source"); };
  if ($("hfModeGround")) $("hfModeGround").onclick = function () { hfSetMode("ground"); };
  if ($("hfOverhead")) $("hfOverhead").onclick = hfOverhead;
  hfResizeOverlay();
  hf.lastDpr = Math.min(devicePixelRatio, 2) * (window.__renderScale || 1.0);
  // Count actual renderer.render invocations for an honest render FPS, distinct
  // from the display/output Hz panels. The page's own loop still owns rendering.
  if (!no3d && renderer && typeof renderer.render === "function") {
    var hfOrigRender = renderer.render.bind(renderer);
    renderer.render = function (sc, cam) {
      hf.renderCount += 1; hf.renderMarks.push(hfNow());
      if (hf.renderMarks.length > 2048) hf.renderMarks.shift();
      return hfOrigRender(sc, cam);
    };
  }
  hfSetSelectMode(false);
  hfRenderCap();
  hfRenderEvents();
  hfRenderPanel();
  if (hf.synthetic) {
    if (banner) banner.textContent = "HF-11 预览 · synthetic/offline " + hf.synthetic +
      " · 静态fixture只读 · 不连接板端 · 参考网格≠已核验地面 · 未验收不产生 confirmed";
    // Offline synthetic entry: forbid any board connection/request and feed the
    // exact same parse / frame-match / render path with an explicit fixture.
    connect = function () { hfLog("HF: synthetic/offline 模式禁止连接板端", 1); };
    toggle = function () { connect(); };
    if ($("btnConnect")) $("btnConnect").onclick = toggle;
    hfStartSynthetic(hf.synthetic);
  }
  // A quiet or disconnected stream must expire even without a new state message.
  setInterval(function () { hfRenderState(); hfRenderCandidates(); hfRenderPanel(); }, 500);
  requestAnimationFrame(hfFrame);
})();
