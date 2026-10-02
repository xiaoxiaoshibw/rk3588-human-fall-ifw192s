/* Real request -> ROS -> ack probe using the exact preview wire packing.
 *
 * Connects to the on-board foxglove_bridge, subscribes to the verify
 * candidates/state/selection_ack topics, then advertises the selection request
 * channel and sends a select using HF.packClientMessage (the same function the
 * preview page uses). Success == the node returns a matching accepted ack.
 *
 * Run: node hf11_wire_probe.mjs [ws://host:8765]
 */
import { createRequire } from "module";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
const libPath = fileURLToPath(new URL(
  "../../../../webui/human_fall_preview/human_fall_lib.js", import.meta.url));
const HF = require(libPath);

const URL_WS = process.argv[2] || "ws://192.168.3.125:8765";
const PREFIX = process.env.HF_PREFIX || "/hf07_verify/";
const CAND = PREFIX + "candidates";
const STATE = PREFIX + "state";
const ACK = PREFIX + "selection_ack";
const REQ = PREFIX + "selection_request";

const ws = new WebSocket(URL_WS, ["foxglove.websocket.v1"]);
ws.binaryType = "arraybuffer";
const pendingSub = new Map();   // subId -> topic
const channelToSub = new Map(); // channelId -> subId
let snapshot = null, state = null, sentId = null, advertised = false, sendReady = false;
let subSeq = 0;

function sendText(obj) { ws.send(JSON.stringify(obj)); }
function subscribe(topic, channelId) {
  if (channelToSub.has(channelId)) return;
  const id = ++subSeq;
  pendingSub.set(id, topic);
  channelToSub.set(channelId, id);
  sendText({ op: "subscribe", subscriptions: [{ id, channelId }] });
}
function maybeSend() {
  if (!snapshot || !state || sentId || !sendReady) return;
  if (snapshot.time_epoch !== state.time_epoch) return;
  const request = {
    schema_version: 1, request_id: "node-wire-" + Date.now(), action: "select",
    session_id: snapshot.session_id, time_epoch: snapshot.time_epoch,
    snapshot_id: snapshot.snapshot_id,
    candidate_id: snapshot.candidates[0].candidate_id,
    selection_version: HF.isInt(state.selection_version) ? state.selection_version : 0
  };
  sentId = request.request_id;
  const frame = HF.packClientMessage(1, JSON.stringify(request));
  ws.send(frame);
  console.log("sent select frame bytes=" + frame.length + " request_id=" + request.request_id);
  console.log("frame head=" + Array.from(frame.slice(0, 13)).join(","));
}

const timer = setTimeout(() => {
  console.log("PROBE_RESULT=TIMEOUT sentId=" + sentId + " hasSnapshot=" + !!snapshot + " hasState=" + !!state);
  process.exit(1);
}, 20000);

ws.addEventListener("message", (ev) => {
  const data = ev.data;
  if (typeof data === "string") {
    let m; try { m = JSON.parse(data); } catch (e) { return; }
    if (m.op === "serverInfo") {
      console.log("serverInfo clientPublish=" + (m.capabilities || []).includes("clientPublish"));
    } else if (m.op === "advertise") {
      for (const ch of m.channels || []) {
        if (ch.topic === CAND || ch.topic === STATE || ch.topic === ACK) subscribe(ch.topic, ch.id);
      }
    }
    return;
  }
  const buf = data;                       // ArrayBuffer
  const dv = new DataView(buf);
  if (dv.getUint8(0) !== 1) return;
  const subId = dv.getUint32(1, true);
  const topic = pendingSub.get(subId);
  if (!topic) return;
  const payload = new Uint8Array(buf, 13);
  const text = HF.parseRos1String(payload);
  if (!text) return;
  let obj; try { obj = JSON.parse(text); } catch (e) { return; }
  if (topic === CAND) {
    if (HF.validSnapshot(obj)) {
      snapshot = obj;
      if (!advertised) {
        advertised = true;
        sendText({ op: "advertise", channels: [{
          id: 1, topic: REQ, encoding: "ros1", schemaName: "std_msgs/String",
          schema: "string data\n", schemaEncoding: "ros1msg" }] });
        console.log("advertised request channel " + REQ);
        setTimeout(() => { sendReady = true; maybeSend(); }, 400);
      } else {
        maybeSend();
      }
    }
  } else if (topic === STATE) {
    if (HF.validState(obj)) { state = obj; maybeSend(); }
  } else if (topic === ACK) {
    if (HF.validAck(obj) && obj.request_id === sentId) {
      clearTimeout(timer);
      console.log("ack request_id=" + obj.request_id + " accepted=" + obj.accepted +
                  " track_id=" + obj.track_id + " reason=" + obj.reason);
      console.log("PROBE_RESULT=" + (obj.accepted ? "PASS" : "REJECTED"));
      process.exit(obj.accepted ? 0 : 2);
    }
  }
});
ws.addEventListener("error", (e) => { console.log("ws error " + (e.message || e)); });
ws.addEventListener("close", () => { console.log("ws closed"); });
