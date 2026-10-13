/* R2 offline authority. Candidate records never select or redefine these anchors. */
'use strict';
const fs=require('fs'),path=require('path'),readline=require('readline'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../../../..'),R1=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const PINS=Object.freeze({
 'pass3/binding.json':'2f0f3aaaf6b6c62aedcf5b02de30539da13cc0afce324d7dc4fba44ccdb26416',
 'pass3/clusters.jsonl':'adc603b5783bee4d71cd38b7341f30dcbe563d9a3464d5bffa6d26ce609d6eee',
 'pass3/votes.jsonl':'110c438ded301353d6464f07ac3cf3687139bb29d91bc298ff19b28151449353',
 'gt_review_template.json':'c934db58ed8e2fb3634d38970d4c55c6cf326bac10a345398f9ca986eea9ac46',
 'review_bundle.json':'86020788aa087eace83dfc7e22820de35128c654f875bb09718e78bdd57610c0'
});
const key=r=>[r.sid,r.mode,r.ordinal].join('/');
function need(ok,code,id){if(!ok)throw Error(code+': '+id);}
function pin(bytes,expected,name){need(R.sha(bytes)===expected,'AUTHORITY_SHA_MISMATCH',name);}
async function jsonl(file){const out=[];for await(const l of readline.createInterface({input:fs.createReadStream(file),crlfDelay:Infinity}))if(l)out.push(JSON.parse(l));return out;}
async function authority(){
 for(const [file,h] of Object.entries(PINS))need(R.shaFile(path.join(R1,file))===h,'AUTHORITY_SHA_MISMATCH',file);
 const binding=R.read(path.join(R1,'pass3/binding.json')),template=R.read(path.join(R1,'gt_review_template.json'));
 need(R.identity(binding)===R.identity(template.binding),'BINDING_MISMATCH','template');
 const clusters=new Map();for(const c of await jsonl(path.join(R1,'pass3/clusters.jsonl'))){
  need(c.id===[c.sid,c.mode,c.ordinal,c.ci].join('/'),'MEMBER_ID_MISMATCH',c.id);
  need(!clusters.has(c.id),'DUPLICATE_ID',c.id);
  need(c.rows.length===c.n&&new Set(c.rows).size===c.n&&R.identity(c.rows)===c.member_sha256,'MEMBER_SHA_MISMATCH',c.id);
  clusters.set(c.id,c);
 }
 const votes=new Map();for(const v of await jsonl(path.join(R1,'pass3/votes.jsonl'))){need(!votes.has(key(v)),'DUPLICATE_VOTE_FRAME',key(v));votes.set(key(v),v);}
 const points=new Map(template.points.map(p=>[p.id,p]));need(points.size===template.points.length,'DUPLICATE_ID','point authority');
 return {binding,clusters,points,votes,sources:new Map()};
}
function source(a,sid){
 if(a.sources.has(sid))return a.sources.get(sid);
 const b=a.binding.sessions.find(s=>s.sid===sid);need(b,'SESSION_UNBOUND',sid);
 const dir=path.join(ROOT,'captures/remote',sid),mb=fs.readFileSync(path.join(dir,'meta.json')),raw=fs.readFileSync(path.join(dir,'points.bin'));
 pin(mb,b.source.meta_sha256,sid+'/meta.json');pin(raw,b.source.bin_sha256,sid+'/points.bin');
 const meta=JSON.parse(mb),td=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/leveling',b.job);
 for(const [file,k] of [['tls/transform.json','tf'],['report.json','report'],['manifest.json','manifest']])need(R.shaFile(path.join(td,file))===b.leveling_sha[k],'TRANSFORM_SHA_MISMATCH',sid+'/'+file);
 const tf=R.read(path.join(td,'tls/transform.json'));
 need(meta.point_layout.stride_bytes===28,'STRIDE_MISMATCH',sid);
 const src={meta,raw,b,tf};a.sources.set(sid,src);return src;
}
function content(src,ref,rows){
 const f=src.meta.frames[ref.ordinal];need(f&&f.seq===ref.seq,'FRAME_MISMATCH',ref.id);
 need(rows.length&&new Set(rows).size===rows.length,'MISSING_OR_DUPLICATE_MEMBER',ref.id);
 const h=crypto.createHash('sha256'),xyz=[];
 for(const row of rows){
  need(Number.isInteger(row)&&row>=0&&row<f.count_points,'ROW_RANGE',ref.id+'/'+row);
  const at=(f.offset_points+row)*28;need(at+28<=src.raw.length,'ROW_RANGE',ref.id+'/'+row);
  h.update(src.raw.subarray(at,at+28));let x=[0,1,2].map(j=>src.raw.readFloatLE(at+j*4));
  const rt=(A,t)=>[0,1,2].map(j=>Math.fround(A[j*3]*x[0]+A[j*3+1]*x[1]+A[j*3+2]*x[2]+t[j]));
  x=rt(src.tf.R.flat(),src.tf.t);if(src.b.transform)x=rt(src.b.transform.rotation_row_major,src.b.transform.translation_m);xyz.push(...x);
 }
 return {raw_member_sha256:h.digest('hex'),xyz_sha256:R.identity(xyz)};
}
function receipt(a,ref,kind='clusters'){
 const rows=kind==='clusters'?ref.rows:[ref.row],v=a.votes.get(key(ref));
 need(v&&v.seq===ref.seq,'VOTE_FRAME_MISMATCH',ref.id);
 if(kind==='clusters')need(v.reference.assigned.filter(x=>x.ci===ref.ci).length===1,'VOTE_MEMBER_MISMATCH',ref.id);
 const actual=content(source(a,ref.sid),ref,rows);
 if(kind==='clusters')need(actual.xyz_sha256===ref.xyz_sha256,'CONTENT_SHA_MISMATCH',ref.id);
 return {id:ref.id,sid:ref.sid,mode:ref.mode,ordinal:ref.ordinal,seq:ref.seq,
  source_path:'captures/remote/'+ref.sid,rows:[...rows],member_sha256:R.identity(rows),...actual,
  review_id:ref.id,vote_member_id:ref.id,vote_frame_sha256:R.identity(v),...(kind==='points'?{row:ref.row}:{ci:ref.ci})};
}
function validate(gt,a){
 need(gt.kind==='hr_sem_shadow_gt'&&gt.schema===1&&gt.binding_version===2&&gt.source==='human','SIDECAR_SCHEMA','root');
 need(typeof gt.reviewer==='string'&&gt.reviewer.trim()&&gt.created_iso,'REVIEWER_REQUIRED','root');
 need(R.identity(gt.authority)===R.identity(PINS),'AUTHORITY_BINDING_MISMATCH','root');
 need(R.identity(gt.binding)===R.identity(a.binding),'BINDING_MISMATCH','root');
 const seen=new Set();
 for(const kind of ['clusters','points']){
  need(Array.isArray(gt[kind]),'RECORD_LIST_REQUIRED',kind);
  for(const r of gt[kind]){
   need(r&&typeof r.id==='string','MEMBER_ID_REQUIRED',kind);need(!seen.has(r.id),'DUPLICATE_ID',r.id);seen.add(r.id);
   const ref=a[kind].get(r.id);need(ref,'MEMBER_UNBOUND',r.id);
   const expect=receipt(a,ref,kind);
   for(const [k,v] of Object.entries(expect))need(r[k]!==undefined&&R.identity(r[k])===R.identity(v),k==='rows'?'MEMBER_ROWS_MISMATCH':k.includes('vote')?'VOTE_BINDING_MISMATCH':k==='review_id'?'DISPLAY_ID_MISMATCH':'RECORD_BINDING_MISMATCH',r.id+'/'+k);
   need(['PERSON','STATIC_OBJECT','MIXED','UNKNOWN'].includes(r.label),'LABEL_INVALID',r.id);
   if(r.label==='PERSON')need(typeof r.person_id==='string'&&r.person_id.trim(),'PERSON_ID_REQUIRED',r.id);
  }
 }
 need(seen.size>0,'EMPTY_REVIEW','root');
 return {records:seen.size,binding_version:2,truth:'NOT_VERIFIED: human label truth/coverage requires actual human review'};
}
module.exports={PINS,ROOT,R1,key,need,pin,authority,source,content,receipt,validate};
if(require.main===module)authority().then(a=>console.log(JSON.stringify(validate(R.read(process.argv[2]),a)))).catch(e=>{console.error(e.message);process.exitCode=1;});
