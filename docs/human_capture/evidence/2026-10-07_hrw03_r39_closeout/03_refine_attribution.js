"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const first=R.read(path.join(__dirname,'03_confirmation_attribution.json')),
    old=R.read(path.join(__dirname,'../2026-10-07_hrw03_r38/04_shadow_results_r3.json'));
const output=R.clone(first);output.supersedes='03_confirmation_attribution.json (first diagnostic, retained)';
output.refinement='R2: reference-dominant loss must not be assigned to incidental cleanup; explain temporal confirmation with saved branch histories.';
for(const row of output.rows) {
    row.initial_category=row.attribution_category;
    const hist=(branch,id)=>id===null?[]:old[branch].frames.slice(Math.max(0,row.frame-5),row.frame+1).map((f,j)=>({frame:Math.max(0,row.frame-5)+j,
        clusters:f.clusters.filter(c=>c.track_id===id).map(c=>({n:c.n,centroid:[c.cx,c.cy,c.cz],joint:c.joint,track_confirmed:c.track_confirmed})),
        track:f.tracks.find(t=>t.id===id)??null}));
    row.P_history=hist('P',row.P_track_id);row.S_history=hist('S',row.S_track_id);
    if(row.attribution_category==='CLEANUP_SIDE_EFFECT'&&row.removed_by_mechanism.REGISTRATION_TRANSFORM_REFERENCE_MATCH>0)
        row.attribution_category='REFERENCE_ABSORPTION';
    const temporal=row.P&&row.S&&row.P.track_confirmed!==row.S.track_confirmed&&
        (row.P.joint===row.S.joint||(row.S.track_confirmed&&row.S.joint!=='CONFIRMED_HUMAN')||(row.P.track_confirmed&&row.P.joint!=='CONFIRMED_HUMAN'));
    if(temporal&&!['STATIC_REMOVAL_EXPECTED','CLUSTER_TOPOLOGY_CHANGE'].includes(row.attribution_category))
        row.attribution_category='TRACK_ID_REASSIGNMENT';
    if(row.change==='new_green'&&row.attribution_category==='UNKNOWN'&&row.P&&row.S&&row.S.track_confirmed)
        row.attribution_category='TRACK_ID_REASSIGNMENT';
    row.temporal_history_changed=temporal;
    if(row.attribution_category==='TRACK_ID_REASSIGNMENT') {
        row.causal_factors.push('INDEPENDENT_TRACK_HISTORY');
        row.reason=`original-point overlap ${row.shared_points}; branch track ${row.P_track_id}->${row.S_track_id}; P votes=${JSON.stringify(row.P_votes)}, S votes=${JSON.stringify(row.S_votes)}; instantaneous joint=${row.P?.joint}->${row.S?.joint}; time confirmation differs. Track category covers reassigned independent histories, not proof of real-person ID.`;
    } else row.reason=`${row.attribution_category}; shared=${row.shared_points}; P-only=${row.points_lost_from_matched_cluster}; S-only=${row.points_gained_in_matched_cluster}; removal=${JSON.stringify(row.removed_by_mechanism)}. Saved geometry/reasons/history permit inspection; human/static semantics remain bounded by GT.`;
    row.semantic_GT=row.attribution_category==='STATIC_REMOVAL_EXPECTED'?'WD01_REGION_GOLDEN (not per-point)':'UNKNOWN';
}
output.categories={};for(const row of output.rows){const k=row.change+'|'+row.attribution_category;output.categories[k]=(output.categories[k]??0)+1;}
assert.equal(output.rows.length,257);assert.deepEqual(output.rows.map(v=>v.id),first.rows.map(v=>v.id));
fs.writeFileSync(path.join(__dirname,'03_confirmation_attribution_r2.json'),R.serialize(output),{flag:'wx'});
console.log(JSON.stringify(output.categories,null,2));
