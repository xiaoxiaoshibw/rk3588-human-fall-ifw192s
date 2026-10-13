/* Offline R2 GT evaluation. Engine/production/GT files remain read-only. */
"use strict";
const fs=require('fs'), path=require('path'), crypto=require('crypto'), os=require('os'), assert=require('assert');
const E=require('./engine'), D=require('./data_loader'), S=require('./schema'), L=require('./leveling');
const GT=require('../human_replay/gt_lib');
const ROOT=path.resolve(__dirname,'../..');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const hash=v=>crypto.createHash('sha256').update(v).digest('hex');
const write=(p,v)=>fs.writeFileSync(p,JSON.stringify(v,null,1),{flag:'wx'});

/* At most two PERSON objects in this protocol. Exact max-cardinality/min-distance assignment. */
function match(gt,pred,gate) {
    let best={pairs:[],distance:Infinity};
    function visit(i,used,pairs,distance) {
        if(i===gt.length) {
            if(pairs.length>best.pairs.length || (pairs.length===best.pairs.length && distance<best.distance))
                best={pairs:pairs.slice(),distance};
            return;
        }
        visit(i+1,used,pairs,distance);
        for(let j=0;j<pred.length;j++) {
            const d=Math.hypot(gt[i].x-pred[j].x,gt[i].y-pred[j].y);
            if(!used.has(j)&&d<=gate) {
                used.add(j); pairs.push([i,j]); visit(i+1,used,pairs,distance+d); pairs.pop(); used.delete(j);
            }
        }
    }
    visit(0,new Set(),[],0);
    return best.pairs;
}
function count(gt,pred,gate) {
    const pairs=match(gt,pred,gate);
    return {tp:pairs.length,fn:gt.length-pairs.length,fp:pred.length-pairs.length,pairs};
}
function metrics(c) {
    return {...c,recall:c.tp+c.fn?c.tp/(c.tp+c.fn):null,
            precision:c.tp+c.fp?c.tp/(c.tp+c.fp):null};
}
function assert_same_source(a,b) {
    for(const k of ['frame_index','timestamp','raw_sha256','leveled_sha256','coordinate_sha256'])
        assert.deepStrictEqual(a[k],b[k],`same-source mismatch ${k}`);
}
function candidate(c) {
    return {id:c.candidate_id,x:c.centroid.x,y:c.centroid.y,z:c.centroid.z,
            n:c.point_count,points_sha256:hash(Buffer.from(Uint32Array.from(c.point_indices).sort().buffer)),
            decision:c.classifier_decision,prob:c.scores.rf51?c.scores.rf51.prob:null,
            accepted:['HUMAN_CANDIDATE','CONFIRMED_HUMAN'].includes(c.classifier_decision),
            track_id:c.track_id,segment:c.track_segment,source:c.fusion_source_SRC||c.foreground_source};
}
function percentile(values,p) {
    const a=values.slice().sort((x,y)=>x-y);
    return a[Math.floor((a.length-1)*p)];
}
function sources(train) {
    const files=['engine.js','schema.js','leveling.js','data_loader.js','fusion.js','evaluate_fusion_gt.js'].map(n=>path.join(__dirname,n));
    ['human_pipe_lib.js','detect_overlay.js','rf_person.js','rf_person_v1.json','bg_envelope.json','gt_lib.js'].forEach(n=>files.push(path.join(__dirname,'../human_replay',n)));
    ['rf_person_v2.json','GT_AUDIT.json','SPLITS.json'].forEach(n=>files.push(path.join(train,n)));
    return Object.fromEntries(files.map(p=>[path.relative(ROOT,p).replace(/\\/g,'/'),E.hash_file(p)]));
}
function run(s,mode,model,modelName) {
    const eng=new E.UnifiedEngine({mode}),sid=path.basename(s.session_dir);
    if(eng.rf && model) {eng.rf.init(fs.readFileSync(model,'utf8')); eng.rf_model_sha=E.hash_file(model);}
    const gen=eng.begin_session(sid);
    if(!['BASE_B','FUSION'].includes(mode)) eng.set_online_background(s.frames.map(f=>f.xyzi),{meta:s.meta});
    const frames=[];
    for(let i=0;i<s.frames.length;i++) {
        const f=s.frames[i],fc=S.make_frame_context({session_id:sid,session_generation:gen,frame_index:i,timestamp:f.timestamp,xyzi:f.xyzi,meta:s.meta});
        const diag=eng.tick(fc), contract=eng.report().coordinate_contract;
        const lv=L.level_frame(f.xyzi,contract.R,contract.T,contract.already_leveled);
        frames.push({frame_index:i,timestamp:f.timestamp,raw_sha256:hash(Buffer.from(f.xyzi.buffer,f.xyzi.byteOffset,f.xyzi.byteLength)),
            leveled_sha256:hash(Buffer.from(lv.buffer)),coordinate_sha256:hash(JSON.stringify(contract)),
            candidates:diag._candidates.map(candidate),
            tracks:diag._tracks.filter(t=>t.human_confirmed&&t.lost===0).map(t=>({
                id:`${eng.track_segment}:${t.id}`,x:t.x,y:t.y,z:t.z})),
            fall_events:diag._events,ms:diag.total_ms,heap_mb:diag.peak_heap_mb,rss_mb:diag.rss_mb,external_mb:diag.external_mb});
    }
    const rep=eng.report(), times=frames.slice(5).map(f=>f.ms), heap=Math.max(...frames.map(f=>f.heap_mb));
    return {sid,mode,model_name:modelName,rf_model_sha256:rep.rf_model_sha,reference_sha256:rep.ref_env_sha||null,
        input_sha256:{points:s.points_sha256,meta:s.meta_sha256},coordinate_contract:rep.coordinate_contract,
        frames,ever_confirmed_track_ids:rep.ever_confirmed_track_ids,
        performance:{warmup:5,n:times.length,p50:percentile(times,.5),p95:percentile(times,.95),p99:percentile(times,.99),
            peak_heap_mb:heap,peak_rss_mb:Math.max(...frames.map(f=>f.rss_mb)),
            peak_external_mb:Math.max(...frames.map(f=>f.external_mb)),pass:percentile(times,.95)<50&&heap<1500}};
}
function evaluate(run,record,doc,meta,gate) {
    if(!record.eligible) return {status:'BLOCKED',reason:record.issues,gate};
    const totals={candidate:{tp:0,fp:0,fn:0},track:{tp:0,fp:0,fn:0}};
    const frameRows=[], previous=new Map(), ids=new Map(); let exposure=0,switches=0;
    const intervals=doc.uncertain_intervals||[];
    const dt=meta.frames.slice(1).map((f,i)=>f.bag_time_sec-meta.frames[i].bag_time_sec);
    const median=percentile(dt,.5);
    for(const f of run.frames) {
        if(!Object.hasOwn(doc.frames_objects,String(f.frame_index))) continue;
        if(intervals.some(x=>f.frame_index>=x.start&&f.frame_index<=x.end)) continue;
        const obs=doc.frames_objects[String(f.frame_index)].map(id=>doc.objects[id]);
        if(!obs.length || obs.some(o=>o.class_name==='UNKNOWN')) continue;
        const gt=obs.filter(o=>o.class_name==='PERSON');
        const cp=count(gt,f.candidates.filter(c=>c.accepted),gate),tp=count(gt,f.tracks,gate);
        for(const [key,c] of [['candidate',cp],['track',tp]]) for(const n of ['tp','fp','fn']) totals[key][n]+=c[n];
        exposure+=f.frame_index+1<meta.frames.length?meta.frames[f.frame_index+1].bag_time_sec-meta.frames[f.frame_index].bag_time_sec:median;
        const matched={};
        for(const [i,j] of tp.pairs) {
            const tid=gt[i].track_id,pid=f.tracks[j].id,old=previous.get(tid);
            if(old && old.frame===f.frame_index-1 && old.pred!==pid) switches++;
            previous.set(tid,{frame:f.frame_index,pred:pid});
            if(!ids.has(tid)) ids.set(tid,new Set()); ids.get(tid).add(pid); matched[tid]=pid;
        }
        frameRows.push({frame_index:f.frame_index,person_count:gt.length,candidate:cp,track:tp,matched_tracks:matched});
    }
    return {status:'EVALUATED_ANNOTATED_FRAMES',gate,annotated_frames:frameRows.length,exposure_seconds:exposure,
        candidate:metrics(totals.candidate),track:metrics(totals.track),
        track_fp_observations_per_hour:exposure?totals.track.fp*3600/exposure:null,
        adjacent_annotated_id_switches:switches,matched_pred_ids_by_gt:Object.fromEntries([...ids].map(([k,v])=>[k,[...v]])),
        precision_assumption:'declared zero/single-person protocol is exhaustive ONLY at reviewed annotated frames; no full-session claim',
        unknown_frames:run.frames.length-frameRows.length,frames:frameRows};
}
function parity(a,b) {
    assert.deepStrictEqual(a.input_sha256,b.input_sha256); assert.strictEqual(a.rf_model_sha256,b.rf_model_sha256);
    assert.strictEqual(a.reference_sha256,b.reference_sha256); assert.deepStrictEqual(a.coordinate_contract,b.coordinate_contract);
    assert.strictEqual(a.frames.length,b.frames.length);
    const differences=[];let exact=0,probMismatches=0;
    a.frames.forEach((f,i)=>{
        const g=b.frames[i]; assert_same_source(f,g);
        const byPoints=new Map(g.candidates.map(c=>[c.points_sha256,c]));
        const common=[];
        for(const c of f.candidates) if(byPoints.has(c.points_sha256)) {
            const bc=byPoints.get(c.points_sha256);exact++;const diff=Math.abs(c.prob-bc.prob);
            if(diff>1e-6)probMismatches++;
            common.push({a:c.id,b:bc.id,prob_diff:diff,decision_equal:c.accepted===bc.accepted});
        }
        differences.push({frame_index:i,same_source:true,a_candidates:f.candidates.length,b_candidates:g.candidates.length,
            a_accepted:f.candidates.filter(c=>c.accepted).length,b_accepted:g.candidates.filter(c=>c.accepted).length,
            a_tracks:f.tracks.length,b_tracks:g.tracks.length,common_exact_point_sets:common});
    });
    return {same_source_frames:a.frames.length,status:probMismatches?'FAIL':'PASS',common_exact_point_sets:exact,
            probability_mismatches:probMismatches,rows:differences};
}
function check_probabilities(train,out) {
    const rows=read(path.join(train,'RF_PROBABILITIES.json')).samples;
    const results=[];
    for(const v of ['v1','v2']) {
        const rf=E.load_production('rf_person.js'),p=v==='v1'?path.join(__dirname,'../human_replay/rf_person_v1.json'):path.join(train,'rf_person_v2.json');
        rf.init(fs.readFileSync(p,'utf8'));let max=0,changed=0;
        for(const r of rows) {const a=rf.predict_person(new Float32Array(r.fv)),b=r[v+'_prob'];max=Math.max(max,Math.abs(a-b));if((a>=.55)!==(b>=.55))changed++;}
        assert(max<1e-6&&changed===0,'JS/model export parity');results.push({model:v,n:rows.length,max_diff:max,decisions_changed:changed});
    }
    write(path.join(out,'MODEL_JS_PARITY.json'),results);
}
function main() {
    const train=path.resolve(process.argv[2]||''),out=path.resolve(process.argv[3]||'');
    if(process.argv.length!==4 || (fs.existsSync(out)&&fs.readdirSync(out).length)) throw Error('train dir and new empty outdir required');
    fs.mkdirSync(out,{recursive:true});
    const frozen=sources(train),audit=read(path.join(train,'GT_AUDIT.json')).sessions,summary=[],pairs=[];
    check_probabilities(train,out);
    for(const record of audit) {
        const sid=record.sid,s=D.load_session(path.join(ROOT,'captures/remote',sid));
        let doc={frames_objects:{},objects:{}};
        const current={...record,issues:record.issues.slice()};
        const manifest=path.join(path.dirname(record.gt_path),'manifest.json');
        if(fs.existsSync(record.gt_path)&&fs.existsSync(manifest)) {
            const bytes=fs.readFileSync(record.gt_path),mb=fs.readFileSync(manifest);
            if(hash(bytes)===record.gt_sha256&&hash(mb)===record.manifest_sha256) {
                doc=JSON.parse(bytes.toString('utf8'));
                const snap=path.join(out,'gt_snapshot',sid);fs.mkdirSync(snap,{recursive:true});
                fs.writeFileSync(path.join(snap,path.basename(record.gt_path)),bytes,{flag:'wx'});
                fs.writeFileSync(path.join(snap,'manifest.json'),mb,{flag:'wx'});
            } else {current.eligible=false;current.issues.push('GT_SOURCE_CHANGED_SINCE_TRAINING');}
        } else {current.eligible=false;current.issues.push('GT_SOURCE_MISSING_SINCE_TRAINING');}
        assert.deepStrictEqual({points:s.points_sha256,meta:s.meta_sha256},record.input_sha256);
        const dir=path.join(out,sid);fs.mkdirSync(dir);
        const collected={};
        for(const version of ['v1','v2']) for(const mode of ['BASE_A','BASE_B','U3','FUSION']) {
            const model=version==='v2'?path.join(train,'rf_person_v2.json'):null;
            const result=run(s,mode,model,version);result.source_sha256=frozen;
            result.gt_source=current;
            result.gt_evaluations=[.5,.75,1].map(gate=>evaluate(result,current,doc,s.meta,gate));
            write(path.join(dir,version+'__'+mode+'.json'),result);collected[version+'__'+mode]=result;
            const core=result.gt_evaluations[1];
            summary.push({sid,version,mode,frames:result.frames.length,gt:core,
                performance:result.performance,rf_model_sha256:result.rf_model_sha256});
            console.log(sid,version,mode,'P95',result.performance.p95.toFixed(2),'GT',core.status);
        }
        for(const v of ['v1','v2']) {
            const p=parity(collected[v+'__FUSION'],collected[v+'__BASE_B']);write(path.join(dir,v+'__PARITY.json'),p);
            pairs.push({sid,version:v,...p,rows:undefined});
        }
        const gtmap=GT.doc_render_map(doc),breaks=GT.find_breaks(gtmap,['P1','P2','t1']);
        write(path.join(dir,'GT_BREAKS.json'),{eligible:current.eligible,issues:current.issues,breaks,
            note:'gap is annotation sampling, not detection loss; S9 frame1 P2 absent is GT defect'});
        assert.strictEqual(E.hash_file(path.join(s.session_dir,'meta.json')),s.meta_sha256);
        assert.strictEqual(E.hash_file(path.join(s.session_dir,'points.bin')),s.points_sha256);
        assert.deepStrictEqual(sources(train),frozen,'source changed during run');
    }
    write(path.join(out,'SUMMARY.json'),{node:process.version,cpu:os.cpus()[0].model,source_sha256:frozen,runs:summary,parity:pairs});
    console.log('COMPLETE',summary.length,'runs');
}
if(require.main===module) main();
module.exports={match,count,evaluate,assert_same_source,parity};
