"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=require('../../../../pc_apps/human_replay/registration'),M=require('../../../../pc_apps/human_replay/registration_method');
const PL=require('../../../../pc_apps/human_replay/human_pipe_lib'),H=require('./audit_lib');
const BR=require('./baseline_code/pc_apps/human_replay/registration');
const phase=process.argv.find(v=>v.startsWith('--phase='))?.slice(8);assert(['before','after'].includes(phase));
const root=R.ROOT,src='cap_20261002_223757',ref='cap_20261004_203349';
const dir=path.join(root,'captures/registration',src+'__to__'+ref),provenance=R.read(path.join(dir,'provenance.json'));
const archive=R.read(path.join(__dirname,'../2026-10-06_hrw03_r8/03_results.json'));
const previous=R.read(path.join(__dirname,'../2026-10-07_hrw03_r38/04_shadow_results_r3.json'));
const sl=R.levelingBinding(root,src,provenance.source_leveling.job_id,provenance.source_leveling.transform_id);
const rl=R.levelingBinding(root,ref,provenance.reference_leveling.job_id,provenance.reference_leveling.transform_id);
const session=R.loadFrames(root,src,sl),raw=session.frames,reference=R.loadFrames(root,ref,rl,true).frames;
const refmap=PL.build_reference_map(reference),refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
const options={source:src,reference:ref,referenceMap:refmap};
const native=R.load(dir,options),loaded=BR.load(dir,options);
assert.equal(loaded.state,'DEGRADED');assert.equal(loaded.artifact_id,previous.artifact_id);
if(phase==='before')assert.equal(native.state,'DEGRADED');else {assert.equal(native.state,'STALE');assert(native.reasons.includes('METHOD_STALE'));}
console.log('Current loader:\n'+R.logLines(native).join('\n'));console.log('Historical code-bound sandbox loader:\n'+BR.logLines(loaded).join('\n'));
const r=loaded.registration,invR=M.m3.t(r.rotation_row_major),invT=M.m3.apply(invR,...r.translation_m.map(v=>-v));
function source(p) {return M.m3.apply(invR,...p).map((v,j)=>v+invT[j]);}
function registered(p) {return M.m3.apply(r.rotation_row_major,...p).map((v,j)=>Math.fround(v+r.translation_m[j]));}
function branch(a,shadow=false) {
    const use=a.state==='VALID'||shadow&&a.state==='DEGRADED';
    const clouds=use?raw.map(buf=>BR.applyRegistration({buf,frame:'leveled_session:'+src},a,{shadow}).buf):raw;
    const clean=clouds.map(PL.denoise),online=PL.build_static_map(clean),tracker=new PL.Tracker(),frames=[],fg=[];
    for(let i=0;i<raw.length;i++) {
        let o,f;
        if(use) {f=PL.extract_foreground(PL.extract_foreground(clean[i],refkeys).fg_xyzi,online);
            o=PL.pipeline_frame(f.fg_xyzi,i,{static_keys:null,tracker});o.n_in=clouds[i].length/4;o.n_denoise=clean[i].length/4;
            o.n_foreground=f.n_fg;o.n_dropped=clean[i].length/4-f.n_fg;}
        else {o=PL.pipeline_frame(clouds[i],i,{static_keys:online,tracker});f=PL.extract_foreground(clean[i],online);}
        if(phase==='after') {
            assert(Number.isInteger(o.cleanup_split_delta));assert.equal(o.cleanup_split_delta,o.clusters_after_cleanup-o.clusters_before_cleanup);
            assert.equal(o.fg_before_cleanup-o.fg_after_cleanup,o.actually_removed_points);
            assert.equal(o.isolated_3d_candidates,o.xy_topology_vetoed+o.actually_removed_voxels);
        }
        frames.push(R.clone(o));fg.push(f.fg_xyzi);
    }
    return {frames,fg,clouds,clean,online,registered:use,digest:R.identity(frames),behavior_digest:R.identity(frames.map(H.behavior))};
}
const P=branch(native),S=branch(loaded,true); // native STALE always SAFE; only archived sandbox enables diagnostic S.
for(const name of ['P','S']) {
    assert.equal(R.identity(previous[name].frames.map(H.behavior)),(name==='P'?P:S).behavior_digest,name+' all non-diagnostic outputs');
    if(phase==='before')assert.equal((name==='P'?P:S).digest,previous[name].digest);
}
const counts={WD01:{P:0,S:0,A:archive.groups.WD01.conditions.A.residual},WD02:{P:0,S:0,A:archive.groups.WD02.conditions.A.residual}};
const wd=p=>({WD01:Math.hypot(p[0]-3.5,p[1]+.76)<=.9,WD02:Math.hypot(p[0],p[1])>8||[[10.75,4.25],[10.25,-1.75],[10.5,5.5]].some(q=>Math.hypot(p[0]-q[0],p[1]-q[1])<=1.5)});
for(let f=0;f<raw.length;f++)for(const name of ['P','S']) {
    const b=(name==='P'?P:S).fg[f];for(let k=0;k<b.length;k+=4) {
        const p=name==='P'?[b[k],b[k+1],b[k+2]]:source([b[k],b[k+1],b[k+2]]);
        for(const [region,yes] of Object.entries(wd(p)))if(yes)counts[region][name]++;
    }
}
assert.deepEqual(counts,previous.counts);
for(const v of Object.values(counts))v.reduction_pct=100*(v.P-v.S)/v.P;
const safety={clean:{},near:{},clean_absorbed:0,z_bands:{'<0.3':0,'0.3-0.6':0,'>0.6':0}},absorbed=[],attr=[],topology=[],views=[];
const legacy={missed_tracks:[],new_green:[],new_purple:[],missed_events:[]};
function trace(p,si) {
    const q=[S.clouds[si.frame][si.index*4],S.clouds[si.frame][si.index*4+1],S.clouds[si.frame][si.index*4+2]],
        workspace=q[2]>=PL.PIPE.ground_keep_below_m&&q[2]<=PL.PIPE.z_max_m,
        denoised=Number.isFinite(Math.hypot(...q))&&Math.hypot(...q)>=PL.PIPE.range_min_m&&Math.hypot(...q)<=PL.PIPE.range_max_m;
    const rh=H.matcher(PL,refkeys,q),oh=H.matcher(PL,S.online,q),pr=H.matcher(PL,refkeys,p),po=H.matcher(PL,P.online,p);
    const mechanism=!denoised?'DENOISE':!workspace?'WORKSPACE_CROP':rh?'REGISTRATION_TRANSFORM_REFERENCE_MATCH':oh?'ONLINE_BACKGROUND':'OTHER';
    return {registered_xyz:q,denoise_pass:denoised,workspace_pass:workspace,reference_match:rh,registered_online_match:oh,
        unregistered_reference_match:pr,P_online_match:po,mechanism};
}
for(let fi=0;fi<raw.length;fi++) {
    const a=H.ownership(PL,P.fg[fi],P.frames[fi],raw[fi]),b=H.ownership(PL,S.fg[fi],S.frames[fi],S.clouds[fi]);
    const pc=P.frames[fi].clusters,sc=S.frames[fi].clusters,edges=H.overlaps(a.ids,b.ids),top=H.topology(a.ids,b.ids,edges);
    topology.push({frame:fi,...top,cleanup_P_before:P.frames[fi].clusters_before_cleanup instanceof Array?P.frames[fi].clusters_before_cleanup.length:P.frames[fi].clusters_before_cleanup,
        cleanup_P_after:P.frames[fi].clusters_after_cleanup instanceof Array?P.frames[fi].clusters_after_cleanup.length:P.frames[fi].clusters_after_cleanup,
        cleanup_S_before:S.frames[fi].clusters_before_cleanup instanceof Array?S.frames[fi].clusters_before_cleanup.length:S.frames[fi].clusters_before_cleanup,
        cleanup_S_after:S.frames[fi].clusters_after_cleanup instanceof Array?S.frames[fi].clusters_after_cleanup.length:S.frames[fi].clusters_after_cleanup});
    const deletions=new Map();
    for(let i=0;i<a.status.length;i++)if(a.status[i].foreground&&!b.status[i].foreground)deletions.set(i,trace(Array.from(raw[fi].subarray(i*4,i*4+3)),{frame:fi,index:i}));
    const clean=archive.params.clean_frames.includes(fi),near=archive.params.near_furniture_frames.includes(fi),center=near?[1.45,.85]:archive.person_centers[fi];
    if(clean||near) {
        const bands={},retained=H.pointSet(S.fg[fi],true);
        for(let k=0;k<P.fg[fi].length;k+=4) {
            const p=Array.from(P.fg[fi].subarray(k,k+3));if(Math.hypot(p[0]-center[0],p[1]-center[1])>.6)continue;
            const band=p[2]>=1.2?'z>=1.2':p[2]>=.8?'0.8-1.2':p[2]>=.3?'0.3-0.8':'below-0.3';
            const v=bands[band]??={n:0,absorbed:0};v.n++;const q=registered(p);
            if(!retained.has(q.join(',')))v.absorbed++;
        }
        if(near)safety.near[fi]=bands;else {
            safety.clean[fi]=bands;safety.clean_absorbed+=Object.values(bands).reduce((n,v)=>n+v.absorbed,0);
            for(const [i,t] of deletions) {
                const p=Array.from(raw[fi].subarray(i*4,i*4+3));if(Math.hypot(p[0]-center[0],p[1]-center[1])>.6)continue;
                const pf=a.status[i],sf=b.status[i],meta=session.meta.frames[fi];
                const id=src+':f'+fi+':p'+i;safety.z_bands[p[2]<.3?'<0.3':p[2]<=.6?'0.3-0.6':'>0.6']++;
                // Prove diagnostic matcher agrees with real production extraction for this point.
                for(const [map,hit] of [[refkeys,t.reference_match],[S.online,t.registered_online_match]])if(t.workspace_pass)
                    assert.equal(PL.extract_foreground(new Float32Array([...t.registered_xyz,raw[fi][i*4+3]]),map).n_fg===0,!!hit);
                absorbed.push({id,frame:fi,frame_seq:meta.seq,stamp_sec:meta.stamp_sec,stamp_nanosec:meta.stamp_nanosec,
                    original_point_index:i,session_point_index:meta.offset_points+i,byte_offset:(meta.offset_points+i)*28,
                    source_xyz:p,distance:Math.hypot(...p),intensity:raw[fi][i*4+3],...t,
                    P_path:pf,S_path:sf,P_cluster:pf.cluster===null?null:H.summarize(pc[pf.cluster]),
                    S_cluster:sf.cluster===null?null:H.summarize(sc[sf.cluster],source([sc[sf.cluster].cx,sc[sf.cluster].cy,sc[sf.cluster].cz])),
                    nearest_reference_voxel:H.nearest(refkeys,t.registered_xyz),
                    nearest_reference_any_occ:H.nearest(refmap.voxels,t.registered_xyz),semantic_label:'UNKNOWN',source:'diagnostic',human_effect:'UNKNOWN'});
            }
        }
    }
    const spatial=(s,p)=>{const u=source([s.cx,s.cy,s.cz]);return Math.hypot(u[0]-p.cx,u[1]-p.cy)<=PL.PIPE.track_gate_xy_m;};
    const changed=[];
    pc.forEach((c,i)=>{if(c.track_confirmed&&!sc.some(s=>s.track_confirmed&&spatial(s,c))){legacy.missed_tracks.push({frame:fi,P_track:c.track_id});changed.push({change:'disappeared',Pidx:i,Sidx:null,legacy:'missed_tracks'});}});
    sc.forEach((c,i)=>{
        if(c.track_confirmed&&!pc.some(p=>p.track_confirmed&&spatial(c,p))){legacy.new_green.push({frame:fi,S_track:c.track_id});changed.push({change:'new_green',Pidx:null,Sidx:i,legacy:'new_green'});}
        if(c.joint==='CONFIRMED_HUMAN'&&!pc.some(p=>p.joint==='CONFIRMED_HUMAN'&&spatial(c,p))){legacy.new_purple.push({frame:fi,S_track:c.track_id});changed.push({change:'new_purple',Pidx:null,Sidx:i,legacy:'new_purple'});}
    });
    for(const ev of P.frames[fi].events) {
        const pt=P.frames[fi].tracks.find(t=>t.id===ev.track_id);
        const yes=S.frames[fi].events.some(se=>{const st=S.frames[fi].tracks.find(t=>t.id===se.track_id);if(!pt||!st)return false;const u=source([st.x,st.y,st.z]);return Math.hypot(u[0]-pt.x,u[1]-pt.y)<=PL.PIPE.track_gate_xy_m;});
        if(!yes)legacy.missed_events.push({frame:fi,event:ev});
    }
    for(const ch of changed) {
        let {Pidx,Sidx}=ch;const candidates=edges.filter(e=>Pidx!==null?e.P===Pidx:e.S===Sidx).sort((x,y)=>y.shared-x.shared);
        if(candidates.length){Pidx=candidates[0].P;Sidx=candidates[0].S;}
        const p=Pidx===null?null:pc[Pidx],s=Sidx===null?null:sc[Sidx];
        const pids=Pidx===null?new Set():a.ids[Pidx],sids=Sidx===null?new Set():b.ids[Sidx];
        const removal={WORKSPACE_CROP:0,REGISTRATION_TRANSFORM_REFERENCE_MATCH:0,ONLINE_BACKGROUND:0,DENOISE:0,OTHER:0,CLEANUP:0};
        for(const i of pids)if(!sids.has(i)){if(deletions.has(i))removal[deletions.get(i).mechanism]++;else if(b.status[i].foreground&&!b.status[i].after_cleanup)removal.CLEANUP++;}
        const staticWindow=p&&wd([p.cx,p.cy,p.cz]).WD01;
        const cat=H.category({change:ch.change,staticWindow,referenceRemoved:removal.REGISTRATION_TRANSFORM_REFERENCE_MATCH,p,s,edges,Pidx,Sidx,removedCleanup:removal.CLEANUP});
        const common=candidates[0]?.shared??0,added=sids.size-common,lost=pids.size-common;
        attr.push({id:'f'+fi+':'+ch.change+':P'+Pidx+':S'+Sidx,frame:fi,frame_seq:session.meta.frames[fi].seq,...ch,Pidx,Sidx,
            P_track_id:p?.track_id??null,S_track_id:s?.track_id??null,P:H.summarize(p),S:H.summarize(s,s?source([s.cx,s.cy,s.cz]):null),
            P_label:p?.joint??'ABSENT',S_label:s?.joint??'ABSENT',correspondence:'largest original-point intersection; null means no shared point, never nearest track-id guess',
            overlap_candidates:candidates,shared_points:common,points_lost_from_matched_cluster:lost,points_gained_in_matched_cluster:added,removed_by_mechanism:removal,
            P_votes:p?P.frames[fi].tracks.find(t=>t.id===p.track_id)?.votes:null,S_votes:s?S.frames[fi].tracks.find(t=>t.id===s.track_id)?.votes:null,
            attribution_category:cat,causal_factors:[lost||added?'POINT_MEMBERSHIP_CHANGE':'SAME_POINTS',p&&s&&p.joint!==s.joint?'GEOMETRIC_LABEL_CHANGE':'',p&&s&&p.track_confirmed!==s.track_confirmed?'TEMPORAL_VOTE_CHANGE':''].filter(Boolean),
            reason:`${cat}; shared=${common}, P-only=${lost}, S-only=${added}; removal=${JSON.stringify(removal)}; geometry and votes recorded`,
            semantic_GT:cat==='STATIC_REMOVAL_EXPECTED'?'WD01_REGION_GOLDEN (not per-point)':'UNKNOWN',
            true_human_track_continuity:'UNKNOWN',requires_human_review:cat!=='STATIC_REMOVAL_EXPECTED'});
    }
    if(changed.length||clean) {
        const centers=[];if(clean)centers.push(center);
        for(const ch of changed){const c=ch.Pidx===null?source([sc[ch.Sidx].cx,sc[ch.Sidx].cy,sc[ch.Sidx].cz]):[pc[ch.Pidx].cx,pc[ch.Pidx].cy];centers.push(c);}
        const pts=[];
        for(let k=0;k<raw[fi].length;k+=4)if(centers.some(c=>Math.hypot(raw[fi][k]-c[0],raw[fi][k+1]-c[1])<=1.1)) {
            const i=k/4,p=a.status[i],s=b.status[i],cleanAbs=absorbed.some(v=>v.frame===fi&&v.original_point_index===i);
            pts.push([i,raw[fi][k],raw[fi][k+1],raw[fi][k+2],S.clouds[fi][k],S.clouds[fi][k+1],S.clouds[fi][k+2],
                p.foreground?1:0,s.foreground?1:0,p.after_cleanup?1:0,s.after_cleanup?1:0,p.cluster,s.cluster,p.track,s.track,cleanAbs?1:0]);
        }
        views.push({frame:fi,seq:session.meta.frames[fi].seq,clean,centers,points:pts,P:pc.map(c=>H.summarize(c)),S:sc.map(c=>H.summarize(c,source([c.cx,c.cy,c.cz]))),
            reference_voxels:[...refkeys].filter(([,v])=>centers.some(c=>{const p=source([v.x,v.y,v.z]);return Math.hypot(p[0]-c[0],p[1]-c[1])<=1.1;})).map(([k,v])=>({key:k,source_xyz:source([v.x,v.y,v.z]),...v}))});
    }
    if(fi%25===0)console.log('audited frame '+fi);
}
assert.deepEqual(legacy,previous.tracks);assert.equal(absorbed.length,31);assert.equal(safety.clean_absorbed,31);
assert.deepEqual(safety.clean,previous.safety.clean);assert.deepEqual(safety.near,previous.safety.near);
const pointDocument={schema:1,session:src,frame_index_base:0,coordinate_frame:'leveled_session:'+src,registration_artifact_id:loaded.artifact_id,
    source_session:provenance.source_session,source_leveling:provenance.source_leveling,semantic_counts:{UNKNOWN:31},points:absorbed};
