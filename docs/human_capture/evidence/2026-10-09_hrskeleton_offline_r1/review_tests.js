'use strict';
// Headless editor contract checks. Separate from actual browser observations.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const elements=new Map();
function element(id){if(!elements.has(id))elements.set(id,{value:'',checked:false,textContent:'',getContext:()=>({clearRect(){}})});return elements.get(id);}
const sandbox={document:{getElementById:element},window:{},structuredClone:x=>JSON.parse(JSON.stringify(x)),
 fetch:()=>new Promise(()=>{}),URLSearchParams,URL,TextDecoder,Date,Math,Set,Map,Number,Object,Array,JSON,Error,
 SKO_CONFIG:{input_sha256:'031040dd0e9da7f956d30f0714b5ede34023c4367838a9b514a3571bf2e4d467'},
 frame:JSON.parse(fs.readFileSync(path.join(__dirname,'frames/f0.json'),'utf8'))};
vm.createContext(sandbox);
vm.runInContext(fs.readFileSync(path.join(__dirname,'review.js'),'utf8'),sandbox);
const out=vm.runInContext(`
current=frame;active=1;verified=true;
$('reviewer').value='SYNTHETIC HEADLESS TEST ONLY';
const record={...structuredClone(member().receipt),label:'UNKNOWN',person_id:null,track_epoch:'SYNTHETIC',continuity:'human_confirmed',nodes:defaults()};
validateRecord(record,member());records.set(record.id,record);
exportObject('synthetic');`,sandbox);
assert.equal(out.source,'synthetic');assert.equal(out.counts_as_real_gt,false);
assert.deepStrictEqual(JSON.parse(JSON.stringify(out.records[0].rows)),sandbox.frame.clusters[1].receipt.rows);
assert.throws(()=>vm.runInContext('exportObject()',sandbox),/ACTUAL_HUMAN_ATTESTATION_REQUIRED/);
assert.throws(()=>vm.runInContext("validateRecord({...record,rows:[0]},member())",sandbox),/RECORD_BINDING_MISMATCH/);
assert.throws(()=>vm.runInContext("const wrong=structuredClone(record);wrong.nodes.HEAD={visibility:'VISIBLE',region_rows:[999999],reason:'SYNTHETIC'};validateRecord(wrong,member())",sandbox),/REGION_ROWS_INVALID/);
vm.runInContext("fail(Error('SYNTHETIC_DISPLAY_FAILURE'))",sandbox);
assert.throws(()=>vm.runInContext("exportObject('synthetic')",sandbox),/DISPLAY_NOT_VERIFIED/);
fs.writeFileSync(path.join(__dirname,'synthetic_ui_export_headless.json'),JSON.stringify(out,null,2)+'\n',{flag:'wx'});
fs.writeFileSync(path.join(__dirname,'review_test_results.json'),JSON.stringify({source:'synthetic',tests:6,pass:true,actual_browser:false,
 checks:['legal complete-member synthetic export','receipt rows unchanged','human attestation required','tampered receipt rejected','foreign support rejected','display failure clears export eligibility'],counts_as_real_gt:false})+'\n',{flag:'wx'});
console.log('REVIEW_CONTRACT_TESTS_PASS 6');
