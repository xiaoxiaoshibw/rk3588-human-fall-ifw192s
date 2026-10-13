"use strict";
const fs=require('fs'),path=require('path'),os=require('os'),cp=require('child_process'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const p=R.read(__dirname+'/01_absorbed_points.json'),a=R.read(__dirname+'/03_confirmation_attribution_r2.json'),rows=[],tmp=fs.mkdtempSync(path.join(os.tmpdir(),'hr-r39-gt-schema-'));
const base={kind:'hrw03_closeout_gt',schema:1,source:'human',reviewer:'SYNTHETIC_SCHEMA_TEST_ONLY',session_id:p.session,artifact_id:p.registration_artifact_id,
    source_session:p.source_session,source_leveling:p.source_leveling,
    points:p.points.map(v=>({id:v.id,frame:v.frame,frame_seq:v.frame_seq,point_index:v.original_point_index,label:'UNKNOWN'})),
    confirmations:a.rows.map(v=>({id:v.id,frame:v.frame,P_track_id:v.P_track_id,S_track_id:v.S_track_id,label:'UNKNOWN',continuity:'UNKNOWN'}))};
const cases=[['unknown remains blocked',()=>{},0],['source must be human',v=>v.source='diagnostic',1],
    ['artifact binding mismatch',v=>v.artifact_id='0'.repeat(64),1],['frame sequence mismatch',v=>v.points[0].frame_seq++,1],
    ['duplicate point identity',v=>v.points[1]=v.points[0],1],['invented semantic label rejected',v=>v.points[0].label='AUTO_GROUND',1]];
try {
    cases.forEach(([name,mutate,expected],i)=>{
        const v=R.clone(base);mutate(v);const input=path.join(tmp,i+'.json'),output=path.join(tmp,i+'_result.json');fs.writeFileSync(input,R.serialize(v));
        const run=cp.spawnSync(process.execPath,[__dirname+'/review_gt.js',input,output],{encoding:'utf8'});
        let result='PASS',error=null;
        try{assert.equal(run.status,expected);if(!expected){const r=R.read(output);assert.equal(r.state,'REWORK_REQUIRED');assert.equal(r.point_counts.UNKNOWN,31);assert.equal(r.point_semantics_closed,false);assert.equal(r.missing_confirmation_labels.length,155);}}
        catch(e){result='FAIL';error=e.stack;}
        rows.push({name,result,actual_exit:run.status,expected_exit:expected,error,stdout:run.stdout,stderr:run.stderr,fixture_scope:'synthetic schema only, NOT human GT'});
    });
} finally {
    const absolute=path.resolve(tmp);assert(absolute.startsWith(path.resolve(os.tmpdir())+path.sep+'hr-r39-gt-schema-'));fs.rmSync(absolute,{recursive:true,force:true});
}
fs.writeFileSync(__dirname+'/05_gt_schema_regression.json',R.serialize(rows),{flag:'wx'});console.log(JSON.stringify(rows.map(v=>({name:v.name,result:v.result,actual_exit:v.actual_exit})),null,2));
process.exitCode=rows.some(v=>v.result==='FAIL')?1:0;
