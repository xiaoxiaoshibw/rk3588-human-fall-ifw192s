"use strict";
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration'),
    BR=require('./baseline_code/pc_apps/human_replay/registration'),PL=require('../../../../pc_apps/human_replay/human_pipe_lib');
const dir=path.join(R.ROOT,'captures/registration/cap_20261002_223757__to__cap_20261004_203349'),p=R.read(path.join(dir,'provenance.json')),
    src=p.source_session.sid,ref=p.reference_session.sid;
const sl=R.levelingBinding(R.ROOT,src,p.source_leveling.job_id),rl=R.levelingBinding(R.ROOT,ref,p.reference_leveling.job_id),
    raw=R.loadFrames(R.ROOT,src,sl).frames,refmap=PL.build_reference_map(R.loadFrames(R.ROOT,ref,rl,true).frames),options={source:src,reference:ref,referenceMap:refmap};
const expected=R.read(__dirname+'/06_shadow_results.json').P.digest,online=PL.build_static_map(raw.map(PL.denoise)),logs=[],rows=[];
function safe(a,shadow=true) {
    logs.push(...R.logLines(a));assert(!['VALID','DEGRADED'].includes(a.state));
    assert(!(a.state==='VALID'||shadow&&a.state==='DEGRADED'),'full shadow branch dispatch guard');
    const tracker=new PL.Tracker(),out=raw.map((v,i)=>R.clone(PL.pipeline_frame(v,i,{static_keys:online,tracker})));
    assert.equal(R.identity(out),expected);return {state:a.state,reasons:a.reasons,digest:R.identity(out)};
}
const test=(id,fn)=>{try{rows.push({id,result:'PASS',details:fn()});}catch(e){rows.push({id,result:'FAIL',error:e.stack});}};
const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hr-r39-fault-'));
try {
    const dup=name=>{const d=path.join(tmp,name);fs.cpSync(dir,d,{recursive:true,errorOnExist:true,force:false});return d;};
    test('T38-07',()=>{
        const first=safe(BR.load(dir,{...options,source:'cap_20261004_202456'}));
        const d=dup('wrong-reference'),r=R.read(path.join(d,'registration.json'));r.reference_session='cap_20261004_202456';
        fs.writeFileSync(path.join(d,'registration.json'),R.serialize(r));const id=R.shaFile(path.join(d,'registration.json'));
        const pp=R.read(path.join(d,'provenance.json'));pp.artifact_id=id;fs.writeFileSync(path.join(d,'provenance.json'),R.serialize(pp));
        const mf=R.read(path.join(d,'manifest.json'));mf.artifact_id=id;mf.files['registration.json']=id;mf.files['provenance.json']=R.shaFile(path.join(d,'provenance.json'));
        fs.writeFileSync(path.join(d,'manifest.json'),R.serialize(mf));return [first,safe(BR.load(d,options))];
    });
    test('T38-08',()=>{
        const d=dup('tampered');fs.appendFileSync(path.join(d,'registration.json'),' ');const a=BR.load(d,options);assert(a.reasons.includes('ARTIFACT_TAMPERED'));
        const first=safe(a),sandbox=path.join(tmp,'leveling-root');fs.mkdirSync(sandbox);
        for(const f of BR.CODE_FILES){const to=path.join(sandbox,f);fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(path.join(BR.ROOT,f),to);}
        for(const sb of [p.source_session,p.reference_session])for(const f of ['meta.json','points.bin']){
            const rel='captures/remote/'+sb.sid+'/'+f,to=path.join(sandbox,rel);fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(path.join(R.ROOT,rel),to);}
        for(const lb of [p.source_leveling,p.reference_leveling])for(const f of ['report.json','manifest.json','tls/transform.json']){
            const rel='captures/leveled/'+lb.job_id+'/'+f,to=path.join(sandbox,rel);fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(path.join(R.ROOT,rel),to);}
        fs.appendFileSync(path.join(sandbox,'captures/leveled',p.source_leveling.job_id,'tls/transform.json'),' ');
        const b=BR.load(dir,{...options,root:sandbox});assert(b.reasons.includes('LEVELING_SHA_MISMATCH'));return [first,safe(b)];
    });
    test('T38-09',()=>{const a=R.load(null,options);assert.equal(a.state,'UNAVAILABLE');return safe(a);});
    test('T38-10',()=>{
        const a=BR.load(dir,options),c=BR.applyRegistration({frame:'leveled_session:'+src,buf:new Float32Array([1,2,1,1])},a,{shadow:true});
        assert.throws(()=>BR.applyRegistration(c,a,{shadow:true}),/ERR_DUPLICATE_REGISTRATION/);
        for(const frame of ['raw','leveled_session:'+ref])assert.throws(()=>BR.applyRegistration({frame,buf:c.buf},a,{shadow:true}),/ERR_FRAME_MISMATCH/);
        return {duplicate:'ERR_DUPLICATE_REGISTRATION',frame:'ERR_FRAME_MISMATCH'};
    });
    test('CURRENT_ARTIFACT_STALE_SAFE',()=>{const a=R.load(dir,options);assert.equal(a.state,'STALE');assert(a.reasons.includes('METHOD_STALE'));assert(a.reasons.includes('REFMAP_DRIFT'));
        assert.throws(()=>R.applyRegistration({frame:'leveled_session:'+src,buf:new Float32Array([1,2,1,1])},a,{shadow:true}),/ERR_REGISTRATION_STALE/);return safe(a);});
} finally {
    const absolute=path.resolve(tmp),prefix=path.resolve(os.tmpdir())+path.sep+'hr-r39-fault-';assert(absolute.startsWith(prefix));fs.rmSync(absolute,{recursive:true,force:true});
}
fs.writeFileSync(__dirname+'/06_fault_regression.json',R.serialize(rows),{flag:'wx'});fs.writeFileSync(__dirname+'/06_fault_logs.txt',logs.join('\n')+'\n',{flag:'wx'});
console.log(R.serialize(rows));process.exitCode=rows.some(v=>v.result==='FAIL')?1:0;
