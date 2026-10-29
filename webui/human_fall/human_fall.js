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
 *
 * 点云模式可在运行时切换（抽样显示流 ↔ 全量原始点云）：页面负责换话题/重订阅，
 * 本层通过 window.hfPointMode(topic) 换键并清空按话题缓存的原始帧。
 */
(function () {
  "use strict";
  var HF = window.HF;

  var params = new URLSearchParams(location.search);
  // runtime.js is written by the release controller at start time: it binds the
  // page to the *same* effective config as the node/profiler. An explicit URL
  // parameter still wins (debugging), but the operator never has to type one.
  var RT = (window.__HF_RUNTIME__ && typeof window.__HF_RUNTIME__ === "object")
    ? window.__HF_RUNTIME__ : null;
  var PREFIX = HF.normalizePrefix(params.get("prefix") || (RT && RT.prefix) || undefined);
  // The main script reads the same ?points= and subscribes to exactly one cloud
  // source, so the verify cloud never mixes with /innolidar_points.
  var POINTS_TOPIC = (typeof HF_POINTS_TOPIC !== "undefined")
    ? HF_POINTS_TOPIC : (params.get("points") || (RT && RT.points) || "/innolidar_points");
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
    rawFrames: [], rawOrder: 0, rawCount: 0, presentCount: 0, presentMarks: []
  };
  window.__hf = hf;

  // One rigid source group keeps points, 3-D source boxes and 2-D selection
  // projections in the same display coordinates. No ground AABB is invented.
  var displayGround = null, displayFrame = null, displayApplied = false, displayWanted = true;
  var groundButton = $("btnGround"), groundUrl = params.get("ground") || (RT && RT.ground) || null;
  function hfApplyDisplayGround() {
    if (!sourceGroup) return;
    var ready = displayWanted && !!hf.presented && hfFresh(hf.presented.rxMs) &&
      hfFresh(hf.lastStateRxMs) && !!hf.lastState &&
      hf.lastState.observability !== "invalid" &&
      hf.lastState.sensor_quality && hf.lastState.sensor_quality.cloud &&
      hf.lastState.sensor_quality.cloud.status === "fresh" &&
      HF.displayGroundMatches(displayGround, hf.lastState, displayFrame);
    ready = !!ready;
    if (groundButton && groundUrl) {
      groundButton.hidden = false;
      groundButton.textContent = ready ? "配平候选 · 未物理验证" : (displayWanted ? "RAW · 等待配平绑定" : "RAW · 点击配平");
    }
    if (ready === displayApplied) return;
    displayApplied = ready;
    var m = sourceGroup.matrix;
    if (ready) {
      var r = displayGround.R, t = displayGround.t;
      m.set(r[0][0],r[0][1],r[0][2],t[0], r[1][0],r[1][1],r[1][2],t[1],
            r[2][0],r[2][1],r[2][2],t[2], 0,0,0,1);
    } else m.identity();
    sourceGroup.matrixWorldNeedsUpdate = true;
    dirty3d = true;
    fitView();
  }
  window.hfDisplayCloudFrame = function (frame) { displayFrame = frame; hfApplyDisplayGround(); };
  hf.displayGround = function () { return { active: displayApplied, config: displayGround, frame: displayFrame }; };
  // 运行时点云话题切换（页面调用）：本层按话题缓存原始帧/呈现帧，换话题必须清缓存，
  // 不能把旧流的帧按新话题重新解释。算法输出与状态流不受影响。
  window.hfPointMode = function (topic) {
    if (typeof topic !== "string" || !topic || topic === POINTS_TOPIC) return POINTS_TOPIC;
    POINTS_TOPIC = topic;
    hfResetContext("points_topic_changed");
    return POINTS_TOPIC;
  };
  hf.pointsTopic = function () { return POINTS_TOPIC; };
  if (groundUrl) {
    groundButton.hidden = false;
    groundButton.onclick = function () { displayWanted = !displayWanted; hfApplyDisplayGround(); };
    var displayUrl = new URL(groundUrl, location.href);
    if (displayUrl.origin === location.origin) fetch(displayUrl.href, {cache:"no-store"}).then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    }).then(function (g) {
      if (!HF.validDisplayGround(g)) throw new Error("invalid display ground candidate");
      displayGround = g; hfApplyDisplayGround();
    }).catch(function (e) { hfLog("配平候选加载失败：" + e.message, 2); });
    else hfLog("配平候选必须来自当前页面服务", 2);
  }

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
                     rxMs: frame.rxMs, presentedAtMs: hfNow(), order: frame.order };
    hf.presentCount += 1;
    hf.presentMarks.push(hfNow());
    if (hf.presentMarks.length > 256) hf.presentMarks.shift();
    if (typeof renderPoints === "function") renderPoints(frame.logTimeNs, frame.payload);
    hfUpdateStreamStats();
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
    displayFrame = null;
    hfApplyDisplayGround();
    hf.rawCount = 0;
    hf.presentCount = 0;
    hf.presentMarks = [];
    if (hfBoxes.cand) { for (var k in hfBoxes.cand) hfBoxes.cand[k].line.visible = false; }
    if (hfBoxes.target) hfBoxes.target.line.visible = false;
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
      var keys = HF.objectKeys(c, POINTS_TOPIC);
      if (!keys.length) { hfLog("HF: 候选快照无可用源键，忽略", 1); return; }
      var entry = { snap: c, rxMs: hfNow() };
      for (var ki = 0; ki < keys.length; ki++) hf.candidates.set(keys[ki], entry);
      while (hf.candidates.size > 16) { hf.candidates.delete(hf.candidates.keys().next().value); }
      hfRenderCandidates();
      hfAdvancePresent();      // output arrived: present the matching raw frame
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
    hfSetText("hfRegions", "0/13 · 0/12 · UNKNOWN");
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

  /* ---- run identity, input source, suspected hints ---- */
  var INPUT_MODE_TEXT = { live_lidar: "实时雷达", pcap: "PCAP 回放",
    unknown: "输入来源未核实" };
  var hfRun = { hintFloor: null, hintFloorSet: false, hints: [], hintIds: {} };

  function hfNoticeSeq(id) {
    var text = String(id || "");
    var parts = text.split(":");
    var value = parseInt(parts[parts.length - 1], 10);
    return isFinite(value) ? value : null;
  }

  function hfRenderRuntime() {
    // Static binding information from runtime.js (available even before the
    // first state message) plus, when present, the *running* release reported
    // by the node itself. A mismatch means the page is stale: reload.
    var meta = document.querySelector('meta[name="hf-page-version"]');
    var pageVersion = meta ? meta.getAttribute("content") : null;
    var parts = [];
    if (RT) {
      parts.push("release " + (RT.release_id || "?"));
      if (RT.scene_id) parts.push("场景 " + RT.scene_id);
      parts.push("页面 " + (pageVersion || RT.page_version || "?"));
      if (pageVersion && RT.page_version && pageVersion !== RT.page_version) {
        // A release switch can leave the browser holding the old index.html
        // (the server sends no cache headers). Reload once through a cache-
        // busting URL instead of asking the operator to hard-refresh; a
        // sessionStorage guard prevents a reload loop if the server still
        // serves the old document.
        var key = "hf_page_reload_" + RT.page_version;
        var tried = false;
        try { tried = sessionStorage.getItem(key) === "1"; } catch (e) { /* private mode */ }
        if (!tried) {
          try { sessionStorage.setItem(key, "1"); } catch (e2) { /* private mode */ }
          hfLog("页面版本 " + pageVersion + " ≠ 运行版本 " + RT.page_version +
                "，自动重新加载", 1);
          location.replace(location.pathname + "?v=" + encodeURIComponent(RT.page_version));
          return;
        }
        parts.push("页面版本与运行版本不一致，请强制刷新");
        hfSetText("hfVer", parts.join(" · "), "hf-cert");
        return;
      }
    } else {
      parts.push("未加载 runtime.js（无发布绑定）");
    }
    var s = hf.lastState;
    var run = (s && hfFresh(hf.lastStateRxMs) && s.run) ? s.run : null;
    if (run && run.release_id && RT && run.release_id !== RT.release_id) {
      parts.push("运行版本 " + run.release_id + " 与页面绑定不一致，请刷新");
      hfSetText("hfVer", parts.join(" · "), "hf-cert");
      return;
    }
    if (run && run.release_id) parts.push("运行 " + run.release_id);
    hfSetText("hfVer", parts.join(" · "), "hf-ok");
  }

  function hfRenderInputSource() {
    var s = hf.lastState;
    if (!s || !hfFresh(hf.lastStateRxMs)) { hfSetText("hfInput", "--"); return; }
    var src = s.input_source || {};
    var mode = src.mode || "unknown";
    var text = INPUT_MODE_TEXT[mode] || ("来源 " + mode);
    if (src.loop_suspected) text += " · 检测到重复/回退帧（疑似循环回放）";
    else if (HF.isInt(src.samples)) text += " · 已观测 " + src.samples + " 帧";
    if (src.conflict) text += " · 证据冲突(" + src.conflict.requested + "/" + src.conflict.evidence + ")";
    hfSetText("hfInput", text, mode === "live_lidar" ? "hf-ok" :
      (mode === "pcap" ? "hf-susp" : "hf-unk"));
  }

  function hfRenderRunRecord() {
    var s = hf.lastState;
    if (!s || !hfFresh(hf.lastStateRxMs)) { hfSetText("hfRunRec", "--"); return; }
    var run = s.run || {};
    if (!run.run_id) { hfSetText("hfRunRec", "运行记录未启用", "hf-unk"); return; }
    var text = "run " + run.run_id + " · 记录 " + (run.records || 0) +
      " · 提示 " + (run.notifications || 0);
    if (run.write_error) text += " · 写入失败: " + run.write_error;
    hfSetText("hfRunRec", text, run.write_error ? "hf-cert" : "hf-ok");
    hfNoteNotification(s);
  }

  // A page reload must not replay an old hint as a new alarm: the numeric part
  // of notification_id is monotone, so the first observed id becomes a floor
  // and only larger ids are announced afterwards. The hint itself stays visible
  // in the list (it is current state, not an alarm).
  function hfNoteNotification(s) {
    var run = s.run || {};
    var notice = run.last_notification;
    if (!notice || !notice.notification_id) return;
    var seq = hfNoticeSeq(notice.notification_id);
    if (seq === null) return;
    if (!hfRun.hintFloorSet) {
      hfRun.hintFloorSet = true;
      hfRun.hintFloor = seq;
      hfUpsertHint(notice, false);
      return;
    }
    if (seq > hfRun.hintFloor) {
      hfRun.hintFloor = seq;
      hfUpsertHint(notice, true);
    } else {
      hfUpsertHint(notice, false);
    }
  }

  function hfUpsertHint(notice, announce) {
    var id = notice.notification_id;
    var entry = hfRun.hintIds[id];
    if (!entry) {
      entry = {id: id, started: notice.started_wall, ended: null,
               track: notice.track_id, reason: (notice.reason_codes || []).join(","),
               height: notice.height_median_m};
      hfRun.hintIds[id] = entry;
      hfRun.hints.unshift(entry);
      if (hfRun.hints.length > 20) hfRun.hints.length = 20;
      if (announce) hfLog("疑似跌倒提示开始（运行记录，非 confirmed 事件）: " + id, 2);
    }
    if (notice.end_state) { entry.ended = notice.ended_wall; entry.endState = notice.end_state; }
    hfRenderHints();
  }

  function hfRenderHints() {
    var el = $("hfHints"); if (!el) return;
    el.textContent = "";
    if (!hfRun.hints.length) {
      var none = document.createElement("div");
      none.textContent = "无疑似提示记录";
      none.style.color = "var(--dim)";
      el.appendChild(none);
      return;
    }
    hfRun.hints.forEach(function (hint) {
      var row = document.createElement("div");
      var start = HF.isNum(hint.started)
        ? new Date(hint.started * 1000).toLocaleTimeString() : "--";
      row.textContent = (hint.ended ? "结束 " : "进行中 ") + start + "  " +
        (hint.track || "?") + "  " + (hint.endState || "suspected") +
        (hint.reason ? "  " + hint.reason : "");
      row.style.color = hint.ended ? "var(--dim)" : "var(--warning)";
      el.appendChild(row);
    });
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
  function hfRenderState() {
    var s = hf.lastState;
    if (!s || !hfFresh(hf.lastStateRxMs)) {
      hfSetText("hfGeometryShadow", RT && RT.event_geometry_shadow ? "影子 · UNKNOWN · 未收到新鲜状态" : "未启用", "hf-unk");
      hfSetText("hfTrack", "--"); hfSetText("hfFall", "unknown", "hf-unk");
      hfSetText("hfObs", "unknown", "hf-unk"); hfSetText("hfPos", "--");
      hfSetText("hfRange", "--"); hfSetText("hfCoord", "--"); hfSetText("hfBaseline", "--");
      hfSetText("hfPred", "--"); hfSetText("hfPersist", "--");
    hfSetText("hfRegions", "0/13 · 0/12 · UNKNOWN");
      hfSetText("hfInput", "--"); hfSetText("hfRunRec", "--");
      hfRenderRuntime();
      var elS0 = $("pcSample"); if (elS0) elS0.textContent = "--";
      return;
    }
    hfSetText("hfGeometryShadow", HF.geometryShadowText(s.event_geometry_shadow), "hf-unk");
    var viz = s.visualization;
    var elS = $("pcSample");
    if (elS) {
      // 采样比只描述节点的抽样显示话题；页面在看全量原始点云时显示全量点数，
      // 不能把并未生效的 stride 说成当前状态。
      var sampledNow = viz && viz.topic === POINTS_TOPIC;
      var lab = $("pcSampleLabel");
      if (lab) lab.textContent = sampledNow ? "抽样" : "全量";
      elS.textContent = (sampledNow && HF.isInt(viz.display_points) &&
        HF.isInt(viz.original_points))
        ? (viz.display_points + "/" + viz.original_points + " s" + viz.stride)
        : (HF.isInt(viz && viz.original_points) ? (viz.original_points + " 点 · 未抽样") : "--");
    }
    hfSetText("hfTrack", (s.track_id || (s.acquisition ? "自动搜索" : "未选目标")) + " / " +
      (s.acquisition ? s.acquisition.status + " · " + s.acquisition.reason : (s.track_status || "--")));
    if (s.target_mode === "automatic") hfSetSelectMode(false);
    var fs = s.fall_status || "unknown";
    hfSetText("hfFall", fs, FALL_CLASS[fs] || "hf-unk");
    hfSetText("hfObs", s.observability || "unknown",
      s.observability === "valid" ? "hf-ok" : (s.observability === "invalid" ? "hf-cert" : "hf-susp"));
    hfSetText("hfPos", HF.isTriple(s.position_source_m) ?
      s.position_source_m.map(function (v) { return v.toFixed(2); }).join(", ") : "--");
    hfSetText("hfRange", (s.range_m && HF.isNum(s.range_m.median)) ? s.range_m.median.toFixed(2) : "--");
    var cal = s.calibration || {};
    hfSetText("hfCoord", "可见点云中心 · 雷达坐标 innolidar（未标定世界坐标）· 标定 " +
      (cal.calibration_id != null ? cal.calibration_id : "未提供") + " · 地面 " + (cal.ground_status || "unknown"));
    var b = s.baseline || {};
    var regions = HF.regionsForState(s), regionCount = 0, edgeCount = 0;
    if (regions) {
      Object.keys(regions.nodes).forEach(function(k) {if (regions.nodes[k].valid) regionCount++;});
      var measuredEdges = (regions.calibration || {}).edges || {};
      Object.keys(measuredEdges).forEach(function(k) {if (measuredEdges[k].state === "CALIBRATED") edgeCount++;});
    }
    hfSetText("hfRegions", regionCount + "/13 · " + edgeCount + "/12 · " +
      (regions ? "本帧支撑（非关节）"
        : ("无实测区域 · " + ((s.regions && s.regions.reason) || "NO_CURRENT_MEASURED_TARGET"))));
    var bExtra = "";
    if (b.status === "pending" || b.status === "collecting") {
      bExtra = " · 样本 " + (b.sample_count || 0);
    }
    hfSetText("hfBaseline", b.status ? (b.status + bExtra + (b.reason ? " (" + b.reason + ")" : "")) : "--",
      b.status === "ready" ? "hf-ok" : "hf-unk");
    var hasMeasuredPos = !!(s.track_id && HF.isTriple(s.position_source_m));
    hfSetText("hfPred", !s.track_id ? "-- / 未选目标" : s.position_predicted ?
      ("预测 age=" + (HF.isNum(s.prediction_age_s) ? s.prediction_age_s.toFixed(2) : "?") + "s")
      : (hasMeasuredPos ? "实测" : "无有效观测"),
      !s.track_id ? "hf-unk" : s.position_predicted ? "hf-susp" : (hasMeasuredPos ? "hf-ok" : "hf-unk"));
    var ep = s.event_persistence || {};
    hfSetText("hfPersist", ep.degraded ? ("降级: " + (ep.reason || "写失败"))
      : ("ok (" + (ep.persisted_count || 0) + ")"), ep.degraded ? "hf-cert" : "hf-ok");
    hfRenderRuntime();
    hfRenderInputSource();
    hfRenderRunRecord();
  }
  function hfCurrentCandidateSnapshot() {
    if (!hf.presented || !hfFresh(hf.presented.rxMs) ||
        !hfFresh(hf.lastStateRxMs)) return null;
    var keys = hf.presented.keys || [];
    for (var i = 0; i < keys.length; i++) {
      var entry = hf.candidates.get(keys[i]);
      if (entry && hfFresh(entry.rxMs) && HF.sameContext(entry.snap, hf.lastState)) {
        return entry.snap;
      }
    }
    return null;
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
        var cm = HF.isTriple(c.center_source_m) ? c.center_source_m.map(function (v) { return v.toFixed(2); }).join(",") : "?";
        var rm = (c.range_m && HF.isNum(c.range_m.median)) ? c.range_m.median.toFixed(2) : "?";
        var rejected = ((hf.lastState || {}).acquisition || {}).rejected || {};
        btn.textContent = "几何候选 " + c.candidate_id + "  (" + cm + ") m  d=" + rm + "  pts=" + c.point_count +
          (rejected[c.candidate_id] ? " · " + rejected[c.candidate_id] : "");
        btn.onclick = function () { hfSendSelect(snap, c.candidate_id); };
        el.appendChild(btn);
      })(list[i]);
    }
  }

  /* ---- 3D boxes（对象池：复用 LineSegments，消失的候选超龄后移除并 dispose，防 scene 无限增长） ---- */
  var HF_BOX_MAX = 20;          /* 活框上限（远多于实际候选数，仅为保险） */
  var HF_BOX_STALE_MS = 2000;   /* 候选消失后保留这么久再删（容忍短暂漏帧） */
  var hfBoxes = { cand: {}, target: null }, hfBoxGroup = null;
  if (!no3d && sourceGroup) { hfBoxGroup = new THREE.Group(); sourceGroup.add(hfBoxGroup); }
  var hfRegionNodes = {}, hfRegionLines = {}, hfRegionGroup = null;
  if (!no3d && sourceGroup) { hfRegionGroup = new THREE.Group(); sourceGroup.add(hfRegionGroup); }
  function hfRenderRegions(state, matches) {
    if (!hfRegionGroup) return;
    var r = matches && HF.regionsForState(state);
    hfRegionGroup.visible = !!r;
    if (!r) return;
    Object.keys(hfRegionNodes).forEach(function(k) {hfRegionNodes[k].visible = false;});
    Object.keys(hfRegionLines).forEach(function(k) {hfRegionLines[k].visible = false;});
    Object.keys(r.nodes).forEach(function(k) {
      var n = r.nodes[k];
      if (!n.valid) return;
      if (!hfRegionNodes[k]) {
        hfRegionNodes[k] = new THREE.Mesh(new THREE.SphereGeometry(.038,8,6),
          new THREE.MeshBasicMaterial({color:0xffea9b}));
        hfRegionGroup.add(hfRegionNodes[k]);
      }
      hfRegionNodes[k].position.set(n.xyz[0],n.xyz[1],n.xyz[2]);
      hfRegionNodes[k].visible = true;
    });
    r.edges.forEach(function(edge) {
      var a = r.nodes[edge[0]], b = r.nodes[edge[1]], key = edge.join("|");
      if (!a || !b || !a.valid || !b.valid) return;
      if (!hfRegionLines[key]) {
        var g = new THREE.BufferGeometry();
        g.setAttribute("position",new THREE.BufferAttribute(new Float32Array(6),3));
        hfRegionLines[key] = new THREE.Line(g,new THREE.LineBasicMaterial({color:0x8796a5}));
        hfRegionGroup.add(hfRegionLines[key]);
      }
      var line = hfRegionLines[key], pos = line.geometry.attributes.position;
      pos.array.set(a.xyz,0); pos.array.set(b.xyz,3); pos.needsUpdate = true;
      var cf = ((r.calibration || {}).edges || {})[key];
      line.material.color.setHex(cf && cf.state === "CALIBRATED" ? 0x62dfc2 : 0x8796a5);
      line.frustumCulled = false; line.visible = true;
    });
    dirty3d = true;
  }
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
  function hfProject(p) {
    if (hfMvpElements === null) return null;
    var ndc = HF.projectNdc(p[0], p[1], p[2], hfMvpElements);
    if (!ndc) return null;
    var rect = renderer.domElement.getBoundingClientRect();
    var view = $("view3d").getBoundingClientRect();
    return HF.ndcToPixels(ndc, rect, view);
  }
  function hfBoxRect(min, max) {
    var corners = [], behind = false;
    var xs = [min[0], max[0]], ys = [min[1], max[1]], zs = [min[2], max[2]];
    for (var a = 0; a < 2; a++) for (var b = 0; b < 2; b++) for (var d = 0; d < 2; d++) {
      var p = hfProject([xs[a], ys[b], zs[d]]);
      if (!p) { behind = true; continue; }
      if (p.z > 1) behind = true;
      corners.push(p);
    }
    var r = HF.boxRect(corners);
    if (r) r.behind = behind;
    return r;
  }
  function hfStrokeRect(r, color, width) {
    hfCtx.strokeStyle = color; hfCtx.lineWidth = width;
    hfCtx.strokeRect(r.x0, r.y0, Math.max(1, r.x1 - r.x0), Math.max(1, r.y1 - r.y0));
  }
  function hfLabel(x, y, text, color) {
    hfCtx.fillStyle = color; hfCtx.font = "11px 'Segoe UI',sans-serif";
    hfCtx.fillText(text, x, Math.max(11, y - 3));
  }

  /* ---- frame loop ---- */
  function hfFrame() {
    requestAnimationFrame(hfFrame);
    hfTickConnection();
    hfApplyDisplayGround();
    if (no3d || !hfCtx) return;
    camera.updateMatrixWorld();
    if (hfMvp) {
      hfMvp.multiplyMatrices(camera.projectionMatrix, camera.matrixWorldInverse);
      hfMvp.multiply(sourceGroup.matrix);
      hfMvpElements = hfMvp.elements;
    }
    var snap = hfCurrentCandidateSnapshot();
    var boxes = [];
    var showCandidates = HF.showCandidateBoxes(hf.candidateLayer, hf.selectMode);
    if (snap && showCandidates) {
      for (var i = 0; i < snap.candidates.length; i++) {
        var c = snap.candidates[i];
        if (!hfBoxes.cand[c.candidate_id]) hfBoxes.cand[c.candidate_id] = hfMakeBox();
        hfBoxes.cand[c.candidate_id].lastSeen = hfNow();
        hfPlace(hfBoxes.cand[c.candidate_id], c.bbox_source_min_m, c.bbox_source_max_m, 0xffd24a);
        var rm = (c.range_m && HF.isNum(c.range_m.median)) ? c.range_m.median.toFixed(2) : "?";
        boxes.push({ box: hfBoxes.cand[c.candidate_id], min: c.bbox_source_min_m,
                     max: c.bbox_source_max_m, label: "几何候选 " + c.candidate_id + " d=" + rm, color: "#ffd24a" });
      }
    }
    var liveIds = {};
    if (snap && showCandidates) for (var j = 0; j < snap.candidates.length; j++) liveIds[snap.candidates[j].candidate_id] = true;
    for (var id in hfBoxes.cand) if (!liveIds[id]) hfBoxes.cand[id].line.visible = false;
    hfPruneBoxes(hfNow());

    var target = null;
    var s = hf.lastState, stFresh = s && hfFresh(hf.lastStateRxMs);
    var stateMatches = false;
    if (stFresh && hf.presented && hfFresh(hf.presented.rxMs)) {
      var pk = hf.presented.keys || [], sk = HF.objectKeys(s, POINTS_TOPIC);
      for (var qi = 0; qi < pk.length && !stateMatches; qi++) {
        if (sk.indexOf(pk[qi]) >= 0) stateMatches = true;
      }
    }
    if (stateMatches &&
        HF.isTriple(s.bbox_source_min_m) && HF.isTriple(s.bbox_source_max_m)) {
      if (!hfBoxes.target) hfBoxes.target = hfMakeBox();
      var pred = !!s.position_predicted;
      hfPlace(hfBoxes.target, s.bbox_source_min_m, s.bbox_source_max_m,
              pred ? 0x6b7a90 : hfFallColor(s.fall_status));
      target = { box: hfBoxes.target, min: s.bbox_source_min_m, max: s.bbox_source_max_m,
        label: (s.track_id || "目标") + " " + (s.fall_status || "") + (pred ? " 预测" : " 实测"),
        color: pred ? "#6b7a90" : hfFallHex(s.fall_status) };
    } else if (hfBoxes.target) { hfBoxes.target.line.visible = false; }

    hfRenderRegions(s, stateMatches);

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
    var box = { x0: rx0, y0: ry0, x1: rx1, y1: ry1 }, hits = [];
    for (var i = 0; i < (snap.candidates || []).length; i++) {
      var c = snap.candidates[i];
      var r = hfBoxRect(c.bbox_source_min_m, c.bbox_source_max_m);
      if (r && !r.behind && HF.rectsIntersect(r, box)) hits.push(c);
    }
    if (!hits.length) { hfLog("HF: 拖框未命中候选", 1); return; }
    if (hits.length === 1) { hfSendSelect(snap, hits[0].candidate_id); return; }
    hfLog("HF: 命中 " + hits.length + " 个候选，请在右侧列表点选确认（防前后重叠误选）", 1);
  }
  $("hfCandidateLayer").onclick = function () {
    hf.candidateLayer = !hf.candidateLayer;
    this.textContent = "几何候选诊断：" + (hf.candidateLayer ? "开" : "关");
  };
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
    var mode = RT && RT.source_mode;
    var sourceText = mode === "live_lidar" ? "实时雷达"
      : (mode === "pcap" ? "PCAP 回放" : "输入来源未核实");
    banner.textContent = "人体跌倒 · " + PREFIX + " · " + sourceText + " · " +
      (synthetic ? "合成/验证输入（非真实人体）" : "全场含静态背景 · 黄框仅几何候选") + " · confirmed 关闭";
  }
  hfResizeOverlay();
  hfSetSelectMode(false);
  hfRenderCap();
  hfRenderEvents();
  hfRenderRuntime();
  hfRenderHints();
  // A quiet or disconnected stream must expire even without a new state message.
  setInterval(function () { hfRenderState(); hfRenderCandidates(); }, 500);
  requestAnimationFrame(hfFrame);
})();
