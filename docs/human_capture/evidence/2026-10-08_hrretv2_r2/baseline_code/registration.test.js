"use strict";
const assert=require('assert'),fs=require('fs'),os=require('os'),path=require('path'),cp=require('child_process');
const R=require('./registration.js'),M=require('./registration_method.js');
function fixtures() {
    const root=fs.mkdtempSync(path.join(os.tmpdir(),'hr-r38-'));
    for(const f of R.CODE_FILES) {fs.mkdirSync(path.dirname(path.join(root,f)),{recursive:true});fs.copyFileSync(path.join(R.ROOT,f),path.join(root,f));}
    const sids=['cap_20261002_223757','cap_20261004_203349'],jobs=['a'.repeat(32),'b'.repeat(32)];
    const dump=(f,v)=>fs.writeFileSync(f,R.serialize(v));
    for(let i=0;i<2;i++) {
        const dir=path.join(root,'captures/remote',sids[i]);fs.mkdirSync(dir,{recursive:true});
        dump(path.join(dir,'meta.json'),{sid:sids[i]});fs.writeFileSync(path.join(dir,'points.bin'),Buffer.alloc(16));
        const sb=R.sessionBinding(root,sids[i]),source={meta_sha256:sb.meta_sha256,bin_sha256:sb.bin_sha256};
        const jd=path.join(root,'captures/leveled',jobs[i]);fs.mkdirSync(path.join(jd,'tls'),{recursive:true});
        const tf={R:[[1,0,0],[0,1,0],[0,0,1]],t:[0,0,0],estimator:'tls',source,transform_id:'c'.repeat(64)};
        dump(path.join(jd,'tls/transform.json'),tf);dump(path.join(jd,'report.json'),{sid:sids[i],recommended:'tls'});
        dump(path.join(jd,'manifest.json'),{job_id:jobs[i],source,artifacts:{tls:{'transform.json':R.shaFile(path.join(jd,'tls/transform.json'))}},report_sha256:R.shaFile(path.join(jd,'report.json'))});
    }
    const map={nframes:1,voxels:new Map([[1,{x:0,y:0,z:1,occ:1}]])},code=R.codeBinding(root);
    const solution={init:'identity',R:M.I3,t:[0,0,0],self_rot:0,self_t:0,holdout_p50:.01};
    const d={kind:'registration_diagnostics',schema:1,protocol:{id:'r3.6_fine_static_v1'},pair:{source:sids[0],reference:sids[1]},
        support:{n_static_source:10000,n_static_target:10000,n_correspondence:6000,inlier_ratio:.6,coverage_xy:.8,max_sector_share:.3},
        geometry:{condition_number:100,eig_ratio:.01},residual:{fit:{p50:.01,p90:.04},holdout:{p50:.01},holdout_fit_ratio_p50:1},
        basins:{solutions:[solution,{...R.clone(solution),init:'tls'}]},direction_check:{forward_p50:.01,inverse_p50:.1},
        sanity:Object.fromEntries(Object.keys(R.PROFILE.sanity).map(k=>[k,{observed:0}]))};
    d.gate=R.gate(d);
    const r={kind:'offline_cross_session_registration',schema:1,units:'m',direction:'current_to_reference',from_frame:'leveled_session',to_frame:'reference_frame',source_session:sids[0],reference_session:sids[1],
        rotation_row_major:M.I3,translation_m:[0,0,0],method:'fixed_icp_r3_2',method_version:1,code_id:code.code_id,
        scope:'offline_display_only',physical_verified:false,extrinsics_verified:false,runtime_eligible:false,quality:{status:d.gate.status,gate_profile:d.gate.profile_id,reasons:d.gate.reasons}};
    const p={kind:'registration_provenance',schema:1,source_session:R.sessionBinding(root,sids[0]),reference_session:R.sessionBinding(root,sids[1]),
        source_leveling:R.levelingBinding(root,sids[0],jobs[0]).binding,reference_leveling:R.levelingBinding(root,sids[1],jobs[1]).binding,background_reference:R.refBinding(map),code};
    let counter=0;
    function artifact(change) {
        const values={r:R.clone(r),d:R.clone(d),p:R.clone(p)};change?.(values);
        const dir=path.join(root,'art'+counter++);fs.mkdirSync(dir);
        const rb=R.serialize(values.r),id=R.sha(rb);values.p.artifact_id=id;
        const text=[rb,R.serialize(values.d),R.serialize(values.p)],files={};
        R.FILES.forEach((f,i)=>{fs.writeFileSync(path.join(dir,f),text[i]);files[f]=R.sha(text[i]);});
        dump(path.join(dir,'manifest.json'),{kind:'registration_manifest',schema:1,artifact_id:id,files});return dir;
    }
    const options={root,referenceMap:map,source:sids[0],reference:sids[1]},load=dir=>R.load(dir,options);
    return {root,r,d,p,map,sids,jobs,artifact,load,options};
}
function run() {
    const f=fixtures(),rows=[];
    const test=(id,fn)=>{try {fn();rows.push({id,result:'PASS'});}catch(e){rows.push({id,result:'FAIL',error:e.stack});}};
    const is=(a,state,reason)=>{assert.equal(a.state,state);if(reason)assert(a.reasons.includes(reason));};
    const reGate=v=>{v.d.gate=R.gate(v.d);v.r.quality={status:v.d.gate.status,gate_profile:v.d.gate.profile_id,reasons:v.d.gate.reasons};};
    try {
        test('T37-01',()=>is(f.load(), 'UNAVAILABLE','NO_ARTIFACT'));
        test('T37-02',()=>{for(const broken of ['missing','bad']) {const dir=f.artifact();if(broken==='missing')fs.unlinkSync(path.join(dir,'manifest.json'));else fs.writeFileSync(path.join(dir,'manifest.json'),'{');is(f.load(dir),'REJECTED','SCHEMA');}});
        test('T37-03',()=>{for(const name of R.FILES) {const dir=f.artifact();fs.appendFileSync(path.join(dir,name),' ');is(f.load(dir),'REJECTED','ARTIFACT_TAMPERED');}});
        test('T37-04',()=>{for(const k of ['kind','schema','from_frame','to_frame','units','scope','runtime_eligible'])is(f.load(f.artifact(v=>v.r[k]='bad')),'REJECTED','SCHEMA');});
        test('T37-05',()=>is(f.load(f.artifact(v=>v.r.direction='reference_to_current')),'REJECTED','DIRECTION'));
        test('T37-05b',()=>{const d=R.clone(f.d);d.direction_check={forward_p50:.1,inverse_p50:.01};assert(R.gate(d).reasons.includes('DIRECTION'));const dir=path.join(f.root,'bad-writer');assert.throws(()=>R.publish(dir,f.r,d,f.p),/DIRECTION/);assert(!fs.existsSync(dir));});
        test('T37-06',()=>{for(const value of [2,-1,NaN,Infinity])is(f.load(f.artifact(v=>v.r.rotation_row_major[0]=value)),'REJECTED','INVALID_MATRIX');});
        test('T37-07',()=>{for(const side of ['source','reference'])for(const k of ['meta_sha256','bin_sha256'])is(f.load(f.artifact(v=>v.p[side+'_session'][k]='0'.repeat(64))),'STALE','SESSION_SHA_MISMATCH');});
        test('T37-08',()=>{for(const side of ['source','reference'])for(const k of ['transform_sha256','report_sha256','manifest_sha256','transform_id'])is(f.load(f.artifact(v=>v.p[side+'_leveling'][k]='0'.repeat(64))),'STALE','LEVELING_SHA_MISMATCH');});
        test('T37-09',()=>{const dir=path.join(f.root,'captures/leveled',f.jobs[0]),hold=dir+'_held';fs.renameSync(dir,hold);try{is(f.load(f.artifact()),'STALE','LEVELING_JOB_MISSING');}finally{fs.renameSync(hold,dir);}});
        test('T37-10',()=>is(f.load(f.artifact(v=>v.p.background_reference.digest.value='0'.repeat(64))),'STALE','REFMAP_DRIFT'));
        test('T37-11',()=>is(f.load(f.artifact(v=>v.r.code_id='0'.repeat(64))),'STALE','METHOD_STALE'));
        test('T37-12',()=>is(f.load(f.artifact(v=>{v.r.quality.gate_profile='reg_gate_v99';v.d.gate.profile_id='reg_gate_v99';})),'REJECTED','UNKNOWN_PROFILE'));
        test('T37-13',()=>{for(const mutation of [v=>v.d.gate.checks[0].band='reject',v=>v.d.gate.thresholds.sanity.t_z=.2,v=>v.d.gate.thresholds=null])is(f.load(f.artifact(mutation)),'REJECTED','INCONSISTENT_GATE');});
        test('T37-14',()=>{for(const [id,[dir,pass,warn]] of Object.entries(R.PROFILE.bands))for(const limit of [pass,warn])for(const delta of [-1e-8,0,1e-8]) {
            const d=R.clone(f.d),value=limit+delta;
            if(id.startsWith('fit_'))d.residual.fit[id.slice(4)]=value;
            else if(id==='holdout_p50')d.residual.holdout.p50=value;
            else if(id==='holdout_fit_ratio_p50')d.residual.holdout_fit_ratio_p50=value;
            else if(id in d.geometry)d.geometry[id]=value;else d.support[id]=value;
            const expected=dir==='max'?(value<=pass?'pass':value<=warn?'warn':'reject'):(value>=pass?'pass':value>=warn?'warn':'reject');
            assert.equal(R.gate(d).checks.find(c=>c.id===id).band,expected,id+' '+value);
        }});
        test('T37-15',()=>{assert.equal(R.gate(f.d).status,'PASS');const d=R.clone(f.d);d.support.coverage_xy=.4;assert.equal(R.gate(d).status,'WARN');d.support.coverage_xy=.2;assert.equal(R.gate(d).status,'REJECT');delete d.support.n_static_source;assert(R.gate(d).reasons.includes('UNFROZEN_PROFILE'));const h=R.clone(f.d);h.residual.holdout.p50=.021;assert.equal(R.gate(h).status,'REJECT');});
        test('T37-16',()=>{const b=R.clone(f.d.basins);assert.equal(R.basinBand(b).band,'pass');b.solutions[1].R=M.m3.rodrigues([.01,0,0]);b.solutions[1].holdout_p50=.012;assert.equal(R.basinBand(b).band,'pass');b.solutions[1].holdout_p50=.0101;assert.equal(R.basinBand(b).band,'warn');b.solutions[1].holdout_p50=.01;assert.equal(R.basinBand(b).band,'reject');});
        test('T37-17',()=>{for(const [k,limit] of Object.entries(R.PROFILE.sanity)){const d=R.clone(f.d);d.sanity[k].observed=limit;assert.equal(R.gate(d).checks.find(c=>c.id===k).band,'pass');d.sanity[k].observed=limit+1e-8;assert(R.gate(d).reasons.includes('SANITY_BOUND'));}});
        test('T37-18',()=>{const valid=f.load(f.artifact());is(valid,'VALID');assert(valid.trace.includes('VALIDATING'));is(f.load(f.artifact(v=>{v.d.support.coverage_xy=.4;reGate(v);})), 'DEGRADED');is(f.load(f.artifact(v=>{v.d.support.coverage_xy=.2;reGate(v);})), 'REJECTED');const stale=f.load(f.artifact(v=>v.p.source_session.meta_sha256='0'.repeat(64)));is(stale,'STALE');is(f.load(f.artifact()),'VALID');is(f.load(f.artifact(v=>v.r.schema=99)),'REJECTED');is(f.load(f.artifact()),'VALID');});
        test('T37-19',()=>{const a=f.load(f.artifact()),cloud={frame:'leveled_session:'+f.sids[0],buf:new Float32Array([1,2,3,4])};R.applyRegistration(cloud,a);assert.throws(()=>R.applyRegistration(cloud,a),/ERR_DUPLICATE_REGISTRATION/);for(const frame of ['raw','leveled_session:'+f.sids[1]])assert.throws(()=>R.applyRegistration({frame,buf:cloud.buf},a),/ERR_FRAME_MISMATCH/);assert.throws(()=>{a.registration.translation_m[0]=1;},TypeError);const bad={frame:'leveled_session:'+f.sids[0],buf:new Float32Array([NaN,2,3,4])};const before=bad.buf;assert.throws(()=>R.applyRegistration(bad,a),/ERR_REGISTRATION_REJECTED/);assert.strictEqual(bad.buf,before);});
        test('T37-21',()=>{const dir=path.join(f.root,'publish');const id=R.publish(dir,f.r,f.d,f.p);assert.throws(()=>R.publish(dir,f.r,f.d,f.p),/EEXIST/);const script='const fs=require("fs"),c=require("crypto");process.stdout.write(c.createHash("sha256").update(fs.readFileSync(process.argv[1])).digest("hex"));';const other=cp.execFileSync(process.execPath,['-e',script,path.join(dir,'registration.json')],{encoding:'utf8'});assert.equal(other,id);is(f.load(dir),'VALID');});
    } finally {
        // Only our mkdtemp fixture tree can be removed; captures and repository are never targets.
        assert(path.resolve(f.root).startsWith(path.resolve(os.tmpdir())+path.sep+'hr-r38-'));
        fs.rmSync(f.root,{recursive:true,force:true});
    }
    return rows;
}
module.exports={fixtures,run};
if(require.main===module) {const rows=run();console.log(JSON.stringify(rows,null,2));process.exitCode=rows.some(r=>r.result==='FAIL')?1:0;}
