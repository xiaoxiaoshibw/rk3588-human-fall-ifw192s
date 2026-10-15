'use strict';
// Read-only instrumentation exposes existing internal match function in an isolated VM.
const fs=require('fs'),path=require('path'),Module=require('module'),zlib=require('zlib');
const ROOT=path.resolve(__dirname,'../..'),E=path.join(ROOT,'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1');
const jsdir=process.argv[2],{stream}=require('./js_diagnose');
const AB=require(path.join(ROOT,'sidequests/human_fusion_lab_next/real_fall/r04/background_ab'));
const source=fs.readFileSync(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'),'utf8');
const instrumented=new Module(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
instrumented._compile(source+'\nmodule.exports.diagnostic_match=_bg_match_rec;',instrumented.id);
const PL=instrumented.exports;PL.PIPE.ground_keep_below_m=-.25;
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
for(const sid of ['cap_20261013_094333','cap_20261010_180557']){
 const inputFolder=path.join(E,jsdir,sid),folder=path.join(inputFolder,'ledger_v2');fs.mkdirSync(folder,{recursive:false});
 const m=read(path.join(inputFolder,'MANIFEST.json')),s=stream(sid,m.R,m.t),r=stream(m.refsid,m.refR,m.refT,m.align);
 const lazy=new Proxy({length:m.FIT.length},{get:(o,k)=>k==='length'?o.length:r.frame(m.FIT[Number(k)]).buf});
 const map=PL.build_reference_map(lazy,{drop_ground:false}),keys=new Map([...map.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
 const ord=new Map([...keys.keys()].map((v,i)=>[v,i]));fs.writeFileSync(path.join(folder,'REFERENCE_KEYS.json'),JSON.stringify([...keys]),{flag:'wx'});
 const history=[],fd=fs.openSync(path.join(folder,'ledger_metadata.jsonl'),'wx');
 try{for(let fi=0;fi<m.frames;fi++){
  const c=s.frame(fi),online=PL.build_static_map(history.map(v=>v.buf)),onlineOrd=new Map([...online.keys()].map((k,i)=>[k,i]));
  // Existing match returns the actual first hit, including its original support record.
  const point=new Map(c.ids.map((i,j)=>[i,j])),n=c.frame.count_points,flags=new Uint16Array(n),nearest=new Int32Array(n*2);nearest.fill(-1);const distances=new Float32Array(n*2);distances.fill(Infinity);
  const stage=zlib.gunzipSync(fs.readFileSync(path.join(inputFolder,`${String(fi).padStart(4,'0')}_C_V2_DIAGNOSTIC.stage.gz`)));
  const keyFor=(map,hit)=>{if(!hit)return null;for(const [k,v] of map)if(v===hit)return k;throw Error('hit not member');};
  // WeakMap avoids scanning maps for every match while retaining exact returned record identity.
  const refIdentity=new WeakMap([...keys].map(([k,v])=>[v,k])),onIdentity=new WeakMap([...online].map(([k,v])=>[v,k]));
  for(let i=0;i<n;i++){
   const b=c.source_bytes,x=b.readFloatLE(i*28),y=b.readFloatLE(i*28+4),z=b.readFloatLE(i*28+8),intensity=b.readFloatLE(i*28+12),rad=Math.hypot(x,y,z);
   if(![x,y,z,intensity].every(Number.isFinite))flags[i]|=1;if(x===0&&y===0&&z===0)flags[i]|=2;if(rad<.35||rad>25)flags[i]|=4;
   const j=point.get(i);if(j===undefined)continue;
   const q=[c.buf[j*4],c.buf[j*4+1],c.buf[j*4+2]];if(q[2]<-.25)flags[i]|=8;if(q[2]>PL.PIPE.z_max_m)flags[i]|=16;
   const ref=PL.diagnostic_match(keys,...q),on=PL.diagnostic_match(online,...q),sup=on?PL.diagnostic_match(keys,on.x,on.y,on.z):null;
   if(ref){flags[i]|=32;nearest[i*2]=ord.get(refIdentity.get(ref));distances[i*2]=Math.hypot(ref.x-q[0],ref.y-q[1],ref.z-q[2]);}
   if(on){flags[i]|=64;nearest[i*2+1]=onlineOrd.get(onIdentity.get(on));distances[i*2+1]=Math.hypot(on.x-q[0],on.y-q[1],on.z-q[2]);}if(sup)flags[i]|=128;
   if(stage[i]===6 && !(ref||sup))throw Error('actual background predicate drift');
  }
  const prefix=path.join(folder,String(fi).padStart(4,'0'));fs.writeFileSync(prefix+'_overlap.gz',zlib.gzipSync(Buffer.from(flags.buffer)),{flag:'wx'});
  fs.writeFileSync(prefix+'_bg_evidence.gz',zlib.gzipSync(Buffer.concat([Buffer.from(nearest.buffer),Buffer.from(distances.buffer)])),{flag:'wx'});
  fs.writeSync(fd,JSON.stringify({sid,fi,source_frame:c.frame,source:m.source,R:m.R,t:m.t,reference_keys:'REFERENCE_KEYS.json',online_keys:[...online],past_frames:history.map(v=>({fi:v.fi,age_frames:fi-v.fi})),
   first_reason_file:`${String(fi).padStart(4,'0')}_C_V2_DIAGNOSTIC.stage.gz`,identity:'UNKNOWN',height_excluded_background_evidence:'COUNTERFACTUAL_NOT_ACTUAL'})+'\n');
  history.push({...c,fi});if(history.length>10)history.shift();if(fi%100===0)console.log('JS EVIDENCE',sid,fi);
 }
 const empty=[];
 for(const fi of m.HOLDOUT){
  const c=r.frame(fi),fg=PL.extract_foreground_fused(c.buf,keys,null),ids=AB.subset(c,fg.fg_xyzi);
  const clean=PL.cleanup_isolated_fg(fg.fg_xyzi),clusters=PL.cluster_voxels(PL.voxelize(clean.xyzi));
  const features=clusters.map(g=>PL.cluster_features(g)).filter(f=>f.ok);
  empty.push({fi,foreground:ids,cleanup_removed:clean.actually_removed_points,xy_clusters:clusters.length,
   geometry_human_candidates:features.filter(f=>PL.classify_human(f).label!=='NON_HUMAN').length,
   confirmed_events:'NOT_ENABLED',reference_fit_only:true});
 }
 fs.writeFileSync(path.join(folder,'EMPTY_HOLDOUT.json'),JSON.stringify({sid:m.refsid,frames:empty,FIT:m.FIT,source:m.reference}),{flag:'wx'});
 }finally{s.close();r.close();fs.closeSync(fd);}
 fs.writeFileSync(path.join(folder,'LEDGER_CODEBOOK.json'),JSON.stringify({source_record:'ordinal0..count-1; global_row=frame.offset_points+ordinal; bytes=global_row*28; opaque original bytes12..27',
  flags_bits:['NONFINITE','ZERO','RANGE','HEIGHT_LOW','HEIGHT_HIGH','REF_MATCH','ONLINE_MATCH','ONLINE_REF_SUPPORTED'],
  background_evidence:'int32[n,2] ref/online key ordinals then float32[n,2] distances; absent -1/Infinity; COUNTERFACTUAL outside actual reached domain',
  stages:'first reason file; later stages NOT_REACHED; XY classification and largest XYZ scoring are separate selectors; recovery NOT_APPLICABLE',
  streaming:'current source + <=10 past frames; full P diagnostic map was streaming array-like noncausal; no inference future'}),{flag:'wx'});
}
