"use strict";
// Read-only W03 diagnostics. No production patch, registration application API,
// ICP refit, threshold change, artifact publication, or automatic human labels.
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=require('../../../../pc_apps/human_replay/registration');
const M=require('../../../../pc_apps/human_replay/registration_method');
const PL=require('../../../../pc_apps/human_replay/human_pipe_lib');
const H=require('../2026-10-07_hrw03_r39_closeout/audit_lib');
const old=path.resolve(__dirname,'../2026-10-07_hrw03_r39_closeout'),root=R.ROOT;
const read=n=>R.read(path.join(old,n));
const write=(n,v)=>fs.writeFileSync(path.join(__dirname,n),R.serialize(v),{flag:'wx'});
const a=read('01_absorbed_points.json'),attr=read('03_confirmation_attribution_r2.json'),s=read('06_shadow_results.json'),g=read('07_gate_samples.json');
const rd=path.join(root,'captures/registration',a.session+'__to__cap_20261004_203349');
const prov=R.read(path.join(rd,'provenance.json')),reg=R.read(path.join(rd,'registration.json'));
assert.equal(R.shaFile(path.join(rd,'registration.json')),a.registration_artifact_id);
const lev={};for(const side of ['source','reference']) {
    assert.deepEqual(R.sessionBinding(root,prov[side+'_session'].sid),prov[side+'_session']);
    lev[side]=R.levelingBinding(root,prov[side+'_session'].sid,prov[side+'_leveling'].job_id);
    assert.deepEqual(lev[side].binding,prov[side+'_leveling']);
}
const sourceFiles=['human_pipe_lib.js','human_replay_lib.js','registration.js','registration_method.js','human_detect.js','leveling.py'];
const baseline=R.read(path.join(__dirname,'00_baseline.json'));
for(const f of sourceFiles) assert.equal(R.shaFile(path.join(root,'pc_apps/human_replay',f)),baseline.files['pc_apps/human_replay/'+f].sha256);
write('00_inputs_sources_params.json',{source:'diagnostic',branch:baseline.branch,head:baseline.head,ponytail:'C:/Users/30680/.codex/skills/ponytail/SKILL.md',runtime:process.version,
    input_binding:prov,source_sha256:Object.fromEntries(sourceFiles.map(f=>[f,R.shaFile(path.join(root,'pc_apps/human_replay',f))])),
    acceptance:{file:'../2026-10-07_hrw03_r37_productionization/06_test_matrix.md',version:1,sha256:R.shaFile(path.join(old,'../2026-10-07_hrw03_r37_productionization/06_test_matrix.md'))},
    params:{PIPE:PL.PIPE,R:reg.rotation_row_major,t:reg.translation_m,gate_profile:R.PROFILE,diagnostic_only:true}});
