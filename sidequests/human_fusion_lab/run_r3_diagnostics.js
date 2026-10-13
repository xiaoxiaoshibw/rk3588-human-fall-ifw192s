'use strict';
/* R3 只读诊断运行器（CC 主线）。
 * 目的：在九会话真实驱动数据上逐帧量化：
 *   1) 默认 FusionTracker 的同帧共享 ID（重复 ID）与 ID 闪烁；
 *   2) 一对一 UniqueTracker 的同一指标（对照，证明唯一赋值修复）；
 *   3) 确认票/最短存活违反（tracker-confirmation 语义缺陷）；
 *   4) 每模型逐帧 候选/轨迹 TP/FP/FN（窄已标分母，诚实）与逐层漏检归因；
 *   5) geometry(post) 决策与 track_confirmed 的不一致计数。
 * 只写 results/R3_*.json 新命名空间（不覆盖 COMPARISON/ATTRIBUTION/旧证据）。
 * 不改任何链源文件；通过引擎 cfg 内建键以非破坏方式挂接对照 tracker。 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const D=require('./core/data_loader'),S=require('./core/schema'),L=require('./core/leveling');
const {createDetector}=require('./detector');
const {UniqueTracker}=require('./unique_tracker');
const {objects,rawMap}=require('./export');
const EV=require('./core/evaluate_fusion_gt');
const audit=JSON.parse(fs.readFileSync(path.join(__dirname,'results/AUDIT.json'),'utf8'));
const ROOT=process.env.HF_REPO_ROOT||path.resolve(__dirname,'../..');
const OUT=path.join(__dirname,'results','R3_DIAGNOSTICS.json');
const OUT_FLICKER=path.join(__dirname,'results','R3_ID_FLICKER.json');
const OUT_VOTES=path.join(__dirname,'results','R3_CONFIRM_VOTES.json');
const OUT_GEO=path.join(__dirname,'results','R3_GEOMETRY_CONSISTENCY.json');
const OUT_PERF=path.join(__dirname,'results','R3_PER_MODEL_PERF.json');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const MODELS=['rf51_baseline','rf51_candidate','xgb69_candidate'];
const GATE_M=0.75;

function presence(doc,index){
  if(!doc)return null;
  const fo=doc.frames_objects||{};
  const ids=fo[String(index)];
  return Array.isArray(ids)&&ids.length>0;
}

/* 挂接对照 tracker：利用引擎 begin/segment 转换处读取 cfg.fusion_cfg.tracker_ctor 的内建键，
 * 不改链源文件；仅在引擎期望 FusionTracker 时替换为 UniqueTracker 实例。 */
function installUniqueNonDestructive(eng){
  try{
    if(!eng.cfg)eng.cfg={};
    if(!eng.cfg.fusion_cfg)eng.cfg.fusion_cfg=Object.assign({},require('./core/fusion').DEFAULT_FUSION_CFG);
    eng.cfg.fusion_cfg.tracker_ctor='unique';
  }catch(e){/* 引擎若不支持该键则回退：调用方检测实际 tracker 类型 */}
}

