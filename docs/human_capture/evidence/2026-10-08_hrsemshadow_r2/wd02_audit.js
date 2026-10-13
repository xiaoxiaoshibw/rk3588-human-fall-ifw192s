/* Diagnose the unchanged fixed job. Never bypass H.level to process WD02. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const ROOT=path.resolve(__dirname,'../../../..'),R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const H=require('../2026-10-08_hrsemshadow_r1/shadow.js');
const sid='cap_20261004_203349',job='c9712acad48c4fb7a78cb119c08d4cdb',dir=path.join(ROOT,'captures/leveled',job);
const report=R.read(path.join(dir,'report.json')),manifest=R.read(path.join(dir,'manifest.json')),tf=R.read(path.join(dir,'tls/transform.json'));
const src=R.sessionBinding(ROOT,sid);delete src.sid;
for(const b of [report.source,manifest.source,tf.source])assert.strictEqual(R.identity(b),R.identity(src));
const artifacts=[];
for(const [method,files] of Object.entries(manifest.artifacts))for(const [name,h] of Object.entries(files)){
 const actual=R.shaFile(path.join(dir,method,name));assert.strictEqual(actual,h);artifacts.push({path:method+'/'+name,sha256:actual});
}
assert.strictEqual(R.shaFile(path.join(dir,'report.json')),manifest.report_sha256);assert.strictEqual(R.shaFile(path.join(dir,'domain.npz')),manifest.domain_sha256);
const different=[];for(const [name,h] of Object.entries(report.code_hashes)){
 const sub=['__init__.py','ransac.py','svd.py','tls.py'].includes(name)?'leveling_estimators/':'';
 const actual=R.shaFile(path.join(ROOT,'pc_apps/human_replay',sub+name));if(actual!==h)different.push({file:sub+name,historical:h,current:actual});
}
const binding=R.levelingBinding(ROOT,sid,job).binding;let blocked;
try{H.level(sid,job,dir);}catch(e){blocked={name:e.name,message:e.message,actual:e.actual,expected:e.expected};}
assert(blocked&&blocked.message.includes('leveling code binding'));
const result={status:'BLOCKED_CONTRACT_ADJUDICATION',sid,job,source:src,all_12_method_artifacts:artifacts,report_sha256:manifest.report_sha256,domain_sha256:manifest.domain_sha256,current_levelingBinding_accepts:true,binding,historical_generator_differences:different,unchanged_harness_rejection:blocked,WD02_processed_frames:0,loader_or_publish_called:false};
fs.writeFileSync(path.join(__dirname,'WD02_contract.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log('WD02_DIAGNOSED_NOT_RUN',artifacts.length,'artifact hashes intact;',different.length,'historical code mismatch; BLOCKED retained');