const dot=(u,v)=>u.reduce((n,x,i)=>n+x*v[i],0),xyz=(Rmat,p,t)=>M.m3.apply(Rmat,...p).map((v,i)=>v+t[i]);
function transformPlane(n,d,A,t) {const nn=M.m3.apply(A,...n);return {normal:nn,offset:d-dot(nn,t)};}
const e3=[0,0,1],zero=[0,0,0],A=reg.rotation_row_major,t=reg.translation_m;
const srcRaw={normal:lev.source.tf.R[2],offset:lev.source.tf.t[2]},refRaw={normal:lev.reference.tf.R[2],offset:lev.reference.tf.t[2]};
const sourceLeveled=transformPlane(srcRaw.normal,srcRaw.offset,lev.source.tf.R.flat(),lev.source.tf.t);
const referenceLeveled=transformPlane(refRaw.normal,refRaw.offset,lev.reference.tf.R.flat(),lev.reference.tf.t);
assert(Math.max(...sourceLeveled.normal.map((v,i)=>Math.abs(v-e3[i])))<1e-12&&Math.abs(sourceLeveled.offset)<1e-12);
assert(Math.max(...referenceLeveled.normal.map((v,i)=>Math.abs(v-e3[i])))<1e-12&&Math.abs(referenceLeveled.offset)<1e-12);
const transported=transformPlane(e3,0,A,t),refInSource=transformPlane(e3,0,M.m3.t(A),M.m3.apply(M.m3.t(A),...t.map(v=>-v)));
const inWorkspace=h=>h>=PL.PIPE.ground_keep_below_m&&h<=PL.PIPE.z_max_m;
const pointRows=a.points.map(p=>{
    const q=p.registered_xyz,height=dot(transported.normal,q)+transported.offset;
    assert(Math.abs(height-p.source_xyz[2])<1e-7);
    const computed=xyz(A,p.source_xyz,t).map(Math.fround);assert.deepEqual(computed,q);
    const zPlane=-(transported.normal[0]*q[0]+transported.normal[1]*q[1]+transported.offset)/transported.normal[2];
    const sourceRule=inWorkspace(p.source_xyz[2]),transportedRule=inWorkspace(height),referenceRule=inWorkspace(q[2]);
    assert.equal(sourceRule,transportedRule);
    return {id:p.id,frame:p.frame,point_index:p.original_point_index,source_xyz:p.source_xyz,registered_xyz:q,
        source_ground_height_m:p.source_xyz[2],transported_ground_signed_height_m:height,reference_ground_height_m:q[2],
        transported_floor_z_at_registered_xy_m:zPlane,reference_minus_source_height_m:q[2]-height,
        current_workspace_pass:referenceRule,diagnostic_source_crop_before_registration:sourceRule,
        diagnostic_transported_plane_crop:transportedRule,reference_hit:!!p.reference_match,online_hit:!!p.registered_online_match,
        diagnostic_after_source_crop_with_frozen_S_maps:sourceRule&&!p.reference_match&&!p.registered_online_match,
        semantic_label:'UNKNOWN',source:'diagnostic'};
});
const stats=v=>({min:Math.min(...v),max:Math.max(...v)});
const coord={source:'diagnostic',planes:{source_raw:srcRaw,source_leveled:sourceLeveled,reference_raw:refRaw,reference_leveled:referenceLeveled,
    transported_source_in_reference:transported,reference_in_source:refInSource},tilt_deg:Math.acos(transported.normal[2])*180/Math.PI,
    rows:pointRows,summary:{points:pointRows.length,crop_flips:pointRows.filter(p=>p.current_workspace_pass!==p.diagnostic_source_crop_before_registration).length,
        reference_minus_source_height_m:stats(pointRows.map(p=>p.reference_minus_source_height_m)),transported_floor_z_m:stats(pointRows.map(p=>p.transported_floor_z_at_registered_xy_m)),
        crop_flips_with_reference_hit:pointRows.filter(p=>!p.current_workspace_pass&&p.reference_hit).length,
        crop_flips_with_online_hit:pointRows.filter(p=>!p.current_workspace_pass&&p.online_hit).length,
        diagnostic_precleanup_survivors:pointRows.filter(p=>p.diagnostic_after_source_crop_with_frozen_S_maps).length},
    caveat:'Counterfactual workspace decision only; S maps fixed, no changed map rebuild/cleanup/Tracker, no safety pass, no claim of physical floor GT.'};
write('02_workspace_planes.json',coord);
console.log('planes '+JSON.stringify({...coord,rows:undefined}));

