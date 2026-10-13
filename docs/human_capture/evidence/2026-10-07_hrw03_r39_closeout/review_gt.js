"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const [input,out]=process.argv.slice(2);assert(input&&out,'node review_gt.js <human-labels.json> <new-output.json>');
const gt=R.read(input),points=R.read(__dirname+'/01_absorbed_points.json'),attr=R.read(__dirname+'/03_confirmation_attribution_r2.json');
assert.equal(gt.kind,'hrw03_closeout_gt');assert.equal(gt.schema,1);assert.equal(gt.source,'human');assert(typeof gt.reviewer==='string'&&gt.reviewer.trim());
assert.equal(gt.session_id,points.session);assert.equal(gt.artifact_id,points.registration_artifact_id);
assert.deepEqual(gt.source_session,points.source_session);assert.deepEqual(gt.source_leveling,points.source_leveling);
const pointEnums=['UNKNOWN','FOOT_SHOE','LOWER_LEG','GROUND_RESIDUE','HUMAN_GROUND_MIXED','REGISTRATION_REFERENCE_MISMATCH'],
    clusterEnums=['UNKNOWN','PERSON','STATIC_OBJECT','MIXED'],continuityEnums=['UNKNOWN','PRESERVED','FRAGMENTED','LOST','STATIC_NOT_HUMAN'];
assert.equal(gt.points.length,31);assert.equal(new Set(gt.points.map(v=>v.id)).size,31);
for(const p of points.points){const v=gt.points.find(v=>v.id===p.id);assert(v);assert.equal(v.frame,p.frame);assert.equal(v.frame_seq,p.frame_seq);assert.equal(v.point_index,p.original_point_index);assert(pointEnums.includes(v.label));}
assert.equal(new Set(gt.confirmations.map(v=>v.id)).size,gt.confirmations.length);
for(const v of gt.confirmations){const row=attr.rows.find(c=>c.id===v.id);assert(row,'unknown confirmation id');assert.equal(v.frame,row.frame);assert.equal(v.P_track_id,row.P_track_id);assert.equal(v.S_track_id,row.S_track_id);assert(clusterEnums.includes(v.label));assert(continuityEnums.includes(v.continuity));}
const required=attr.rows.filter(v=>v.attribution_category!=='STATIC_REMOVAL_EXPECTED'),counts={};
for(const v of gt.points)counts[v.label]=(counts[v.label]??0)+1;
const missing=required.filter(r=>!gt.confirmations.some(v=>v.id===r.id&&v.label!=='UNKNOWN'&&v.continuity!=='UNKNOWN')).map(v=>v.id);
const broken=gt.confirmations.filter(v=>v.continuity==='FRAGMENTED'||v.continuity==='LOST');
const result={state:'REWORK_REQUIRED',GT_input_sha256:R.shaFile(input),reviewer:gt.reviewer,point_counts:counts,
    point_semantics_closed:gt.points.every(v=>v.label!=='UNKNOWN'),known_human_structure_loss:gt.points.filter(v=>['FOOT_SHOE','LOWER_LEG','HUMAN_GROUND_MIXED'].includes(v.label)).length,
    uncertain_or_mismatched_loss:gt.points.filter(v=>['UNKNOWN','REGISTRATION_REFERENCE_MISMATCH'].includes(v.label)).length,
    missing_confirmation_labels:missing,broken_human_continuity:broken,
    reason:'GT review cannot override frozen DEGRADED gate or T38-06 strict common gate; no automatic release, no artifact rewrite',
    rerun:'closeout_shadow.js --phase=after uses exclusive fixed outputs; create a fresh evidence directory/copy tools and baseline_code before rerunning. Never overwrite this experiment.'};
fs.writeFileSync(path.resolve(out),R.serialize(result),{flag:'wx'});console.log(JSON.stringify(result,null,2));
