// Resume shim: run baseline 180235 sensor_valid + 180337/180557/180751 x 2 modes.
// Writes into docs/.../sub_d01_verify/resume_run (new absent dir, like baseline.js).
// Read-only wrt repo; only writes inside OUT dir.
const path=require('path'),fs=require('fs');
const B=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/eval/baseline.js');
const OUT=path.resolve(__dirname,'resume_run');
if(fs.existsSync(OUT)) throw Error('out exists');
fs.mkdirSync(OUT,{recursive:true});
const WANT={'cap_20261010_180235':['sensor_valid'],
            'cap_20261010_180337':['source_legacy','sensor_valid'],
            'cap_20261010_180557':['source_legacy','sensor_valid'],
            'cap_20261010_180751':['source_legacy','sensor_valid']};
const results=[];
for(const rec of B.audit.sessions){
  const modes=WANT[rec.sid]; if(!modes) continue;
  for(const inputMode of modes){
    const s=B.runSession(rec,OUT,{inputMode});
    results.push(s);
    console.log(rec.sid,inputMode,JSON.stringify({strict:s.strict,legacy:s.legacy,invalid:s.invalid_candidate_row_count,gt_valid:s.gt_binding_valid}));
  }
}
fs.writeFileSync(path.join(OUT,'RESUME_RESULTS.json'),JSON.stringify(results,null,2),{flag:'wx'});
console.log('DONE',results.length,'runs ->',OUT);
