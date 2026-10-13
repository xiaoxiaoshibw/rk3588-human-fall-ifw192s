/* gt_live.js — GT 标注台 live 模式：从 foxglove_bridge 订阅 /innolidar_points
 * 实时抽稀渲染到同一 canvas；与录制完全解耦（录制由板端 rosbag 全量录，
 * 本文件只负责"把什么画到屏上"）。
 *
 * 纯函数层，node 可测：不 import，不依赖 THREE / gt_lib / GT_OPS。
 *
 * 接口：
 *   GT_LIVE.connect(url, opts) -> conn
 *     opts: {
 *       render: function(pts /*Float32Array xyz 紧凑[i*3+0..2]/, count) {}
 *       on_state: function(connected) {}        // 可选
 *       on_error: function(msg) {}              // 可选
 *       stride:  int >= 1                        // 空间均匀抽稀步长 (默认 4)
 *       max_points: int >= 1                     // 渲染上限 (默认 40000)
 *       topics:   ["/innolidar_points"]          // 默认仅主点云
 *     }
 *   conn.close()
 *
 * 抽稀语义：stride 均匀步进保空间覆盖，绝不"只取前 N 个"丢一半空间。
 * 与板端 _publish_display 同 stride 语义，但板端走 (row*row_step + col*point_step)
 * 2D 寻址；本文件按 IFW192S 实测只走 unorganized (height=1) 线性寻址，
 * organized 带行填充的云会被 row_step 校验拒绝。
 */
"use strict";

