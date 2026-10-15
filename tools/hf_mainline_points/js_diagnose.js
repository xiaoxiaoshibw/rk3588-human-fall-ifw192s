'use strict';
// Thin source-row adapter. All background/cleanup/XY clustering use frozen functions.
const fs=require('fs'),path=require('path'),zlib=require('zlib'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../..'), E=path.join(ROOT,'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1');
const JS_DIR=process.argv[2] || 'js';
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib'));
const AB=require(path.join(ROOT,'sidequests/human_fusion_lab_next/real_fall/r04/background_ab'));
const REG=require(path.join(ROOT,'pc_apps/human_replay/registration'));
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const write=(p,v)=>fs.writeFileSync(p,JSON.stringify(v),{flag:'wx'});
function stream(sid,R,t,alignment){
 const dir=path.join(ROOT,'captures/remote',sid),m=read(path.join(dir,'meta.json')),fd=fs.openSync(path.join(dir,'points.bin'),'r');
 if(fs.fstatSync(fd).size!==m.total_points*28)throw Error('source size');
 return {m,close:()=>fs.closeSync(fd),frame(fi){const f=m.frames[fi],b=Buffer.alloc(f.count_points*28);fs.readSync(fd,b,0,b.length,f.offset_points*28);const a=[],ids=[],initial=new Uint8Array(f.count_points);
 for(let k=0;k<f.count_points;k++){let q=[0,1,2].map(j=>b.readFloatLE(k*28+j*4));const intensity=b.readFloatLE(k*28+12),radius=Math.hypot(...q);
 if(!q.every(Number.isFinite)||!Number.isFinite(intensity)){initial[k]=1;continue;}if(q.every(v=>v===0)){initial[k]=2;continue;}if(radius<PL.PIPE.range_min_m||radius>PL.PIPE.range_max_m){initial[k]=3;continue;}
 q=R.map((r,i)=>r.reduce((s,v,j)=>s+v*q[j],0)+t[i]);if(alignment){const v=q;q=[0,1,2].map(i=>alignment.R.slice(i*3,i*3+3).reduce((s,x,j)=>s+x*v[j],0)+alignment.t[i]);}a.push(...q,intensity);ids.push(k);}
 return {buf:Float32Array.from(a),ids,initial,frame:f,source_bytes:b};}};
}
// An array-like view lets the unchanged full-P builder stream rather than cache a recording.
const lazy=(s,frames)=>new Proxy({length:frames.length},{get:(o,k)=>k==='length'?o.length:s.frame(frames[Number(k)]).buf});
function compare(a,b,label){if(a.length!==b.length||a.some((v,i)=>v!==b[i]))throw Error('member mismatch '+label);}
function nativeLedger(c,fg){
 const ids=AB.subset(c,fg.fg_xyzi),stage=Uint8Array.from(c.initial),clean=PL.cleanup_isolated_fg(fg.fg_xyzi),cleanids=AB.subset({buf:fg.fg_xyzi,ids},clean.xyzi);
 const keep=new Set(ids),ck=new Set(cleanids);for(let j=0;j<c.ids.length;j++){const i=c.ids[j],z=c.buf[j*4+2];stage[i]=z<PL.PIPE.ground_keep_below_m?4:z>PL.PIPE.z_max_m?5:!keep.has(i)?6:!ck.has(i)?7:8;}
 const clusters=PL.cluster_voxels(PL.voxelize(clean.xyzi)),voxelCluster=new Map();clusters.forEach((g,i)=>g.keys.forEach(k=>voxelCluster.set(k,i)));
 const eligible=clusters.map(g=>PL.cluster_features(g).ok);
 for(let j=0;j<cleanids.length;j++){const g=voxelCluster.get(PL.key_vox(clean.xyzi[j*4],clean.xyzi[j*4+1]));if(g!==undefined)stage[cleanids[j]]=eligible[g]?10:9;}
 if(stage.some(v=>v===0))throw Error('terminal conservation');
 return {ids,cleanids,stage,clusters:clusters.length,cleanup:clean.actually_removed_points};
}
function execute(sid,refsid,R,t,refR,refT,align){
 const s=stream(sid,R,t),r=stream(refsid,refR,refT,align),frames=s.m.frames.map((_,i)=>i),fit=r.m.frames.map((_,i)=>i).filter(i=>i%3===0);
 const folder=path.join(E,JS_DIR,sid);fs.mkdirSync(folder,{recursive:false});
 const refmaps={},fullmaps={};for(const h of [.1,-.25]){PL.PIPE.ground_keep_below_m=h;
  const map=PL.build_reference_map(lazy(r,fit));refmaps[h]=new Map([...map.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
  fullmaps[h]=PL.build_static_map(lazy(s,frames));}
 PL.PIPE.ground_keep_below_m=-.25;
 const originalRef=PL.build_reference_map(lazy(r,fit),{drop_ground:false});const originalKeys=new Map([...originalRef.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
 const oldpath=path.join(ROOT,'docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1',sid+'_ab_indices.jsonl');
 const old=fs.readFileSync(oldpath,'utf8').trim().split(/\r?\n/).map(JSON.parse);
 const fd=fs.openSync(path.join(folder,'members.jsonl'),'wx'),history=[];let rows=0;
 try {for(let fi=0;fi<frames.length;fi++){
  const c=s.frame(fi),causals={};for(const h of [.1,-.25]){PL.PIPE.ground_keep_below_m=h;causals[h]=PL.build_static_map(history.map(v=>v.buf));}
  const arms={};for(const build of [.1,-.25])for(const extract of [.1,-.25]){
   PL.PIPE.ground_keep_below_m=extract;const suffix=`b${build}_e${extract}`;
   arms['FULL_P_'+suffix]=PL.extract_foreground(c.buf,fullmaps[build]);arms['PAST10_P_'+suffix]=PL.extract_foreground(c.buf,causals[build]);
   arms['B_'+suffix]=PL.extract_foreground(c.buf,refmaps[build]);arms['C_'+suffix]=PL.extract_foreground_fused(c.buf,refmaps[build],causals[build]);
  }
  PL.PIPE.ground_keep_below_m=-.25;
  arms.A_P=PL.extract_foreground(c.buf,causals[-.25]);arms.B_FROZEN=PL.extract_foreground(c.buf,originalKeys);arms.C_V2_DIAGNOSTIC=PL.extract_foreground_fused(c.buf,originalKeys,causals[-.25]);
  const result={sid,frame:fi,t:c.frame.stamp_sec+c.frame.stamp_nanosec*1e-9,source_frame:c.frame,arms:{},native:{}};
  for(const [name,fg] of Object.entries(arms)){
   PL.PIPE.ground_keep_below_m=name.includes('_e0.1')?.1:-.25;
   const v=nativeLedger(c,fg);if(old[fi].arms[name])compare(v.ids,old[fi].arms[name],sid+'/'+fi+'/'+name);
   result.arms[name]=v.ids;result.native[name]={cleanup:v.cleanup,clusters:v.clusters,clean_count:v.cleanids.length};
   // Row ordinal is never replaced by coordinate deduplication.
   fs.writeFileSync(path.join(folder,`${String(fi).padStart(4,'0')}_${name}.stage.gz`),zlib.gzipSync(v.stage),{flag:'wx'});
  }
  fs.writeSync(fd,JSON.stringify(result)+'\n');rows++;
  history.push(c);if(history.length>10)history.shift();if(fi%100===0)console.log('JS',sid,fi);
 }}finally{fs.closeSync(fd);s.close();r.close();}
 write(path.join(folder,'MANIFEST.json'),{sid,refsid,source:REG.sessionBinding(ROOT,sid),reference:REG.sessionBinding(ROOT,refsid),R,t,refR,refT,align,
  frames:rows,FIT:fit,HOLDOUT:r.m.frames.map((_,i)=>i).filter(i=>i%3===2),range:'raw inclusive .35..25m; finite intensity required; transform then Float32',
  baseline:'A_P/B_FROZEN/C_V2_DIAGNOSTIC members exactly equal old source-row arrays; no cleanup in old AB scores',
  E1:'independent build height .1/-.25 x extraction .1/-.25; upper limit unchanged; all four contexts',
  FULL_P:'NONCAUSAL all-recording map, diagnostic only',past:'previous <=10 frames; bounded cache',
  codes:{1:'NONFINITE',2:'ZERO',3:'RANGE',4:'HEIGHT_LOW',5:'HEIGHT_HIGH',6:'BACKGROUND_MATCH',7:'ISOLATED_CLEANUP',8:'VOXEL_NOISE_MIN_CLUSTER',9:'CANDIDATE_QUALIFICATION',10:'ELIGIBLE_XY_CLUSTER_NOT_SELECTED_TARGET'},
  selection:'AB metrics use Python frozen XYZ largest cluster after foreground; native XY stages separate, no target/GT selection here',
  recovery:'NOT_APPLICABLE',unknown_identity:true});
}
if(require.main===module){const saved={...PL.PIPE};fs.mkdirSync(path.join(E,JS_DIR),{recursive:false});
 try{const old=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_02_r1');const a=read(path.join(old,'cap_20261013_094333_foreground.json')),b=read(path.join(old,'cap_20261013_131958_foreground.json'));
 execute(a.sid,b.sid,a.transform.R,a.transform.t,b.transform.R,b.transform.t,a.background.alignment);
 const cat=read(path.join(ROOT,'sidequests/human_fusion_lab_next/pointset/r01/output/catalog.json'));execute('cap_20261010_180557','cap_20261010_175227',cat.R,cat.T,cat.R,cat.T,null);
 }finally{Object.assign(PL.PIPE,saved);}}
module.exports={stream,nativeLedger};
