'use strict';
// ponytail: reuse the timed engine; no per-frame recorder allocations outside it.
const fs=require('fs'),path=require('path'),assert=require('assert');
const B=require('../../../background/detector_b'),D=require('../../../../human_fusion_lab/core/data_loader'),S=require('../../../../human_fusion_lab/core/schema');
const R04=require('../../r04/run'),{applyVariant}=require('./run'),{sourceManifest}=require('./trace');
const output=process.argv[2];assert(output&&!fs.existsSync(output));
const audit=JSON.parse(fs.readFileSync(path.join(B.LAB,'results/AUDIT.json'))),ref=B.buildReference(),sources=sourceManifest(),results=[];
for(const rec of audit.sessions){
    const session=D.load_session(path.join(B.ROOT,'captures/remote',rec.sid));
    assert.equal(session.meta_sha256,rec.input_sha256.meta);assert.equal(session.points_sha256,rec.input_sha256.points);
    for(const variant of ['native','control','guard']){
        const det=B.createDetector(ref);
        if(variant==='native')R04.applyVariant(det.engine,'fast');else applyVariant(det.engine,variant,false);
        const gen=det.begin(rec.sid),times=[];
        for(const f of session.frames){
            const fc=S.make_frame_context({session_id:rec.sid,session_generation:gen,frame_index:f.index,timestamp:f.timestamp,xyzi:f.xyzi,meta:session.meta});
            const d=det.tick(fc);if(f.index>=5)times.push(d.total_ms);
        }
        times.sort((a,b)=>a-b);const q=p=>times[Math.min(times.length-1,Math.floor(times.length*p))];
        const row={sid:rec.sid,variant,frames:session.frames.length,samples:times.length,input_sha256:rec.input_sha256,model_sha256:det.engine.rf_model_sha,p50:q(.5),p95:q(.95),p99:q(.99),gate_50ms:q(.95)<50?'PASS':'FAIL'};
        results.push(row);console.log(JSON.stringify(row));
    }
    assert.equal(B.sha(path.join(session.session_dir,'meta.json')),rec.input_sha256.meta);assert.equal(B.sha(path.join(session.session_dir,'points.bin')),rec.input_sha256.points);
}
assert.deepStrictEqual(sourceManifest(),sources,'source drift');
fs.writeFileSync(output,JSON.stringify({version:'R06-pure-probe-v1',node:process.version,platform:process.platform,sources,scope:'timed tick; first5 each run excluded; no GT/shadow/trace/owners or per-frame snapshot/serialization/log; native wrapper diagnostic only; sequential one sweep Windows offline',results},null,2),{flag:'wx'});
