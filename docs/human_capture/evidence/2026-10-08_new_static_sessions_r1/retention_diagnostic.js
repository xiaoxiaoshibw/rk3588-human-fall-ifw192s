/* Offline library experiment. No registration.publish/load, artifact installation or flags. */
"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const M=require(path.join(ROOT,'pc_apps/human_replay/registration_method.js'));
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const results=R.read(path.join(OUT,'registration_results.json'));
const levels=R.read(path.join(OUT,'leveling_results.json'));
const CENTERS={'114205':[2.03,-.32], '114254':[1.65,-.65], '114340':[2.10,-.08], '114422':[2.03,-.32]};
const RADIUS=.45; // Spatial proxy, not pointwise person GT; furniture may enter this cylinder.
const stat=a=>{const b=a.slice().sort((x,y)=>x-y);return {min:b[0],p50:b[Math.floor(b.length/2)],max:b[b.length-1]};};
const write=(n,v)=>fs.writeFileSync(path.join(OUT,n),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
function levelFrames(sid) {
    const level=levels.find(r=>r.sid===sid);
    assert.strictEqual(level.recommended,'tls');
    const tf=R.read(path.join(OUT,'leveling',level.job,'tls/transform.json'));
    assert.strictEqual(R.identity(R.sessionBinding(ROOT,sid)),R.identity({sid,...level.source}));
    return R.loadFrames(ROOT,sid,{tf},true).frames;
}
function transform(buf,A,t) {
    const out=new Float32Array(buf.length);
    for(let k=0;k<buf.length;k+=4) {
        const v=M.m3.apply(A,buf[k],buf[k+1],buf[k+2]);
        for(let j=0;j<3;j++) out[k+j]=v[j]+t[j];out[k+3]=buf[k+3];
    }
    return PL.denoise(out);
}
function inside(x,y,z,center) {return Math.hypot(x-center[0],y-center[1])<=RADIUS && z>=.1 && z<=2.3;}
function count(buf,center) {let n=0;for(let k=0;k<buf.length;k+=4) if(inside(buf[k],buf[k+1],buf[k+2],center)) n++;return n;}
function chain(buf,fg,i,tracker,center) {
    const iso=PL.cleanup_isolated_fg(fg);
    const cs=PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c=>PL.cluster_features(c).ok);
    const out=PL.pipeline_frame(fg,i,{static_keys:null,tracker});
    assert.strictEqual(cs.length,out.clusters.length);
    const byKey=new Map();cs.forEach((c,ci)=>c.keys.forEach(k=>byKey.set(k,ci)));
    const owners=new Map();
    for(let k=0;k<iso.xyzi.length;k+=4) {
        if(!inside(iso.xyzi[k],iso.xyzi[k+1],iso.xyzi[k+2],center)) continue;
        const ci=byKey.get(PL.key_vox(iso.xyzi[k],iso.xyzi[k+1]));
        if(ci!==undefined) owners.set(ci,(owners.get(ci)||0)+1);
    }
    const top=[...owners].sort((a,b)=>b[1]-a[1])[0];
    const c=top?out.clusters[top[0]]:null;
    return {raw:count(buf,center),fg:count(fg,center),cleanup:count(iso.xyzi,center),
        top:c?{roi_points:top[1],n:c.n,label:c.label,joint:c.joint,reasons:c.reasons,
            evidence:c.evidence,evidence_tag:c.evidence_tag,track_id:c.track_id,confirmed:!!c.track_confirmed}:null,
        n_foreground:out.n_foreground,cleanup_split_delta:out.cleanup_split_delta};
}
function summary(rows) {
    const labels={},joint={},reasons={};let confirmed=0,candidate=0;
    for(const row of rows) {
        const c=row.top;const label=c?.label??'NONE';labels[label]=(labels[label]??0)+1;
        const j=c?.joint??'NONE';joint[j]=(joint[j]??0)+1;
        if(c?.confirmed) confirmed++;
        if(c && c.label==='HUMAN_CANDIDATE') candidate++;
        for(const reason of c?.reasons??[]) reasons[reason]=(reasons[reason]??0)+1;
    }
    const raw=stat(rows.map(r=>r.raw)),fg=stat(rows.map(r=>r.fg)),cleanup=stat(rows.map(r=>r.cleanup));
    return {raw,fg,cleanup,retention_pct:raw.p50?100*fg.p50/raw.p50:null,
        labels,joint,reasons,confirmed_frames:confirmed,candidate_frames:candidate,rows};
}
const refsid='cap_20261008_114819', ref=levelFrames(refsid);
const refmap=PL.build_reference_map(ref),refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
const output=[];
for(const item of results.filter(r=>r.gate)) {
    const cur=levelFrames(item.sid).map(buf=>transform(buf,item.transform.rotation_row_major,item.transform.translation_m));
    const online=PL.build_static_map(cur),center=CENTERS[item.sid.slice(-6)];
    const modes=item.gate==='PASS'?['P','REF','UNION','V2']:['P','REF'];
    const data={sid:item.sid,name:item.name,gate:item.gate,center,radius:RADIUS,
        roi_semantics:'spatial proxy only, not pointwise GT; all arms share registered coordinates',
        v2_status:item.gate==='PASS'?'offline_library_only':'BLOCKED_NON_PASS_GATE',arms:{}};
    for(const mode of modes) {
        const tracker=new PL.Tracker(),rows=[];
        for(let i=0;i<cur.length;i++) {
            const buf=cur[i];let fg;
            if(mode==='P') fg=PL.extract_foreground(buf,online).fg_xyzi;
            else if(mode==='REF') fg=PL.extract_foreground(buf,refkeys).fg_xyzi;
            else if(mode==='UNION') fg=PL.extract_foreground(PL.extract_foreground(buf,refkeys).fg_xyzi,online).fg_xyzi;
            else fg=PL.extract_foreground_fused(buf,refkeys,online).fg_xyzi;
            rows.push(chain(buf,fg,i,tracker,center));
        }
        data.arms[mode]=summary(rows);
        console.log(item.sid,mode,'ROI%',data.arms[mode].retention_pct,'labels',data.arms[mode].labels,'confirmed',data.arms[mode].confirmed_frames);
    }
    write(item.sid+'_retention.json',data);output.push(data);
}
const emptyOnline=PL.build_static_map(ref),emptyTracker=new PL.Tracker(),emptyRows=[];
for(let i=0;i<ref.length;i++) {
    const o=PL.pipeline_frame(ref[i],i,{static_keys:emptyOnline,tracker:emptyTracker,fusion:{refkeys}});
    emptyRows.push({i,n_foreground:o.n_foreground,clusters:o.clusters.length,
        candidates:o.clusters.filter(c=>c.label==='HUMAN_CANDIDATE').length,
        confirmed:o.tracks.filter(t=>t.confirmed).length});
}
write('empty_v2_library.json',{sid:refsid,scope:'identity reference offline library only',rows:emptyRows,
    candidate_frames:emptyRows.filter(r=>r.candidates>0).length,confirmed_frames:emptyRows.filter(r=>r.confirmed>0).length});
write('retention_results.json',output);
