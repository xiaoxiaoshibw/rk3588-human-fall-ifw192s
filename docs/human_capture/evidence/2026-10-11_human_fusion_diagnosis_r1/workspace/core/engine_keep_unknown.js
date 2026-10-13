/* HUMAN-UNIFY-R1 离线适配器。生产源码只读；算法模块在每个实例独立闭包中执行。 */
"use strict";
var fs = require("fs"), path = require("path"), crypto = require("crypto"), vm = require("vm");
var S = require("./schema.js"), leveling = require("./leveling.js");
var PROD = path.join(__dirname, "../human_replay");
var MODE = Object.freeze({ BASE_A:"BASE_A", BASE_B:"BASE_B", U1:"U1", U2:"U2", U3:"U3", U4:"U4", U5:"U5", U6:"U6", FUSION:"FUSION" });
var FUSION_CFG_KEYS = ["fusion_cfg"];  /* cfg 顶层仅允许此 fusion 配置键, 由 _validate_mode_cfg 在 FUSION 下验真 */
var DEFAULT_CFG = {
    mode:MODE.U1, background:"online", candidates:"fg_only", classifier:"geometry_gate",
    rf51_threshold:0.55, confirm_window:5, confirm_votes:3, min_age_frames:3,
    track_gate_xy_m:0.75, track_lost_max:8, ema_alpha:0.35,
    retention:{ window_confirm:3, timeout_s:180, hot_cell_radius_m:0.4, max_lost_for_retain:30 },
    leveling_rt:null, hard_gate_n500:false, replay_policy:"strict", diagnostics:true,
};
function load_production(name) {
    // 原模块有闭包状态（RF trees/B tracks/A PIPE），Object.create 无法隔离闭包。
    // 不缓存可变工作树中的代码，且隔离生产模块的globalThis导出副作用。
    var factory = vm.compileFunction(fs.readFileSync(path.join(PROD, name), "utf8"), ["module", "globalThis"], {filename:name});
    var mod = {exports:{}}; factory(mod, {}); return mod.exports;
}
function hash_file(file) { return crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex"); }
function indices(n) { return Uint32Array.from({length:n}, function (_, i) { return i; }); }
/* 生产过滤器保持点顺序，逐点子序列匹配保留重复点各自的raw索引，O(N)。 */
function subset_indices(source, ids, subset) {
    var result = new Uint32Array(subset.length / 4), cursor = 0;
    for (var i = 0; i < result.length; i++) {
        while (cursor < ids.length) {
            var matches = true;
            for (var d = 0; d < 4; d++) if (!Object.is(source[cursor*4+d], subset[i*4+d])) { matches=false; break; }
            if (matches) break;
            cursor++;
        }
        if (cursor === ids.length) throw new Error("过滤器未保持点级子序列契约");
        result[i] = ids[cursor++];
    }
    return result;
}
function add_layer(diag, layer, start, in_pts, out_pts, in_cand, out_cand) {
    var item = S.make_layer_diag(layer);
    Object.assign(item, {in_points:in_pts||0, out_points:out_pts||0, in_candidates:in_cand||0, out_candidates:out_cand||0, elapsed_ms:performance.now()-start});
    diag.layers.push(item); return item;
}
function UnifiedEngine(cfg) {
    cfg = cfg || {};
    this.cfg = Object.assign({}, DEFAULT_CFG, cfg);
    this.cfg.retention = Object.assign({}, DEFAULT_CFG.retention, cfg.retention || {});
    var m = this.cfg.mode;
    if (m === MODE.U2 || m === MODE.U3 || m === MODE.U6) this.cfg.candidates = "fg_plus_retained";
    if (m === MODE.U3 || m === MODE.U6) this.cfg.classifier = "rf51";
    if (m === MODE.FUSION) { this.cfg.candidates = "fg_plus_retained"; this.cfg.classifier = "rf51"; this.cfg.background = "ref_only"; }
    if (m === MODE.U6 && cfg.track_lost_max === undefined) this.cfg.track_lost_max = 30;
    if (m === MODE.BASE_B) Object.assign(this.cfg, {background:"ref_only",classifier:"rf51",candidates:"fg_only",track_gate_xy_m:1,track_lost_max:15,ema_alpha:1,confirm_window:3,confirm_votes:3,min_age_frames:3});
    this._validate_mode_cfg(cfg);
    this.pipe = load_production("human_pipe_lib.js");
    Object.assign(this.pipe.PIPE, {track_gate_xy_m:this.cfg.track_gate_xy_m, track_lost_max:this.cfg.track_lost_max,
        ema_alpha:this.cfg.ema_alpha, human_confirm_window:this.cfg.confirm_window,
        human_confirm_votes:this.cfg.confirm_votes, human_confirm_min_age:this.cfg.min_age_frames});
    this.overlay = (m === MODE.BASE_B || m === MODE.FUSION) ? load_production("detect_overlay.js") : null;
    this.rf = null; this.rf_model_sha = null;
    if (this.cfg.classifier === "rf51") {
        this.rf = load_production("rf_person.js");
        var model = path.join(PROD, "rf_person_v1.json"); this.rf.init(fs.readFileSync(model,"utf8")); this.rf_model_sha=hash_file(model);
    }
    this.session_id=null; this.generation=0; this.track_log=[]; this.report_rows=[]; this._seen_frames=new Set();
}
UnifiedEngine.prototype._validate_mode_cfg = function (supplied) {
    var c=this.cfg, m=c.mode;
    if (m===MODE.U4 || m===MODE.U5) throw new Error(m+" BLOCKED — 无推理artifact");
    if (!Object.values(MODE).includes(m)) throw new Error("未知mode");
    var allowed = Object.keys(DEFAULT_CFG).concat(m===MODE.FUSION ? FUSION_CFG_KEYS : []);
    Object.keys(supplied).forEach(function(k){if (allowed.indexOf(k)<0) throw new Error("未知配置 "+k);});
    var b=m===MODE.BASE_B, f=m===MODE.FUSION;
    var fixed={background:"ref_only",classifier:"rf51",candidates:"fg_only",track_gate_xy_m:1,track_lost_max:15,ema_alpha:1,confirm_window:3,confirm_votes:3,min_age_frames:3,rf51_threshold:0.55,hard_gate_n500:false};
    if (b) Object.keys(fixed).forEach(function(k){if (supplied[k]!==undefined && supplied[k]!==fixed[k]) throw new Error("BASE_B固定生产配置 "+k);});
    if (!b && !f && c.background!=="online") throw new Error("尚未实现background "+c.background);
    if (!["geometry_gate","rf51"].includes(c.classifier)) throw new Error("未实现classifier");
    if (!["fg_only","fg_plus_retained"].includes(c.candidates)) throw new Error("未知candidates");
    if (!["strict","lenient"].includes(c.replay_policy)) throw new Error("未知replay_policy");
    ["confirm_window","confirm_votes","min_age_frames","track_lost_max"].forEach(function(k){if (!Number.isSafeInteger(c[k]) || c[k]<1) throw new Error("非法配置 "+k);});
    if (c.confirm_votes>c.confirm_window || !Number.isFinite(c.track_gate_xy_m) || c.track_gate_xy_m<=0 || !Number.isFinite(c.ema_alpha) || c.ema_alpha<=0 || c.ema_alpha>1 || !Number.isFinite(c.rf51_threshold) || c.rf51_threshold<0 || c.rf51_threshold>1) throw new Error("非法门限");
    var r=c.retention;
    Object.keys(r).forEach(function(k){if (!(k in DEFAULT_CFG.retention)) throw new Error("未实现retention "+k);});
    ["window_confirm","max_lost_for_retain"].forEach(function(k){if (!Number.isSafeInteger(r[k]) || r[k]<1) throw new Error("非法retention "+k);});
    ["timeout_s","hot_cell_radius_m"].forEach(function(k){if (!Number.isFinite(r[k]) || r[k]<=0) throw new Error("非法retention "+k);});
    if (c.leveling_rt) leveling.validate_rt(c.leveling_rt);
    if (f) {
        var F = require("./fusion.js").DEFAULT_FUSION_CFG;
        var fc = Object.assign({}, F, supplied.fusion_cfg || {});
        Object.keys(fc).forEach(function(k){ if (!(k in F)) throw new Error("未实现fusion "+k); });
        if (!Number.isFinite(fc.assoc_gate_xy_m) || fc.assoc_gate_xy_m<=0
            || !Number.isFinite(fc.track_gate_xy_m) || fc.track_gate_xy_m<=0
            || !Number.isSafeInteger(fc.track_lost_max) || fc.track_lost_max<1
            || !Number.isSafeInteger(fc.track_still_confirm_window) || fc.track_still_confirm_window<1
            || !Number.isSafeInteger(fc.track_still_confirm_votes) || fc.track_still_confirm_votes<1
            || fc.track_still_confirm_votes>fc.track_still_confirm_window
            || !Number.isSafeInteger(fc.track_still_confirm_min_age) || fc.track_still_confirm_min_age<1
            || !Number.isFinite(fc.rf51_threshold) || fc.rf51_threshold<0 || fc.rf51_threshold>1
            || (fc.bg_envelope_path!==null && typeof fc.bg_envelope_path!=="string")
            || (fc.online_background!==undefined && typeof fc.online_background!=="boolean")) throw new Error("非法fusion配置");
        if (c.classifier!=="rf51") throw new Error("FUSION 必须 rf51 (geometry_only 未实现)");
        if (fc.online_background===true) throw new Error("FUSION 暂不支持 online_background=true (空场自污染) — 用默认 ref_only");
        c.fusion_cfg = fc;
    }
};
UnifiedEngine.prototype.begin_session = function (session_id, reason) {
    if (session_id===undefined || session_id===null || String(session_id)==="") throw new Error("session_id为空");
    var sid=String(session_id), last=this.session_id;
    this.session_id=sid; this.generation++;
    this._seen_frames.clear(); this.report_rows=[]; this.retention={tracks:{}};
    this._last_frame_index=null; this._last_timestamp=null; this._coordinate_contract=null; this.track_segment=0;
    this._ever_confirmed=new Set(); this._all_track_ids=new Set();
    this.pipe_ctx={static_keys:null,tracker:new this.pipe.Tracker(),fusion:null};
    if (this.cfg.mode===MODE.FUSION) {
        var FM=require("./fusion.js"), fc=this.cfg.fusion_cfg;
        this.fusion_ctx={tracker:new FM.FusionTracker(fc), b_frame_no:0};
        this.load_ref_envelope(fc.bg_envelope_path||undefined);
    }
    if (this.overlay) this.overlay.reset();
    this.track_log.push({at:"session_begin",session_id:sid,generation:this.generation,reason:reason||(last===null?"new":last===sid?"loop_back":"session_switch")});
    return this.generation;
};
UnifiedEngine.prototype._level = function (xyzi, opts) {
    var contract=leveling.resolve_contract(opts,this.cfg.leveling_rt);
    if (this._coordinate_contract && JSON.stringify(contract)!==JSON.stringify(this._coordinate_contract)) throw new Error("会话背景/帧坐标契约冲突");
    this._coordinate_contract=contract;
    return leveling.level_frame(xyzi,contract.R,contract.T,contract.already_leveled);
};
UnifiedEngine.prototype.set_online_background = function (frames_xyzi, opts) {
    if (!this.pipe_ctx) throw new Error("先begin_session");
    var self=this;
    // 与human_detect.js一致：先配平、denoise，再建背景。
    var clean=frames_xyzi.map(function(x){return self.pipe.denoise(self._level(x,opts));});
    this.pipe_ctx.static_keys=this.pipe.build_static_map(clean,{drop_ground:true});
};
UnifiedEngine.prototype.load_ref_envelope = function (file) {
    file=file||path.join(PROD,"bg_envelope.json");
    this._ref_env=JSON.parse(fs.readFileSync(file,"utf8")); this._ref_env_sha=hash_file(file);
};
UnifiedEngine.prototype.tick = function (fc) {
    if (!this.pipe_ctx || fc.session_id!==this.session_id || fc.session_generation!==this.generation) throw new Error("过时session/代际（必须携带begin_session返回值）");
    var start=performance.now(), diag=S.make_diagnostics(fc.frame_id);
    if (this._seen_frames.has(fc.frame_id)) {
        if (this.cfg.replay_policy==="strict") throw new Error("重复帧 "+fc.frame_id);
        diag.notes.push("duplicate_frame_ignored"); return diag;
    }
    if (this._last_frame_index!==null && fc.frame_index<=this._last_frame_index) throw new Error("回退需begin_session重置");
    if (this._last_timestamp!==null && fc.timestamp<this._last_timestamp) throw new Error("timestamp回退");
    var leveled=this._level(fc.xyzi,fc);
    if (this.cfg.mode!==MODE.BASE_B && this.cfg.mode!==MODE.FUSION && !this.pipe_ctx.static_keys) throw new Error("online背景未set");
    if (this.cfg.mode===MODE.BASE_B && !this._ref_env) this.load_ref_envelope();
    add_layer(diag,S.LAYER.LEVELED,start,fc.n_points,fc.n_points);
    // 跳帧采用显式重置；不把未知中间帧当观测，不延续旧票窗或保留bank。
    if (this._last_frame_index!==null && fc.frame_index!==this._last_frame_index+1) {
        this.pipe_ctx.tracker=new this.pipe.Tracker(); if(this.overlay)this.overlay.reset();
        this.retention={tracks:{}}; this.track_segment++;
        if (this.fusion_ctx) {
            var FMF=require("./fusion.js"), fcw=this.cfg.fusion_cfg;
            this.fusion_ctx.tracker=new FMF.FusionTracker(fcw); this.fusion_ctx.b_frame_no=0;
        }
        this.track_log.push({at:"gap_reset",from:this._last_frame_index,to:fc.frame_index}); diag.notes.push("gap_reset");
    }
    if(this.cfg.mode===MODE.BASE_B)this._tick_base_b(fc,leveled,diag);
    else if(this.cfg.mode===MODE.FUSION)this._tick_fusion(fc,leveled,diag);
    else this._tick_pipechain(fc,leveled,diag);
    this._seen_frames.add(fc.frame_id); this._last_frame_index=fc.frame_index; this._last_timestamp=fc.timestamp;
    diag.total_ms=performance.now()-start;
    var mem=process.memoryUsage(); diag.peak_heap_mb=mem.heapUsed/1048576;diag.rss_mb=mem.rss/1048576;diag.external_mb=mem.external/1048576;
    var self=this; diag._tracks.forEach(function(t){var key=self.track_segment+":"+t.id;self._all_track_ids.add(key);if(t.human_confirmed && t.lost===0)self._ever_confirmed.add(key);});
    diag._candidates.forEach(function(c){c.track_segment=self.track_segment;});
    this.report_rows.push(this._flatten_frame_row(fc,diag)); return diag;
};
UnifiedEngine.prototype._tick_base_b = function (fc, leveled, diag) {
    var start=performance.now(), n=leveled.length/4;
    var frame={n:n,x:new Float32Array(n),y:new Float32Array(n),z:new Float32Array(n)}, hot=[];
    for(var k=0;k<n;k++){
        frame.x[k]=leveled[k*4];frame.y[k]=leveled[k*4+1];frame.z[k]=leveled[k*4+2];
        var z=frame.z[k], bg=this._ref_env[this.overlay._test.grid_key(frame.x[k],frame.y[k])];
        if(z>0.1 && z<2.3 && bg!==undefined && bg>=-9 && z>bg+0.25)hot.push(k);
    }
    add_layer(diag,S.LAYER.FOREGROUND,start,n,hot.length);
    start=performance.now();var clusters=this.overlay._test.find_clusters(frame,hot);
    add_layer(diag,S.LAYER.CLUSTER,start,hot.length,0,0,clusters.length);
    start=performance.now();var cands=[], accepted=[];
    for(var ci=0;ci<clusters.length;ci++){
        var cl=clusters[ci], sub={n:cl.members.length,x:new Float32Array(cl.n),y:new Float32Array(cl.n),z:new Float32Array(cl.n)}, inten=new Float32Array(cl.n);
        var zsum=0;
        for(var mi=0;mi<cl.n;mi++){var pp=cl.members[mi];sub.x[mi]=frame.x[pp];sub.y[mi]=frame.y[pp];sub.z[mi]=frame.z[pp];inten[mi]=leveled[pp*4+3];zsum+=sub.z[mi];}
        var prob=this.rf.predict_person(this.rf.extract(sub,inten)); cl.person_prob=prob;
        var c=S.make_candidate({candidate_id:"b_"+fc.frame_index+"_"+ci,point_indices:new Uint32Array(cl.members),centroid:{x:cl.cx,y:cl.cy,z:zsum/cl.n},point_count:cl.n,
            scores:{rf51:{prob:prob,threshold:this.cfg.rf51_threshold,model_sha:this.rf_model_sha}},classifier_decision:prob>=this.cfg.rf51_threshold?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN});
        cands.push(c);if(prob>=this.cfg.rf51_threshold)accepted.push(cl);else c.rejection_reasons.push("rf51_threshold");
        diag.cls_scores.push({candidate_id:c.candidate_id,model:"rf51",score:prob,decision:c.classifier_decision});
    }
    add_layer(diag,S.LAYER.CLASSIFIER,start,0,0,clusters.length,accepted.length);
    start=performance.now();this.overlay._dbg_state.frame_no++;this.overlay._test.associate(accepted,10);
    var tracks=this.overlay._dbg_state.tracks;
    accepted.forEach(function(cl){var c=cands[clusters.indexOf(cl)];c.track_id=cl.track_id;});
    diag._tracks=tracks.map(function(t){return {id:t.id,active:true,x:t.cx,y:t.cy,z:t.zmax,r90:t.r90,n:t.n,age:t.age,born_idx:t.born,last_seen:fc.frame_index-t.miss,lost:t.miss,human_confirmed:t.miss===0 && t.age>=3};});
    // 公共report当前tracks只是快照；B真正的寿命/关联只由原associate管理。
    this.pipe_ctx.tracker.tracks=diag._tracks;
    add_layer(diag,S.LAYER.TRACK,start,0,0,accepted.length,tracks.length);
    diag._candidates=cands;diag._events=[];
};
UnifiedEngine.prototype._tick_pipechain = function (fc, leveled, diag) {
    var pipe=this.pipe, start=performance.now(), clean=pipe.denoise(leveled);
    var clean_ids=subset_indices(leveled,indices(fc.n_points),clean);
    add_layer(diag,S.LAYER.DENOISE,start,fc.n_points,clean.length/4);
    start=performance.now();var fg=pipe.extract_foreground(clean,this.pipe_ctx.static_keys);
    var fg_ids=subset_indices(clean,clean_ids,fg.fg_xyzi);
    add_layer(diag,S.LAYER.FOREGROUND,start,clean.length/4,fg.n_fg);
    start=performance.now();var iso=pipe.cleanup_isolated_fg(fg.fg_xyzi);
    var final_ids=Array.from(subset_indices(fg.fg_xyzi,fg_ids,iso.xyzi));
    add_layer(diag,S.LAYER.CLEANUP,start,iso.fg_before_cleanup,iso.fg_after_cleanup);
    start=performance.now();var values=Array.from(iso.xyzi), sources=new Array(final_ids.length).fill(S.CAND_SRC.FG), seen=new Set(final_ids);
    if(this.cfg.candidates==="fg_plus_retained"){
        var bank=this.retention.tracks, rc=this.cfg.retention, live=[];
        Object.keys(bank).forEach(function(id){var a=bank[id];if(fc.timestamp-a.timestamp>rc.timeout_s || fc.frame_index-a.frame_index>rc.max_lost_for_retain)delete bank[id];else if(a.confirmations>=rc.window_confirm)live.push(a);});
        for(var k=0;k<clean_ids.length;k++){
            if(seen.has(clean_ids[k]))continue;
            var x=clean[k*4],y=clean[k*4+1],z=clean[k*4+2];
            if(z<pipe.PIPE.ground_keep_below_m || z>pipe.PIPE.z_max_m)continue;
            if(live.some(function(a){return (x-a.x)*(x-a.x)+(y-a.y)*(y-a.y)<=rc.hot_cell_radius_m*rc.hot_cell_radius_m;})){
                values.push(x,y,z,clean[k*4+3]);final_ids.push(clean_ids[k]);sources.push(S.CAND_SRC.RETAINED);seen.add(clean_ids[k]);
            }
        }
    }
    var fg_final=new Float32Array(values), added=final_ids.length-iso.xyzi.length/4;
    add_layer(diag,S.LAYER.RETAINED,start,iso.fg_after_cleanup,fg_final.length/4).notes.push("added="+added);
    start=performance.now();var clusters=pipe.cluster_voxels(pipe.voxelize(fg_final)), ev=pipe.evidence_postpass(fg_final,clusters);
    add_layer(diag,S.LAYER.CLUSTER,start,fg_final.length/4,0,0,clusters.length);
    // 扫一遍点，生成每簇raw索引/来源；RF与Candidate消费同一份点。
    var owners=new Map(), members=clusters.map(function(){return [];});
    clusters.forEach(function(cl,i){cl.keys.forEach(function(key){owners.set(key,i);});});
    for(var p=0;p<final_ids.length;p++){var owner=owners.get(pipe.key_vox(fg_final[p*4],fg_final[p*4+1]));if(owner!==undefined)members[owner].push(p);}
    start=performance.now();var cands=[], invalid=0;
    for(var i=0;i<clusters.length;i++){
        var f=pipe.cluster_features(clusters[i]);if(!f.ok || (this.cfg.hard_gate_n500 && f.n<500)){invalid++;continue;}
        var cg=pipe.classify_human(f);f.label=cg.label;f.confidence=cg.confidence;f.reasons=cg.reasons;f.evidence=ev.clusters_extra[i];f.evidence_tag=pipe.evidence_label(f.evidence);f.joint=pipe.joint_status(f);
        var decision=f.joint==="CONFIRMED_HUMAN"?S.CLS_DECISION.CONFIRMED_HUMAN:f.joint==="HUMAN_CANDIDATE"?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN;
        var scores={geometry:{gates:f.confidence,label:f.label}}, mem=members[i];
        if(this.cfg.classifier==="rf51"){
            var sub={n:mem.length,x:new Float32Array(mem.length),y:new Float32Array(mem.length),z:new Float32Array(mem.length)}, inten=new Float32Array(mem.length);
            mem.forEach(function(pp,mi){sub.x[mi]=fg_final[pp*4];sub.y[mi]=fg_final[pp*4+1];sub.z[mi]=fg_final[pp*4+2];inten[mi]=fg_final[pp*4+3];});
            var prob=this.rf.predict_person(this.rf.extract(sub,inten));scores.rf51={prob:prob,threshold:this.cfg.rf51_threshold,model_sha:this.rf_model_sha};
            decision=prob>=this.cfg.rf51_threshold?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN;f.joint=prob>=this.cfg.rf51_threshold?"CONFIRMED_HUMAN":"NON_HUMAN";
        }
        var retained=mem.filter(function(pp){return sources[pp]===S.CAND_SRC.RETAINED;}).length;
        var source=retained===0?S.CAND_SRC.FG:retained===mem.length?S.CAND_SRC.RETAINED:S.CAND_SRC.MERGED;
        var min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
        mem.forEach(function(pp){for(var d=0;d<3;d++){min[d]=Math.min(min[d],fg_final[pp*4+d]);max[d]=Math.max(max[d],fg_final[pp*4+d]);}});
        var c=S.make_candidate({candidate_id:"a_"+fc.frame_index+"_"+i,point_indices:Uint32Array.from(mem,function(pp){return final_ids[pp];}),centroid:{x:f.cx,y:f.cy,z:f.cz},bbox:{min:min,max:max},point_count:mem.length,
            foreground_source:source,gen_reason:retained?S.GEN_REASON.SELF_RETAINED_RENEW:S.GEN_REASON.CLUSTER,geo_features:f,evidence_tag:f.evidence_tag,scores:scores,classifier_decision:decision,rejection_reasons:f.reasons||[],cluster_keys:clusters[i].keys});
        c._pipe_f=f;cands.push(c);diag.cls_scores.push({candidate_id:c.candidate_id,model:this.cfg.classifier,score:scores.rf51?scores.rf51.prob:f.confidence,decision:decision});
    }
    var accepted=cands.filter(function(c){return c.classifier_decision===S.CLS_DECISION.HUMAN_CANDIDATE || c.classifier_decision===S.CLS_DECISION.CONFIRMED_HUMAN;});
    add_layer(diag,S.LAYER.CLASSIFIER,start,0,0,clusters.length,accepted.length).reject_reasons.invalid_cluster=invalid;
    start=performance.now();this.pipe_ctx.tracker.tick(fc.frame_index,cands.map(function(c){return c._pipe_f;}));
    var tracks=this.pipe_ctx.tracker.tracks, self=this;
    cands.forEach(function(c){c.track_id=c._pipe_f.track_id;});
    // 仅独立FG确认刷新锚点。retained/merged再确认不续命，避免家具自维持。
    tracks.forEach(function(t){
        if(!t.active || !t.human_confirmed)return;
        if(!cands.some(function(c){return c.track_id===t.id && c.foreground_source===S.CAND_SRC.FG && c._pipe_f.joint==="CONFIRMED_HUMAN";}))return;
        var old=self.retention.tracks[t.id];
        self.retention.tracks[t.id]={x:t.x,y:t.y,timestamp:fc.timestamp,frame_index:fc.frame_index,confirmations:old && old.frame_index===fc.frame_index-1?old.confirmations+1:1};
    });
    diag._tracks=tracks.filter(function(t){return t.active;});diag._candidates=cands;
    diag._events=diag._tracks.map(function(t){var ev=pipe.fall_assess(t);return ev?Object.assign({track_id:t.id},ev):null;}).filter(Boolean);
    add_layer(diag,S.LAYER.TRACK,start,0,0,cands.length,diag._tracks.length);
};

/* ---------- FUSION 分支 (F2 统一融合) ---------- */

/* REF 包络 → PIPE static_keys (供 FUSION 的 ref_only 前景分割; 只算一次缓存) */
UnifiedEngine.prototype._build_ref_static_keys = function () {
    if (this._ref_static_keys) return this._ref_static_keys;
    var gz={}, env=this._ref_env;
    Object.keys(env).forEach(function(gk){ var z=env[gk]; if (typeof z!=="number") return; gz[gk]=Math.max(z, z+0.05); });
    var sk=new Map();
    /* 与 human_pipe_lib.build_static_map(denoised frames, drop_ground) 同键语义:
       key 5cm 网格 → dense z bands, 但实际生产实现是 voxelize 10cm 键。 用 10cm 与线上同键。 */
    Object.keys(env).forEach(function(gk_s){
        var gk=Number(gk_s), z=env[gk_s];
        if (typeof z!=="number" || z<0.05) return;
        var kx=Math.floor(gk/4096), ky=gk-kx*4096;
        var k10x=Math.floor(kx/2), k10y=Math.floor(ky/2);
        var k10=k10x*2048+k10y;
        if (!sk.has(k10)) sk.set(k10, {z_min:Infinity, z_max:-Infinity});
        var band=sk.get(k10);
        if (z<band.z_min) band.z_min=z;
        if (z>band.z_max) band.z_max=z;
    });
    this._ref_static_keys=sk; return sk;
};

/* A 链: 对 leveled 帧跑 U3 同构 PIPE 链 (fg/retained/candidates/同本实例 PIPE/RF)。
 * 背景: FUSION 固定 ref_only (online 空场背景会自污染 — S1 empty 实测 accepted=304/304);
 * 若 fusion_cfg.bg_envelope_path 指定则用该 envelope, 否则用生产默认 (同 BASE_B)。 */
UnifiedEngine.prototype._fusion_a_chain = function (fc, leveled, diag) {
    var pipe=this.pipe, start=performance.now();
    /* ref_only: 直接按 envelope 热点过滤, 不经 build_static_map */
    var env=this._ref_env, n0=leveled.length/4, hot=[];
    for(var k=0;k<n0;k++){
        var x=leveled[k*4],y=leveled[k*4+1],z=leveled[k*4+2];
        if(z<=0.1||z>=2.3)continue;
        var bg=env[this.overlay._test.grid_key(x,y)];
        if(bg===undefined||bg<-9)bg=z-0.251;
        if(z<=bg+0.25)continue;
        hot.push(k);
    }
    var fg_pts=new Float32Array(hot.length*4);
    for(var hi=0;hi<hot.length;hi++){fg_pts.set(leveled.subarray(hot[hi]*4,hot[hi]*4+4),hi*4);}
    add_layer(diag,S.LAYER.FOREGROUND,start,n0,hot.length);
    start=performance.now();
    var iso=pipe.cleanup_isolated_fg(fg_pts);
    var final_ids=new Array(hot.length);
    for(var k2=0;k2<hot.length;k2++)final_ids[k2]=hot[k2];
    add_layer(diag,S.LAYER.CLEANUP,start,iso.fg_before_cleanup,iso.fg_after_cleanup);
    final_ids=Array.from(subset_indices(fg_pts,final_ids,iso.xyzi));
    var values=Array.from(iso.xyzi), sources=new Array(final_ids.length).fill(S.CAND_SRC.FG), seen=new Set(final_ids);
    if(this.cfg.candidates==="fg_plus_retained"){
        var bank=this.retention.tracks, rc=this.cfg.retention, live=[];
        Object.keys(bank).forEach(function(id){var a=bank[id];if(fc.timestamp-a.timestamp>rc.timeout_s || fc.frame_index-a.frame_index>rc.max_lost_for_retain)delete bank[id];else if(a.confirmations>=rc.window_confirm)live.push(a);});
        /* ref_only 分支没有 clean_ids; 直接在 leveled 帧上找「在 live anchor 半径内」的新点 */
        var nlev=leveled.length/4;
        for(var k=0;k<nlev;k++){
            if(seen.has(k))continue;
            var x=leveled[k*4],y=leveled[k*4+1],z=leveled[k*4+2];
            if(z<pipe.PIPE.ground_keep_below_m || z>pipe.PIPE.z_max_m)continue;
            if(live.some(function(a){return (x-a.x)*(x-a.x)+(y-a.y)*(y-a.y)<=rc.hot_cell_radius_m*rc.hot_cell_radius_m;})){
                values.push(x,y,z,leveled[k*4+3]);final_ids.push(k);sources.push(S.CAND_SRC.RETAINED);seen.add(k);
            }
        }
    }
    var fg_final=new Float32Array(values), added=final_ids.length-iso.xyzi.length/4;
    add_layer(diag,S.LAYER.RETAINED,start,iso.fg_after_cleanup,fg_final.length/4).notes.push("added="+added);
    start=performance.now();var clusters=pipe.cluster_voxels(pipe.voxelize(fg_final)), ev=pipe.evidence_postpass(fg_final,clusters);
    add_layer(diag,S.LAYER.CLUSTER,start,fg_final.length/4,0,0,clusters.length);
    var owners=new Map(), members=clusters.map(function(){return [];});
    clusters.forEach(function(cl,i){cl.keys.forEach(function(key){owners.set(key,i);});});
    for(var p=0;p<final_ids.length;p++){var owner=owners.get(pipe.key_vox(fg_final[p*4],fg_final[p*4+1]));if(owner!==undefined)members[owner].push(p);}
    start=performance.now();var cands=[], invalid=0;
    for(var i=0;i<clusters.length;i++){
        var f=pipe.cluster_features(clusters[i]);if(!f.ok || (this.cfg.hard_gate_n500 && f.n<500)){invalid++;continue;}
        var cg=pipe.classify_human(f);f.label=cg.label;f.confidence=cg.confidence;f.reasons=cg.reasons;f.evidence=ev.clusters_extra[i];f.evidence_tag=pipe.evidence_label(f.evidence);f.joint=pipe.joint_status(f);
        var mem=members[i], scores={geometry:{gates:f.confidence,label:f.label}};
        var prob=null;
        {
            var sub={n:mem.length,x:new Float32Array(mem.length),y:new Float32Array(mem.length),z:new Float32Array(mem.length)}, inten=new Float32Array(mem.length);
            mem.forEach(function(pp,mi){sub.x[mi]=fg_final[pp*4];sub.y[mi]=fg_final[pp*4+1];sub.z[mi]=fg_final[pp*4+2];inten[mi]=fg_final[pp*4+3];});
            prob=this.rf.predict_person(this.rf.extract(sub,inten));scores.rf51={prob:prob,threshold:this.cfg.rf51_threshold,model_sha:this.rf_model_sha};
            if(prob>=this.cfg.rf51_threshold) f.joint="CONFIRMED_HUMAN"; else f.joint="NON_HUMAN";
        }
        var retained=mem.filter(function(pp){return sources[pp]===S.CAND_SRC.RETAINED;}).length;
        var source=retained===0?S.CAND_SRC.FG:retained===mem.length?S.CAND_SRC.RETAINED:S.CAND_SRC.MERGED;
        var min=[Infinity,Infinity,Infinity],max=[-Infinity,-Infinity,-Infinity];
        mem.forEach(function(pp){for(var d=0;d<3;d++){min[d]=Math.min(min[d],fg_final[pp*4+d]);max[d]=Math.max(max[d],fg_final[pp*4+d]);}});
        var c=S.make_candidate({candidate_id:"a_"+fc.frame_index+"_"+i,point_indices:Uint32Array.from(mem,function(pp){return final_ids[pp];}),centroid:{x:f.cx,y:f.cy,z:f.cz},bbox:{min:min,max:max},point_count:mem.length,
            foreground_source:source,gen_reason:retained?S.GEN_REASON.SELF_RETAINED_RENEW:S.GEN_REASON.CLUSTER,geo_features:f,evidence_tag:f.evidence_tag,scores:scores,classifier_decision:S.CLS_DECISION.UNKNOWN,rejection_reasons:f.reasons||[],cluster_keys:clusters[i].keys});
        c._pipe_f=f; c.rf51_prob=prob; cands.push(c);
        diag.cls_scores.push({candidate_id:c.candidate_id,model:"rf51",score:prob,decision:c.classifier_decision});
    }
    return {cands:cands, final_ids:final_ids, sources:sources, fg_final:fg_final, invalid:invalid};
};

/* B 链: 在「A 的 final_ids 点视图」上找 ref-envelope 簇并过 RF。
 * 只加工 A 没消费的独立点(可能由 retained bank 加回); A 已覆盖的 body 点不重复成簇。
 * 返回 {items:[{candidate 半成品, frame_pos_intens}]} — items 都是「B 判定为 person 候选」的点集合。 */
UnifiedEngine.prototype._fusion_b_chain = function (fc, leveled, diag, a_out) {
    var start=performance.now(), pipe=this.pipe;
    var final_ids=a_out.final_ids, fg_final=a_out.fg_final;
    var n=final_ids.length;
    var frame={n:n,x:new Float32Array(n),y:new Float32Array(n),z:new Float32Array(n)}, intens=new Float32Array(n);
    for(var k=0;k<n;k++){frame.x[k]=fg_final[k*4];frame.y[k]=fg_final[k*4+1];frame.z[k]=fg_final[k*4+2];intens[k]=fg_final[k*4+3];}
    /* PERF-R3 M1: O(N^2) indexOf -> Map 一次性构建 O(N), 语义等价输出 */
    var pos_by_id = new Map();
    for (var k3 = 0; k3 < n; k3++) pos_by_id.set(final_ids[k3], k3);
    a_out.cands.forEach(function(c){
        c._fusion_positions=[];
        Array.from(c.point_indices).forEach(function(pi){
            var idx = pos_by_id.get(pi); c._fusion_positions.push({frame_pos:idx, intensity: intens[idx]||0});
        });
    });
    var in_b=new Uint8Array(n);
    a_out.cands.forEach(function(c){ c._fusion_positions.forEach(function(p){ in_b[p.frame_pos]=1; }); });
    var hot=[];
    for(var k2=0;k2<n;k2++){
        if(in_b[k2])continue;
        var x=frame.x[k2],y=frame.y[k2],z=frame.z[k2];
        if(z<=0.1||z>=2.3)continue;
        var bg=this._ref_env[this.overlay._test.grid_key(x,y)];
        if(bg===undefined||bg<-9)bg=z-0.251;
        if(z<=bg+0.25)continue;
        hot.push(k2);
    }
    add_layer(diag,S.LAYER.FOREGROUND+"_b",start,n,hot.length);
    start=performance.now();var clusters=this.overlay._test.find_clusters(frame,hot);
    add_layer(diag,S.LAYER.CLUSTER+"_b",start,hot.length,0,0,clusters.length);
    start=performance.now();var items=[], accepted_n=0;
    for(var ci=0;ci<clusters.length;ci++){
        var cl=clusters[ci];
        var inten=new Float32Array(cl.members.length), zsum=0;
        for(var mi=0;mi<cl.members.length;mi++){var pp=cl.members[mi];inten[mi]=intens[pp];zsum+=frame.z[pp];}
        var sub={n:cl.members.length,x:new Float32Array(cl.members.length),y:new Float32Array(cl.members.length),z:new Float32Array(cl.members.length)};
        for(var m2=0;m2<cl.members.length;m2++){var p2=cl.members[m2];sub.x[m2]=frame.x[p2];sub.y[m2]=frame.y[p2];sub.z[m2]=frame.z[p2];}
        var prob=this.rf.predict_person(this.rf.extract(sub,inten));
        items.push({frame_positions:cl.members.slice(), frame_intens:Array.from(inten),
            centroid:{x:cl.cx,y:cl.cy,z:zsum/cl.n}, point_count:cl.n,
            rf51_prob:prob, is_person:prob>=this.cfg.rf51_threshold,
            raw_indices:cl.members.map(function(pp){return final_ids[pp];})});
        if(prob>=this.cfg.rf51_threshold)accepted_n++;
        diag.cls_scores.push({candidate_id:"b_"+fc.frame_index+"_"+ci,model:"rf51",score:prob,decision:prob>=this.cfg.rf51_threshold?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN});
    }
    add_layer(diag,S.LAYER.CLASSIFIER+"_b",start,0,0,items.length,accepted_n);
    return items;
};

/* A/B 联合组织: 返回 fusion 候选 (含 source/decision/track_id 用于 FusionTracker 输入) + 更新 A track_id 关联。 */
UnifiedEngine.prototype._fusion_organize = function (fc, diag, a_out, b_items) {
    var cfg=this.cfg.fusion_cfg, gate2=cfg.assoc_gate_xy_m*cfg.assoc_gate_xy_m;
    /* 1) A 候选 dbo 挂接: _fusion_members = {frame_pos, intensity} */
    /* 2) B items ↔ A 候选 贪心关联 (质心门内成对; 失败独立) */
    var pairs=[], used_b=new Uint8Array(b_items.length);
    a_out.cands.forEach(function(ac){
        var best=-1,best_d2=gate2;
        for(var bi=0;bi<b_items.length;bi++){
            if(used_b[bi])continue;
            var it=b_items[bi];
            var dx=ac.centroid.x-it.centroid.x, dy=ac.centroid.y-it.centroid.y, d2=dx*dx+dy*dy;
            if(d2<best_d2){best_d2=d2;best=bi;}
        }
        if(best>=0){
            var merged_pos=new Map();
            ac._fusion_positions.forEach(function(p){merged_pos.set(p.frame_pos,p.intensity);});
            b_items[best].frame_positions.forEach(function(fp,bi2){ if(!merged_pos.has(fp)) merged_pos.set(fp,b_items[best].frame_intens[bi2]); });
            var fps=Array.from(merged_pos.keys()), fit=fps.map(function(k){return merged_pos.get(k);});
            var sub={n:fps.length,x:new Float32Array(fps.length),y:new Float32Array(fps.length),z:new Float32Array(fps.length)}, itn=new Float32Array(fit);
            fps.forEach(function(fp,mi){sub.x[mi]=a_out.fg_final[fp*4];sub.y[mi]=a_out.fg_final[fp*4+1];sub.z[mi]=a_out.fg_final[fp*4+2];});
            var prob=this.rf.predict_person(this.rf.extract(sub,itn));
            var decision=prob>=this.cfg.rf51_threshold?S.CLS_DECISION.CONFIRMED_HUMAN
                :(prob>=0.35?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN);
            if(prob<0.35 && ac.rf51_prob>=0.35 && b_items[best].rf51_prob<0.35) decision=S.CLS_DECISION.UNKNOWN;
            ac.classifier_decision=decision;
            ac.scores.rf51={prob:prob,threshold:this.cfg.rf51_threshold,model_sha:this.rf_model_sha};
            ac.scores.rf51_a=ac.rf51_prob; ac.scores.rf51_b=b_items[best].rf51_prob;
            // R5: public raw indices MUST represent the exact ordered scoring union.
            ac.point_indices=Uint32Array.from(fps,function(fp){return a_out.final_ids[fp];});
            ac.point_count=fps.length;
            ac.scoring_pointset_version="raw-union-v1";
            var lo=[Infinity,Infinity,Infinity],hi=[-Infinity,-Infinity,-Infinity];
            fps.forEach(function(fp){for(var d=0;d<3;d++){lo[d]=Math.min(lo[d],a_out.fg_final[fp*4+d]);hi[d]=Math.max(hi[d],a_out.fg_final[fp*4+d]);}});
            ac.bbox={min:lo,max:hi};
            // Association centroid stays the A anchor for R4 tracker parity; publish scoring centroid separately.
            ac.scoring_centroid={x:sub.x.reduce((a,b)=>a+b,0)/fps.length,y:sub.y.reduce((a,b)=>a+b,0)/fps.length,z:sub.z.reduce((a,b)=>a+b,0)/fps.length};
            ac.fusion_source_SRC="A+B";
            used_b[best]=1;b_items[best]._merged_into=ac;
        }
    }, this);
    /* 3) 未并入的 B items → 独立 B-only fusion 候选 */
    var self=this;
    var fusions=a_out.cands.slice();
    b_items.forEach(function(it,bi){
        if(used_b[bi]||!it.is_person)return;
        var sub={n:it.frame_positions.length,x:new Float32Array(it.frame_positions.length),y:new Float32Array(it.frame_positions.length),z:new Float32Array(it.frame_positions.length)}, inten=new Float32Array(it.frame_intens);
        it.frame_positions.forEach(function(fp,mi){sub.x[mi]=a_out.fg_final[fp*4];sub.y[mi]=a_out.fg_final[fp*4+1];sub.z[mi]=a_out.fg_final[fp*4+2];});
        var c=S.make_candidate({candidate_id:"b_"+fc.frame_index+"_"+bi,point_indices:Uint32Array.from(it.raw_indices),centroid:it.centroid,bbox:null,point_count:it.point_count,
            foreground_source:S.CAND_SRC.FG,gen_reason:S.GEN_REASON.CLUSTER,geo_features:null,evidence_tag:null,
            scores:{rf51:{prob:it.rf51_prob,threshold:self.cfg.rf51_threshold,model_sha:self.rf_model_sha}},classifier_decision:it.rf51_prob>=cfg.rf51_threshold?S.CLS_DECISION.CONFIRMED_HUMAN:S.CLS_DECISION.NON_HUMAN,rejection_reasons:[]});
        c.rf51_prob=it.rf51_prob;c.fusion_source_SRC="B";
        c._fusion_positions=it.frame_positions.map(function(fp,mi){return {frame_pos:fp,intensity:inten[mi]};});
        fusions.push(c);
    });
    /* 4) source 标记: A-only=A, B-only=B, merged=A+B; A-only 按 rf51_prob 定 decision */
    fusions.forEach(function(c){
        if(!c.fusion_source_SRC){
            c.fusion_source_SRC="A";
            var p=c.rf51_prob;
            c.classifier_decision=p>=self.cfg.rf51_threshold?S.CLS_DECISION.CONFIRMED_HUMAN
                :(p>=0.35?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN);
            /* 同步给 cls_scores 补 true decision (之前 fusion_a_chain 里写 UNKNOWN, 此处覆盖填上更准) */
            for(var ci=0;ci<diag.cls_scores.length;ci++){if(diag.cls_scores[ci].candidate_id===c.candidate_id){diag.cls_scores[ci].decision=c.classifier_decision;break;}}
        }
    });
    return fusions;
};

UnifiedEngine.prototype._tick_fusion = function (fc, leveled, diag) {
    var start=performance.now();
    /* A 链必走 retained (candidates 在 _validate_mode_cfg 时已被 FUSION 强制为 rf51; candidates 取默认 fg_plus_retained) */
    this.cfg.candidates="fg_plus_retained";
    var a_out=this._fusion_a_chain(fc,leveled,diag);
    start=performance.now();
    /* A 内部跟踪: A 链候选按 rf51 判定 (同 U3), 然后 PIPE.Tracker */
    a_out.cands.forEach(function(c){
        /* a_out 内已按 merge 前概率设置 f.joint; 此处重算一遍决策用于 PIPE track */
        var p=c.rf51_prob;
        var decision=p>=this.cfg.rf51_threshold?S.CLS_DECISION.CONFIRMED_HUMAN:(p>=0.35?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN);
        c.classifier_decision_auc=decision;
        if(p>=this.cfg.rf51_threshold) c._pipe_f.joint="CONFIRMED_HUMAN"; else c._pipe_f.joint="NON_HUMAN";
    }, this);
    this.pipe_ctx.tracker.tick(fc.frame_index, a_out.cands.map(function(c){return c._pipe_f;}));
    var a_tracks=this.pipe_ctx.tracker.tracks, self=this;
    a_out.cands.forEach(function(c){c.track_id=c._pipe_f.track_id;});
    /* 保留 bank: 只收 FG+confirmed 的 A 候选 */
    a_tracks.forEach(function(t){
        if(!t.active||!t.human_confirmed)return;
        var hit=a_out.cands.some(function(c){return c.track_id===t.id && c.foreground_source===S.CAND_SRC.FG && c.classifier_decision_auc===S.CLS_DECISION.CONFIRMED_HUMAN;});
        if(!hit)return;
        var old=self.retention.tracks[t.id];
        self.retention.tracks[t.id]={x:t.x,y:t.y,timestamp:fc.timestamp,frame_index:fc.frame_index,confirmations:old && old.frame_index===fc.frame_index-1?old.confirmations+1:1};
    });
    add_layer(diag,S.LAYER.CLASSIFIER,start,0,0,a_out.cands.length,a_out.cands.filter(function(c){return c.classifier_decision_auc===S.CLS_DECISION.CONFIRMED_HUMAN;}).length);
    /* B 链 */
    var b_items=this._fusion_b_chain(fc,leveled,diag,a_out);
    var fusions=this._fusion_organize(fc,diag,a_out,b_items);
    /* FUSION tracker */
    start=performance.now();
    fusions.forEach(function(c){c.track_segment=self.track_segment;});
    this.fusion_ctx.tracker.tick(fc.frame_index, fusions);
    var ft=this.fusion_ctx.tracker.tracks.filter(function(t){return t.active;});
    diag._tracks=ft.map(function(t){return {id:t.id,track_segment:t.track_segment,track_id_fusion:"FUS_t"+t.track_segment+"_"+t.id,active:true,
        x:t.x,y:t.y,z:t.z,lost:t.lost,born_frame_idx:t.born_frame_idx,last_seen:t.last_seen,
        human_confirmed:t.human_confirmed,source_a_hit:!!t.source_a_hit,source_b_hit:!!t.source_b_hit};});
    diag._candidates=fusions;
    diag._events=ft.map(function(t){
        var hx=t.pose_history; if(!hx||hx.length<10)return null;
        var ev=self.pipe.fall_assess({pose_history:hx, active:true, id:t.id});
        return ev?Object.assign({track_id:"FUS_t"+t.track_segment+"_"+t.id},ev):null;
    }).filter(Boolean);
    add_layer(diag,S.LAYER.TRACK,start,0,0,fusions.length,ft.length);
};

UnifiedEngine.prototype._flatten_frame_row = function (fc, diag) {
    var row={session_id:fc.session_id,session_generation:this.generation,track_segment:this.track_segment,frame_index:fc.frame_index,timestamp:fc.timestamp,total_ms:+diag.total_ms.toFixed(2)};
    diag.layers.forEach(function(l){row[l.layer+"_in"]=l.in_points;row[l.layer+"_out_pts"]=l.out_points;row[l.layer+"_out_cand"]=l.out_candidates;row[l.layer+"_ms"]=+l.elapsed_ms.toFixed(2);});
    var accepted=diag._candidates.filter(function(c){return c.classifier_decision===S.CLS_DECISION.HUMAN_CANDIDATE || c.classifier_decision===S.CLS_DECISION.CONFIRMED_HUMAN;}).length;
    row.n_cand=diag._candidates.length;row.n_accepted_cand=accepted;row.n_rejected_cand=diag._candidates.length-accepted;
    row.n_tracks_active=diag._tracks.length;row.n_tracks_confirmed_current=diag._tracks.filter(function(t){return t.human_confirmed && t.lost===0;}).length;
    row.n_fall_events=diag._events.length;return row;
};
UnifiedEngine.prototype.report = function () {
    var tracks=this.pipe_ctx?this.pipe_ctx.tracker.tracks:[];
    var fusion_tracks=this.fusion_ctx?this.fusion_ctx.tracker.tracks:null;
    return {session_id:this.session_id,generation:this.generation,rows:this.report_rows,
        tracks:fusion_tracks||tracks,
        fusion_track_ids:fusion_tracks?fusion_tracks.map(function(t){return "FUS_t"+t.track_segment+"_"+t.id;}):undefined,
        pipe_track_ids:tracks.map(function(t){return t.id;}),
        track_ids:Array.from(this._all_track_ids||[]),ever_confirmed_track_ids:Array.from(this._ever_confirmed||[]),
        config:this.cfg,rf_model_sha:this.rf_model_sha,ref_env_sha:this._ref_env_sha,coordinate_contract:this._coordinate_contract};
};
module.exports={UnifiedEngine:UnifiedEngine,MODE:MODE,DEFAULT_CFG:DEFAULT_CFG,load_production:load_production,hash_file:hash_file};
