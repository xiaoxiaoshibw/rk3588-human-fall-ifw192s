"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=require('../../../../pc_apps/human_replay/registration'),PL=require('../../../../pc_apps/human_replay/human_pipe_lib'),M=require('../../../../pc_apps/human_replay/registration_method');
const dir=path.join(R.ROOT,'captures/registration/cap_20261002_223757__to__cap_20261004_203349');
const p=R.read(path.join(dir,'provenance.json')),r=R.read(path.join(dir,'registration.json')),d=R.read(path.join(dir,'diagnostics.json'));
const frames=b=>R.loadFrames(R.ROOT,b.sid,R.levelingBinding(R.ROOT,b.sid,p[b===p.source_session?'source_leveling':'reference_leveling'].job_id),true).frames;
const cur=frames(p.source_session),ref=frames(p.reference_session),online=PL.build_static_map(cur),refmap=PL.build_reference_map(ref);
const cf=M.fineStatic(cur,new Set([...online].filter(([,v])=>v.tier==='strong').map(([k])=>k)),.06);
const rf=M.fineStatic(ref,new Set([...refmap.voxels].filter(([,v])=>v.occ>=.9).map(([k])=>k)),.06);
M.estimateNormals(rf,.10);const idx=M.build_vox_index(rf,.10),coarse=M.build_vox_index([...refmap.voxels].filter(([,v])=>v.occ>=.5).map(([key,v])=>({key,...v})),.15);
const sc=M.PP_SCHED.at(-1),Rmat=r.rotation_row_major,t=r.translation_m,counts={NO_TARGET_WITHIN_008:0,NEAREST_TARGET_NO_NORMAL:0,RAW_CORRESPONDENCE:0};
const rows=[],distanceValues=[],eligible=[];
for(let i=0;i<cf.length;i++) {
    const s=cf[i],u=M.m3.apply(Rmat,s.x,s.y,s.z).map((v,j)=>v+t[j]);
    const hit=M.nn_query(idx,...u,sc.inlier),near=M.nn_query(idx,...u,.30),co=M.nn_query(coarse,...u,.30);
    const reason=!hit?'NO_TARGET_WITHIN_008':hit.rec.nx===null?'NEAREST_TARGET_NO_NORMAL':'RAW_CORRESPONDENCE';counts[reason]++;
    if(near)distanceValues.push(near.d);
    const residual=hit&&hit.rec.nx!==null?Math.abs(hit.rec.nx*(u[0]-hit.rec.x)+hit.rec.ny*(u[1]-hit.rec.y)+hit.rec.nz*(u[2]-hit.rec.z)):null;
    if(reason==='RAW_CORRESPONDENCE')eligible.push({i,residual});
    rows.push({i,source:[s.x,s.y,s.z],registered_xyz:u,sample_support_points:s.n,reason,
        nearest_fine_within_030_m:near?{distance:near.d,normal_valid:near.rec.nx!==null,xyz:[near.rec.x,near.rec.y,near.rec.z]}:null,
        nearest_reference_occ05_within_030_m:co?{distance:co.d,occ:co.rec.occ,key:co.rec.key}:null,
        abs_point_to_plane_residual:residual,semantic_cause:'UNKNOWN'});
}
eligible.sort((a,b)=>a.residual-b.residual);const n=Math.max(30,Math.floor(eligible.length*sc.keep)),kept=new Set(eligible.slice(0,n).map(v=>v.i));
for(const v of rows)v.trim_status=kept.has(v.i)?'KEPT':v.reason==='RAW_CORRESPONDENCE'?'TRIMMED':'NO_PAIR';
assert.equal(cf.length,d.support.n_static_source);assert.equal(rf.length,d.support.n_static_target);assert.equal(n,d.support.n_correspondence);
assert.equal(n/cf.length,d.support.inlier_ratio);
const requiredKeep=Math.ceil(cf.length*R.PROFILE.bands.inlier_ratio[1]),requiredRaw=Math.ceil(requiredKeep/sc.keep);
const gap={ratio:n/cf.length,ratio_percent:100*n/cf.length,gap_percentage_points:100*(.5-n/cf.length),
    current_keep:n,required_keep:requiredKeep,additional_keep:requiredKeep-n,current_raw:eligible.length,required_raw:requiredRaw,additional_raw:requiredRaw-eligible.length};
const misses=rows.filter(v=>v.reason!=='RAW_CORRESPONDENCE');
const supportMiss={within_030:misses.filter(v=>v.nearest_fine_within_030_m).length,
    no_fine_within_030:misses.filter(v=>!v.nearest_fine_within_030_m).length,
    occ05_near_012:misses.filter(v=>v.nearest_reference_occ05_within_030_m?.distance<.12).length,
    no_occ05_within_030:misses.filter(v=>!v.nearest_reference_occ05_within_030_m).length,
    boundary_079_to_081:rows.filter(v=>v.nearest_fine_within_030_m&&Math.abs(v.nearest_fine_within_030_m.distance-.08)<=.001).length};
const bySector=Array.from({length:8},(_,sector)=>({sector,source:0,raw:0,kept:0}));
for(const v of rows){const sector=Math.min(7,Math.floor((Math.atan2(v.source[1],v.source[0])+Math.PI)/(Math.PI/4)));bySector[sector].source++;if(v.reason==='RAW_CORRESPONDENCE')bySector[sector].raw++;if(v.trim_status==='KEPT')bySector[sector].kept++;}
const supportPoints=cf.map(v=>v.n).sort((a,b)=>a-b),q=(a,p)=>a[Math.ceil(a.length*p)-1];
const result={frozen:true,artifact_id:R.shaFile(path.join(dir,'registration.json')),params:{source_fine_cell:.06,target_fine_cell:.06,normals_radius:.10,correspondence_radius:sc.inlier,trim_keep:sc.keep,gate_pass:.5},
    source:cf.length,target:rf.length,target_normal_valid:rf.filter(v=>v.nx!==null).length,counts,gap,supportMiss,bySector,
    source_point_support:{min:supportPoints[0],p50:q(supportPoints,.5),p90:q(supportPoints,.9),max:supportPoints.at(-1)},
    nearest_fine_distance_within_030_stats:R.residualStats(distanceValues),recorded_residual:d.residual,recorded_geometry:d.geometry,
    hypotheses:{correspondence_coverage:'MEASURED',reference_map_coverage:'coarse/fine threshold coverage measured; unobserved physical surfaces UNKNOWN',
        dynamic_contamination:'UNKNOWN: source strong occupancy is not human/static GT',occlusion:'UNKNOWN: no paired visibility/ray GT',
        FOV_difference:'sector and missing target support measured; physical FOV cause UNKNOWN',
        leveling_registration_residual:'MEASURED residual only; no transform change/refit',voxel_discretization:'fixed bins and boundary proximity measured; causal intervention NOT_RUN',
        sample_support:'MEASURED finite support, no statistical independence assumed'},
    verdict:'real finite correspondence-support shortfall close to the configured boundary; no evidence of PASS and no valid confidence interval proving statistical equivalence',rows};
fs.writeFileSync(path.join(__dirname,'07_gate_samples.json'),R.serialize(result),{flag:'wx'});
console.log(JSON.stringify({source:cf.length,target:rf.length,counts,gap,supportMiss,bySector},null,2));
