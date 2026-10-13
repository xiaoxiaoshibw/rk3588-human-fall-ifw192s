'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../../../..'),OUT=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_02_r1');
const OLD=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_01_r1');
const D=require('../../../human_fusion_lab/core/data_loader'),L=require('../../../human_fusion_lab/core/leveling');
const P=require('../../../../pc_apps/human_replay/human_pipe_lib');
const SID='cap_20261013_094333',REF='cap_20261013_131958';
const reports=[JSON.parse(fs.readFileSync(path.join(OLD,SID+'_leveling.json'))),JSON.parse(fs.readFileSync(path.join(OUT,REF+'_leveling.json')))];
const loaded=[D.load_session(path.join(ROOT,'captures/remote',SID)),D.load_session(path.join(ROOT,'captures/remote',REF))];
const frames=loaded.map((s,i)=>{
 const r=reports[i];if(!r.recommended)throw Error('NO_RECOMMENDATION '+r.sid);
 if(s.meta_sha256!==r.source.meta_sha256||s.points_sha256!==r.source.bin_sha256)throw Error('SHA mismatch');
 const rt=r.estimators[r.recommended];
 return s.frames.map(f=>{const p=L.level_frame(f.xyzi,rt.R.flat(),rt.t,false);
  // Preserve source point ordinals. Invalid/zero raw input never becomes foreground after translation.
  for(let k=0;k<p.length;k+=4)if(!Number.isFinite(f.xyzi[k]+f.xyzi[k+1]+f.xyzi[k+2])||!(f.xyzi[k]||f.xyzi[k+1]||f.xyzi[k+2]))p[k]=p[k+1]=p[k+2]=NaN;
  return p;});
});
const REG=require('../../../../pc_apps/human_replay/registration_method');
const outside=p=>{const a=[];for(let k=0;k<p.length;k+=4){const x=p[k],y=p[k+1],z=p[k+2];
 if(!Number.isFinite(x+y+z)||x<-.5||x>6||Math.abs(y)>3||z<.1||z>2.5)continue;
 if(x>=.2&&x<=2.7&&y>=.1&&y<=2.3)continue;a.push(x,y,z,p[k+3]);}return Float32Array.from(a);};
const fitTarget=P.build_static_map(frames[0].slice(0,5).map(outside));
const fitRef=P.build_reference_map(frames[1].map(outside));
const icp=REG.fixedICP(fitTarget,fitRef);
const angle=Math.acos(Math.max(-1,Math.min(1,(icp.R[0]+icp.R[4]+icp.R[8]-1)/2)))*180/Math.PI;
const movement=Math.hypot(...icp.t);
const rigidOk=icp.n_src>=100&&icp.n_tgt>=100&&icp.iters>0&&Number.isFinite(angle)&&angle<=5&&movement<=.30;
fs.writeFileSync(path.join(OUT,'REFERENCE_ICP.json'),JSON.stringify({...icp,angle_deg:angle,translation_m:movement,rigidOk,
 old_saved_pass_not_current_gate:true,fit_active_frames:[0,1,2,3,4],holdout_active_frames:[5,10],excluded_activity_xy:[.2,2.7,.1,2.3]},null,2),{flag:'wx'});
if(!rigidOk)throw Error('rigid alignment gate failed');
const alignedRef=frames[1].map(p=>L.level_frame(p,icp.R,icp.t,false));
const ref=P.build_reference_map(alignedRef);const keys=new Map();ref.voxels.forEach((r,k)=>{if(r.occ>=.5)keys.set(k,r);});
function finiteWorkspace(p){const a=[];for(let k=0;k<p.length;k+=4)if(Number.isFinite(p[k]+p[k+1]+p[k+2])&&p[k+2]>=.1&&p[k+2]<=2.5)a.push(p[k],p[k+1],p[k+2],p[k+3]);return new Float32Array(a);}
let staticN=0,staticFG=0;const alignment=[];
for(const fi of [0,5,10]){const p=frames[0][fi],a=[];
 for(let k=0;k<p.length;k+=4){const x=p[k],y=p[k+1],z=p[k+2];
  if(!Number.isFinite(x+y+z)||x<-.5||x>6||Math.abs(y)>3||z<.1||z>2.5)continue;
  if(x>=.2&&x<=2.7&&y>=.1&&y<=2.3)continue; // exclude visually observed activity zone, diagnostic only
  a.push(x,y,z,p[k+3]);}
 const clean=Float32Array.from(a),fg=P.extract_foreground(clean,keys).fg_xyzi;
 staticN+=clean.length/4;staticFG+=fg.length/4;alignment.push({frame:fi,static_points:clean.length/4,unmatched:fg.length/4});
}
const match=1-staticFG/staticN;
const registration={kind:'static_region_overlap_probe',mask_xy:[.2,2.7,.1,2.3],frames:alignment,matched_fraction:match,
 gate_min:.7,gate_basis:'preregistered coarse reference compatibility screen, not physical registration accuracy',passed:staticN>100&&match>=.7&&alignment.slice(1).every(r=>1-r.unmatched/r.static_points>=.7),
 source_active:reports[0].source,source_reference:reports[1].source,physical_verified:false};
fs.writeFileSync(path.join(OUT,'REFERENCE_COMPATIBILITY_ALIGNED.json'),JSON.stringify(registration,null,2),{flag:'wx'});
if(!registration.passed)throw Error('Reference static overlap BLOCKED: '+match);
for(let session=0;session<2;session++){
 const sid=session?REF:SID,parts=[],rowParts=[],meta=[];let offset=0;
 const sessionFrames=session?alignedRef:frames[0];
 for(let i=0;i<sessionFrames.length;i++){
  const p=sessionFrames[i],fg=P.extract_foreground(finiteWorkspace(p),keys).fg_xyzi;
  let j=0;const rows=[];
  for(let k=0;k<p.length&&j<fg.length;k+=4)if(p[k]===fg[j]&&p[k+1]===fg[j+1]&&p[k+2]===fg[j+2]){rows.push(k/4);j+=4;}
  if(j!==fg.length)throw Error('rows mismatch');
  parts.push(Buffer.from(fg.buffer));rowParts.push(Buffer.from(Uint32Array.from(rows).buffer));
  meta.push({frame:i,t:loaded[session].meta.frames[i].bag_time_sec-loaded[session].meta.frames[0].bag_time_sec,offset,count:rows.length});offset+=rows.length;
 }
 const data=Buffer.concat(parts),rows=Buffer.concat(rowParts),rt=reports[session].estimators[reports[session].recommended];
 const manifest={sid,source:reports[session].source,frames:meta,transform:{R:rt.R,t:rt.t,reference_alignment:session?{R:icp.R,t:icp.t}:null},background:{kind:'user_designated_empty_scene',sid:REF,source:reports[1].source,alignment:{R:icp.R,t:icp.t},
  frames:frames[1].length,keys:keys.size,occupancy:.5,match_radius:.12,ground_min:.1,physical_stationarity_verified:false,compatibility:registration},
  data_sha256:crypto.createHash('sha256').update(data).digest('hex'),rows_sha256:crypto.createHash('sha256').update(rows).digest('hex')};
 fs.writeFileSync(path.join(OUT,sid+'_foreground.bin'),data,{flag:'wx'});fs.writeFileSync(path.join(OUT,sid+'_source_rows.bin'),rows,{flag:'wx'});
 fs.writeFileSync(path.join(OUT,sid+'_foreground.json'),JSON.stringify(manifest,null,2),{flag:'wx'});
 console.log(sid,meta.length,'frames',offset,'FG; reference match',match);
}
