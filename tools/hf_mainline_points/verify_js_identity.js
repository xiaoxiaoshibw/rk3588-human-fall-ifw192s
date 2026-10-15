'use strict';
// Source identity travels as loop ordinals. XYZ comparison is only an equivalence check.
const fs=require('fs'),path=require('path'),Module=require('module'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../..'),E=path.join(ROOT,'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1');
const {stream}=require('./js_diagnose'),read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const filename=path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js');const original=fs.readFileSync(filename,'utf8');let source=original;
function instrument(name,next,fn){const start=source.indexOf('function '+name+'('),end=source.indexOf('function '+next+'(',start);if(start<0||end<0)throw Error('instrument boundary');source=source.slice(0,start)+fn(source.slice(start,end))+source.slice(end);}
function replaceOnce(s,a,b){if(!s.includes(a)||s.indexOf(a)!==s.lastIndexOf(a))throw Error('instrument anchor '+a);return s.replace(a,b);}
instrument('extract_foreground','_bg_match_rec',s=>{
 s=replaceOnce(s,'var out = [], n_in','var diagnostic_source_ordinals = [], out = [], n_in');
 s=replaceOnce(s,'out.push(x, y, z, i);','out.push(x, y, z, i); diagnostic_source_ordinals.push(k / 4);');
 return replaceOnce(s,'return { vox_fg:','return { diagnostic_source_ordinals: diagnostic_source_ordinals, vox_fg:');});
instrument('extract_foreground_fused','cleanup_isolated_fg',s=>{
 s=replaceOnce(s,'var out = [], n_in','var diagnostic_source_ordinals = [], out = [], n_in');
 s=replaceOnce(s,'out.push(x, y, z, i);','out.push(x, y, z, i); diagnostic_source_ordinals.push(k / 4);');
 return replaceOnce(s,'return { fg_xyzi:','return { diagnostic_source_ordinals: diagnostic_source_ordinals, fg_xyzi:');});
instrument('cleanup_isolated_fg','cluster_voxels',s=>{
 s=replaceOnce(s,'var before = xyzi.length / 4;','var before = xyzi.length / 4; var diagnostic_source_ordinals = Array.from({length:before},function(_,i){return i;});');
 s=replaceOnce(s,'out = [];','out = []; diagnostic_source_ordinals = [];');
 s=replaceOnce(s,'out.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]);','out.push(xyzi[i], xyzi[i + 1], xyzi[i + 2], xyzi[i + 3]); diagnostic_source_ordinals.push(i / 4);');
 return replaceOnce(s,'return { xyzi:','return { diagnostic_source_ordinals: diagnostic_source_ordinals, xyzi:');});
const moduleCopy=new Module(filename);moduleCopy._compile(source,filename);const PL=moduleCopy.exports;
const ordinary=require(filename);const equal=(a,b,label)=>{if(a.length!==b.length||a.some((v,i)=>v!==b[i]))throw Error('identity/equivalence drift '+label);};
function verify(c,fg,expected,label){
 const ids=fg.diagnostic_source_ordinals.map(i=>c.ids[i]);equal(ids,expected,label);
 const cleaned=PL.cleanup_isolated_fg(fg.fg_xyzi),normal=ordinary.cleanup_isolated_fg(fg.fg_xyzi);
 equal(Array.from(cleaned.xyzi),Array.from(normal.xyzi),label+'/cleanup');
 const cleanids=cleaned.diagnostic_source_ordinals.map(i=>ids[i]);if(new Set(cleanids).size!==cleanids.length)throw Error('identity merged');
 return cleanids.length;
}
// SYNTHETIC duplicate XYZ and duplicate XYZI preserve distinct source identities.
PL.PIPE.ground_keep_below_m=-.25;ordinary.PIPE.ground_keep_below_m=-.25;
const duplicate={buf:new Float32Array([1,1,1,2,1,1,1,2]),ids:[7,11]};const dup=PL.extract_foreground(duplicate.buf,null);equal(dup.diagnostic_source_ordinals.map(i=>duplicate.ids[i]),[7,11],'SYNTHETIC duplicate identity');
const results=[];
for(const sid of ['cap_20261013_094333','cap_20261010_180557']){
 const folder=path.join(E,'js_02',sid),m=read(path.join(folder,'MANIFEST.json')),s=stream(sid,m.R,m.t),r=stream(m.refsid,m.refR,m.refT,m.align);
 const lazy=(stream,frames)=>new Proxy({length:frames.length},{get:(o,k)=>k==='length'?o.length:stream.frame(frames[Number(k)]).buf});
 const all=s.m.frames.map((_,i)=>i),refs={},full={};for(const h of [.1,-.25]){PL.PIPE.ground_keep_below_m=h;const map=PL.build_reference_map(lazy(r,m.FIT));refs[h]=new Map([...map.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));full[h]=PL.build_static_map(lazy(s,all));}
 PL.PIPE.ground_keep_below_m=-.25;const ref=PL.build_reference_map(lazy(r,m.FIT),{drop_ground:false});const keys=new Map([...ref.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
 const lines=fs.readFileSync(path.join(folder,'members.jsonl'),'utf8').trim().split(/\r?\n/);const history=[];let arms=0,records=0,cleanrecords=0;
 try{for(let fi=0;fi<all.length;fi++){
  const c=s.frame(fi),old=JSON.parse(lines[fi]),causal={};for(const h of [.1,-.25]){PL.PIPE.ground_keep_below_m=h;causal[h]=PL.build_static_map(history.map(v=>v.buf));}
  const out={};for(const b of [.1,-.25])for(const e of [.1,-.25]){PL.PIPE.ground_keep_below_m=e;const suffix=`b${b}_e${e}`;
   out['FULL_P_'+suffix]=PL.extract_foreground(c.buf,full[b]);out['PAST10_P_'+suffix]=PL.extract_foreground(c.buf,causal[b]);
   out['B_'+suffix]=PL.extract_foreground(c.buf,refs[b]);out['C_'+suffix]=PL.extract_foreground_fused(c.buf,refs[b],causal[b]);}
  PL.PIPE.ground_keep_below_m=-.25;out.A_P=PL.extract_foreground(c.buf,causal[-.25]);out.B_FROZEN=PL.extract_foreground(c.buf,keys);out.C_V2_DIAGNOSTIC=PL.extract_foreground_fused(c.buf,keys,causal[-.25]);
  for(const [name,fg] of Object.entries(out)){PL.PIPE.ground_keep_below_m=name.includes('_e0.1')?.1:-.25;ordinary.PIPE.ground_keep_below_m=PL.PIPE.ground_keep_below_m;cleanrecords+=verify(c,fg,old.arms[name],sid+'/'+fi+'/'+name);arms++;}
  records+=c.frame.count_points;history.push(c);if(history.length>10)history.shift();if(fi%100===0)console.log('JS ORDINAL ID',sid,fi);
 }}finally{s.close();r.close();}
 results.push({sid,frames:all.length,arms_frames:arms,raw_source_records:records,clean_member_records:cleanrecords,all_source_member_sets_equal:true});
}
fs.writeFileSync(path.join(E,'JS_ORDINAL_IDENTITY_PROOF.json'),JSON.stringify({source_sha256:crypto.createHash('sha256').update(original).digest('hex'),instrumentation_sha256:crypto.createHash('sha256').update(source).digest('hex'),
 meaning:'Source identity carried by original loop input ordinal, not XYZ lookup; old coordinate-ordered mapper used only for equivalence; all19 arms and cleanup checked.',synthetic_duplicate_ids:[7,11],results}),{flag:'wx'});