// Replay saved candidate features through unchanged Tracker, without cloud pipeline.
// This isolates assignment/vote defects from point removal and preserves old results.
function traceBranch(name) {
    const tracker=new PL.Tracker(),trace=[],collisions=[],order=[];
    for(let fi=0;fi<s[name].frames.length;fi++) {
        const frame=s[name].frames[fi],before=R.clone(tracker),clusters=R.clone(frame.clusters),sim=R.clone(tracker),assign=[];
        for(let ci=0;ci<clusters.length;ci++) {
            const c=clusters[ci],dist=sim.tracks.filter(v=>v.active).map(v=>({id:v.id,distance:Math.hypot(v.x-c.cx,v.y-c.cy)})).sort((a,b)=>a.distance-b.distance);
            const best=dist.find(v=>v.distance<PL.PIPE.track_gate_xy_m);
            let tr=best?sim.tracks.find(v=>v.id===best.id):null;
            const prior=tr?.votes?.slice()??[],alreadyUpdated=tr?.last_seen===fi;
            if(!tr) {tr={id:sim.next_id++,active:true,born_idx:fi,x:c.cx,y:c.cy,votes:[]};sim.tracks.push(tr);}
            else {tr.x+=PL.PIPE.ema_alpha*(c.cx-tr.x);tr.y+=PL.PIPE.ema_alpha*(c.cy-tr.y);}
            tr.last_seen=fi;tr.votes??=[];tr.votes.push(c.joint==='CONFIRMED_HUMAN'?1:0);if(tr.votes.length>PL.PIPE.human_confirm_window)tr.votes.shift();
            const confirmed=tr.votes.reduce((n,v)=>n+v,0)>=PL.PIPE.human_confirm_votes&&fi-tr.born_idx+1>=PL.PIPE.human_confirm_min_age;
            assert.equal(tr.id,c.track_id);assert.equal(confirmed,c.track_confirmed);
            assign.push({cluster:ci,track:tr.id,joint:c.joint,candidate_centroid:[c.cx,c.cy,c.cz],distance:best?.distance??null,candidates:dist,prior_votes:prior,votes:tr.votes.slice(),same_frame_reuse:alreadyUpdated,confirmed});
        }
        tracker.tick(fi,clusters);
        assert.deepEqual(R.clone(tracker.tracks.filter(v=>v.active)),frame.tracks);
        const groups=new Map();assign.forEach(v=>{const arr=groups.get(v.track)??[];arr.push(v);groups.set(v.track,arr);});
        for(const [tid,rows] of groups)if(rows.length>1)collisions.push({frame:fi,track:tid,assignments:rows,final_votes:tracker.tracks.find(v=>v.id===tid).votes});
        const reversed=Object.assign(new PL.Tracker(),R.clone(before)),rc=frame.clusters.map((c,ci)=>({...R.clone(c),diagnostic_original_index:ci})).reverse();
        reversed.tick(fi,rc);
        const changes=rc.filter(c=>c.track_id!==frame.clusters[c.diagnostic_original_index].track_id||c.track_confirmed!==frame.clusters[c.diagnostic_original_index].track_confirmed).map(c=>({cluster:c.diagnostic_original_index,baseline_track:frame.clusters[c.diagnostic_original_index].track_id,reverse_track:c.track_id,baseline_confirmed:frame.clusters[c.diagnostic_original_index].track_confirmed,reverse_confirmed:c.track_confirmed}));
        if(changes.length)order.push({frame:fi,changes});
        trace.push({frame:fi,assignments:assign});
    }
    return {trace,collisions,collision_frames:[...new Set(collisions.map(v=>v.frame))],order_sensitive_frames:order};
}
const trackDiag={source:'diagnostic',P:traceBranch('P'),S:traceBranch('S'),equivalence:'All 165 saved active Tracker snapshots per branch matched unchanged tick exactly. Reverse order is per-frame diagnostic from identical prefix; never new production output.'};
function fake(joint,x=.1){return {ok:true,cx:x,cy:0,cz:1,height_m:1.6,upcos:.99,label:'HUMAN_CANDIDATE',n:100,joint};}
const repro=new PL.Tracker();repro.tick(0,[fake('NON_HUMAN')]);repro.tick(1,[fake('NON_HUMAN')]);
const cc=[fake('CONFIRMED_HUMAN',0),fake('CONFIRMED_HUMAN',.2),fake('CONFIRMED_HUMAN',.4)];repro.tick(2,cc);
assert.deepEqual(cc.map(c=>c.track_id),[1,1,1]);assert.equal(cc[2].track_confirmed,true);
assert.deepEqual(repro.tracks[0].pose_history.map(v=>v.f),[0,1,2,2,2]);
trackDiag.reproduction={kind:'SYNTHETIC_REPRODUCTION_ONLY',distinct_positive_frames:1,clusters:cc,track:repro.tracks[0],bug:'BUG-R40-T01 same-frame assignment reuse; 3 positive clusters in one frame meet 3/5 confirmation at age 3'};
write('04_tracker_reproduction_and_trace.json',trackDiag);
console.log('tracker '+JSON.stringify({P_collision_frames:trackDiag.P.collision_frames,S_collision_frames:trackDiag.S.collision_frames,P_order_sensitive:trackDiag.P.order_sensitive_frames.map(v=>v.frame),S_order_sensitive:trackDiag.S.order_sensitive_frames.map(v=>v.frame)}));

