/* Offline registration jobs only. R3.8; no browser/server/production caller. */
"use strict";
const fs = require('fs'), path = require('path'), crypto = require('crypto');
const PL = require('./human_pipe_lib.js'), RL = require('./human_replay_lib.js');
const M = require('./registration_method.js');
const ROOT = path.resolve(__dirname, '../..');
const FILES = ['registration.json','diagnostics.json','provenance.json'];
const CODE_FILES = ['pc_apps/human_replay/human_pipe_lib.js','pc_apps/human_replay/human_replay_lib.js',
    'pc_apps/human_replay/registration_method.js','pc_apps/human_replay/registration.js'];
const PROFILE = {
    profile_id:'reg_gate_v1',
    bands:{
        fit_p50:['max',0.020,0.030,'RESIDUAL_HIGH'],fit_p90:['max',0.080,0.100,'RESIDUAL_HIGH'],
        holdout_p50:['max',0.020,0.030,'HOLDOUT_MISMATCH'],holdout_fit_ratio_p50:['max',1.50,2.00,'HOLDOUT_MISMATCH'],
        n_static_source:['min',5000,2000,'WEAK_SUPPORT'],n_static_target:['min',5000,2000,'WEAK_SUPPORT'],
        n_correspondence:['min',500,200,'SPARSE_CORRESPONDENCE'],inlier_ratio:['min',0.50,0.30,'SPARSE_CORRESPONDENCE'],
        coverage_xy:['min',0.50,0.30,'LOW_COVERAGE'],max_sector_share:['max',0.60,0.75,'WALL_CONCENTRATION'],
        condition_number:['max',1e4,1e5,'ILL_CONDITIONED'],eig_ratio:['min',1e-4,1e-5,'ILL_CONDITIONED']},
    sanity:{roll_deg:6,pitch_deg:3,yaw_deg:5,theta_deg:7,translation:0.20,t_z:0.15},
    self_rot:0.25,self_t:0.010,compete_rot:0.02,compete_t:0.01,advantage:0.95,
    provisional:['n_correspondence','inlier_ratio','coverage_xy','max_sector_share','condition_number','eig_ratio']
};
function sha(bytes) { return crypto.createHash('sha256').update(bytes).digest('hex'); }
function shaFile(file) {
    const hash=crypto.createHash('sha256'), fd=fs.openSync(file,'r'), buf=Buffer.alloc(1<<20);
    try { let n; while((n=fs.readSync(fd,buf,0,buf.length,null))) hash.update(buf.subarray(0,n)); }
    finally { fs.closeSync(fd); }
    return hash.digest('hex');
}
function canonical(v) {
    if(Array.isArray(v)) return v.map(canonical);
    if(v && typeof v==='object') return Object.fromEntries(Object.keys(v).sort().map(k=>[k,canonical(v[k])]));
    return v;
}
function identity(v) { return sha(JSON.stringify(canonical(v))); }
function read(file) { return JSON.parse(fs.readFileSync(file,'utf8')); }
function clone(v) { return JSON.parse(JSON.stringify(v)); }
function freeze(v) { if(v && typeof v==='object') { Object.values(v).forEach(freeze); Object.freeze(v); } return v; }
freeze(PROFILE);
function matrixOK(R,t) {
    if(!Array.isArray(R)||R.length!==9||!Array.isArray(t)||t.length!==3||![...R,...t].every(Number.isFinite)) return false;
    const Q=M.m3.mul(R,M.m3.t(R));
    const det=R[0]*(R[4]*R[8]-R[5]*R[7])-R[1]*(R[3]*R[8]-R[5]*R[6])+R[2]*(R[3]*R[7]-R[4]*R[6]);
    return Math.max(...Q.map((v,i)=>Math.abs(v-M.I3[i])))<=1e-6 && Math.abs(det-1)<=1e-6;
}
function rotationDelta(A,B) {
    const R=M.m3.mul(A,M.m3.t(B));
    return Math.acos(Math.max(-1,Math.min(1,(R[0]+R[4]+R[8]-1)/2)))*180/Math.PI;
}
function basinBand(b,p=PROFILE) {
    if(!b||!Array.isArray(b.solutions)||b.solutions.length<2||!b.solutions.every(s=>
        Number.isFinite(s.holdout_p50)&&s.holdout_p50>=0&&Number.isFinite(s.self_rot)&&Number.isFinite(s.self_t)&&
        matrixOK(s.R,s.t))) return {band:'reject',reason:'UNFROZEN_PROFILE'};
    const [a,c]=b.solutions;
    const competing=rotationDelta(a.R,c.R)>p.compete_rot||Math.hypot(...a.t.map((v,i)=>v-c.t[i]))>p.compete_t;
    if(!competing) return {band:'pass',resolution:{resolved:true,by:'single_basin'}};
    const stable=s=>s.self_rot<=p.self_rot&&s.self_t<=p.self_t;
    const ordered=b.solutions.slice().sort((x,y)=>Number(stable(y))-Number(stable(x))||x.holdout_p50-y.holdout_p50);
    const [w,l]=ordered;
    if(w.holdout_p50===l.holdout_p50 && stable(w)===stable(l)) return {band:'reject',reason:'WEAK_OBSERVABILITY',resolution:{resolved:false,by:'indistinguishable'}};
    const resolved=stable(w)&&w.holdout_p50<=p.advantage*l.holdout_p50&&w.holdout_p50<=p.bands.holdout_p50[1];
    return {band:resolved?'pass':'warn',reason:resolved?null:'WEAK_OBSERVABILITY',
        resolution:{resolved,by:'split_half+holdout',winner:w.init,winner_holdout:w.holdout_p50,loser_holdout:l.holdout_p50,ratio:l.holdout_p50?w.holdout_p50/l.holdout_p50:null}};
}
function metricValues(d) {
    return {...d.support,...d.geometry,fit_p50:d.residual?.fit?.p50,fit_p90:d.residual?.fit?.p90,
        holdout_p50:d.residual?.holdout?.p50,holdout_fit_ratio_p50:d.residual?.holdout_fit_ratio_p50};
}
function gate(d,p=PROFILE) {
    if(!p||typeof p!=='object') p={};
    const checks=[], vals=metricValues(d);
    const add=(id,metric,band,reason)=>checks.push({id,metric:metric??null,band,verdict:band==='pass',reason:band==='pass'?null:reason});
    if(identity(p)!==identity(PROFILE)) add('profile',null,'reject','UNFROZEN_PROFILE');
    for(const [id,[dir,pass,warn,reason]] of Object.entries(PROFILE.bands)) {
        const v=vals[id], bounds=p.bands?.[id];
        const band=!Number.isFinite(v)||v<0||!bounds?'reject':dir==='max'?(v<=bounds[1]?'pass':v<=bounds[2]?'warn':'reject'):(v>=bounds[1]?'pass':v>=bounds[2]?'warn':'reject');
        add(id,v,band,!Number.isFinite(v)||!bounds?'UNFROZEN_PROFILE':reason);
    }
    for(const [id,limit] of Object.entries(PROFILE.sanity)) {
        const v=d.sanity?.[id]?.observed;
        add(id,v,!Number.isFinite(v)||!Number.isFinite(p.sanity?.[id])?'reject':Math.abs(v)<=limit?'pass':'reject',
            !Number.isFinite(v)||!Number.isFinite(p.sanity?.[id])?'UNFROZEN_PROFILE':'SANITY_BOUND');
    }
    const b=basinBand(d.basins,identity(p)===identity(PROFILE)?p:PROFILE); add('basins',null,b.band,b.reason);
    const dc=d.direction_check;
    add('direction',dc?.forward_p50,(!Number.isFinite(dc?.forward_p50)||!Number.isFinite(dc?.inverse_p50))?'reject':dc.forward_p50<=dc.inverse_p50?'pass':'reject',dc?'DIRECTION':'UNFROZEN_PROFILE');
    if(checks.filter(c=>c.id.startsWith('fit_')).every(c=>c.band==='pass')&&checks.some(c=>c.id.startsWith('holdout')&&c.band!=='pass'))
        add('fit_holdout_guard',null,'reject','HOLDOUT_MISMATCH');
    const status=checks.some(c=>c.band==='reject')?'REJECT':checks.some(c=>c.band==='warn')?'WARN':'PASS';
    return {profile_id:p.profile_id,thresholds:clone(p),checks,status,reasons:[...new Set(checks.filter(c=>c.band!=='pass').map(c=>c.reason))],basin_resolution:b.resolution??null};
}
function sessionBinding(root,sid) {
    if(typeof sid!=='string'||!/^cap_[0-9]{8}_[0-9]{6}$/.test(sid)) throw Error('SESSION_SHA_MISMATCH');
    const dir=path.join(root,'captures/remote',sid);
    return {sid,meta_sha256:shaFile(path.join(dir,'meta.json')),bin_sha256:shaFile(path.join(dir,'points.bin'))};
}
function levelingBinding(root,sid,job,transform_id) {
    if(typeof job!=='string'||!/^[a-f0-9]{32}$/.test(job)) throw Error('LEVELING_JOB_MISSING');
    const dir=path.join(root,'captures/leveled',job);
    if(!fs.existsSync(dir)) throw Error('LEVELING_JOB_MISSING');
    const tf=read(path.join(dir,'tls/transform.json')),report=read(path.join(dir,'report.json')),manifest=read(path.join(dir,'manifest.json'));
    const b={job_id:job,method:'tls',transform_id:tf.transform_id,transform_sha256:shaFile(path.join(dir,'tls/transform.json')),
        report_sha256:shaFile(path.join(dir,'report.json')),manifest_sha256:shaFile(path.join(dir,'manifest.json'))};
    if(report.sid!==sid||report.recommended!=='tls'||(transform_id&&tf.transform_id!==transform_id)||tf.estimator!=='tls'||
        manifest.job_id!==job||manifest.artifacts?.tls?.['transform.json']!==b.transform_sha256||manifest.report_sha256!==b.report_sha256||
        identity(tf.source)!==identity(manifest.source)||!matrixOK(tf.R?.flat(),tf.t)) throw Error('LEVELING_SHA_MISMATCH');
    return {binding:b,tf};
}
function loadFrames(root,sid,level,denoised=false) {
    const dir=path.join(root,'captures/remote',sid), meta=read(path.join(dir,'meta.json'));
    const raw=fs.readFileSync(path.join(dir,'points.bin')), f32=new Float32Array(raw.buffer,raw.byteOffset,raw.byteLength/4);
    return {meta,frames:RL.frame_slice(meta).map(f=>{
        const buf=RL.strided_f32_copy(f32,f.start_pts,f.count,RL.STRIDE_F32),R=level.tf.R.flat(),t=level.tf.t;
        transformBuffer(buf,R,t);
        return denoised?PL.denoise(buf):buf;
    })};
}
function transformBuffer(buf,R,t) {
    for(let i=0;i<buf.length;i+=4) {
        const q=M.m3.apply(R,buf[i],buf[i+1],buf[i+2]);
        for(let j=0;j<3;j++) buf[i+j]=q[j]+t[j];
    }
}
function refBinding(map) {
    const p={bg_ref_hit_min_pts:PL.PIPE.bg_ref_hit_min_pts,bg_ref_occ_min:PL.PIPE.bg_ref_occ_min,
        bg_voxel_xy:PL.PIPE.bg_voxel_xy,bg_voxel_z:PL.PIPE.bg_voxel_z,ground_keep_below_m:PL.PIPE.ground_keep_below_m,z_max_m:PL.PIPE.z_max_m};
    const rows=[...map.voxels].filter(([,v])=>v.occ>=p.bg_ref_occ_min).sort((a,b)=>a[0]-b[0]);
    const lines=[`refmap_digest_v1|voxel_xy=${p.bg_voxel_xy}|voxel_z=${p.bg_voxel_z}|hit_min=${p.bg_ref_hit_min_pts}|occ_min=${p.bg_ref_occ_min}|nframes=${map.nframes}`,
        ...rows.map(([k,v])=>[k,...['x','y','z','occ'].map(f=>v[f].toFixed(5))].join('|'))];
    const builderFiles={'human_pipe_lib.js':shaFile(path.join(__dirname,'human_pipe_lib.js'))};
    return {builder:'build_reference_map',code_id:identity(builderFiles),params:p,nframes:map.nframes,ref_voxels_total:map.voxels.size,
        universe_count:rows.length,digest:{algo:'refmap_digest_v1',value:sha(lines.join('\n'))}};
}
function codeBinding(root=ROOT) {
    const files=Object.fromEntries(CODE_FILES.map(f=>[f,shaFile(path.join(root,f))]));
    return {files,code_id:identity(files)};
}
function serialize(v) { return JSON.stringify(v,null,2)+'\n'; }
function publish(dir,r,d,p) {
    if(!matrixOK(r.rotation_row_major,r.translation_m)) throw Error('INVALID_MATRIX');
    const g=gate(d);
    if(g.reasons.includes('DIRECTION')) throw Error('DIRECTION');
    if(identity(g)!==identity(d.gate)||identity(r.quality)!==identity({status:g.status,gate_profile:g.profile_id,reasons:g.reasons})) throw Error('INCONSISTENT_GATE');
    fs.mkdirSync(dir); // Exclusive, never delete failed/old jobs. Manifest is the publication marker.
    const rb=serialize(r), artifact_id=sha(rb), prov={...p,artifact_id};
    const values=[rb,serialize(d),serialize(prov)], hashes={};
    FILES.forEach((f,i)=>{fs.writeFileSync(path.join(dir,f),values[i],{flag:'wx'});hashes[f]=sha(values[i]);});
    fs.writeFileSync(path.join(dir,'manifest.json'),serialize({kind:'registration_manifest',schema:1,artifact_id,files:hashes}),{flag:'wx'});
    return artifact_id;
}
function load(dir,options={}) {
    const errors=[], trace=['UNAVAILABLE'];
    const fail=(state,reason)=>errors.push({state,reason});
    const finish=(r,d,p,id)=>{
        const state=errors[0]?.state??(d?.gate?.status==='PASS'?'VALID':d?.gate?.status==='WARN'?'DEGRADED':'REJECTED');
        const reasons=errors.length?errors.map(e=>e.reason):d?.gate?.reasons??[];
        trace.push(state);
        return freeze({state,reasons,errors,trace,artifact_id:id??null,registration:r??null,diagnostics:d??null,provenance:p??null});
    };
    if(!dir||!fs.existsSync(dir)) {fail('UNAVAILABLE','NO_ARTIFACT');return finish();}
    trace.push('VALIDATING');
    let mf; try {mf=read(path.join(dir,'manifest.json'));} catch {fail('REJECTED','SCHEMA');return finish();}
    if(mf.kind!=='registration_manifest'||mf.schema!==1||!mf.files||FILES.some(f=>!/^[a-f0-9]{64}$/.test(mf.files[f]))) {fail('REJECTED','SCHEMA');return finish();}
    const bytes={};
    for(const f of FILES) { try {bytes[f]=fs.readFileSync(path.join(dir,f));if(sha(bytes[f])!==mf.files[f]) fail('REJECTED','ARTIFACT_TAMPERED');}
        catch {fail('REJECTED','ARTIFACT_TAMPERED');} }
    let r,d,p;try {[r,d,p]=FILES.map(f=>JSON.parse(bytes[f]));} catch {fail('REJECTED','SCHEMA');return finish();}
    const id=sha(bytes['registration.json']);
    if(id!==mf.artifact_id||id!==p?.artifact_id) fail('REJECTED','ARTIFACT_TAMPERED');
    if(!r||!d||!p) {fail('REJECTED','SCHEMA');return finish();}
    if(r.kind!=='offline_cross_session_registration'||r.schema!==1||r.units!=='m'||r.from_frame!=='leveled_session'||r.to_frame!=='reference_frame'||
        r.scope!=='offline_display_only'||r.physical_verified!==false||r.extrinsics_verified!==false||r.runtime_eligible!==false||r.method!=='fixed_icp_r3_2'||r.method_version!==1||
        d.kind!=='registration_diagnostics'||d.schema!==1||d.protocol?.id!=='r3.6_fine_static_v1'||p.kind!=='registration_provenance'||p.schema!==1) fail('REJECTED','SCHEMA');
    if(r.direction!=='current_to_reference') fail('REJECTED','DIRECTION');
    if(!matrixOK(r.rotation_row_major,r.translation_m)) fail('REJECTED','INVALID_MATRIX');
    const root=options.root??ROOT;
    for(const side of ['source','reference']) {
        const sid=r[side+'_session'], sb=p[side+'_session'], lb=p[side+'_leveling'];
        try {
            if(options[side]&&sid!==options[side]) throw Error('SESSION_SHA_MISMATCH');
            const actual=sessionBinding(root,sid);
            if(identity(actual)!==identity(sb)||d.pair?.[side]!==sid) throw Error('SESSION_SHA_MISMATCH');
        } catch {fail('STALE','SESSION_SHA_MISMATCH');}
        try {
            const lv=levelingBinding(root,sid,lb?.job_id,lb?.transform_id);
            if(identity(lv.binding)!==identity(lb)||identity(lv.tf.source)!==identity({meta_sha256:sb?.meta_sha256,bin_sha256:sb?.bin_sha256})) throw Error('LEVELING_SHA_MISMATCH');
        } catch(e) {fail('STALE',e.message==='LEVELING_JOB_MISSING'?e.message:'LEVELING_SHA_MISMATCH');}
    }
    try {
        const lb=p.reference_leveling;
        const ref=options.referenceMap??PL.build_reference_map(loadFrames(root,r.reference_session,levelingBinding(root,r.reference_session,lb.job_id,lb.transform_id),true).frames);
        if(identity(refBinding(ref))!==identity(p.background_reference)) fail('STALE','REFMAP_DRIFT');
    } catch {fail('STALE','REFMAP_DRIFT');}
    try { if(identity(codeBinding(root))!==identity(p.code)||r.code_id!==p.code.code_id) fail('STALE','METHOD_STALE'); }
    catch {fail('STALE','METHOD_STALE');}
    if(d.gate?.profile_id!=='reg_gate_v1'||r.quality?.gate_profile!=='reg_gate_v1') fail('REJECTED','UNKNOWN_PROFILE');
    else {
        const g=gate(d,d.gate.thresholds);
        if(identity(g)!==identity(d.gate)||identity(r.quality)!==identity({status:g.status,gate_profile:g.profile_id,reasons:g.reasons})) fail('REJECTED','INCONSISTENT_GATE');
        else if(g.status==='REJECT') for(const reason of g.reasons) fail('REJECTED',reason);
    }
    return finish(r,d,p,id);
}
function applyRegistration(cloud,loaded,{shadow=false}={}) {
    if(cloud.frame?.startsWith('reference_frame:')) throw Error('ERR_DUPLICATE_REGISTRATION');
    const r=loaded.registration;
    if(!r||cloud.frame!=='leveled_session:'+r.source_session) throw Error('ERR_FRAME_MISMATCH');
    if(loaded.state!=='VALID'&&!(shadow&&loaded.state==='DEGRADED')) throw Error(loaded.state==='STALE'?'ERR_REGISTRATION_STALE':'ERR_REGISTRATION_REJECTED');
    if(!matrixOK(r.rotation_row_major,r.translation_m)||!(cloud.buf instanceof Float32Array)||cloud.buf.length%4||
        !cloud.buf.every(Number.isFinite)) throw Error('ERR_REGISTRATION_REJECTED');
    const buf=cloud.buf.slice();transformBuffer(buf,r.rotation_row_major,r.translation_m);
    if(!buf.every(Number.isFinite)) throw Error('ERR_REGISTRATION_REJECTED');
    cloud.buf=buf;cloud.frame='reference_frame:'+r.reference_session;return cloud;
}
function logLines(a) {
    const r=a.registration,d=a.diagnostics;
    const lines=[`[REG] state=${a.state}${a.reasons.length?' reason='+a.reasons.join(','):''}`];
    if(r) lines.push(`[REG] source=${r.source_session}`,`[REG] reference=${r.reference_session}`,`[REG] artifact_sha=${a.artifact_id}`,
        `[REG] method=${r.method} gate=${r.quality.gate_profile}`,
        `[REG] holdout_rmse=${d?.residual?.holdout?.p50??null}`,`[REG] support=${d?.support?.n_correspondence??null}/${d?.support?.inlier_ratio??null}`,
        `[REG] conditioning=${d?.geometry?.condition_number??null}`,
        `[REG] transform rpy=${JSON.stringify(r.euler_deg_zyx)} translation=${JSON.stringify(r.translation_m)}`,
        `[REG] frame_after=${a.state==='VALID'?'reference_frame:'+r.reference_session:'leveled_session:'+r.source_session}`);
    if(a.state==='DEGRADED') lines.push(`[REG] gate=WARN reasons=${JSON.stringify(a.reasons)}`);
    return lines;
}
function residualStats(values) {
    const v=values.slice().sort((a,b)=>a-b),q=p=>v.length?v[Math.ceil(p*v.length)-1]:null;
    return {n:v.length,p50:q(.5),p90:q(.9)};
}
function correspondences(src,idx,R,t,radius) {
    const pairs=[];
    for(const s of src) {
        const u=M.m3.apply(R,s.x,s.y,s.z),p=u.map((v,i)=>v+t[i]),hit=M.nn_query(idx,...p,radius);
        if(!hit||hit.rec.nx===null) continue;
        const q=hit.rec,n=[q.nx,q.ny,q.nz],r=n.reduce((v,nv,i)=>v+nv*(p[i]-[q.x,q.y,q.z][i]),0);
        pairs.push({s,p,q,n,r});
    }
    return pairs;
}
function measure(cur,ref,R,t,tlsR) {
    const online=PL.build_static_map(cur),map=PL.build_reference_map(ref);
    const cf=M.fineStatic(cur,new Set([...online].filter(([,v])=>v.tier==='strong').map(([k])=>k)),.06);
    const rf=M.fineStatic(ref,new Set([...map.voxels].filter(([,v])=>v.occ>=.9).map(([k])=>k)),.06);
    M.estimateNormals(rf,.10);const idx=M.build_vox_index(rf,.10);
    const all=correspondences(cf,idx,R,t,.30),sc=M.PP_SCHED.at(-1);
    const pp=correspondences(cf,idx,R,t,sc.inlier).sort((a,b)=>Math.abs(a.r)-Math.abs(b.r));
    const keep=pp.slice(0,Math.max(30,Math.floor(pp.length*sc.keep)));
    const H=Array.from({length:6},()=>Array(6).fill(0)),sectors=Array(8).fill(0),grid=s=>Math.floor(s.x/.15)+','+Math.floor(s.y/.15);
    for(const {p,n,s} of keep) {
        const j=[p[1]*n[2]-p[2]*n[1],p[2]*n[0]-p[0]*n[2],p[0]*n[1]-p[1]*n[0],...n];
        for(let a=0;a<6;a++) for(let b=0;b<6;b++) H[a][b]+=j[a]*j[b];
        sectors[Math.min(7,Math.floor((Math.atan2(s.y,s.x)+Math.PI)/(Math.PI/4)))]++;
    }
    const eig=M.jacobi_eig(H,6).vals.sort((a,b)=>b-a),eu=M.eulerFromR(R);
    const fit=residualStats(all.map(p=>Math.abs(p.r)));
    const inverseR=M.m3.t(R),inverseT=M.m3.apply(inverseR,...t.map(v=>-v));
    const inv=all.map(({s,q,n})=>{const u=M.m3.apply(inverseR,s.x,s.y,s.z);return Math.abs(n.reduce((v,nv,i)=>v+nv*(u[i]+inverseT[i]-[q.x,q.y,q.z][i]),0));});
    const halves=[cf.filter((_,i)=>i%2===0),cf.filter((_,i)=>i%2===1)];
    const solutions=[];
    for(const [init,R0,t0] of [['identity',M.I3,[0,0,0]],['tls',tlsR,[0,0,0]]]) {
        const full=M.ppICP(cf,idx,R0,t0,M.PP_SCHED,init);
        const hs=halves.map((h,i)=>M.ppICP(h,idx,R0,t0,M.PP_SCHED,init+'_half'+i));
        const holdout=hs.flatMap((v,i)=>M.normalResiduals(halves[1-i],idx,v.R,v.t,.30));
        solutions.push({init,R:full.R,t:full.t,iters:full.iters,half_split:hs,
            self_rot:rotationDelta(hs[0].R,hs[1].R),self_t:Math.hypot(...hs[0].t.map((v,i)=>v-hs[1].t[i])),holdout_p50:residualStats(holdout).p50});
    }
    // R3.6 half-split protocol, initialized at B. These diagnostic fits never replace B.
    const bhalf=halves.map((h,i)=>M.ppICP(h,idx,R,t,M.PP_SCHED,'B_half'+i));
    const hold=residualStats(bhalf.flatMap((v,i)=>M.normalResiduals(halves[1-i],idx,v.R,v.t,.30)));
    const observed={roll_deg:eu.roll,pitch_deg:eu.pitch,yaw_deg:eu.yaw,theta_deg:rotationDelta(R,M.I3),translation:Math.hypot(...t),t_z:Math.abs(t[2])};
    const d={kind:'registration_diagnostics',schema:1,protocol:{id:'r3.6_fine_static_v1',fit_set:'curFinestrong(0.06m rebin) -> refFine(occ>=0.9, 0.06m rebin)',normals:'refFine PCA 0.10m, min-eigvec',residual:'point-to-plane |n·(Rs+t-q)|',holdout:'even/odd half-split refit (fit-half -> eval-other)'},
        support:{n_static_source:cf.length,n_static_target:rf.length,n_correspondence:keep.length,inlier_ratio:keep.length/cf.length,
            coverage_xy:new Set(keep.map(v=>grid(v.s))).size/new Set(cf.map(grid)).size,azimuth_sectors:sectors,max_sector_share:keep.length?Math.max(...sectors)/keep.length:null},
        geometry:{jtj_eigvals:eig,eig_ratio:eig[5]/eig[0],condition_number:eig[5]>0?eig[0]/eig[5]:null},
        residual:{fit,holdout:hold,holdout_fit_ratio_p50:hold.p50/fit.p50,half_split:bhalf},
        basins:{solutions,cross_method_notes:'identity/tls ppICP diagnostic family only; fixed B is never selected/replaced by C; see R3.6'},
        sanity:Object.fromEntries(Object.entries(observed).map(([k,v])=>[k,{observed:v,limit:PROFILE.sanity[k],band:Math.abs(v)<=PROFILE.sanity[k]?'pass':'reject'}])),
        direction_check:{forward_p50:fit.p50,inverse_p50:residualStats(inv).p50,n:all.length,protocol:'same forward-correspondence set; inverse R and -R^T t'}
    };
    d.gate=gate(d);d.basins.resolution=d.gate.basin_resolution;return d;
}
function writeJob({root=ROOT,source,reference,sourceJob,referenceJob,outdir}) {
    if(fs.existsSync(outdir)) throw Error('ARTIFACT_EXISTS');
    const sb=sessionBinding(root,source),rb=sessionBinding(root,reference),code=codeBinding(root);
    const sl=levelingBinding(root,source,sourceJob),rl=levelingBinding(root,reference,referenceJob);
    for(const [s,l] of [[sb,sl],[rb,rl]]) if(identity(l.tf.source)!==identity({meta_sha256:s.meta_sha256,bin_sha256:s.bin_sha256})) throw Error('SESSION_SHA_MISMATCH');
    const cur=loadFrames(root,source,sl,true).frames,ref=loadFrames(root,reference,rl,true).frames;
    const online=PL.build_static_map(cur),refmap=PL.build_reference_map(ref),icp=M.fixedICP(online,refmap);
    const R=M.m3.t(icp.R),t=M.m3.apply(R,...icp.t.map(v=>-v)),tlsR=M.m3.mul(rl.tf.R.flat(),M.m3.t(sl.tf.R.flat()));
    const d=measure(cur,ref,R,t,tlsR),created_utc=new Date().toISOString();
    d.pair={source,reference};d.created_utc=created_utc;
    const r={kind:'offline_cross_session_registration',schema:1,units:'m',direction:'current_to_reference',from_frame:'leveled_session',to_frame:'reference_frame',source_session:source,reference_session:reference,
        rotation_row_major:R,translation_m:t,euler_deg_zyx:M.eulerFromR(R),method:'fixed_icp_r3_2',method_version:1,code_id:code.code_id,
        quality:{status:d.gate.status,gate_profile:d.gate.profile_id,reasons:d.gate.reasons},scope:'offline_display_only',physical_verified:false,extrinsics_verified:false,runtime_eligible:false,created_utc};
    const p={kind:'registration_provenance',schema:1,source_session:sb,reference_session:rb,source_leveling:sl.binding,reference_leveling:rl.binding,
        background_reference:refBinding(refmap),code,verified:[{check:'session_sha',pass:true},{check:'leveling_sha',pass:true}],writer:{tool:'registration.js',version:'1',runtime:process.version},created_utc};
    if(identity(sessionBinding(root,source))!==identity(sb)||identity(sessionBinding(root,reference))!==identity(rb)||identity(codeBinding(root))!==identity(code)||
        identity(levelingBinding(root,source,sourceJob).binding)!==identity(sl.binding)||identity(levelingBinding(root,reference,referenceJob).binding)!==identity(rl.binding)) throw Error('INPUT_CHANGED');
    const id=publish(outdir,r,d,p);return {artifact_id:id,quality:r.quality,outdir};
}
module.exports={PROFILE,FILES,CODE_FILES,ROOT,sha,shaFile,identity,read,clone,serialize,matrixOK,rotationDelta,basinBand,gate,sessionBinding,levelingBinding,loadFrames,refBinding,codeBinding,publish,load,applyRegistration,logLines,residualStats,correspondences,measure,writeJob};
if(require.main===module) {
    const opts=Object.fromEntries(process.argv.slice(2).map(a=>{const i=a.indexOf('=');return [a.slice(2,i),a.slice(i+1)];}));
    try { console.log(JSON.stringify(writeJob({source:opts.source,reference:opts.reference,sourceJob:opts['source-job'],referenceJob:opts['reference-job'],outdir:opts.outdir}),null,2)); }
    catch(e) {console.error(e.stack);process.exitCode=1;}
}
