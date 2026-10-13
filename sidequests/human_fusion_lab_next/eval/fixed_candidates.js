'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const {audit,LAB,ROOT}=require('./baseline'),D=require(LAB+'/core/data_loader'),L=require(LAB+'/core/leveling'),{subset,extra}=require(LAB+'/export'),{createDetector}=require(LAB+'/detector'),I=require('../contracts/index_v1');
const out=path.resolve(process.argv[2]||'');if(!process.argv[2]||fs.existsSync(out))throw Error('new file path required');
const results=[],inputs={},models=['rf51_candidate','rf69_candidate','xgb69_candidate'],det=Object.fromEntries(models.map(m=>[m,createDetector(m)]));
for(const sid of Object.values(audit.splits).flat()){
 const p=path.join(LAB,'results',sid+'.jsonl');if(!fs.existsSync(p))continue;inputs[path.relative(ROOT,p)]=I.sha(fs.readFileSync(p));const rows=fs.readFileSync(p,'utf8').trim().split('\n').filter(Boolean).map(JSON.parse).filter(r=>r.label!==null);if(!rows.length)continue;
 const frames=D.iter_frames_lazy(path.join(ROOT,'captures/remote',sid)),byFrame=new Map();for(const r of rows){if(!byFrame.has(r.frame_index))byFrame.set(r.frame_index,[]);byFrame.get(r.frame_index).push(r);}let f;
 try{while((f=frames.next())){if(!byFrame.has(f.index))continue;const co=L.resolve_contract({meta:frames.meta}),lv=L.level_frame(f.xyzi,co.R,co.T,co.already_leveled);for(const r of byFrame.get(f.index)){
  const [sub,it]=subset(lv,r.indices),sample=Array.from({length:256},(_,j)=>{const k=Math.floor(j*r.indices.length/256);return [sub.x[k],sub.y[k],sub.z[k]];}),maxdiff=Math.max(...sample.flatMap((p,j)=>p.map((v,k)=>Math.abs(v-r.points[j][k]))));assert.equal(maxdiff,0,'frozen sample differs from current source');
  const x=r.features.concat(r.extended),probs=Object.fromEntries(models.map(m=>[m,det[m].engine.rf.predict_person(Float32Array.from(x.slice(0,m.startsWith('rf51')?51:69)))]));
  results.push({sid,frame_index:r.frame_index,id:r.id,label:r.label,pointset_sha256:I.pointsetSha(r.indices),sample_maxdiff:maxdiff,probs});
 }}}finally{frames.close();}
}
assert.equal(results.length,859);fs.writeFileSync(out,JSON.stringify({n:results.length,inputs,results},null,2),{flag:'wx'});console.log('FIXED_CANDIDATES_PASS',results.length,'sample maxdiff 0');