// Targeted point-identity trace only: build frozen maps once, inspect selected frames.
const current=R.loadFrames(root,prov.source_session.sid,lev.source),ref=R.loadFrames(root,prov.reference_session.sid,lev.reference,true);
const raw=current.frames,registered=raw.map(fr=>{const b=fr.slice();R.transformBuffer?assert.fail('unexpected API'):null;for(let k=0;k<b.length;k+=4){const q=xyz(A,[b[k],b[k+1],b[k+2]],t);for(let j=0;j<3;j++)b[k+j]=q[j];}return b;});
const pclean=raw.map(PL.denoise),sclean=registered.map(PL.denoise),onlineP=PL.build_static_map(pclean),onlineS=PL.build_static_map(sclean),refmap=PL.build_reference_map(ref.frames),refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
assert.equal(R.refBinding(refmap).digest.value,prov.background_reference.digest.value);
const disappear=attr.rows.filter(r=>r.change==='disappeared'&&r.attribution_category!=='STATIC_REMOVAL_EXPECTED');assert.equal(disappear.length,24);
const tops=s.topology.frames.filter(v=>v.split||v.merge),selected=[...new Set([...disappear.map(v=>v.frame),...tops.map(v=>v.frame),65,146])].sort((a,b)=>a-b);
const caseFrames=[];
for(const fi of selected) {
    const pf=PL.extract_foreground(pclean[fi],onlineP),sf=PL.extract_foreground(PL.extract_foreground(sclean[fi],refkeys).fg_xyzi,onlineS);
    const po=H.ownership(PL,pf.fg_xyzi,s.P.frames[fi],raw[fi]),so=H.ownership(PL,sf.fg_xyzi,s.S.frames[fi],registered[fi]);
    const edges=H.overlaps(po.ids,so.ids);assert.deepEqual(edges,s.topology.frames[fi].edges);
    const owners=name=>(name==='P'?po:so).ids.map((ids,ci)=>({cluster:ci,geometry:H.summarize(s[name].frames[fi].clusters[ci]),point_indices:[...ids].sort((a,b)=>a-b)}));
    const pointRows=[];
    for(let i=0;i<raw[fi].length/4;i++) if(po.status[i].cluster!==null||so.status[i].cluster!==null) {
        const q=[registered[fi][i*4],registered[fi][i*4+1],registered[fi][i*4+2]],p=[raw[fi][i*4],raw[fi][i*4+1],raw[fi][i*4+2]];
        let mechanism='RETAINED_OR_REASSIGNED';
        if(po.status[i].cluster!==null&&so.status[i].cluster===null) {
            if(!inWorkspace(q[2]))mechanism='WORKSPACE_CROP';
            else if(H.matcher(PL,refkeys,q))mechanism='REFERENCE';
            else if(H.matcher(PL,onlineS,q))mechanism='ONLINE';
            else if(so.status[i].foreground&&!so.status[i].after_cleanup)mechanism='CLEANUP';
            else if(so.status[i].after_cleanup)mechanism='BELOW_CANDIDATE_SIZE';
            else mechanism='DENOISE_OR_OTHER';
        }
        pointRows.push({point_index:i,P:po.status[i],S:so.status[i],source_xyz:p,registered_xyz:q,mechanism,semantic:'UNKNOWN'});
    }
    const shared=edges.map(e=>({...e,point_indices:[...po.ids[e.P]].filter(v=>so.ids[e.S].has(v)).sort((a,b)=>a-b)}));
    caseFrames.push({frame:fi,frame_seq:current.meta.frames[fi].seq,P:owners('P'),S:owners('S'),edges:shared,
        cleanup:{P_before:pf.n_fg,P_after:po.iso.xyzi.length/4,S_before:sf.n_fg,S_after:so.iso.xyzi.length/4},
        changed_rows:attr.rows.filter(r=>r.frame===fi&&r.attribution_category!=='STATIC_REMOVAL_EXPECTED'),
        tracker:{P:trackDiag.P.trace[fi],S:trackDiag.S.trace[fi]},points:pointRows});
}
write('03_topology_point_cases.json',{source:'diagnostic',frames:caseFrames,selected_frames:selected,scope:'24 non-WD01 disappearances + every split/merge frame + f65/f146; full candidate identities, not cropped viewer identities',semantic_GT:'UNKNOWN'});
console.log('point cases '+JSON.stringify({selected_frames:selected,count:caseFrames.length}));

