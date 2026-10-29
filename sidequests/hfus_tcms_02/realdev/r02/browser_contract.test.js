'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const controls=new Map();function element(id){if(!controls.has(id))controls.set(id,{value:'0',textContent:'',append(){},addEventListener(){}});return controls.get(id);}
let pending;
const sandbox={document:{getElementById:element},window:{addEventListener(){}},URLSearchParams,console,
 fetch:async()=>new Promise(resolve=>pending=body=>resolve({ok:true,json:async()=>body}))};
vm.createContext(sandbox);
const text=fs.readFileSync(__dirname+'/app.js','utf8');
// Skip network bootstrap only; execute the actual event handlers and query code.
vm.runInContext(text.slice(0,text.lastIndexOf('(async()=>{const c=')),sandbox);
vm.runInContext('render=()=>{}; data={fi:430,tag:{transform_id:"T",coordinate_version:"V"}};',sandbox);
(async()=>{
 const first=vm.runInContext('query(9)',sandbox);
 vm.runInContext('requestSerial++;data={fi:431,tag:{transform_id:"T",coordinate_version:"V"}};selected=null;',sandbox);
 pending({fi:430,source_row:9,tag:{transform_id:'T',coordinate_version:'V'}});await first;
 assert.equal(vm.runInContext('selected',sandbox),null,'late old-frame point response must be discarded');
 const second=vm.runInContext('query(10)',sandbox);pending({fi:431,source_row:10,tag:{transform_id:'T',coordinate_version:'V'}});await second;
 assert.equal(vm.runInContext('selected.source_row',sandbox),10,'current response must be applied');
 const surface=vm.runInContext('querySurface()',sandbox);vm.runInContext('requestSerial++;data.fi=432;',sandbox);
 pending({tag:{fi:431,coordinate_version:'V'}});await surface;
 assert.equal(element('surfaceInfo').textContent,'','late old-frame surface response must be discarded');
 const wrong=vm.runInContext('query(1)',sandbox);pending({fi:432,tag:{transform_id:'OTHER',coordinate_version:'V'}});await wrong;
 assert.match(element('point').textContent,/mismatch/);
 const mixedSurface=vm.runInContext('querySurface()',sandbox);pending({tag:{fi:432,transform_id:'OTHER',coordinate_version:'V'}});await mixedSurface;
 assert.match(element('surfaceInfo').textContent,/mismatch/);
 console.log('PASS actual query handlers: late point/surface responses discarded; current response accepted; mixed version rejected');
})().catch(e=>{console.error(e);process.exitCode=1;});
