'use strict';
// ponytail: startup background with an explicit visually excluded target box;
// not an empty-scene reference or a general automatic person detector.
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../../../..');
const OUT=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_01_r1');
const D=require('../../../human_fusion_lab/core/data_loader');
const L=require('../../../human_fusion_lab/core/leveling');
const P=require('../../../../pc_apps/human_replay/human_pipe_lib');
const sid=process.argv[2]||'cap_20261013_094333';
const report=JSON.parse(fs.readFileSync(path.join(OUT,sid+'_leveling.json')));
if(!report.recommended)throw Error('No offline recommendation');
const rt=report.estimators[report.recommended];
const s=D.load_session(path.join(ROOT,'captures/remote',sid));
if(s.meta_sha256!==report.source.meta_sha256||s.points_sha256!==report.source.bin_sha256)throw Error('Source SHA changed');
const leveled=s.frames.map(f=>L.level_frame(f.xyzi,rt.R.flat(),rt.t,false));
const exclusion=[1.4,2.6,1.25,2.2];
const bgFrames=leveled.slice(0,10).map(p=>{
 const out=[];for(let k=0;k<p.length;k+=4){const x=p[k],y=p[k+1];
 if(x>=exclusion[0]&&x<=exclusion[1]&&y>=exclusion[2]&&y<=exclusion[3])continue;
 if(!Number.isFinite(x+y+p[k+2])||(x===0&&y===0&&p[k+2]===0))continue;
 out.push(p[k],p[k+1],p[k+2],p[k+3]);}return new Float32Array(out);
});
const ref=P.build_reference_map(bgFrames);
const keys=new Map();ref.voxels.forEach((r,k)=>{if(r.occ>=.5)keys.set(k,r);});
const chunks=[],rowChunks=[],frames=[];let offset=0;
for(let i=0;i<leveled.length;i++){
 const p=leveled[i],fg=P.extract_foreground(p,keys).fg_xyzi;
 const kept=[],rows=[];let j=0;
 for(let k=0;k<p.length && j<fg.length;k+=4){
  if(p[k]===fg[j]&&p[k+1]===fg[j+1]&&p[k+2]===fg[j+2]){
   if(Number.isFinite(p[k]+p[k+1]+p[k+2])&&(p[k]!==0||p[k+1]!==0||p[k+2]!==0)){
    kept.push(p[k],p[k+1],p[k+2],p[k+3]);rows.push(k/4);
   }j+=4;
  }
 }
 if(j!==fg.length)throw Error('Source-row alignment failure');
 const data=Float32Array.from(kept),ids=Uint32Array.from(rows);
 chunks.push(Buffer.from(data.buffer));rowChunks.push(Buffer.from(ids.buffer));
 frames.push({frame:i,t:s.meta.frames[i].bag_time_sec-s.meta.frames[0].bag_time_sec,offset,count:ids.length});offset+=ids.length;
}
const data=Buffer.concat(chunks),rows=Buffer.concat(rowChunks);
const manifest={sid,source:report.source,transform:{R:rt.R,t:rt.t},frames,
 background:{kind:'first_10_frames_target_excluded_startup',frame_indices:[0,1,2,3,4,5,6,7,8,9],exclusion_xy:exclusion,
 exclusion_source:'assistant visual inference from leveled contact sheets; NOT HUMAN GT',empty_verified:false,keys:keys.size,
 occupancy:.5,match_radius:P.PIPE.bg_match_radius,ground_min:P.PIPE.ground_keep_below_m,
 limitation:'masked furniture remains possible; no full-session self-background; target moves through mask'},
 data_sha256:crypto.createHash('sha256').update(data).digest('hex'),rows_sha256:crypto.createHash('sha256').update(rows).digest('hex')};
fs.writeFileSync(path.join(OUT,sid+'_foreground.bin'),data,{flag:'wx'});
fs.writeFileSync(path.join(OUT,sid+'_source_rows.bin'),rows,{flag:'wx'});
fs.writeFileSync(path.join(OUT,sid+'_foreground.json'),JSON.stringify(manifest,null,2),{flag:'wx'});
console.log(JSON.stringify({sid,frames:frames.length,foreground_points:offset,background_keys:keys.size}));