// Input-validity inconsistency: exporter preserves all-zero XYZ, JS loaders transform it.
const zeroAudit=[];
for(const side of ['source','reference']) {
    const sid=prov[side+'_session'].sid,dir=path.join(root,'captures/remote',sid),meta=R.read(path.join(dir,'meta.json')),bytes=fs.readFileSync(path.join(dir,'points.bin'));
    let zeros=0,zeroIntensity=0;const perFrame=[],examples=[];
    for(let fi=0;fi<meta.frames.length;fi++) {const f=meta.frames[fi];let count=0;for(let i=0;i<f.count_points;i++) {const pos=(f.offset_points+i)*meta.point_stride_bytes;
        if(bytes.readFloatLE(pos)===0&&bytes.readFloatLE(pos+4)===0&&bytes.readFloatLE(pos+8)===0) {count++;zeros++;if(bytes.readFloatLE(pos+12)===0)zeroIntensity++;
            if(examples.length<3)examples.push({frame:fi,point_index:i,intensity:bytes.readFloatLE(pos+12),record_hex:bytes.subarray(pos,pos+28).toString('hex')});}
    }perFrame.push({frame:fi,zeros:count});}
    const buf=new Float32Array([0,0,0,0]),lv=lev[side].tf;const q=xyz(lv.R.flat(),[0,0,0],lv.t).map(Math.fround);buf.set([...q,0]);
    assert.equal(PL.denoise(new Float32Array([0,0,0,0])).length,0);assert.equal(PL.denoise(buf).length,4);
    zeroAudit.push({side,sid,total_points:meta.total_points,zero_xyz:zeros,zero_intensity:zeroIntensity,leveled_zero_xyz:q,after_leveling_denoise_count:1,
        examples,frames:perFrame,gate_sample_matching_zero:g.rows.filter(v=>side==='source'&&v.source.every((x,j)=>x===q[j])).map(v=>({i:v.i,support:v.sample_support_points,reason:v.reason,trim:v.trim_status}))});
}
write('04_zero_xyz_reproduction.json',{source:'diagnostic',bug:'BUG-R40-I01 invalid XYZ preservation differs between leveling.export_dataset and JS in-place consumers',rows:zeroAudit,
    scope:'No validity filtering change; no recalculated gate, denominator, reference map, or ICP. One fine centroid is not 1.25M independent correspondence samples.'});