const categories={};for(const v of attr){const k=v.change+'|'+v.attribution_category;categories[k]=(categories[k]??0)+1;}
const confirmation={schema:1,legacy_term_semantics:{green:'track_confirmed',purple:'joint==CONFIRMED_HUMAN (R38 naming, not UI purple)'},
    count_unit:'frame-cluster rows; green and purple may overlap, not independent people',categories,rows:attr,
    limitations:['Original point overlap is diagnostic correspondence, not real-human GT.','No FP/FN/precision/recall can be inferred.','True-human continuity for changed candidates remains UNKNOWN.']};
const write=(name,v)=>fs.writeFileSync(path.join(__dirname,name),R.serialize(v),{flag:'wx'});
if(phase==='before') {
    write('01_absorbed_points.json',pointDocument);write('03_confirmation_attribution.json',confirmation);
    write('09_visualization_data.json',{schema:1,columns:['point_index','P_x','P_y','P_z','S_x','S_y','S_z','P_fg','S_fg','P_cleanup_retained','S_cleanup_retained','P_cluster','S_cluster','P_track','S_track','clean_absorbed'],
        frame_index_base:0,coordinate_notes:'P/S source view shares leveled source coordinates; native S uses registered xyz.',session:src,artifact_id:loaded.artifact_id,frames:views,absorbed,confirmation:attr});
} else {assert.deepEqual(pointDocument,R.read(path.join(__dirname,'01_absorbed_points.json')));assert.deepEqual(confirmation,R.read(path.join(__dirname,'03_confirmation_attribution.json')));}
const testRows=[],test=(id,fn)=>{try{fn();testRows.push({id,result:'PASS'});}catch(e){testRows.push({id,result:'FAIL',reason:e.message});}};
test('T37-20',()=>assert(loaded.diagnostics.direction_check.forward_p50<=loaded.diagnostics.direction_check.inverse_p50));
test('T38-02',()=>assert(counts.WD01.S<=.5*counts.WD01.A&&counts.WD01.S<=counts.WD01.P));
test('T38-03',()=>assert(counts.WD02.S<=.5*counts.WD02.A&&counts.WD02.S<=counts.WD02.P));
test('T38-04',()=>{const v=safety.near[55]['z>=1.2'];assert(v.absorbed/v.n<=.01);});
test('T38-05',()=>assert(safety.clean_absorbed<=5,'clean total=31>5'));
test('T38-06',()=>{
    assert(S.frames.every(f=>f.cleanup_split_delta===0),'nonzero/nonfinite cleanup delta');
    assert.equal(legacy.new_green.length,0,'new green');assert.equal(legacy.new_purple.length,0,'new purple');assert.equal(legacy.missed_tracks.length,0,'P confirmation loss (proxy)');
});
test('T38-11',()=>{const two=branch(loaded,true);assert.equal(two.digest,S.digest);});
test('T38-12',()=>assert(R.logLines(native).some(l=>l.startsWith('[REG] state=')&&l.includes('reason='))));
const sumTopology={};for(const k of ['before','after','split','merge','disappeared','appeared'])sumTopology[k]=topology.reduce((n,v)=>n+v[k],0);
const output={phase,scope:'offline historical-artifact diagnostic replay, never production consumption',counts,safety:{...safety,
    involved_frames:[...new Set(absorbed.map(p=>p.frame))],involved_P_clusters:[...new Set(absorbed.filter(p=>p.P_path.cluster!==null).map(p=>p.frame+':'+p.P_path.cluster))],
    involved_P_tracks:[...new Set(absorbed.map(p=>p.P_path.track).filter(v=>v!==null))]},
    registration:{native_loader:{state:native.state,reasons:native.reasons},historical_sandbox_loader:{state:loaded.state,reasons:loaded.reasons},
        gate:loaded.diagnostics.gate,transform:r,artifact_id:loaded.artifact_id,code_binding:provenance.code,current_code_binding:R.codeBinding(),
        refmap_digest:{historical:provenance.background_reference.digest,current:R.refBinding(refmap).digest}},
    confirmation:{legacy_counts:Object.fromEntries(Object.entries(legacy).map(([k,v])=>[k,v.length])),categories:phase==='after'?R.read(path.join(__dirname,'03_confirmation_attribution_r2.json')).categories:categories,
        attribution_file:phase==='after'?'03_confirmation_attribution_r2.json':'03_confirmation_attribution.json',
        green_delta:S.frames.reduce((n,f)=>n+f.clusters.filter(c=>c.track_confirmed).length,0)-P.frames.reduce((n,f)=>n+f.clusters.filter(c=>c.track_confirmed).length,0),
        purple_delta:S.frames.reduce((n,f)=>n+f.clusters.filter(c=>c.joint==='CONFIRMED_HUMAN').length,0)-P.frames.reduce((n,f)=>n+f.clusters.filter(c=>c.joint==='CONFIRMED_HUMAN').length,0)},
    topology:{summary:sumTopology,frames:topology},
    P:{digest:P.digest,behavior_digest:P.behavior_digest,frames:P.frames},S:{digest:S.digest,behavior_digest:S.behavior_digest,frames:S.frames},
    regression:{all_non_diagnostic_fields_identical_to_R38:true,point_audit_identical:phase==='after',confirmation_attribution_identical:phase==='after',conservation:phase==='after'?'PASS':'NOT_RUN'},rows:testRows};
write(phase==='before'?'06_shadow_before.json':'06_shadow_results.json',output);
console.log(JSON.stringify({counts,clean:safety.clean_absorbed,mechanisms:absorbed.reduce((a,p)=>(a[p.mechanism]=(a[p.mechanism]??0)+1,a),{}),categories,topology:sumTopology,rows:testRows},null,2));
process.exitCode=testRows.some(v=>v.result==='FAIL')?1:0;