var GT_LIVE = (function () {
    var FIELDS_REQUIRED = ["x", "y", "z"];

    /* PointField datatype -> DataView getter */
    function _getter(dv, f, bigEndian) {
        var o = f.offset, le = !bigEndian;
        switch (f.datatype) {
            case 1: return function (b) { return dv.getInt8(b + o); };
            case 2: return function (b) { return dv.getUint8(b + o); };
            case 3: return function (b) { return dv.getInt16(b + o, le); };
            case 4: return function (b) { return dv.getUint16(b + o, le); };
            case 5: return function (b) { return dv.getInt32(b + o, le); };
            case 6: return function (b) { return dv.getUint32(b + o, le); };
            case 7: return function (b) { return dv.getFloat32(b + o, le); };
            case 8: return function (b) { return dv.getFloat64(b + o, le); };
            default: return null;
        }
    }

    /* UTF-8 简易 decoder (字符串以 u32 长度前缀) */
    var _tc = (typeof TextDecoder !== "undefined") ? new TextDecoder("utf-8") : null;
    function _read_str(u8, dv, o) {
        var len = dv.getUint32(o, true); o += 4;
        var s;
        if (_tc) s = _tc.decode(u8.subarray(o, o + len));
        else {
            s = "";
            for (var k = 0; k < len; k++) s += String.fromCharCode(u8[o + k]);
        }
        return { s: s, o: o + len };
    }

    /* 解析 ROS1 sensor_msgs/PointCloud2 为 {header,x,y,z,intensity,n_points}。
     * 输出 pts: 原 buffer 子视图（零拷贝）。
     */
    function parse_pc2(payload_u8) {
        var dv = new DataView(payload_u8.buffer, payload_u8.byteOffset, payload_u8.byteLength);
        var o = 0;
        // Header header
        /* seq u32, stamp (sec u32 + nsec u32), frame_id (sized str) */
        var seq = dv.getUint32(o, true); o += 4;
        var stamp_sec = dv.getUint32(o, true); o += 4;
        var stamp_nsec = dv.getUint32(o, true); o += 4;
        var fr = _read_str(payload_u8, dv, o);
        var frame_id = fr.s; o = fr.o;
        // height, width, fields[]
        var height = dv.getUint32(o, true); o += 4;
        var width = dv.getUint32(o, true); o += 4;
        var nf = dv.getUint32(o, true); o += 4;
        var fields = [];
        for (var i = 0; i < nf; i++) {
            var rr = _read_str(payload_u8, dv, o);
            var name = rr.s; o = rr.o;
            var off = dv.getUint32(o, true); o += 4;
            var dtype = dv.getUint8(o); o += 1;
            var count = dv.getUint32(o, true); o += 4;
            fields.push({ name: name, offset: off, datatype: dtype, count: count });
        }
        var bigEndian = dv.getUint8(o) !== 0; o += 1;
        var pointStep = dv.getUint32(o, true); o += 4;
        var rowStep = dv.getUint32(o, true); o += 4;
        var dataLen = dv.getUint32(o, true); o += 4;
        var dataOff = o;
        var dense = dv.getUint8(o + dataLen) !== 0;  // dense byte 是 data 后面的那个
        return {
            header: { seq: seq, stamp: stamp_sec + stamp_nsec / 1e9, frame_id: frame_id },
            height: height, width: width, fields: fields,
            bigEndian: bigEndian, pointStep: pointStep, rowStep: rowStep,
            dataLen: dataLen, dataOff: dataOff, dense: dense,
        };
    }

    /* 每帧 raw PC2 -> Float32Array 紧凑 xyz (按 stride 抽稀) */
    function subsample_xyz(payload_u8, stride, max_pts) {
        if (!stride || stride < 1) stride = 1;
        if (!max_pts || max_pts < 1) max_pts = 40000;
        var m;
        try {
            m = parse_pc2(payload_u8);
        } catch (e) {
            /* parse 阶段 DataView 越界 → 不抛，返回空帧（UI 继续等下一帧） */
            return { pts: new Float32Array(0), n: 0, m: null };
        }
        if (m.pointStep <= 0 || m.width === 0) return { pts: new Float32Array(0), n: 0, m: m };
        /* FIX-REVIEW-M2: 仅支持 unorganized (height==1) 云 + 数据体越界校验。
         * 若 organized 带行填充（row_step > point_step*width），纯线性寻址会读到错点 — 拒绝。 */
        if (m.height !== 1) return { pts: new Float32Array(0), n: 0, m: m };
        if (m.rowStep !== m.pointStep * m.width) return { pts: new Float32Array(0), n: 0, m: m };
        if (m.dataLen < m.pointStep * m.width) return { pts: new Float32Array(0), n: 0, m: m };
        if (m.dataOff + m.dataLen > payload_u8.byteLength) return { pts: new Float32Array(0), n: 0, m: m };
        var dv = new DataView(payload_u8.buffer, payload_u8.byteOffset, payload_u8.byteLength);
        var fmap = {};
        for (var i = 0; i < m.fields.length; i++) fmap[m.fields[i].name] = m.fields[i];
        for (var j = 0; j < FIELDS_REQUIRED.length; j++) {
            if (!fmap[FIELDS_REQUIRED[j]]) return { pts: new Float32Array(0), n: 0, m: m };
        }
        var gx = _getter(dv, fmap.x, m.bigEndian);
        var gy = _getter(dv, fmap.y, m.bigEndian);
        var gz = _getter(dv, fmap.z, m.bigEndian);
        if (!gx || !gy || !gz) return { pts: new Float32Array(0), n: 0, m: m };
        var src_n = m.width * m.height;   // 对外语义=总点数；width 可能=点数 height=1
        // ROS1 unorganized cloud: height==1, width=N — 与 organized 都按 width*height 量
        var cap = Math.min(Math.ceil(src_n / stride), max_pts);
        var out = new Float32Array(cap * 3);
        var n_out = 0;
        for (var k = 0; k < src_n && n_out < cap; k += stride) {
            var b0 = m.dataOff + k * m.pointStep;
            var x = gx(b0), y = gy(b0), z = gz(b0);
            if (!isFinite(x) || !isFinite(y) || !isFinite(z)) continue;
            /* IFW192S invalid 点 = (0,0,0) 而不是 NaN — 丢弃（雷达中心无返回） */
            if (x === 0 && y === 0 && z === 0) continue;
            out[n_out * 3] = x; out[n_out * 3 + 1] = y; out[n_out * 3 + 2] = z;
            n_out++;
        }
        return { pts: out, n: n_out, m: m };
    }

    /* Foxglove WebSocket 客户端（ros1 编码，文本控制 + 二进制帧） */
    function connect(url, opts) {
        opts = opts || {};
        var render = opts.render || function () {};
        var on_state = opts.on_state || function () {};
        var on_error = opts.on_error || function () {};
        var stride = Math.max(1, opts.stride | 0 || 4);
        var max_pts = Math.max(1, opts.max_points | 0 || 40000);
        var topics = opts.topics || ["/innolidar_points"];
        var ws = null, closed = false;
        var chid_to_sub = {};      // channelId -> subId
        var subid_to_topic = {};   // subId -> topic
        var next_sub_id = 1;

        function _subscribe(ch) {
            if (topics.indexOf(ch.topic) < 0) return;
            if (ch.encoding !== "ros1") {
                on_error("话题 " + ch.topic + " 编码异常: " + ch.encoding);
                return;
            }
            /* FIX-REVIEW-M5: 重复 advertise 同一 channelId（bridge 重启/复用 id 时）
             * 必须先去重，避免双订双渲染。 */
            if (chid_to_sub[ch.id]) {
                _send({ op: "unsubscribe", subscriptionIds: [chid_to_sub[ch.id]] });
                delete subid_to_topic[chid_to_sub[ch.id]];
                delete chid_to_sub[ch.id];
            }
            var sub_id = next_sub_id++;
            chid_to_sub[ch.id] = sub_id;
            subid_to_topic[sub_id] = ch.topic;
            // foxglove.websocket.v1 订阅需数组形式
            _send({ op: "subscribe", subscriptions: [{ id: sub_id, channelId: ch.id }] });
        }
        function _send(obj) {
            if (ws && ws.readyState === 1) {
                try { ws.send(JSON.stringify(obj)); } catch (e) { /* ignore */ }
            }
        }
        function _on_text(txt) {
            var j;
            try { j = JSON.parse(txt); } catch (e) { on_error("JSON 解析失败: " + e.message); return; }
            if (j.op === "advertise" && j.channels) {
                for (var i = 0; i < j.channels.length; i++) _subscribe(j.channels[i]);
            } else if (j.op === "unadvertise" && j.channelIds) {
                for (var k = 0; k < j.channelIds.length; k++) {
                    var cid = j.channelIds[k];
                    if (chid_to_sub[cid]) {
                        delete subid_to_topic[chid_to_sub[cid]];
                        delete chid_to_sub[cid];
                    }
                }
            }
            // serverInfo / status 等都忽略
        }
        function _on_binary(ab) {
            var dv = new DataView(ab);
            if (dv.byteLength < 13) return;
            var op = dv.getUint8(0);
            if (op !== 1) return;              // 2=TIME 忽略
            var subId = dv.getUint32(1, true);
            var topic = subid_to_topic[subId];
            if (topic !== "/innolidar_points") return;   // 本模块只关心主点云
            try {
                var u8 = new Uint8Array(ab, 13);
                var r = subsample_xyz(u8, stride, max_pts);
                if (r.n > 0) render(r.pts, r.n);
            } catch (e) { on_error("帧处理异常: " + e.message); }
        }
        var _retry_ms = 1000, _retry_timer = null;
        function _open() {
            if (closed) return;
            var sock;
            try { sock = new WebSocket(url, ["foxglove.websocket.v1"]); }
            catch (e) { on_error("连接创建失败: " + e.message); _reconnect(); return; }
            sock.binaryType = "arraybuffer";
            ws = sock;
            sock.onopen = function () {
                /* FIX-REVIEW-M3: 旧 socket 的迟到事件不得污染新连接 */
                if (sock !== ws) return;
                chid_to_sub = {}; subid_to_topic = {}; next_sub_id = 1;
                _retry_ms = 1000;   /* FIX-REVIEW-M4: 连上后退避归零，下次瞬断仍 1s 起 */
                on_state(true);
            };
            sock.onmessage = function (ev) {
                if (sock !== ws) return;
                if (typeof ev.data === "string") _on_text(ev.data);
                else if (ev.data instanceof ArrayBuffer) _on_binary(ev.data);
            };
            sock.onclose = function () {
                if (sock !== ws) return;
                ws = null;
                on_state(false);
                _reconnect();
            };
            sock.onerror = function () { /* close 会处理 */ };
        }
        function _reconnect() {
            if (closed) return;
            if (_retry_timer) return;  // 已排程
            _retry_timer = setTimeout(function () {
                _retry_timer = null;
                _retry_ms = Math.min(_retry_ms * 2, 10000);
                _open();
            }, _retry_ms);
        }
        _open();
        return {
            close: function () {
                closed = true;
                if (_retry_timer) { clearTimeout(_retry_timer); _retry_timer = null; }
                if (ws) { try { ws.close(); } catch (e) {} }
            },
            url: url,
        };
    }

    return {
        parse_pc2: parse_pc2,
        subsample_xyz: subsample_xyz,
        connect: connect,
    };
})();

/* node 测试钩子（不影响浏览器） */
if (typeof module !== "undefined" && module.exports) {
    module.exports = GT_LIVE;
}
