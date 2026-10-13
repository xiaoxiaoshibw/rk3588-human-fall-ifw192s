/* PC offline only: fixed historical transforms, immutable PL pipeline, frozen S-A+.
 * Full source row lineage; no artifact loader/publisher, network, flags, or GT invention. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const RL=require(path.join(ROOT,'pc_apps/human_replay/human_replay_lib.js'));
const M=require(path.join(ROOT,'pc_apps/human_replay/registration_method.js'));
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const S=require('./semantic.js');
const PREV=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1');
const levels=R.read(path.join(PREV,'leveling_results.json')),regs=R.read(path.join(PREV,'registration_results.json'));
const previous=R.read(path.join(PREV,'retention_results.json')),region=R.read(path.join(PREV,'region_audit.json'));
const frozenProbe=R.read(path.join(ROOT,'docs/human_capture/evidence/2026-10-08_semantic_new_holdout_r1/results.json'));
const EXPECT={114205:244,114254:271,114340:281,114422:195,114819:285};
const JOBS={'114205':'80a4bd6fe3a4476fa099b053d74de8be','114254':'abe747de448a4974ad9e7a6e1c70bac4',
    '114340':'9d389dc38cb84343b66f97db2198dbbb','114422':'24a7ba629d904f63af03ecdaadb9a9ec','114819':'6e87c6e4146f48ba84e24c801820e5e1'};
const write=(base,n,v)=>fs.writeFileSync(path.join(base,n),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
const increment=(o,k)=>o[k]=(o[k]||0)+1;
const identity=v=>R.identity(v);
function level(sid,job,dir) {
    const tf=R.read(path.join(dir,'tls/transform.json')),report=R.read(path.join(dir,'report.json')),manifest=R.read(path.join(dir,'manifest.json'));
    const source=R.sessionBinding(ROOT,sid);delete source.sid;
    assert.strictEqual(report.sid,sid);assert.strictEqual(manifest.job_id,job);assert.strictEqual(tf.estimator,'tls');
    assert.strictEqual(report.recommended,'tls');
    for(const src of [tf.source,report.source,manifest.source]) assert.strictEqual(identity(source),identity(src),'source binding');
    assert.strictEqual(R.shaFile(path.join(dir,'tls/transform.json')),manifest.artifacts.tls['transform.json']);
    assert.strictEqual(R.shaFile(path.join(dir,'report.json')),manifest.report_sha256);
    assert(R.matrixOK(tf.R.flat(),tf.t));
    for(const [name,sha] of Object.entries(report.code_hashes)) {
        const sub=['__init__.py','ransac.py','svd.py','tls.py'].includes(name)?'leveling_estimators/':'';
        assert.strictEqual(R.shaFile(path.join(ROOT,'pc_apps/human_replay',sub+name)),sha,'leveling code binding');
    }
    return {tf,report,manifest,job,dir,source,sha:{tf:R.shaFile(path.join(dir,'tls/transform.json')),
        report:R.shaFile(path.join(dir,'report.json')),manifest:R.shaFile(path.join(dir,'manifest.json'))}};
}
function equalRecord(a,i,b,j) {for(let k=0;k<4;k++) if(!Object.is(a[i*4+k],b[j*4+k])) return false;return true;}
function subset(frame,buf) {
    const rows=[];let cursor=0;
    for(let i=0;i<buf.length/4;i++) {
        while(cursor<frame.rows.length&&!equalRecord(frame.buf,cursor,buf,i)) cursor++;
        assert(cursor<frame.rows.length,'filter is not source ordered subset');rows.push(frame.rows[cursor++]);
    }
    return {buf,rows,invalid:frame.invalid,info:frame.info};
}
function transform(frame,A,t) {
    const buf=frame.buf.slice();
    for(let i=0;i<buf.length;i+=4) {const q=M.m3.apply(A,buf[i],buf[i+1],buf[i+2]);for(let j=0;j<3;j++) buf[i+j]=q[j]+t[j];}
    return {...frame,buf};
}
function load(sid,lev,reg=null) {
    const dir=path.join(ROOT,'captures/remote',sid),meta=R.read(path.join(dir,'meta.json'));
    assert.strictEqual(meta.point_layout.stride_bytes,RL.STRIDE_BYTES);
    const raw=fs.readFileSync(path.join(dir,'points.bin')),data=new Float32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
    const slices=RL.frame_slice(meta);assert.strictEqual(raw.length,slices.at(-1).end_pts*RL.STRIDE_BYTES);
    const frames=slices.map((info,ordinal)=>{
        const buf=RL.strided_f32_copy(data,info.start_pts,info.count,RL.STRIDE_F32),invalid=new Set();
        for(let i=0;i<info.count;i++) {const xyz=[buf[4*i],buf[4*i+1],buf[4*i+2]];
            if(!xyz.every(Number.isFinite)||xyz.every(v=>v===0)) invalid.add(i);}
        let f={buf,rows:Array.from({length:info.count},(_,i)=>i),invalid,info:{...info,ordinal}};
        f=transform(f,lev.tf.R.flat(),lev.tf.t);f=subset(f,PL.denoise(f.buf));
        if(reg) {f=transform(f,reg.rotation_row_major,reg.translation_m);f=subset(f,PL.denoise(f.buf));}
        return f;
    });
    assert.strictEqual(frames.reduce((s,f)=>s+f.invalid.size,0),lev.report.invalid_xyz_count,'raw invalid ledger');
    return {sid,meta,frames,level:lev,reg};
}
const inside=(x,y,z,c,r=.45)=>Math.hypot(x-c[0],y-c[1])<=r&&z>=.1&&z<=2.3;
function countROI(frame,center) {let n=0;for(let i=0;i<frame.rows.length;i++) if(inside(...frame.buf.subarray(4*i,4*i+3),center)) n++;return n;}
function pointRows(frame,ids) {const by=new Map(frame.rows.map((r,i)=>[r,i]));return ids.map(r=>{
    const i=by.get(r);assert(i!==undefined);return {row:r,xyz:Array.from(frame.buf.subarray(i*4,i*4+3)),raw_invalid:frame.invalid.has(r)};});}

// Reference association is deliberately conservative: only unique bidirectional gate edges.
// ponytail: spatial machine identities only; GT must establish real person continuity.
class FrameVotes {
    constructor(){this.tracks=[];this.next=1;this.last=-1;}
    tick(fi,clusters) {
        assert(fi===this.last+1,'actual stored frames must advance once');this.last=fi;
        const active=this.tracks.filter(t=>t.active),gate=PL.PIPE.track_gate_xy_m**2;
        const edges=clusters.map(c=>active.filter(t=>(t.x-c.cx)**2+(t.y-c.cy)**2<gate));
        const inverse=new Map(active.map(t=>[t.id,[]]));edges.forEach((ts,ci)=>ts.forEach(t=>inverse.get(t.id).push(ci)));
        const seen=new Set(),ambiguity=new Set(),assigned=[];
        edges.forEach((ts,ci)=>{
            const c=clusters[ci];let t=null,uncertain=false;
            if(ts.length===1&&inverse.get(ts[0].id).length===1) t=ts[0];
            else if(ts.length) {uncertain=true;ts.forEach(t=>ambiguity.add(t.id));}
            if(!t&&!ts.length) {t={id:this.next++,active:true,born:fi,x:c.cx,y:c.cy,lost:0,history:[]};this.tracks.push(t);}
            if(t) {seen.add(t.id);t.lost=0;t.x+=PL.PIPE.ema_alpha*(c.cx-t.x);t.y+=PL.PIPE.ema_alpha*(c.cy-t.y);
                t.history.push({f:fi,semantic:c.semantic==='HUMAN_EVIDENCE'?1:0,old:c.joint==='CONFIRMED_HUMAN'?1:0,ci});}
            assigned.push({ci,identity:t?.id??null,status:uncertain?'UNKNOWN_ASSOCIATION':'PROVISIONAL_MACHINE_ID',
                gate_candidates:ts.map(t=>t.id),human_identity_status:'BLOCKED_GT'});
        });
        for(const t of this.tracks.filter(t=>t.active)) {
            if(!seen.has(t.id)) {t.history.push({f:fi,semantic:ambiguity.has(t.id)?null:0,old:ambiguity.has(t.id)?null:0,
                ci:null,missing:!ambiguity.has(t.id),association_unknown:ambiguity.has(t.id)});t.lost++;if(t.lost>PL.PIPE.track_lost_max)t.active=false;}
            t.history=t.history.filter(h=>h.f>fi-PL.PIPE.human_confirm_window);
        }
        const windows=this.tracks.filter(t=>t.active||t.history.some(h=>h.f===fi)).map(t=>{
            assert(new Set(t.history.map(h=>h.f)).size===t.history.length);
            const unknown=t.history.some(h=>h.semantic===null),age=fi-t.born+1;
            const eligible=age>=PL.PIPE.human_confirm_min_age;
            return {id:t.id,born:t.born,age,lost:t.lost,active:t.active,window:t.history.map(h=>({...h})),
                semantic_votes:t.history.reduce((s,h)=>s+(h.semantic||0),0),old_votes:t.history.reduce((s,h)=>s+(h.old||0),0),
                semantic_confirmed:unknown?null:eligible&&t.history.reduce((s,h)=>s+(h.semantic||0),0)>=PL.PIPE.human_confirm_votes,
                old_confirmed:unknown?null:eligible&&t.history.reduce((s,h)=>s+(h.old||0),0)>=PL.PIPE.human_confirm_votes,
                status:unknown?'UNKNOWN_ASSOCIATION':'PROVISIONAL_MACHINE_ID',human_identity_status:'BLOCKED_GT'};
        });
        return {assigned,windows};
    }
}
function voteSelfcheck() {
    const c=(x=1)=>({cx:x,cy:0,semantic:'HUMAN_EVIDENCE',joint:'CONFIRMED_HUMAN'});
    let v=new FrameVotes(),o;for(let i=0;i<3;i++)o=v.tick(i,[c()]);assert(o.windows[0].semantic_confirmed);
    v=new FrameVotes();for(let i=0;i<=9;i++)o=v.tick(i,[0,1,9].includes(i)?[c()]:[]);
    assert.strictEqual(o.windows[0].semantic_votes,1);assert.strictEqual(o.windows[0].semantic_confirmed,false);
    v=new FrameVotes();v.tick(0,[c()]);o=v.tick(1,[c(.9),c(1.1)]);
    assert(o.assigned.every(a=>a.identity===null));assert.strictEqual(o.windows[0].semantic_confirmed,null);
    assert.throws(()=>v.tick(1,[]));
    return {continuous_three:true,gap_ages_votes:true,collision_unknown:true,duplicate_frame_rejected:true};
}
function clusterFrame(frame,foreground,fi,tracker) {
    const iso=PL.cleanup_isolated_fg(foreground.buf),clean=subset(foreground,iso.xyzi);
    const all=PL.cluster_voxels(PL.voxelize(clean.buf)),raw=all.filter(c=>PL.cluster_features(c).ok);
    const output=PL.pipeline_frame(foreground.buf,fi,{static_keys:null,tracker});
    assert.strictEqual(raw.length,output.clusters.length);assert.strictEqual(clean.rows.length,output.fg_after_cleanup);
    const owner=new Map();all.forEach((c,ci)=>c.keys.forEach(k=>owner.set(k,ci)));
    const members=all.map(()=>[]),xyz=all.map(()=>[]),xyzi=all.map(()=>[]);
    let unassigned=0;
    for(let k=0;k<clean.buf.length;k+=4) {
        const ci=owner.get(PL.key_vox(clean.buf[k],clean.buf[k+1]));
        if(ci===undefined) {unassigned++;continue;}
        members[ci].push(clean.rows[k/4]);xyz[ci].push(clean.buf[k],clean.buf[k+1],clean.buf[k+2]);
        xyzi[ci].push(clean.buf[k],clean.buf[k+1],clean.buf[k+2],clean.buf[k+3]);
    }
    assert.strictEqual(members.reduce((s,a)=>s+a.length,0)+unassigned,clean.rows.length);
    const cs=[];let outputIndex=0;
    const small=[];
    for(let ai=0;ai<all.length;ai++) {
        assert.strictEqual(members[ai].length,all[ai].acc.n);
        if(all[ai].acc.n<PL.PIPE.human_n_min) {small.push({component:ai,n:members[ai].length,rows:members[ai]});continue;}
        const old=output.clusters[outputIndex++],invalidRows=members[ai].filter(r=>frame.invalid.has(r));
        const validXYZ=[];for(let j=0;j<members[ai].length;j++) if(!frame.invalid.has(members[ai][j])) validXYZ.push(...xyz[ai].slice(j*3,j*3+3));
        // Contaminated full candidate cannot assert HUMAN; preserve original output separately.
        const sem=invalidRows.length?{...S.classify([]),reason:'RAW_INVALID_MEMBER',invalid_rows:invalidRows}:S.classify(validXYZ);
        const f=PL.cluster_features(all[ai]);
        for(const k of ['n','cx','cy','cz','height_m','radius_m','upcos']) assert.strictEqual(f[k],old[k]);
        const bbox=[[Infinity,Infinity,Infinity],[-Infinity,-Infinity,-Infinity]];
        for(let i=0;i<xyz[ai].length;i++) {const k=i%3;bbox[0][k]=Math.min(bbox[0][k],xyz[ai][i]);bbox[1][k]=Math.max(bbox[1][k],xyz[ai][i]);}
        cs.push({ci:cs.length,component:ai,n:old.n,rows:members[ai],global_rows:members[ai].map(r=>frame.info.start_pts+r),
            member_sha256:identity(members[ai]),xyz_sha256:identity(xyz[ai]),center:[old.cx,old.cy,old.cz],bbox,
            invalid_rows:invalidRows,old:JSON.parse(JSON.stringify(old)),semantic:sem,
            same_member_input:invalidRows.length===0,scope:'full cleanup candidate; no old human hard-gate filter'});
    }
    return {cs,small,clean,iso,output,unassigned,memberCount:members.reduce((s,a)=>s+a.length,0)};
}

function run(pass) {
    const base=path.join(OUT,pass);fs.mkdirSync(base);const fds={};
    for(const n of ['frames','clusters','votes','review','points'])fds[n]=fs.openSync(path.join(base,n+'.jsonl'),'wx');
    const emit=(n,v)=>fs.writeSync(fds[n],JSON.stringify(v)+'\n');
    const binding={ticket:R.shaFile(path.join(ROOT,'docs/human_capture/tickets/HR-SEM-SHADOW.md')),
        acceptance:R.shaFile(path.join(ROOT,'docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md')),
        pipeline:R.codeBinding(ROOT),parameters:PL.PIPE,semantic:S.binding,
        previous_inputs:Object.fromEntries(['leveling_results.json','registration_results.json','retention_results.json','region_audit.json','integrity.json'].map(n=>[n,R.shaFile(path.join(PREV,n))])),
        sessions:[],historical_semantic_review:R.shaFile(path.join(ROOT,'docs/human_capture/evidence/2026-10-08_human_semantic_sa_r2/review_results.json'))};
    assert.strictEqual(identity(binding.pipeline),identity(regs[0].code),'diagnostic code binding');
    const refsid='cap_20261008_114819',refjob=JOBS['114819'];
    const ref=load(refsid,level(refsid,refjob,path.join(PREV,'leveling',refjob)));
    const refmap=PL.build_reference_map(ref.frames.map(f=>f.buf));
    assert.strictEqual(identity(R.refBinding(refmap)),identity(R.read(path.join(PREV,'reference_summary.json')).binding));
    const refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
    const summaries=[],reconciliation={roi_features:0,roi_point_arrays:0,empty_sample_clusters:0,retention_frames:0,
        invalid_placeholder_policy:'unchanged upstream baseline; invalid raw members cannot contribute semantic evidence'};
    for(const sid of ['cap_20261008_114205','cap_20261008_114254','cap_20261008_114340','cap_20261008_114422',refsid]) {
        const suffix=sid.slice(-6),reg=regs.find(r=>r.sid===sid),job=JOBS[suffix];
        const data=sid===refsid?ref:load(sid,level(sid,job,path.join(PREV,'leveling',job)),reg.transform);
        assert.strictEqual(data.frames.length,EXPECT[suffix]);
        if(reg){assert.strictEqual(reg.leveling_job,job);assert.strictEqual(identity(reg.code),identity(binding.pipeline));
            assert.strictEqual(identity(data.level.source),identity(reg.source));assert.strictEqual(reg.gate,R.gate(reg.diagnostics).status);
            assert.strictEqual(identity(reg),identity(R.read(path.join(PREV,sid+'_registration_diagnostic.json'))));}
        binding.sessions.push({sid,frames:data.frames.length,source:data.level.source,job,leveling_sha:data.level.sha,
            transform:reg?.transform??null,gate:reg?.gate??'IDENTITY_REFERENCE',production_artifact:'NOT_CREATED'});
        const online=PL.build_static_map(data.frames.map(f=>f.buf)),center=previous.find(s=>s.sid===sid)?.center;
        const modes=sid===refsid?['V2_IDENTITY','WORKSPACE']:reg.gate==='PASS'?['V2']:['REF_SHADOW'];
        for(const mode of modes) {
            const tracker=new PL.Tracker(),refVotes=new FrameVotes(),oldEvents=new Map();
            const sum={sid,mode,frames:data.frames.length,clusters:0,semantic:{},size_bins:{},reasons:{},flags:{},
                any_human_frames:0,no_cluster_frames:0,old_geometry_frames:0,old_instant_joint_frames:0,old_cluster_confirmed_frames:0,
                old_active_track_confirmed_frames:0,reference_semantic_frames:0,reference_old_frames:0,association_unknown_frames:0,
                collision_frames:0,stale_window_confirmed_frames:0,proxy:{status:'PROVISIONAL',roi_human_frames:0,old_joint:{},old_confirmed_frames:0},
                invalid:{raw:0,transformed_denoise:0,workspace:0,foreground:0,cleanup:0,candidate_members:0},
                source_points:0,foreground_points:0,cleanup_removed:0,unassigned_points:0,small_components:0,raw_human_annotations:data.meta.human_annotations?.length??0};
            for(let fi=0;fi<data.frames.length;fi++) {
                const frame=data.frames[fi],ws=subset(frame,PL.extract_foreground(frame.buf,null).fg_xyzi);
                const refFg=subset(frame,PL.extract_foreground(frame.buf,refkeys).fg_xyzi);
                const fgbuf=mode==='WORKSPACE'?ws.buf:mode==='REF_SHADOW'?refFg.buf:PL.extract_foreground_fused(frame.buf,refkeys,online).fg_xyzi;
                const fg=subset(frame,fgbuf),chain=clusterFrame(frame,fg,fi,tracker),cs=chain.cs;
                const frameKey={sid,mode,ordinal:fi,seq:frame.info.seq,stamp_sec:frame.info.stamp_sec,stamp_nanosec:frame.info.stamp_nanosec};
                const votes=refVotes.tick(fi,cs.map(c=>({...c.old,semantic:c.semantic.semantic})));
                let collision=false,stale=false;const oldCounts={};
                cs.forEach(c=>{increment(oldCounts,c.old.track_id);let ev=oldEvents.get(c.old.track_id)||[];
                    ev.push({f:fi,ci:c.ci,v:c.old.joint==='CONFIRMED_HUMAN'?1:0});oldEvents.set(c.old.track_id,ev);});
                const oldWindows=chain.output.tracks.map(t=>{
                    const ev=oldEvents.get(t.id)||[],last=ev.slice(-PL.PIPE.human_confirm_window);
                    assert.strictEqual(identity(last.map(e=>e.v)),identity(t.votes));
                    const recent=ev.filter(e=>e.f>fi-PL.PIPE.human_confirm_window),positiveFrames=[...new Set(recent.filter(e=>e.v).map(e=>e.f))];
                    const coll=(oldCounts[t.id]||0)>1;if(coll)collision=true;
                    const normal=positiveFrames.length>=PL.PIPE.human_confirm_votes&&fi-t.born_idx+1>=PL.PIPE.human_confirm_min_age;
                    if(t.human_confirmed&&!normal)stale=true;
                    return {id:t.id,age:fi-t.born_idx+1,lost:t.lost,last_seen:t.last_seen,original_votes:t.votes.slice(),
                        original_human_confirmed:!!t.human_confirmed,last_observations:last,actual_recent_positive_frames:positiveFrames,
                        normalized_old_confirmed:normal,collision_this_frame:coll,
                        older_than_five_frame_votes:last.filter(e=>e.f<=fi-PL.PIPE.human_confirm_window).length,
                        human_identity:'BLOCKED_GT'};
                });
                emit('votes',{...frameKey,original:oldWindows,reference:votes});
                const rawROI=center?countROI(frame,center):0,fgROI=center?countROI(fg,center):0,cleanROI=center?countROI(chain.clean,center):0;
                const overlaps=cs.map(c=>({ci:c.ci,n:center?pointRows(chain.clean,c.rows).filter(p=>inside(...p.xyz,center)).length:0}));
                const top=overlaps.filter(x=>x.n).sort((a,b)=>b.n-a.n)[0],topC=top?cs[top.ci]:null;
                if(center) {
                    const old=previous.find(s=>s.sid===sid).arms[mode==='V2'?'V2':'REF'].rows[fi];
                    const actual={raw:rawROI,fg:fgROI,cleanup:cleanROI,top:topC?{roi_points:top.n,n:topC.n,label:topC.old.label,joint:topC.old.joint,
                        reasons:topC.old.reasons,evidence:topC.old.evidence,evidence_tag:topC.old.evidence_tag,track_id:topC.old.track_id,confirmed:!!topC.old.track_confirmed}:null,
                        n_foreground:chain.output.n_foreground,cleanup_split_delta:chain.output.cleanup_split_delta};
                    assert.strictEqual(identity(actual),identity(old),'previous ROI/full pipeline reconciliation '+sid+'/'+fi);reconciliation.retention_frames++;
                    increment(sum.proxy.old_joint,topC?.old.joint??'NONE');
                    if(topC?.semantic.semantic==='HUMAN_EVIDENCE')sum.proxy.roi_human_frames++;
                    if(topC?.old.track_confirmed)sum.proxy.old_confirmed_frames++;
                }
                const sample=region.sessions.find(s=>s.sid===sid)?.rows.find(r=>r.ordinal===fi);
                if(sample) {
                    for(const [arm,f] of [['rawROI',ws],['keptROI',refFg]]) {
                        const p=[];for(let i=0;i<f.rows.length;i++)if(inside(...f.buf.subarray(i*4,i*4+3),center))p.push(Array.from(f.buf.subarray(i*4,i*4+3)));
                        assert.strictEqual(identity(p),identity(sample[arm]),'region point array');reconciliation.roi_point_arrays++;
                        const expected=frozenProbe.positives.find(s=>s.sid===sid).rows.find(r=>r.ordinal===fi&&r.arm===arm);
                        assert.strictEqual(identity(S.feats(p.flat())),identity(expected.features));reconciliation.roi_features++;
                    }
                }
                if(sid===refsid&&mode==='WORKSPACE'&&[0,142,284].includes(fi)) {
                    const comps=PL.cluster_voxels(PL.voxelize(ws.buf)),key2ci=new Map();comps.forEach((c,ci)=>c.keys.forEach(k=>key2ci.set(k,ci)));
                    const pts=comps.map(()=>[]);for(let k=0;k<ws.buf.length;k+=4){const ci=key2ci.get(PL.key_vox(ws.buf[k],ws.buf[k+1]));if(ci!==undefined)pts[ci].push(ws.buf[k],ws.buf[k+1],ws.buf[k+2]);}
                    for(let ci=0;ci<pts.length;ci++)if(pts[ci].length/3>=S.TH.min_pts){const expected=frozenProbe.negatives.find(r=>r.ordinal===fi&&r.ci===ci);
                        assert(expected);assert.strictEqual(identity(S.feats(pts[ci])),identity(expected.features));reconciliation.empty_sample_clusters++;}
                }
                const stageRows={workspace:ws.rows,
                    foreground:fg.rows,cleanup:chain.clean.rows};
                // Avoid per-row Set construction for the full-stage deletion ledger.
                const refSet=new Set(refFg.rows);stageRows.reference_removed=ws.rows.filter(r=>!refSet.has(r));
                const fgSet=new Set(fg.rows),cleanSet=new Set(chain.clean.rows);
                stageRows.online_supported_removed=refFg.rows.filter(r=>!fgSet.has(r));
                stageRows.cleanup_removed=fg.rows.filter(r=>!cleanSet.has(r));
                const counts={source:frame.info.count,denoised:frame.rows.length,workspace:ws.rows.length,foreground:fg.rows.length,
                    cleanup:chain.clean.rows.length,candidates:cs.length,small:chain.small.length,unassigned:chain.unassigned,
                    ref_removed:stageRows.reference_removed.length,online_supported_removed:stageRows.online_supported_removed.length};
                const invalid={raw:frame.invalid.size,transformed_denoise:frame.rows.filter(r=>frame.invalid.has(r)).length,
                    workspace:ws.rows.filter(r=>frame.invalid.has(r)).length,foreground:fg.rows.filter(r=>frame.invalid.has(r)).length,
                    cleanup:chain.clean.rows.filter(r=>frame.invalid.has(r)).length,candidate_members:cs.reduce((s,c)=>s+c.invalid_rows.length,0)};
                emit('frames',{...frameKey,counts,invalid,roi:{status:'PROVISIONAL',raw:rawROI,fg:fgROI,cleanup:cleanROI,top_ci:top?.ci??null},
                    stage_rows:stageRows,small_components:chain.small,source_offset_points:frame.info.start_pts,
                    invalid_source_rows:[...frame.invalid],missing_seq_before:fi?frame.info.seq-data.frames[fi-1].info.seq-1:0});
                for(const [k,v] of Object.entries(invalid))sum.invalid[k]+=v;
                sum.source_points+=frame.info.count;sum.foreground_points+=fg.rows.length;sum.cleanup_removed+=stageRows.cleanup_removed.length;
                sum.unassigned_points+=chain.unassigned;sum.small_components+=chain.small.length;
                if(!cs.length)sum.no_cluster_frames++;if(cs.some(c=>c.semantic.semantic==='HUMAN_EVIDENCE'))sum.any_human_frames++;
                if(cs.some(c=>c.old.label==='HUMAN_CANDIDATE'))sum.old_geometry_frames++;
                if(cs.some(c=>c.old.joint==='CONFIRMED_HUMAN'))sum.old_instant_joint_frames++;
                if(cs.some(c=>c.old.track_confirmed))sum.old_cluster_confirmed_frames++;
                if(chain.output.tracks.some(t=>t.human_confirmed))sum.old_active_track_confirmed_frames++;
                if(votes.windows.some(t=>t.semantic_confirmed===true))sum.reference_semantic_frames++;
                if(votes.windows.some(t=>t.old_confirmed===true))sum.reference_old_frames++;
                if(votes.assigned.some(a=>a.status==='UNKNOWN_ASSOCIATION'))sum.association_unknown_frames++;
                if(collision)sum.collision_frames++;if(stale)sum.stale_window_confirmed_frames++;
                const reviewReasons=[];if(stageRows.cleanup_removed.length)reviewReasons.push('CLEANUP_REMOVED');
                if(suffix==='114340'&&fi===140)reviewReasons.push('HISTORICAL_185_EDGE_POINTS');
                if(collision||stale)reviewReasons.push('TRACK_VOTE_ANOMALY');
                for(const c of cs) {
                    sum.clusters++;increment(sum.semantic,c.semantic.semantic);increment(sum.reasons,c.semantic.reason);
                    increment(sum.size_bins,c.n<200?'60-199':c.n<400?'200-399':'>=400');
                    for(const [k,v] of Object.entries(c.semantic.flags))increment(sum.flags,k+'='+String(v));
                    const assignment=votes.assigned[c.ci],overlap=overlaps[c.ci].n;
                    const id=sid+'/'+mode+'/'+fi+'/'+c.ci;
                    const row={...frameKey,id,...c,reference_assignment:assignment,roi_overlap:overlap,
                        gt:{source:'diagnostic',label:'UNKNOWN',status:'BLOCKED',person_id:null},
                        proxy:overlap?'PROVISIONAL_ROI_OVERLAP':'NO_ROI_OVERLAP'};
                    emit('clusters',row);
                    const reasons=[];if(c.semantic.semantic==='UNKNOWN')reasons.push('SEMANTIC_UNKNOWN');
                    if(c.semantic.semantic==='HUMAN_EVIDENCE'&&c.old.joint!=='CONFIRMED_HUMAN')reasons.push('NEW_HUMAN_OLD_NOT_CONFIRMED');
                    if(assignment.status==='UNKNOWN_ASSOCIATION')reasons.push('ASSOCIATION_UNKNOWN');
                    if(c.semantic.conflict_observed)reasons.push('FROZEN_CONFLICT');
                    if(mode==='WORKSPACE'&&c.semantic.semantic==='HUMAN_EVIDENCE')reasons.push('EMPTY_HUMAN_FALSE_ALARM');
                    if(reasons.length||reviewReasons.length||[0,Math.floor(data.frames.length/2),data.frames.length-1].includes(fi)) {
                        const task={id,...frameKey,ci:c.ci,member_sha256:c.member_sha256,rows:c.rows,reasons:[...new Set([...reasons,...reviewReasons])],
                            source:'diagnostic',label:'UNKNOWN',person_id:null,reviewer:null,status:'PENDING',proxy:row.proxy};
                        emit('review',task);
                    }
                }
                if(reviewReasons.length||[0,Math.floor(data.frames.length/2),data.frames.length-1].includes(fi)) {
                    const rowToIndex=new Map(ws.rows.map((r,i)=>[r,i]));
                    const deleted=[...new Set([...stageRows.cleanup_removed,...(suffix==='114340'?stageRows.reference_removed.filter(r=>{
                        const i=rowToIndex.get(r);return inside(...ws.buf.subarray(i*4,i*4+3),center);}):[])])];
                    const p={...frameKey,reasons:reviewReasons,deleted:pointRows(ws,deleted),
                        clusters:cs.map(c=>({ci:c.ci,semantic:c.semantic.semantic,old_joint:c.old.joint,points:pointRows(chain.clean,c.rows)}))};
                    emit('points',p);
                }
                if(fi%80===0) console.log(pass,suffix,mode,fi,'clusters',cs.length);
            }
            summaries.push(sum);console.log('SUMMARY',JSON.stringify(sum));
        }
    }
    assert.strictEqual(reconciliation.roi_features,24);assert.strictEqual(reconciliation.empty_sample_clusters,12);
    assert.strictEqual(reconciliation.retention_frames,991);
    write(base,'binding.json',binding);write(base,'reconciliation.json',reconciliation);write(base,'summary.json',summaries);
    for(const fd of Object.values(fds))fs.closeSync(fd);
    write(base,'digests.json',Object.fromEntries(['frames','clusters','votes','review','points','summary','binding','reconciliation'].map(n=>
        [n,R.shaFile(path.join(base,n+(['summary','binding','reconciliation'].includes(n)?'.json':'.jsonl')))])));
    return summaries;
}
module.exports={FrameVotes,voteSelfcheck,level,load,subset,transform,clusterFrame,pointRows,inside,run};
if(require.main===module) {
    console.log('VOTE_SELF_CHECK',JSON.stringify(voteSelfcheck()));
    if(process.argv[2]==='selfcheck') console.log('SELF_CHECK_OK');
    else run(process.argv[2]);
}
