"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert');
const R=require('../../../../pc_apps/human_replay/registration'),PL=require('../../../../pc_apps/human_replay/human_pipe_lib');
const H=require('../2026-10-07_hrw03_r39_closeout/audit_lib');
const read=n=>R.read(path.join(__dirname,n)),write=(n,v)=>fs.writeFileSync(path.join(__dirname,n),R.serialize(v),{flag:'wx'});
const saved=R.read(path.join(__dirname,'../2026-10-07_hrw03_r39_closeout/06_shadow_results.json'));
const trace=read('04_tracker_reproduction_and_trace.json');
// First diagnostic retained a live votes array in collision.final_votes. Correct
// that derived field from immutable saved frame snapshots; all trace rows unchanged.
for(const name of ['P','S'])for(const c of trace[name].collisions) {
    c.final_votes=saved[name].frames[c.frame].tracks.find(v=>v.id===c.track).votes.slice();
    assert.deepEqual(c.final_votes,c.assignments.at(-1).votes);
}
trace.supersedes='04_tracker_reproduction_and_trace.json collision.final_votes only; original output and run retained';
const fake=joint=>({ok:true,cx:1,cy:0,cz:1,height_m:1.7,upcos:1,n:100,label:'HUMAN_CANDIDATE',joint});
const tr=new PL.Tracker();tr.tick(0,[fake('CONFIRMED_HUMAN')]);tr.tick(1,[fake('CONFIRMED_HUMAN')]);
for(let f=2;f<=8;f++)tr.tick(f,[]);const last=[fake('CONFIRMED_HUMAN')];tr.tick(9,last);
assert.equal(last[0].track_confirmed,true);assert.deepEqual(tr.tracks[0].pose_history.map(v=>v.f),[0,1,9]);
trace.missing_frame_reproduction={source:'synthetic',bug:'BUG-R40-T02 votes are last five observations, not last five frames; missed frames do not age votes',positive_frames:[0,1,9],recent_five_frame_positive_count:1,actual_confirmed:last[0].track_confirmed,track:tr.tracks[0]};
const missed=[];
for(const name of ['P','S'])for(const fr of saved[name].frames)for(const t of fr.tracks) {
    if(!t.pose_history?.length)continue;
    const last5=t.pose_history.slice(-5).map(v=>v.f);if(new Set(last5).size!==last5.length||Math.max(...last5)-Math.min(...last5)>4)missed.push({branch:name,frame:t.last_seen,track:t.id,vote_frame_indices:last5,votes:t.votes,confirmed:t.human_confirmed,lost:t.lost});
}
trace.real_vote_window_anomalies=[...new Map(missed.map(v=>[v.branch+':'+v.frame+':'+v.track,v])).values()];
write('04_tracker_reproduction_and_trace_r2.json',trace);

const cases=read('03_topology_point_cases.json'),decomp=[];
function partition(rows,coord,predicate) {
    const points=rows.filter(predicate),buf=new Float32Array(points.flatMap(p=>[...p[coord],0]));
    const cs=PL.cluster_voxels(PL.voxelize(buf)).filter(v=>v.acc.n>=PL.PIPE.human_n_min),ids=cs.map(()=>new Set()),owner=new Map();
    cs.forEach((c,i)=>c.keys.forEach(k=>owner.set(k,i)));for(const p of points){const ci=owner.get(PL.key_vox(p[coord][0],p[coord][1]));if(ci!==undefined)ids[ci].add(p.point_index);}
    assert(ids.every((v,i)=>v.size===cs[i].acc.n));return {cs,ids};
}
for(const fr of cases.frames) {
    // Use all point rows that belong to either output cluster. Q deliberately
    // excludes P small/noneligible components; this makes pure-grid effect on
    // exactly the compared candidate identities explicit, not a full pipeline.
    const P=fr.P.map(c=>new Set(c.point_indices)),S=fr.S.map(c=>new Set(c.point_indices));
    const Q=partition(fr.points,'registered_xyz',p=>p.P.cluster!==null);
    const U=partition(fr.points,'registered_xyz',p=>p.S.foreground);
    const unionP=new Set(P.flatMap(v=>[...v])),unionS=new Set(S.flatMap(v=>[...v]));
    const removed=fr.points.filter(p=>unionP.has(p.point_index)&&!unionS.has(p.point_index));
    const mechanisms={};for(const p of removed)mechanisms[p.mechanism]=(mechanisms[p.mechanism]??0)+1;
    decomp.push({frame:fr.frame,P_to_Q_grid_only:H.topology(P,Q.ids),Q_to_S_actual_membership:H.topology(Q.ids,S),
        S_precleanup_to_S_postcleanup:H.topology(U.ids,S),
        Q_clusters:Q.cs.map((c,i)=>({cluster:i,point_count:c.acc.n,point_indices:[...Q.ids[i]],geometry:PL.cluster_features(c)})),
        removed_from_all_S_candidates:removed.length,removed_mechanisms:mechanisms,
        reference_removed_by_source_band:removed.filter(p=>p.mechanism==='REFERENCE').reduce((o,p)=>{const b=p.source_xyz[2]<.3?'below_0.3':p.source_xyz[2]<.6?'0.3_0.6':p.source_xyz[2]<1.2?'0.6_1.2':'above_1.2';o[b]=(o[b]??0)+1;return o;},{}),
        added_to_S_candidates:fr.points.filter(p=>!unionP.has(p.point_index)&&unionS.has(p.point_index)).length,
        boundary:'Q transforms only P output-eligible candidate points without removal or new points. U uses stored union-of-candidate point context; not all tiny foreground components. Diagnostic partitions, no production or semantic identity.'});
}
write('03_topology_stage_decomposition.json',{source:'diagnostic',rows:decomp});
const zero=read('04_zero_xyz_reproduction.json');
for(const side of zero.rows){const job=read('00_inputs_sources_params.json').input_binding[side.side+'_leveling'].job_id;
    const report=R.read(path.join(R.ROOT,'captures/leveled',job,'report.json'));assert.equal(report.invalid_xyz_count,side.zero_xyz);
}
const info={source:'diagnostic',assertions:'PASS',tracker_collisions:{P:trace.P.collisions.length,S:trace.S.collisions.length},S46:trace.S.collisions[0],S53_reverse:trace.S.order_sensitive_frames,
    vote_window_anomalies:trace.real_vote_window_anomalies.length,zero_xyz_matches_existing_invalid_count:true,
    topology:decomp.filter(r=>[46,53,55,61,102,151,152,159,160].includes(r.frame)).map(r=>({frame:r.frame,
        grid_split:r.P_to_Q_grid_only.split,grid_merge:r.P_to_Q_grid_only.merge,membership_split:r.Q_to_S_actual_membership.split,membership_merge:r.Q_to_S_actual_membership.merge,
        removed:r.removed_from_all_S_candidates,mechanisms:r.removed_mechanisms,bands:r.reference_removed_by_source_band,added:r.added_to_S_candidates}))};
write('03_followup_summary.json',info);console.log(JSON.stringify(info,null,2));
