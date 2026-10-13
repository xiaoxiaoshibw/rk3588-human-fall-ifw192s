'use strict';
// Converts new manual raw-row drafts to a bound local artifact; never repairs
// historical provenance by changing a SHA, never promotes a draft to reviewed GT.
const fs=require('fs'),path=require('path'),assert=require('assert'),D=require('./core/data_loader'),L=require('./core/leveling');
function validateDraft(doc,load){
 if(doc.schema!=='fusion_demo_v2/raw_row_draft/1'||!Array.isArray(doc.annotations))throw Error('draft schema');
 const sessions=new Map(),group=new Map();
 for(const a of doc.annotations){
  if(!/^cap_\d{8}_\d{6}$/.test(a.session_id))throw Error('invalid sid');
  if(!sessions.has(a.session_id))sessions.set(a.session_id,load(a.session_id));
  const s=sessions.get(a.session_id);
  if(a.session_sha256?.meta!==s.meta_sha256||a.session_sha256?.points!==s.points_sha256)throw Error('capture binding mismatch');
  if(!Number.isSafeInteger(a.frame_index)||a.frame_index<0||a.frame_index>=s.frames.length)throw Error('frame out of range');
  const f=s.frames[a.frame_index],ids=a.raw_point_indices;
  if(a.index_domain!=='raw_28B_row'||!Array.isArray(ids)||!ids.length||new Set(ids).size!==ids.length||!ids.every(i=>Number.isSafeInteger(i)&&i>=0&&i<f.n_points))throw Error('invalid raw indices');
  if(!ids.every(i=>[0,1,2].every(k=>Number.isFinite(f.xyzi[i*4+k]))))throw Error('invalid source points');
  if(a.source!=='human'||!['PERSON','FURNITURE','BACKGROUND','UNKNOWN'].includes(a.class_name)||a.review_status!=='DRAFT_UNREVIEWED')throw Error('source/class/review');
  if(a.class_name==='PERSON'&&(typeof a.track_id!=='string'||!a.track_id.trim()))throw Error('person track missing');
  const co=L.resolve_contract({meta:s.meta});
  if(JSON.stringify(co)!==JSON.stringify(a.coordinate_contract))throw Error('coordinate mismatch');
  const key=a.session_id+':'+a.frame_index,prev=group.get(key)||[];
  if(a.class_name==='PERSON'&&prev.some(p=>p.class_name==='PERSON'&&p.track_id===a.track_id))throw Error('duplicate person id in frame');
  const set=new Set(ids);if(prev.some(p=>p.raw_point_indices.some(i=>set.has(i))))throw Error('overlapping manual objects');
  prev.push(a);group.set(key,prev);
 }
 return {schema:'fusion_demo_v2/bound_manual_draft/1',trusted_gt:false,review_status:'DRAFT_UNREVIEWED',index_domain:'raw_28B_row',annotations:doc.annotations,bindings:Object.fromEntries(Array.from(sessions,([sid,s])=>[sid,{meta:s.meta_sha256,points:s.points_sha256}]))};
}
if(require.main===module){
 if(process.argv[2]==='--test'){
  const co={already_leveled:false,R:Array.from(L.REF_RT.R),T:Array.from(L.REF_RT.T)},s={meta:{},meta_sha256:'m',points_sha256:'p',frames:[{n_points:2,xyzi:Float32Array.from([1,1,1,1,2,2,2,2])}]};
  const a={session_id:'cap_20261010_180751',frame_index:0,session_sha256:{meta:'m',points:'p'},coordinate_contract:co,index_domain:'raw_28B_row',raw_point_indices:[0],source:'human',review_status:'DRAFT_UNREVIEWED',class_name:'PERSON',track_id:'P1'};
  const wrap=annotations=>({schema:'fusion_demo_v2/raw_row_draft/1',annotations});
  assert.equal(validateDraft(wrap([a]),()=>s).trusted_gt,false);
  for(const change of [{session_sha256:{points:'a'.repeat(64)}},{raw_point_indices:[2]},{frame_index:1},{review_status:'reviewed'},{raw_point_indices:[0,0]}])assert.throws(()=>validateDraft(wrap([{...a,...change}]),()=>s));
  assert.throws(()=>validateDraft(wrap([a,{...a,raw_point_indices:[1]}]),()=>s));console.log('ANNOTATION_BINDING_PASS');
 }else{
  if(!process.argv[2]||!process.argv[3])throw Error('Usage: node annotation_v2.js draft.json NEW-output.json');
  const root=path.resolve(__dirname,'../..'),doc=JSON.parse(fs.readFileSync(process.argv[2]));
  const result=validateDraft(doc,sid=>D.load_session(path.join(root,'captures/remote',sid)));
  fs.writeFileSync(process.argv[3],JSON.stringify(result,null,2),{flag:'wx'});console.log('Bound draft exported; trusted_gt=false');
 }
}
module.exports={validateDraft};