const rawCount=g.rows.filter(v=>v.reason==='RAW_CORRESPONDENCE').length,keepCount=g.rows.filter(v=>v.trim_status==='KEPT').length;
assert.equal(rawCount,9897);assert.equal(keepCount,5938);assert.equal(Math.floor(rawCount*.6),keepCount);
assert.equal(keepCount/g.source,s.registration.gate.checks.find(c=>c.id==='inlier_ratio').metric);
const needKeep=Math.ceil(g.source*.5),needRaw=Math.ceil(needKeep/.6);assert.equal(needKeep,5980);assert.equal(needRaw,9967);
write('05_gate_protocol_review.json',{source:'diagnostic',fixed:true,source_count:g.source,raw_count:rawCount,kept_count:keepCount,
    raw_coverage:rawCount/g.source,trimmed_coverage:keepCount/g.source,max_trimmed_coverage:Math.floor(g.source*.6)/g.source,
    raw_needed:needRaw,raw_coverage_needed:needRaw/g.source,keep_needed:needKeep,
    missing_support:g.counts,bySector:g.bySector,zero_xyz_findings:zeroAudit.map(v=>({side:v.side,zeros:v.zero_xyz,gate_sample:v.gate_sample_matching_zero})),
    design_only:['Use explicit raw_valid_correspondence_ratio and trimmed_support_ratio names in a future versioned schema; retain current v1 ratio and 50% gate.',
        'Contract currently calls n_correspondence final accepted iteration; implementation recomputes sorted/trimmed pairs at fixed B, not saved point-to-point B solver iteration. Clarify protocol without replacing B.',
        'No independent multi-pair safety calibration supports a new profile; provisional support bands remain conservative. No new profile published.',
        'Separate matched-only fit residual at radius .30 from fit support radius .08, and validate input/normal coverage before attributing physical causes.'],
    physical_causes:{occlusion:'UNKNOWN',FOV:'UNKNOWN',dynamic:'UNKNOWN',quantization:'UNKNOWN',physical_floor:'UNKNOWN'},gate_override:false});

const pointFrames=[...new Set(a.points.map(p=>p.frame))],priorityFrames=[...new Set([...pointFrames,...disappear.map(r=>r.frame),...tops.map(r=>r.frame)])].sort((a,b)=>a-b);
const gt={source:'diagnostic',kind:'hrw03_gt_task_manifest',schema:1,input_binding:prov,viewer:'../2026-10-07_hrw03_r39_closeout/09_point_review.html',
    label_export_validator:'../2026-10-07_hrw03_r39_closeout/review_gt.js',
    points:a.points.map(p=>({id:p.id,frame:p.frame,seq:p.frame_seq,point_index:p.original_point_index,label:'UNKNOWN'})),
    disappeared_rows:disappear.map(r=>({id:r.id,frame:r.frame,Pidx:r.Pidx,Sidx:r.Sidx,P_track_id:r.P_track_id,S_track_id:r.S_track_id,label:'UNKNOWN',continuity:'UNKNOWN'})),
    topology:tops.map(v=>({frame:v.frame,split:v.split,merge:v.merge,edges:v.edges,GT:'UNKNOWN'})),priority_frames:priorityFrames,
    all_required_rows:attr.rows.filter(v=>v.attribution_category!=='STATIC_REMOVAL_EXPECTED').map(r=>({id:r.id,frame:r.frame,label:'UNKNOWN',continuity:'UNKNOWN'})),
    caveat:'Task manifest is machine diagnostic, never source human. Existing viewer supplies one pair-level label; separate P/S cluster semantics, real person identity and topology need a small human-authored sidecar.'};
write('06_gt_tasks.json',gt);
console.log('GT '+JSON.stringify({priority_frames:priorityFrames,count:priorityFrames.length,points:31,nonWD01_disappearances:24,required_rows:155}));
console.log('zero XYZ '+JSON.stringify(zeroAudit.map(v=>({side:v.side,total:v.total_points,zeros:v.zero_xyz,zero_intensity:v.zero_intensity,gate:v.gate_sample_matching_zero}))));
console.log('All targeted diagnostic assertions passed. Historical gate WARN and strict T38-05/06 FAIL unchanged; actual human GT BLOCKED.');
