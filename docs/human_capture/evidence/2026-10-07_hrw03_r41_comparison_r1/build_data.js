"use strict";
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const old=path.resolve(__dirname,'../2026-10-07_hrw03_r39_closeout');
const read=n=>JSON.parse(fs.readFileSync(path.join(old,n),'utf8'));
const shadow=read('06_shadow_results.json'),points=read('01_absorbed_points.json'),attr=read('03_confirmation_attribution_r2.json');
const manifest=JSON.parse(fs.readFileSync(path.join(old,'09_viewer_manifest.js'),'utf8').replace(/^window.HR_MANIFEST=/,'').trim().replace(/;$/,''));
const compact=c=>({n:c.n,cx:c.cx,cy:c.cy,cz:c.cz,zmin:c.zmin,height:c.height_m,width:c.width_m,depth:c.depth_m,radius:c.radius_m,
    upcos:c.upcos,joint:c.joint,confirmed:c.track_confirmed,track:c.track_id,cv:c.evidence.spread_cv,reasons:c.reasons});
const frames=shadow.P.frames.map((p,i)=>({frame:i,P:{pre:p.fg_before_cleanup,post:p.fg_after_cleanup,clusters:p.clusters.map(compact),tracks:p.tracks.map(t=>({id:t.id,votes:t.votes,confirmed:t.human_confirmed}))},
    S:{pre:shadow.S.frames[i].fg_before_cleanup,post:shadow.S.frames[i].fg_after_cleanup,clusters:shadow.S.frames[i].clusters.map(compact),tracks:shadow.S.frames[i].tracks.map(t=>({id:t.id,votes:t.votes,confirmed:t.human_confirmed}))},
    topology:shadow.topology.frames[i],loss:points.points.filter(p=>p.frame===i).map(p=>({id:p.id,index:p.original_point_index,xyz:p.source_xyz,mechanism:p.mechanism})),
    changes:attr.rows.filter(p=>p.frame===i).map(p=>({id:p.id,change:p.change,category:p.attribution_category,Pidx:p.Pidx,Sidx:p.Sidx,shared:p.shared_points,lost:p.points_lost_from_matched_cluster,gained:p.points_gained_in_matched_cluster,semantic:p.semantic_GT}))}));
assert.equal(frames.length,165);assert.equal(manifest.frames.length,153);assert.equal(frames.reduce((n,f)=>n+f.loss.length,0),31);
const used=['06_shadow_results.json','01_absorbed_points.json','03_confirmation_attribution_r2.json','09_viewer_manifest.js'];
for(const f of manifest.frames){const name='viewer_frames/f'+f.frame+'.js';assert(fs.existsSync(path.join(old,name)));used.push(name);}
const sha=f=>crypto.createHash('sha256').update(fs.readFileSync(f)).digest('hex');
const data={source:'diagnostic',session:points.session,artifact_id:points.registration_artifact_id,
    available:manifest.frames.map(f=>({frame:f.frame,seq:f.seq,count:f.point_count})),frames,counts:shadow.counts,gate:shadow.registration.gate,
    transform:shadow.registration.transform,scope:'R39 frozen offline P/S outputs. Proposed R40 fixes were NOT implemented. Local clouds are evidence crops, full-session counts shown separately.',
    input_binding:{source_session:points.source_session,source_leveling:points.source_leveling},source_sha256:Object.fromEntries(used.map(f=>[f,sha(path.join(old,f))]))};
fs.writeFileSync(path.join(__dirname,'comparison_data.js'),'window.COMPARE_DATA='+JSON.stringify(data)+';\n',{flag:'wx'});
fs.writeFileSync(path.join(__dirname,'01_data_binding.json'),JSON.stringify({source:'diagnostic',input_files:data.source_sha256,session:points.session,artifact_id:points.registration_artifact_id,frames:165,local_frames:153,points:31,ponytail:'C:/Users/30680/.codex/skills/ponytail/SKILL.md'},null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({frames:165,local_frames:153,clean_loss:31,source_files:used.length,bytes:fs.statSync(path.join(__dirname,'comparison_data.js')).size,checks:'PASS'}));