function runSession(sid,model,useUnique,forceGeometry){
  const rec=audit.sessions.find(r=>r.sid===sid);
  if(!rec||!rec.eligible)return {sid,model,skipped:'NOT_ELIGIBLE'};
  const session=D.load_session(path.join(ROOT,'captures/remote',sid));
  if(session.meta_sha256!==rec.input_sha256.meta||session.points_sha256!==rec.input_sha256.points)throw Error('capture SHA changed: '+sid);
  const det=createDetector(forceGeometry?'geometry':model);
  if(useUnique)installUniqueNonDestructive(det.engine);
  if(useUnique)require('./unique_tracker').install(det.engine); // 生产同款非破坏挂接：begin 时换 tracker 实例
  const generation=det.begin(sid); // generation 握手：tick 必须携带
  let doc=audit.docs[sid]||null;
  const docOk=doc&&doc.session_id===sid&&doc.review_status==='reviewed'&&fs.existsSync(rec.gt_path)
    &&hash(fs.readFileSync(rec.gt_path))===rec.gt_sha256;
  if(!docOk)doc=null;
  const trackerKinds=new Set();
  const out={sid,model,activity:rec.activity,detector:det.name,unique:!!useUnique,frames:session.frames.length,
    frames_with_gt:0,
    candidate:{tp:0,fp:0,fn:0},track:{tp:0,fp:0,fn:0},
    duplicate_id_frames:[],id_flicker_frames:[],confirm_vote_violations:[],layer_miss:[],
    furniture_fp_frames:0,geometry_mismatch:0,geometry_mismatch_examples:[],unknown_frames:0};
  let prevAssigned=new Map(), prevKeys=new Set();
  const n=session.frames.length;
  for(let fi=0;fi<n;fi++){
    const f=session.frames[fi];
    const d=det.tick(S.make_frame_context({session_id:sid,session_generation:generation,frame_index:fi,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta}));
    const cands=d._candidates||[];
    const tracks=(d._tracks||[]).filter(t=>t&&t.active);
    for(const t of tracks)trackerKinds.add(t.constructor&&t.constructor.name||'unknown');
    // --- 1) 同帧共享 ID ---
    const assigned={};
    for(const c of cands){ if(c.track_id!=null){ if(assigned[c.track_id]===undefined)assigned[c.track_id]=[]; assigned[c.track_id].push(c.candidate_id);} }
    const shared=Object.keys(assigned).filter(k=>assigned[k].length>1);
    if(shared.length)out.duplicate_id_frames.push({frame:fi,track_ids:shared.map(k=>({track_id:k,candidates:assigned[k]}))});
    // --- 2) ID 闪烁：只有一帧没证据的 track 短暂丢失后重现 ---
    const keys=new Set(Object.keys(assigned)); // 正确：track_id 集合
    for(const k of keys){ if(prevKeys.size&&!prevKeys.has(k)){
      // 重现？查该 track 是否在更早某帧以其它 candidate 出现
      // 简化闪烁计数：candidate 保留上轮被指派但本轮换 ID 的。
    }}
    for(const k of Object.keys(prevAssigned)){
      // candidate 连续性近似闪烁：上一轮出现的 candidate_id 本轮得到不同 track_id
    }
    for(const c of cands){
      const cid=c.candidate_id;
      if(prevAssigned[cid]!==undefined&&prevAssigned[cid]!==c.track_id){
        out.id_flicker_frames.push({frame:fi,candidate:cid,prev:prevAssigned[cid],now:c.track_id});
      }
    }
    prevAssigned={};for(const c of cands)prevAssigned[c.candidate_id]=c.track_id;prevKeys=new Set(Object.values(prevAssigned));
    // --- 3) 确认票违反：human_confirmed 须 = (window 内票数和>=确认票 且 存活>=最短帧) ---
    /* 确认票核验（修正 off-by-one）：valid 语义应为
     *   human_confirmed == ( 截至本帧最近 window 张票之和 >= votes  且  当帧存活时长 >= min_age )。
     * 关键：t.votes 在 tick 内先 push 本票再 shift 截断；human_confirmed 在"未超窗"帧
     * 用"已投全部票"判定。故正确预期窗口 = 本帧投完后的 votes 数组本身（已含 shift），
     * 但存活时长须在"判定那一刻"（ticket 投出帧）回看。直接以 track 自报 votes 数组复算，
     * 且把"确认"定义为幂等：confirmed(track 的 votes) 应与 track.human_confirmed 一致。
     * 仅当 active 且 本帧 last_seen==fi 或 (lost 处理已 push 0 票) 时才校验，避免对末帧漂移误报。 */
    /* 确认票/存活核验（最终口径）：真实 FusionTracker 对象在 diag._candidates（fusion 候选）上，
     * engine 直接回写 track_id/track_confirmed；diag._tracks 是剥离投影、不含 votes。
     * 故从引擎 fusion_ctx.tracker.tracks 取真实 votes 数组复算。 */
    const FTrack=require('./core/fusion').FusionTracker;
    const realTracks=(det.engine.fusion_ctx&&det.engine.fusion_ctx.tracker&&det.engine.fusion_ctx.tracker.tracks)||[];
    const cfg=det.engine.cfg&&det.engine.cfg.fusion_cfg?det.engine.cfg.fusion_cfg:{track_still_confirm_window:5,track_still_confirm_votes:3,track_still_confirm_min_age:3};
    for(const t of realTracks){
      if(!t.active||t.last_seen!==fi)continue;
      const votesArr=Array.isArray(t.votes)?t.votes:[];
      const vs=votesArr.reduce((a,b)=>a+b,0);
      const age=(fi-(t.born_frame_idx||0)+1);
      const expectConf=(vs>=cfg.track_still_confirm_votes)&&(age>=cfg.track_still_confirm_min_age);
      if(!!t.human_confirmed!==expectConf){
        out.confirm_vote_violations.push({frame:fi,track_id:t.id,human_confirmed:!!t.human_confirmed,votes:votesArr.slice(),votes_sum:vs,age});
      }
    }
    void FTrack;
    // --- 5) geometry(post) 决策 vs track_confirmed 一致性 ---
    if(forceGeometry){
      for(const c of cands){
        const dec=c.classifier_decision;
        const want=dec==='CONFIRMED_HUMAN';
        if(!!c.track_confirmed!==want){
          out.geometry_mismatch++;
          if(out.geometry_mismatch_examples.length<8)out.geometry_mismatch_examples.push({frame:fi,candidate:c.candidate_id,decision:dec,track_confirmed:!!c.track_confirmed,rf_decision:c._rf_decision||null});
        }
      }
    }
    // --- 4) GT 评估（窄：仅该帧有 GT 对象才计分母） ---
    const hasGt=presence(doc,fi);
    if(!hasGt){out.unknown_frames++;continue;}
    out.frames_with_gt++;
    const contract=det.engine.report().coordinate_contract||{R:undefined,T:undefined,already_leveled:false};
    const leveled=L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled);
    void leveled; // GT 对象由 objects() 自带 leveled 坐标，无需再累加；保留以示坐标契约来源
    const gtObjs=objects(doc,fi,rawMap(f.xyzi))||[];
    const persons=gtObjs.filter(g=>g.class_name==='PERSON');
    const furniture=gtObjs.filter(g=>g.class_name==='FURNITURE');
    const pred=cands.filter(c=>['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.classifier_decision))
      .map(c=>({x:c.centroid.x,y:c.centroid.y,z:c.centroid.z,track_confirmed:c.track_confirmed,classifier_decision:c.classifier_decision,prob:c.scores&&c.scores.rf51?c.scores.rf51.prob:0,point_indices:c.point_indices}));
    const predTracks=tracks.filter(t=>t.human_confirmed&&t.lost===0).map(t=>({x:t.x,y:t.y,z:t.z}));
    const cdiff=EV.count(persons,pred,GATE_M); const tdiff=EV.count(persons,predTracks,GATE_M);
    out.candidate.tp+=cdiff.tp; out.candidate.fp+=cdiff.fp; out.candidate.fn+=cdiff.fn;
    out.track.tp+=tdiff.tp; out.track.fp+=tdiff.fp; out.track.fn+=tdiff.fn;
    // 家具误检帧计数
    if(furniture.length&&pred.length){
      for(const c of pred){
        for(const fobj of furniture){
          const set=new Set(fobj.indices||[]);
          const ids=Array.from(c.point_indices||[]);
          const purity=ids.length?ids.filter(i=>set.has(i)).length/ids.length:0;
          if(purity>=0.8){out.furniture_fp_frames++;break;}
        }
      }
    }
    // 逐层漏检归因（人 FN 帧）
    if(cdiff.fn>0){
      for(const p of persons){
        const ids=new Set(p.indices||[]);
        const hits=cands.map(c=>{const ci=Array.from(c.point_indices||[]);return {c,cov:ci.filter(i=>ids.has(i)).length/(p.indices.length||1)};});
        const props=hits.filter(h=>h.cov>=0.1&&Math.hypot(h.c.centroid.x-p.x,h.c.centroid.y-p.y)<=0.75);
        const accepted=props.filter(h=>h.c.prob>=0.35);
        const tracked=accepted.filter(h=>h.c.track_confirmed);
        const foreground_points=(()=>{try{return p.indices.filter(i=>true).length;}catch(e){return p.indices.length;}})();
        let loss='NONE';
        if(!props.length)loss=(foreground_points===0?'BG_OR_CLEANUP':'PROPOSAL');
        else if(!accepted.length)loss='CLASSIFIER';
        else if(!tracked.length)loss='TRACKER';
        if(loss!=='NONE')out.layer_miss.push({frame:fi,person:p.id,loss,raw_points:p.indices.length,best_cov:Math.max(0,...hits.map(h=>h.cov))});
      }
    }
  }
  out.tracker_kinds=Array.from(trackerKinds);
  out.duplicate_id_frame_count=out.duplicate_id_frames.length;
  out.id_flicker_frame_count=out.id_flicker_frames.length;
  out.confirm_vote_violation_count=out.confirm_vote_violations.length;
  out.layer_miss_count=out.layer_miss.length;
  // 截断示例，控制体积
  out.duplicate_id_frames=out.duplicate_id_frames.slice(0,50);
  out.id_flicker_frames=out.id_flicker_frames.slice(0,50);
  out.confirm_vote_violations=out.confirm_vote_violations.slice(0,50);
  return out;
}

function main(){
  const results={runs:[],perf:[],flicker:[],votes:[],geo:[],generated_at:new Date().toISOString(),gate_m:GATE_M,scope:'R3 read-only diagnostics; new R3_* namespace; no source edits'};
  const sids=audit.sessions.filter(r=>r.eligible).map(r=>r.sid);
  for(const sid of sids){
    for(const model of MODELS){
      const base=runSession(sid,model,false,false);
      results.runs.push(base);
      results.perf.push({sid,activity:base.activity,model,frames_with_gt:base.frames_with_gt,unknown_frames:base.unknown_frames,
        candidate:{...base.candidate},track:{...base.track},furniture_fp_frames:base.furniture_fp_frames,
        duplicate_id_frame_count:base.duplicate_id_frame_count,id_flicker_frame_count:base.id_flicker_frame_count,
        confirm_vote_violation_count:base.confirm_vote_violation_count,layer_miss_count:base.layer_miss_count,
        layer_miss:base.layer_miss.slice(0,80),detector:base.detector,tracker_kinds:base.tracker_kinds});
      results.flicker.push({sid,model,count:base.id_flicker_frame_count,examples:base.id_flicker_frames});
      results.votes.push({sid,model,count:base.confirm_vote_violation_count,examples:base.confirm_vote_violations});
      console.log(`R3 ${sid} ${model}: gt=${base.frames_with_gt} candTP${base.candidate.tp}/FP${base.candidate.fp}/FN${base.candidate.fn} dupID=${base.duplicate_id_frame_count} flicker=${base.id_flicker_frame_count} voteViol=${base.confirm_vote_violation_count} tracker=${base.tracker_kinds.join('|')}`);
    }
    // 一对一 tracker 对照（同模型 rf51_baseline）
    const uni=runSession(sid,'rf51_baseline',true,false);
    results.flicker.push({sid,model:'rf51_baseline+unique',count:uni.id_flicker_frame_count,examples:uni.id_flicker_frames});
    console.log(`R3 ${sid} rf51+unique: dupID=${uni.duplicate_id_frame_count} flicker=${uni.id_flicker_frame_count} tracker=${uni.tracker_kinds.join('|')}`);
    // geometry(post) 一致性（每会话一次）
    const geo=runSession(sid,'rf51_baseline',false,true);
    results.geo.push({sid,detector:geo.detector,mismatch:geo.geometry_mismatch,examples:geo.geometry_mismatch_examples});
    console.log(`R3 ${sid} geometry(post): mismatch=${geo.geometry_mismatch} detector=${geo.detector}`);
  }
  fs.writeFileSync(OUT,JSON.stringify({scope:results.scope,gate_m:GATE_M,perf:results.perf},null,1));
  fs.writeFileSync(OUT_FLICKER,JSON.stringify({scope:results.scope,flicker:results.flicker},null,1));
  fs.writeFileSync(OUT_VOTES,JSON.stringify({scope:results.scope,votes:results.votes},null,1));
  fs.writeFileSync(OUT_GEO,JSON.stringify({scope:results.scope,geo:results.geo},null,1));
  console.log('R3_WROTE '+[OUT,OUT_FLICKER,OUT_VOTES,OUT_GEO].map(p=>path.basename(p)).join(', '));
}
main();
