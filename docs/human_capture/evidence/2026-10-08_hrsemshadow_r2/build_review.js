/* Generate a new R2 page from immutable R1 evidence; no historical writes. */
'use strict';
const fs=require('fs'),path=require('path'),B=require('./review_binding.js');
const R=require(path.join(B.ROOT,'pc_apps/human_replay/registration.js'));
async function main(){
 const a=await B.authority(),bundle=R.read(path.join(B.R1,'review_bundle.json'));
 B.need(R.identity(bundle.binding)===R.identity(a.binding),'BINDING_MISMATCH','bundle');
 bundle.authority=B.PINS;bundle.votes=Object.fromEntries(a.votes);
 for(const frame of bundle.cases){
  for(const c of frame.clusters){
   const id=[frame.sid,frame.mode,frame.ordinal,c.ci].join('/'),ref=a.clusters.get(id);
   B.need(ref&&frame.seq===ref.seq,'MEMBER_ID_MISMATCH',id);
   B.need(R.identity(c.points.map(p=>p.row))===ref.member_sha256,'MEMBER_ROWS_MISMATCH',id);
   B.need(R.identity(c.points.flatMap(p=>p.xyz))===ref.xyz_sha256,'CONTENT_SHA_MISMATCH',id);
   c.receipt=B.receipt(a,ref);
  }
  for(const p of frame.deleted){
   const id=[frame.sid,frame.mode,frame.ordinal,'p'+p.row].join('/'),ref=a.points.get(id);
   B.need(ref,'POINT_UNBOUND',id);p.receipt=B.receipt(a,ref,'points');
   B.need(R.identity(p.xyz)===p.receipt.xyz_sha256,'CONTENT_SHA_MISMATCH',id);
  }
 }
 const payload=JSON.stringify(bundle).replace(/<\//g,'<\\/'),digest=R.sha(payload);
 const html=fs.readFileSync(path.join(__dirname,'review_template.html'),'utf8').replace('__PAYLOAD__',payload).replace('__PAYLOAD_SHA__',digest).replace('__INDEX_SHA__',B.PINS['pass3/clusters.jsonl']);
 fs.writeFileSync(path.join(__dirname,'review.html'),html,{flag:'wx'});
 fs.writeFileSync(path.join(__dirname,'review_build.json'),JSON.stringify({cases:bundle.cases.length,clusters:a.clusters.size,points:a.points.size,authority:B.PINS,payload_sha256:digest,page_sha256:R.sha(html),real_labels:0},null,2)+'\n',{flag:'wx'});
 console.log('BOUND_REVIEW_BUILT',bundle.cases.length,a.clusters.size,a.points.size);
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
