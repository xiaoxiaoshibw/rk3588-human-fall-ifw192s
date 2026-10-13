/* b2a_review_probe.js — B2-A-REVIEW 模式探针: 复刻旧 detect_overlay.associate (R1 冻结版).
 *
 * 用途: 产生 R1(before) 的 6 段 track 快照, 与 FIX-R1 后 (b2a_shadow_probe 重跑) 对比.
 * 与 b2a_shadow_probe 的唯一差异: associate 无 claimed 集 (审计 r1 版语义).
 * 跑法同 b2a_shadow_probe.
 */
"use strict";
var fs = require("fs"), path = require("path");
var RL = require("./human_replay_lib.js"), RF_PERSON = require("./rf_person.js");

var BG_CELL = 0.05;
function grid_key(x, y) { return Math.floor(x / BG_CELL) * 4096 + Math.floor(y / BG_CELL); }
function find_hot(frame, BG, z_lo, z_hi) {
    var hot = [];
    for (var k = 0; k < frame.n; k++) {
        var z = frame.z[k];
        if (z <= z_lo || z >= z_hi) continue;
        var key = grid_key(frame.x[k], frame.y[k]);
        var bg = BG && BG[key] !== undefined ? BG[key] : -10;
        if (bg < -9) continue;
        if (z > bg + 0.25) hot.push(k);
    }
    return hot;
}
function find_clusters(frame, hot) {
    if (!hot.length) return [];
    var grid = {};
    for (var i = 0; i < hot.length; i++) { var k = hot[i], key = grid_key(frame.x[k], frame.y[k]);
        (grid[key] = grid[key] || []).push(k); }
    var seen = {}, comps = [];
    for (var key in grid) {
        if (seen[key]) continue;
        var stack = [key], members = []; seen[key] = 1;
        while (stack.length) {
            var cur = stack.pop();
            members.push.apply(members, grid[cur]);
            var cgx = Math.floor(cur / 4096), cgy = cur % 4096;
            for (var dx = -1; dx <= 1; dx++) for (var dy = -1; dy <= 1; dy++) {
                var nk = (cgx + dx) * 4096 + (cgy + dy);
                if (grid[nk] && !seen[nk]) { seen[nk] = 1; stack.push(nk); }
            }
        }
        if (members.length >= 30) comps.push(members);
    }
    comps.sort(function (a, b) { return b.length - a.length; });
    return comps.slice(0, 4).map(function (members) {
        var xs = [], ys = [], zs = [];
        for (var i = 0; i < members.length; i++) { var k = members[i];
            xs.push(frame.x[k]); ys.push(frame.y[k]); zs.push(frame.z[k]); }
        xs.sort(); ys.sort();
        var cx = xs[xs.length >> 1], cy = ys[ys.length >> 1];
        var r = members.map(function (k) { var dx = frame.x[k]-cx, dy = frame.y[k]-cy; return dx*dx+dy*dy; })
            .sort(function (a, b) { return a - b; });
        return { members: members, cx: cx, cy: cy, r90: Math.sqrt(r[(r.length*0.9)|0]),
                 zmax: Math.max.apply(null, zs), n: members.length };
    });
}

/* ===== R1 冻结版 associate: 无 claimed 集 (审计对象语义) ===== */
var TRACK_GATE_M = 1.0, TRACK_TTL_FRAMES = 15, TRACK_MIN_AGE = 3;
function associate_r1(state, clusters, fps) {
    var alive = new Set();
    for (var c = 0; c < clusters.length; c++) {
        var cl = clusters[c], best = null, best_d = TRACK_GATE_M;
        for (var t = 0; t < state.tracks.length; t++) {
            var tr = state.tracks[t];
            var d = Math.hypot(cl.cx - tr.cx, cl.cy - tr.cy);
            if (d < best_d) { best_d = d; best = tr; }
        }
        if (best) { best.cx=cl.cx; best.cy=cl.cy; best.r90=cl.r90; best.zmax=cl.zmax;
                    best.n=cl.n; best.miss=0; best.age++; cl.track_id=best.id; }
        else { var tr = { id: state.t_id_next++, cx: cl.cx, cy: cl.cy, r90: cl.r90, zmax: cl.zmax,
                          n: cl.n, miss: 0, age: 1, born: state.frame_no };
               state.tracks.push(tr); cl.track_id = tr.id; }
        alive.add(cl.track_id);
    }
    for (var t = state.tracks.length-1; t >= 0; t--) {
        var tr = state.tracks[t];
        if (!alive.has(tr.id)) { tr.miss++; if (tr.miss > TRACK_TTL_FRAMES) state.tracks.splice(t,1); }
    }
}

