'use strict';
// Every schema label below is SYNTHETIC test data, never consumed as real GT.
const assert=require('assert'),fs=require('fs'),path=require('path');
const {loadAuthority,validate,checkNodes}=require('./bind_inputs.js');
const OUT=__dirname,clone=x=>JSON.parse(JSON.stringify(x));
async function main(){
 const {B,a}=await loadAuthority(),input=JSON.parse(fs.readFileSync(path.join(OUT,'input_manifest.json'),'utf8'));
 const refs=input.entries.flatMap(e=>e.clusters.map(c=>a.clusters.get(c.id))).slice(0,2);
 const record=c=>({...B.receipt(a,c),label:'PERSON',person_id:'SYNTHETIC_PERSON'});
 const gt={kind:'hr_sem_shadow_gt',schema:1,binding_version:2,source:'human',reviewer:'SYNTHETIC TEST ONLY',created_iso:'2026-10-09T00:00:00+08:00',authority:B.PINS,binding:a.binding,clusters:refs.map(record),points:[]};
 const results=[];
 const bad=(name,edit,code)=>{const copy=clone(gt);edit(copy);assert.throws(()=>B.validate(copy,a),new RegExp(code));results.push({name,status:'PASS',expected:code});};
 assert.equal(B.validate(gt,a).records,2);results.push({name:'two bound real-member synthetic labels',status:'PASS'});
 bad('replace rows keep SHA',g=>g.clusters[0].rows[0]=0,'MEMBER_ROWS_MISMATCH');
 bad('swap SHA',g=>g.clusters[0].member_sha256=g.clusters[1].member_sha256,'RECORD_BINDING_MISMATCH');
 bad('rename identity',g=>g.clusters[0].id+='bad','MEMBER_UNBOUND');
 bad('display rename',g=>g.clusters[0].review_id+='bad','DISPLAY_ID_MISMATCH');
 bad('vote member mismatch',g=>g.clusters[0].vote_member_id=g.clusters[1].id,'VOTE_BINDING_MISMATCH');
 bad('remove member',g=>g.clusters[0].rows.pop(),'MEMBER_ROWS_MISMATCH');
 bad('duplicate ID',g=>g.clusters.push(g.clusters[0]),'DUPLICATE_ID');
 bad('missing field',g=>delete g.clusters[0].raw_member_sha256,'RECORD_BINDING_MISMATCH');
 bad('internally consistent fake rows',g=>{g.clusters[0].rows=[1,2];g.clusters[0].member_sha256=B.R.identity([1,2]);},'MEMBER_ROWS_MISMATCH');
 bad('fake authority',g=>g.authority['pass3/binding.json']='0'.repeat(64),'AUTHORITY_BINDING_MISMATCH');
 bad('source redirection',g=>g.clusters[0].source_path='elsewhere','RECORD_BINDING_MISMATCH');
 const bytes=Buffer.from('test');assert.throws(()=>B.pin(bytes,'0'.repeat(64),'synthetic raw'),/AUTHORITY_SHA_MISMATCH/);
 results.push({name:'changed raw bytes reject independent pin',status:'PASS'});
 // New skeleton entry must reject synthetic review and missing input binding.
 const synthetic={kind:'hr_skeleton_offline_gt',schema:1,source:'synthetic',reviewer:'SYNTHETIC TEST ONLY',created_iso:gt.created_iso,
  input_binding:B.R.shaFile(path.join(OUT,'input_manifest.json')),records:gt.clusters,fixture_type:'SYNTHETIC_NOT_REAL_GT'};
 const suffix=process.argv[2]||'';
 const p=path.join(OUT,'synthetic_sidecar_rejected'+suffix+'.json');fs.writeFileSync(p,JSON.stringify(synthetic),{flag:'wx'});
 await assert.rejects(()=>validate(p),/REAL_REVIEW_REQUIRED/);results.push({name:'synthetic cannot enter real GT',status:'PASS'});
 const fixture={id:'SYNTHETIC_NODE_SCHEMA',nodes:Object.fromEntries(['HEAD','UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION','LOWER_A','LOWER_B'].map(k=>[k,{visibility:'VISIBLE',region_rows:[1,2],reason:'SYNTHETIC_TEST_ONLY'}]))};
 checkNodes(fixture,new Set([1,2]));results.push({name:'valid synthetic visibility regions',status:'PASS'});
 for(const [name,edit,code] of [
  ['foreign support row',r=>r.nodes.HEAD.region_rows=[3],'REGION_ROWS_INVALID'],
  ['duplicate support row',r=>r.nodes.HEAD.region_rows=[1,1],'REGION_ROWS_INVALID'],
  ['visible without region',r=>r.nodes.HEAD.region_rows=[],'VISIBLE_REGION_REQUIRED'],
  ['missing node visibility',r=>delete r.nodes.HEAD.visibility,'NODE_VISIBILITY_REQUIRED'],
  ['missing review reason',r=>r.nodes.HEAD.reason='','VISIBILITY_REASON_REQUIRED']]){
   const r=clone(fixture);edit(r);assert.throws(()=>checkNodes(r,new Set([1,2])),new RegExp(code));results.push({name,status:'PASS',expected:code});
 }
 fs.writeFileSync(path.join(OUT,'binding_test_results'+suffix+'.json'),JSON.stringify({fixture_type:'SYNTHETIC_NOT_REAL_GT',results,tests:results.length})+'\n',{flag:'wx'});
 console.log('BINDING_TESTS_PASS',results.length);
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
