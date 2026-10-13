/* Synthetic integrity challenge in memory. No true labels, no r1 writes, no browser policy bypass. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),readline=require('readline'),crypto=require('crypto');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..'),R1=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const save=(n,x)=>fs.writeFileSync(path.join(OUT,n),JSON.stringify(x,null,2)+'\n');
async function main(){
 const sid='cap_20261004_203349',job='c9712acad48c4fb7a78cb119c08d4cdb',dir=path.join(ROOT,'captures/leveled',job);
 const tf=R.read(path.join(dir,'tls/transform.json')),report=R.read(path.join(dir,'report.json')),manifest=R.read(path.join(dir,'manifest.json'));
 const source=R.sessionBinding(ROOT,sid);delete source.sid;
 assert.deepStrictEqual(source,tf.source);assert.deepStrictEqual(source,report.source);assert.deepStrictEqual(source,manifest.source);
 assert.strictEqual(R.shaFile(path.join(dir,'report.json')),manifest.report_sha256);
 for(const [method,files] of Object.entries(manifest.artifacts))for(const [n,h] of Object.entries(files))assert.strictEqual(R.shaFile(path.join(dir,method,n)),h);
 const contract=R.levelingBinding(ROOT,sid,job);
 const historicalDiff=[];for(const [n,h] of Object.entries(report.code_hashes)){const sub=['__init__.py','ransac.py','svd.py','tls.py'].includes(n)?'leveling_estimators/':'';const cur=R.shaFile(path.join(ROOT,'pc_apps/human_replay',sub+n));if(cur!==h)historicalDiff.push({file:n,historical:h,current:cur});}
 save('WD02_contract.json',{sid,job,source_and_all_artifacts_sha_match:true,current_levelingBinding_contract_accepts:true,
  binding:contract.binding,historical_generator_differences:historicalDiff,conclusion:'harness adds historical-generator-equals-current requirement; this is not evidence of raw input or artifact drift. Diagnostic only; WD02 remains unrun and no loader/artifact authorization.'});
 const html=fs.readFileSync(path.join(R1,'review.html'),'utf8'),payload=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1],script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
 const bundle=JSON.parse(payload),elements=new Map();let draws=0;
 const element=id=>{if(!elements.has(id))elements.set(id,{value:id==='projection'?'xz':'',checked:false,files:[],children:[],textContent:id==='payload'?payload:'',width:1000,height:650,
   selectedOptions:[{textContent:'X/Z'}],append(o){this.children.push(o);if(!this.value)this.value=String(o.value??'');},getContext(){return {clearRect(){},fillText(){},fillRect(){draws++;}}},getBoundingClientRect(){return {left:0,top:0,width:1000,height:650}},click(){}});return elements.get(id);};
 const ctx={document:{getElementById:element,createElement:()=>element('created-'+elements.size)},console,TextDecoder,DataView,Uint8Array,URL,Blob,crypto:crypto.webcrypto};
 vm.createContext(ctx);new vm.Script(script,{filename:'r1review:inline'}).runInContext(ctx);
 for(const r of bundle.cases){element('cases').value=[r.sid,r.mode,r.ordinal].join('/');element('cases').onchange();}
 assert(draws>0);element('label').value='PERSON';element('person').value='';element('save').onclick();assert(element('status').textContent.includes('person_id'));assert.strictEqual(vm.runInContext('records.length',ctx),0);
 // Use a real bound frame but alter the independently selected index's row list.
 const iter=readline.createInterface({input:fs.createReadStream(path.join(R1,'pass3/clusters.jsonl')),crlfDelay:Infinity});let first;
 for await(const line of iter){first=JSON.parse(line);break;}
 const forged={...first,rows:[0],semantic:{...first.semantic,semantic:'HUMAN_EVIDENCE'}};
 element('indexfile').files=[{text:async()=>JSON.stringify(forged)+'\n'}];await element('indexfile').onchange();
 const sid2=first.sid,d=path.join(ROOT,'captures/remote',sid2),toArrayBuffer=b=>b.buffer.slice(b.byteOffset,b.byteOffset+b.byteLength);
 const mb=fs.readFileSync(path.join(d,'meta.json')),pb=fs.readFileSync(path.join(d,'points.bin'));
 element('session').value=sid2;element('mode').value=first.mode;element('ordinal').value=first.ordinal;
 element('metafile').files=[{arrayBuffer:async()=>toArrayBuffer(mb)}];element('binfile').files=[{arrayBuffer:async()=>toArrayBuffer(pb)}];
 await element('loadraw').onclick();
 const viewed=vm.runInContext('({sid:current.sid,mode:current.mode,ordinal:current.ordinal,ci:current.clusters[0].ci,rows:current.clusters[0].points.map(p=>p.row),member_sha256:current.clusters[0].member_sha256})',ctx);
 assert.strictEqual(viewed.rows.length,1);assert.strictEqual(viewed.rows[0],0);assert.strictEqual(viewed.member_sha256,first.member_sha256);
 element('label').value='UNKNOWN';element('person').value='';element('save').onclick();
 const record=JSON.parse(JSON.stringify(vm.runInContext('records[0]',ctx)));
 save('review_index_challenge.json',{source:'synthetic adversarial integrity test; no real labels created',headless_embedded_cases:bundle.cases.length,
  source_meta_bin_sha_passed:true,original_member_count:first.n,tampered_display:viewed,status:element('status').textContent,
  exported_record_in_memory:record,expected_rejection:false,defect:'unbound index accepted; copied original member SHA while displaying row 0 instead of real cluster'});
 const c=(positive,x=1)=>({ok:true,cx:x,cy:0,cz:1,height_m:1.8,upcos:1,n:1000,label:'HUMAN_CANDIDATE',joint:positive?'CONFIRMED_HUMAN':'NON_HUMAN',semantic:positive?'HUMAN_EVIDENCE':'UNKNOWN'});
 const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js')),H=require(path.join(R1,'shadow.js'));
 const traces=[];let original=new PL.Tracker(),reference=new H.FrameVotes();
 for(let f=0;f<3;f++){const cs=f===2?[c(true,.9),c(true,1),c(true,1.1)]:[c(false)];original.tick(f,cs);traces.push({case:'collision',f,original:JSON.parse(JSON.stringify(original.tracks)),reference:reference.tick(f,cs)});}
 assert(original.tracks.some(t=>t.human_confirmed));assert(traces.at(-1).reference.assigned.every(t=>t.identity===null));
 original=new PL.Tracker();reference=new H.FrameVotes();for(let f=0;f<=9;f++){const cs=[0,1,9].includes(f)?[c(true)]:[];original.tick(f,cs);traces.push({case:'gap',f,original:JSON.parse(JSON.stringify(original.tracks)),reference:reference.tick(f,cs)});}
 assert(original.tracks.some(t=>t.human_confirmed));assert.strictEqual(traces.at(-1).reference.windows[0].semantic_votes,1);assert.strictEqual(traces.at(-1).reference.windows[0].semantic_confirmed,false);
 save('vote_repro_independent.json',{source:'synthetic mechanical only',traces});console.log('TOOL_AUDIT: WD02 hashes intact, extra harness contract; tampered review index accepted; vote collision and gap reproduced');
}
main().catch(e=>{console.error(e);process.exitCode=1;});