function level_frame_passthrough(buf, start, count) {
    var n = count, out = { n:n, x:new Float32Array(n), y:new Float32Array(n), z:new Float32Array(n) };
    for (var k=0;k<n;k++){var o=(start+k)*7; out.x[k]=buf[o]; out.y[k]=buf[o+1]; out.z[k]=buf[o+2];}
    return out;
}
function load_session_leveled(root, sid) {
    var dir = path.join(root, sid);
    var meta = JSON.parse(fs.readFileSync(path.join(dir,"meta.json"),"utf8"));
    var buf = fs.readFileSync(path.join(dir,"points.bin"));
    var f32 = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset+buf.byteLength));
    var d=RL.DEFAULT_LEVEL_TRANSFORM, r=d.R, t=d.t, N=f32.length/7;
    for (var p=0;p<N;p++){var s=p*7,x=f32[s],y=f32[s+1],z=f32[s+2];
        f32[s]=r[0]*x+r[1]*y+r[2]*z+t[0]; f32[s+1]=r[3]*x+r[4]*y+r[5]*z+t[1]; f32[s+2]=r[6]*x+r[7]*y+r[8]*z+t[2];}
    return { meta:meta, buf_f32:f32, frames:RL.frame_slice(meta), fps:RL.default_fps(meta) };
}
function score(rf, clusters, frame, buf, start_pts){
    for (var ci=0; ci<clusters.length; ci++){var cl=clusters[ci];
        var sub={n:cl.members.length,x:new Float32Array(cl.members.length),y:new Float32Array(cl.members.length),z:new Float32Array(cl.members.length)};
        var inten=new Float32Array(cl.members.length);
        for(var mi=0;mi<cl.members.length;mi++){var k=cl.members[mi];
            sub.x[mi]=frame.x[k];sub.y[mi]=frame.y[k];sub.z[mi]=frame.z[k];inten[mi]=buf[(start_pts+k)*7+3];}
        cl.person_prob = rf.predict_person(rf.extract(sub,inten));
    }
}
function main(){
    var argv=process.argv.slice(2);
    var root=argv[0], out=argv[1], sids=argv.slice(2);
    fs.mkdirSync(out,{recursive:true});
    var BG=JSON.parse(fs.readFileSync(path.join(__dirname,"bg_envelope.json"),"utf8"));
    RF_PERSON.init(fs.readFileSync(path.join(__dirname,"rf_person_v1.json"),"utf8"));
    sids.forEach(function(sid){
        var sess=load_session_leveled(root,sid);
        var st={t_id_next:1,tracks:[],frame_no:0};
        var ws=fs.createWriteStream(path.join(out,sid+".tracks.jsonl"));
        for(var fi=0;fi<sess.frames.length;fi++){
            var f=sess.frames[fi];
            var frame=level_frame_passthrough(sess.buf_f32,f.start_pts,f.count);
            var clusters=find_clusters(frame,find_hot(frame,BG,0.1,2.3));
            score(RF_PERSON,clusters,frame,sess.buf_f32,f.start_pts);
            clusters=clusters.filter(function(c){return c.person_prob>=0.55;});
            st.frame_no++;
            associate_r1(st,clusters,sess.fps);
            var snap=st.tracks.map(function(tr){return{id:tr.id,age:tr.age,miss:tr.miss,
                cx:+tr.cx.toFixed(3),cy:+tr.cy.toFixed(3)};});
            ws.write(JSON.stringify({frame:fi,tracks:snap})+"\n");
        }
        ws.end();
        console.log("[r1] "+sid+" frames="+sess.frames.length+" tracks_final="+st.tracks.length);
    });
}
main();
