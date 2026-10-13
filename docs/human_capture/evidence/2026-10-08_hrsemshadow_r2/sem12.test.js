/* Explicit adversarial expectations; all labels below are synthetic, never human GT. */
'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const B=require('./review_binding.js'),R=require(path.join(B.ROOT,'pc_apps/human_replay/registration.js'));
const results=[];
const clone=x=>JSON.parse(JSON.stringify(x));
async function main(){
 const a=await B.authority(),refs=[...a.clusters.values()].slice(0,2),r=refs.map(x=>B.receipt(a,x));
 const base={schema:1,binding_version:2,kind:'hr_sem_shadow_gt',source:'human',reviewer:'SYNTHETIC TEST ONLY',created_iso:'fixture',authority:B.PINS,binding:a.binding,clusters:r.map(x=>({...x,label:'UNKNOWN',person_id:null})),points:[]};
 assert.strictEqual(B.validate(base,a).records,2);results.push({case:'positive_two_different_members',result:'ACCEPT'});
 function reject(name,code,mutate){const g=clone(base);mutate(g);let message;try{B.validate(g,a);}catch(e){message=e.message;}assert(message&&message.startsWith(code+':'),name+': '+message);results.push({case:name,result:'REJECT',error:message});}
 reject('1_replace_member_keep_old_sha','MEMBER_ROWS_MISMATCH',g=>g.clusters[0].rows=[0]);
 reject('2_swap_member_sha','RECORD_BINDING_MISMATCH',g=>{[g.clusters[0].member_sha256,g.clusters[1].member_sha256]=[g.clusters[1].member_sha256,g.clusters[0].member_sha256];});
 reject('3_rename_member_only','MEMBER_UNBOUND',g=>g.clusters[0].id+='-renamed');
 reject('3b_rename_display_only','DISPLAY_ID_MISMATCH',g=>g.clusters[0].review_id=g.clusters[1].id);
 const src=B.source(a,refs[0].sid),changed=Buffer.from(src.raw),at=(src.meta.frames[refs[0].ordinal].offset_points+refs[0].rows[0])*28;changed[at]^=1;
 assert.throws(()=>B.pin(changed,src.b.source.bin_sha256,'points.bin'),/AUTHORITY_SHA_MISMATCH: points.bin/);
 results.push({case:'4_member_content_changed_source_bytes',result:'REJECT',error:'AUTHORITY_SHA_MISMATCH: points.bin'});
 const changedContent=B.content({...src,raw:changed},refs[0],refs[0].rows);
 reject('4b_content_receipt_changed_without_authority','RECORD_BINDING_MISMATCH',g=>Object.assign(g.clusters[0],changedContent));
 reject('5_display_and_ticket_member_differ','VOTE_BINDING_MISMATCH',g=>g.clusters[0].vote_member_id=g.clusters[1].id);
 reject('5b_ticket_frame_digest_differ','VOTE_BINDING_MISMATCH',g=>g.clusters[0].vote_frame_sha256='0'.repeat(64));
 reject('6_missing_required_member','MEMBER_ROWS_MISMATCH',g=>g.clusters[0].rows.pop());
 reject('6b_duplicate_member_id','DUPLICATE_ID',g=>g.clusters.push(g.clusters[0]));
 reject('6c_missing_required_rows','MEMBER_ROWS_MISMATCH',g=>delete g.clusters[0].rows);
 reject('7_internally_consistent_forgery','MEMBER_ROWS_MISMATCH',g=>{
  const c=g.clusters[0];c.rows=[0];c.member_sha256=R.identity(c.rows);Object.assign(c,B.content(src,refs[0],c.rows));
 });
 reject('7b_candidate_redefines_authority','AUTHORITY_BINDING_MISMATCH',g=>g.authority['pass3/clusters.jsonl']='0'.repeat(64));
 reject('source_path_redirect','RECORD_BINDING_MISMATCH',g=>g.clusters[0].source_path='captures/remote/fake');
 const point=[...a.points.values()][0],pg=clone(base);pg.clusters=[];pg.points=[{...B.receipt(a,point,'points'),label:'UNKNOWN',person_id:null}];
 assert.strictEqual(B.validate(pg,a).records,1);results.push({case:'positive_bound_deleted_point',result:'ACCEPT'});
 reject('PERSON_without_identity','PERSON_ID_REQUIRED',g=>g.clusters[0].label='PERSON');
 // DOM callbacks exercise the delivered page, independent from validator decisions.
 const html=fs.readFileSync(path.join(__dirname,'review.html'),'utf8'),payload=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1],script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
 const els=new Map();let draws=0,exported=null;
 function el(id){if(!els.has(id))els.set(id,{value:id==='projection'?'xz':id==='label'?'UNKNOWN':'',checked:false,files:[],children:[],textContent:id==='payload'?payload:'',width:1000,height:650,selectedOptions:[{textContent:'X/Z'}],append(o){this.children.push(o);if(!this.value)this.value=String(o.value??'');},getContext(){return {clearRect(){},fillText(){},fillRect(){draws++;}};},getBoundingClientRect(){return {left:0,top:0,width:1000,height:650};},click(){}});return els.get(id);}
 const ctx={document:{getElementById:el,createElement:()=>el('created-'+els.size)},console,TextDecoder,TextEncoder,DataView,Uint8Array,crypto:crypto.webcrypto,Blob,URL:{createObjectURL(blob){exported=blob;return 'blob:synthetic';},revokeObjectURL(){}}};
 vm.createContext(ctx);new vm.Script(script).runInContext(ctx);
 for(let i=0;i<1000&&!el('status').textContent.startsWith('R2');i++)await new Promise(resolve=>setTimeout(resolve,10));
 assert(el('status').textContent.startsWith('R2'),el('status').textContent);assert(draws>0);
 for(const c of JSON.parse(payload).cases){el('row').value='12345';el('cases').value=B.key(c);el('cases').onchange();assert.strictEqual(el('row').value,'');assert(el('status').textContent.includes(c.sid+' / '+c.mode+' / f'+c.ordinal+' / seq '+c.seq));}
 el('cases').value=B.key(refs[0]);el('cases').onchange();el('save').onclick();
 el('reviewer').value='SYNTHETIC TEST ONLY';el('export').onclick();assert(exported);assert.strictEqual(B.validate(JSON.parse(await exported.text()),a).records,1);
 results.push({case:'positive_embedded_page_export_validates',result:'ACCEPT'});
 const file=buf=>({arrayBuffer:async()=>buf.buffer.slice(buf.byteOffset,buf.byteOffset+buf.byteLength)});
 el('indexfile').files=[file(Buffer.from(JSON.stringify({...refs[0],rows:[0]})+'\n'))];await el('indexfile').onchange();
 assert(el('status').textContent.startsWith('INDEX_SHA_MISMATCH'));el('save').onclick();assert.strictEqual(el('status').textContent,'DISPLAY_NOT_VERIFIED');
 results.push({case:'page_tampered_index_and_stale_display',result:'REJECT',error:'INDEX_SHA_MISMATCH; DISPLAY_NOT_VERIFIED'});
 el('indexfile').files=[file(fs.readFileSync(path.join(B.R1,'pass3/clusters.jsonl')))];await el('indexfile').onchange();assert(el('status').textContent.includes('4311'),el('status').textContent);
 el('session').value=refs[0].sid;el('mode').value=refs[0].mode;el('ordinal').value='0';
 el('metafile').files=[file(fs.readFileSync(path.join(B.ROOT,'captures/remote',refs[0].sid,'meta.json')))];el('binfile').files=[file(src.raw)];
 await el('loadraw').onclick();assert(el('status').textContent.includes('成员内容与票据已核对'),el('status').textContent);el('cluster').value='0';el('save').onclick();el('export').onclick();
 const full=JSON.parse(await exported.text());assert.strictEqual(B.validate(full,a).records,1);assert.deepStrictEqual(full.clusters[0].rows,refs[0].rows);
 results.push({case:'positive_full_index_raw_page_export_validates',result:'ACCEPT'});
 el('binfile').files=[file(changed)];await el('loadraw').onclick();assert(el('status').textContent.includes('源 SHA 不匹配'));el('save').onclick();assert.strictEqual(el('status').textContent,'DISPLAY_NOT_VERIFIED');
 results.push({case:'page_tampered_content',result:'REJECT',error:'source SHA mismatch; DISPLAY_NOT_VERIFIED'});
 fs.writeFileSync(path.join(__dirname,process.argv[2]||'sem12_results.json'),JSON.stringify({failed:0,results,embedded_cases:34,headless_only:true,real_human_labels_created:0},null,2)+'\n',{flag:'wx'});
 console.log('SEM12_PASS',results.filter(r=>r.result==='ACCEPT').length,'positive',results.filter(r=>r.result==='REJECT').length,'rejections; failed=0; realGT=0');
}
main().catch(e=>{console.error(e.stack);process.exitCode=1;});
