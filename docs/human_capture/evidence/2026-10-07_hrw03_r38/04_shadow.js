"use strict";
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert');
const R=require('../../../../pc_apps/human_replay/registration'),M=require('../../../../pc_apps/human_replay/registration_method');
const PL=require('../../../../pc_apps/human_replay/human_pipe_lib');
const root=R.ROOT,src='cap_20261002_223757',ref='cap_20261004_203349';
const run=process.argv.find(a=>a.startsWith('--run='))?.slice(6)??'r2';
assert(/^[a-z0-9_]+$/.test(run));
const dir=path.join(root,'captures/registration',src+'__to__'+ref);
const archive=R.read(path.join(__dirname,'../2026-10-06_hrw03_r8/03_results.json'));
const p=R.read(path.join(dir,'provenance.json'));
const sl=R.levelingBinding(root,src,p.source_leveling.job_id,p.source_leveling.transform_id);
const rl=R.levelingBinding(root,ref,p.reference_leveling.job_id,p.reference_leveling.transform_id);
const raw=R.loadFrames(root,src,sl).frames,base=raw.map(PL.denoise),reference=R.loadFrames(root,ref,rl,true).frames;
const refmap=PL.build_reference_map(reference),refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
const options={source:src,reference:ref,referenceMap:refmap},loaded=R.load(dir,options);
console.log(R.logLines(loaded).join('\n'));
const key=(a,i)=>a[i]+','+a[i+1]+','+a[i+2];
function branch(a,shadow=false,regions=false) {
    const registered=a.state==='VALID'||(shadow&&a.state==='DEGRADED');
    const clouds=registered?raw.map(buf=>R.applyRegistration({buf,frame:'leveled_session:'+src},a,{shadow}).buf):raw;
    const clean=clouds.map(PL.denoise),online=PL.build_static_map(clean),ctx={static_keys:online,tracker:new PL.Tracker()};
    const frames=[],fg=[];
    for(let i=0;i<clouds.length;i++) {
        let out,foreground;
        if(registered) {
            // OR uses two calls to the unchanged matcher. Map overwrite would lose a centroid
            // when online and reference contain the same key. denoise is idempotent here.
            foreground=PL.extract_foreground(PL.extract_foreground(clean[i],refkeys).fg_xyzi,online);
            out=PL.pipeline_frame(foreground.fg_xyzi,i,{static_keys:null,tracker:ctx.tracker});
            out.n_in=clouds[i].length/4;out.n_denoise=clean[i].length/4;
            out.n_foreground=foreground.n_fg;out.n_dropped=clean[i].length/4-foreground.n_fg;
        } else {out=PL.pipeline_frame(clouds[i],i,ctx);foreground=PL.extract_foreground(clean[i],online);}
        frames.push(R.clone(out));if(regions)fg.push(foreground.fg_xyzi);
    }
    return {frames,fg,digest:R.identity(frames),registered};
}
const P=branch(R.load(null,options),false,true),S=branch(loaded,true,true);
const rows=[],test=(id,fn)=>{try{const details=fn();rows.push({id,result:'PASS',details});}catch(e){rows.push({id,result:'FAIL',error:e.message});}};
const counts={WD01:{P:0,S:0,A:archive.groups.WD01.conditions.A.residual},WD02:{P:0,S:0,A:archive.groups.WD02.conditions.A.residual}};
const wd=(x,y)=>({WD01:Math.hypot(x-3.50,y+.76)<=.9,WD02:Math.hypot(x,y)>8||[[10.75,4.25],[10.25,-1.75],[10.50,5.50]].some(([a,b])=>Math.hypot(x-a,y-b)<=1.5)});
const r=loaded.registration,invR=M.m3.t(r.rotation_row_major),invT=M.m3.apply(invR,...r.translation_m.map(v=>-v));
for(let i=0;i<raw.length;i++) for(const name of ['P','S']) {
    const buf=(name==='P'?P:S).fg[i];
    for(let k=0;k<buf.length;k+=4) {
        let x=buf[k],y=buf[k+1];
        if(name==='S'&&S.registered){const u=M.m3.apply(invR,x,y,buf[k+2]);x=u[0]+invT[0];y=u[1]+invT[1];}
        const regions=wd(x,y);for(const [region,inRegion] of Object.entries(regions))if(inRegion)counts[region][name]++;
    }
}
const safety={near:{},clean:{},clean_absorbed:0};
for(const fi of [...archive.params.near_furniture_frames,...archive.params.clean_frames]) {
    const retained=new Set();for(let k=0;k<S.fg[fi].length;k+=4)retained.add(key(S.fg[fi],k));
    const near=archive.params.near_furniture_frames.includes(fi),center=near?[1.45,.85]:archive.person_centers[fi],bands={};
    // Same P-foreground cohorts as R3.6. Use original coordinates for windows/bands.
    for(let k=0;k<P.fg[fi].length;k+=4) {
        const buf=P.fg[fi],x=buf[k],y=buf[k+1],z=buf[k+2];if(Math.hypot(x-center[0],y-center[1])>.6)continue;
        const b=z>=1.2?'z>=1.2':z>=.8?'0.8-1.2':z>=.3?'0.3-0.8':'below-0.3',row=bands[b]??={n:0,absorbed:0};row.n++;
        const u=S.registered?M.m3.apply(r.rotation_row_major,x,y,z).map((v,j)=>Math.fround(v+r.translation_m[j])):[x,y,z];
        if(!retained.has(u.join(',')))row.absorbed++;
    }
    if(near)safety.near[fi]=bands;else {safety.clean[fi]=bands;safety.clean_absorbed+=Object.values(bands).reduce((n,v)=>n+v.absorbed,0);}
}
function compareTracks() {
    const missed=[],newGreen=[],newPurple=[];
    for(let i=0;i<P.frames.length;i++) {
        const pc=P.frames[i].clusters,sc=S.frames[i].clusters;
        const sxy=c=>{const u=M.m3.apply(invR,c.cx,c.cy,c.cz);return [u[0]+invT[0],u[1]+invT[1]];};
        const match=(a,b,flag)=>b.some(c=>flag(c)&&Math.hypot(a[0]-c.cx,a[1]-c.cy)<=PL.PIPE.track_gate_xy_m);
        for(const c of pc.filter(c=>c.track_confirmed)) if(!sc.some(v=>v.track_confirmed&&Math.hypot(sxy(v)[0]-c.cx,sxy(v)[1]-c.cy)<=PL.PIPE.track_gate_xy_m))missed.push({frame:i,P_track:c.track_id});
        for(const c of sc) {
            if(c.track_confirmed&&!match(sxy(c),pc,v=>v.track_confirmed))newGreen.push({frame:i,S_track:c.track_id});
            if(c.joint==='CONFIRMED_HUMAN'&&!match(sxy(c),pc,v=>v.joint==='CONFIRMED_HUMAN'))newPurple.push({frame:i,S_track:c.track_id});
        }
    }
    // Identity is not preserved across independent trackers; assess events spatially by track.
    const missedEvents=[];
    P.frames.forEach((frame,i)=>frame.events.forEach(ev=>{
        const pt=frame.tracks.find(t=>t.id===ev.track_id);
        const ok=S.frames[i].events.some(se=>{const st=S.frames[i].tracks.find(t=>t.id===se.track_id);if(!pt||!st)return false;const u=M.m3.apply(invR,st.x,st.y,st.z);return Math.hypot(u[0]+invT[0]-pt.x,u[1]+invT[1]-pt.y)<=PL.PIPE.track_gate_xy_m;});
        if(!ok)missedEvents.push({frame:i,event:ev});
    }));
    return {missed_tracks:missed,new_green:newGreen,new_purple:newPurple,missed_events:missedEvents};
}
const topology=S.frames.map((f,i)=>({frame:i,delta:f.cleanup_split_delta})).filter(f=>f.delta!==0),tracks=compareTracks();
test('T37-20',()=>{assert(loaded.diagnostics.direction_check.forward_p50<=loaded.diagnostics.direction_check.inverse_p50);return loaded.diagnostics.direction_check;});
test('T38-02',()=>{assert(counts.WD01.S<=.5*counts.WD01.A&&counts.WD01.S<=counts.WD01.P,JSON.stringify(counts.WD01));return counts.WD01;});
test('T38-03',()=>{assert(counts.WD02.S<=.5*counts.WD02.A&&counts.WD02.S<=counts.WD02.P,JSON.stringify(counts.WD02));return counts.WD02;});
test('T38-04',()=>{const h=safety.near[55]['z>=1.2'];assert(h.absorbed/h.n<=.01,JSON.stringify(h));return safety.near;});
test('T38-05',()=>{assert(safety.clean_absorbed<=5,'clean_absorbed='+safety.clean_absorbed);return safety.clean;});
test('T38-06',()=>{assert.equal(topology.length,0,'cleanup_split');assert.equal(tracks.new_green.length,0,'new_green');assert.equal(tracks.new_purple.length,0,'new_purple');assert.equal(tracks.missed_tracks.length,0,'P-confirmed track loss (proxy, includes known static false positives)');assert.equal(tracks.missed_events.length,0,'event loss');return tracks;});
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hr-r38-shadow-'));
function faultDir(name,mutate) {
    const dst=path.join(tmp,name);fs.cpSync(dir,dst,{recursive:true});mutate?.(dst);return dst;
}
function rewrite(dst,file,fn) {
    const v=R.read(path.join(dst,file));fn(v);fs.writeFileSync(path.join(dst,file),R.serialize(v));
    const mf=R.read(path.join(dst,'manifest.json'));mf.files[file]=R.shaFile(path.join(dst,file));
    if(file==='registration.json') {mf.artifact_id=mf.files[file];const pp=R.read(path.join(dst,'provenance.json'));pp.artifact_id=mf.artifact_id;fs.writeFileSync(path.join(dst,'provenance.json'),R.serialize(pp));mf.files['provenance.json']=R.shaFile(path.join(dst,'provenance.json'));}
    fs.writeFileSync(path.join(dst,'manifest.json'),R.serialize(mf));
}
const faultLogs=[],faultResults=[];
function safe(a) {faultLogs.push(...R.logLines(a));assert(a.state!=='VALID'&&a.state!=='DEGRADED');const out=branch(a);assert.equal(out.digest,P.digest);faultResults.push({state:a.state,reasons:a.reasons,digest:out.digest});}
try {
    test('T38-07',()=>{safe(R.load(dir,{...options,source:'cap_20261004_202456'}));const dst=faultDir('wrong-ref',d=>rewrite(d,'registration.json',v=>v.reference_session='cap_20261004_202456'));safe(R.load(dst,options));});
    test('T38-08',()=>{
        const dst=faultDir('tamper',d=>fs.appendFileSync(path.join(d,'registration.json'),' '));const a=R.load(dst,options);assert(a.reasons.includes('ARTIFACT_TAMPERED'));safe(a);
        // Copies work across Windows volumes; fault mutations never target original sessions.
        for(const sid of [src,ref]){const target=path.join(tmp,'captures/remote',sid);fs.mkdirSync(target,{recursive:true});for(const file of ['meta.json','points.bin'])fs.copyFileSync(path.join(root,'captures/remote',sid,file),path.join(target,file));}
        for(const lb of [p.source_leveling,p.reference_leveling]) {const td=path.join(tmp,'captures/leveled',lb.job_id);fs.mkdirSync(path.join(td,'tls'),{recursive:true});for(const file of ['report.json','manifest.json','tls/transform.json'])fs.copyFileSync(path.join(root,'captures/leveled',lb.job_id,file),path.join(td,file));}
        for(const f of R.CODE_FILES){fs.mkdirSync(path.dirname(path.join(tmp,f)),{recursive:true});fs.copyFileSync(path.join(root,f),path.join(tmp,f));}
        fs.appendFileSync(path.join(tmp,'captures/leveled',p.source_leveling.job_id,'tls/transform.json'),' ');
        const b=R.load(dir,{...options,root:tmp});assert(b.reasons.includes('LEVELING_SHA_MISMATCH'));safe(b);
    });
    test('T38-09',()=>safe(R.load(null,options)));
    test('T38-10',()=>{const cloud=R.applyRegistration({frame:'leveled_session:'+src,buf:new Float32Array([1,2,1,1])},loaded,{shadow:true});assert.throws(()=>R.applyRegistration(cloud,loaded,{shadow:true}),/ERR_DUPLICATE_REGISTRATION/);for(const frame of ['raw','leveled_session:'+ref])assert.throws(()=>R.applyRegistration({frame,buf:cloud.buf},loaded,{shadow:true}),/ERR_FRAME_MISMATCH/);});
    test('T38-11',()=>{const two=branch(loaded,true);assert.equal(two.digest,S.digest);return {run1:S.digest,run2:two.digest};});
    test('T38-12',()=>{assert(faultLogs.filter(l=>l.startsWith('[REG] state=')).every(l=>l.includes('reason=')));assert(R.logLines(loaded).some(l=>l.startsWith('[REG] conditioning=')));return {faults:faultResults};});
} finally {assert(path.resolve(tmp).startsWith(path.resolve(os.tmpdir())+path.sep+'hr-r38-shadow-'));fs.rmSync(tmp,{recursive:true,force:true});}
const output={state:loaded.state,reasons:loaded.reasons,artifact_id:loaded.artifact_id,counts,safety,tracks,topology,
    P:{digest:P.digest,frames:P.frames},S:{digest:S.digest,frames:S.frames},rows,
    limitations:['All baseline-confirmed tracks are proxies, may include static false positives; no true-human/event GT.','S uses DEGRADED only under explicit offline shadow; SAFE/production remains P.','Human cohorts and geometry windows use frozen R3.6 proxy definitions.']};
fs.writeFileSync(path.join(__dirname,`04_shadow_results_${run}.json`),R.serialize(output),{flag:'wx'});
fs.writeFileSync(path.join(__dirname,`04_fault_logs_${run}.txt`),faultLogs.join('\n')+'\n',{flag:'wx'});
console.log(JSON.stringify({state:loaded.state,counts,clean_absorbed:safety.clean_absorbed,rows},null,2));
process.exitCode=rows.some(r=>r.result==='FAIL')?1:0;
