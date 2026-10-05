// Extra existing-matrix consumers not exercised by the R4 submission.
const fs=require('fs'),path=require('path'),assert=require('assert');
const {createRequire}=require('module');
const source=fs.readFileSync(path.join(__dirname,'r7_self_90.js'),'utf8');
const prefix=source.slice(0,source.indexOf("check('V01'"));
const {fixture,worldWith}=new Function('require','module','__dirname',prefix+';return {fixture,worldWith};')(
  createRequire(path.join(__dirname,'r7_self_90.js')),{exports:{}},__dirname);
const results=[];
function check(id,name,fn){try{fn();results.push({id,name,result:'PASS'});}catch(e){results.push({id,name,result:'FAIL',error:e.message});}}
check('V09','legacy source-only locked current target keeps source track and XYZ',()=>{
  const f=fixture();
  f.snap.calibration={calibration_id:null,schema_version:null,ground_status:'unknown',ground_derived_id:null};
  f.snap.coordinate={source_frame:'innolidar',ground_relative_available:false,ground_derived_id:null,horizontal_basis:'raw_xy_uncalibrated'};
  f.snap.ground=null;f.snap.ground_render=null;
  Object.assign(f.state,{calibration:structuredClone(f.snap.calibration),coordinate:structuredClone(f.snap.coordinate),ground:null,ground_derived_id:null,
    sensor_quality:{ground_valid:false},center_ground_m:null,bbox_ground_from:'unavailable',bbox_ground_min_m:null,bbox_ground_max_m:null,baseline:{status:'failed'},fall_status:'unknown'});
  const w=worldWith(f);assert.ok(w.$('hfTrack').textContent.includes('/ locked'));assert.ok(w.$('hfPos').textContent.includes('3.00'));
});
check('V07','predicted old pose with other current candidate does not become current position',()=>{
  const f=fixture(),c=f.snap.candidates[0];c.candidate_id='other';c.center_source_m=[12,0,-.5];c.center_ground_m=[12,0,1];
  c.bbox_source_min_m=[11.8,-.2,-1];c.bbox_source_max_m=[12.2,.2,.5];c.bbox_ground_min_m=[11.8,-.2,.5];c.bbox_ground_max_m=[12.2,.2,2];
  Object.assign(f.state,{position_predicted:true,prediction_age_s:.5,track_status:'occluded',fall_status:'unknown'});
  const w=worldWith(f);assert.strictEqual(w.$('hfPos').textContent,'--');
});
const out=path.join(__dirname,'r7_self_92_results.json');if(fs.existsSync(out))throw new Error('Evidence exists');
fs.writeFileSync(out,JSON.stringify(results,null,2));for(const r of results)console.log(r.result+' '+r.id+' '+r.name+(r.error?' :: '+r.error:''));
process.exitCode=results.some(r=>r.result==='FAIL')?1:0;
