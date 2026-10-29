'use strict';
// Regression: a rejected/older request must never remain visible as a new scheme/frame.
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const elements={}, pending=[];
function element(id){return elements[id]||=( {value:'',textContent:'',selectedIndex:0,width:1000,height:600,options:[],add(o){this.options.push(o);},getContext(){return {clearRect(){},fillRect(){},fillText(){},beginPath(){},moveTo(){},lineTo(){},stroke(){},arc(){},fill(){}};}} );}
for(const [k,v] of Object.entries({coord:'corrected',height:'128',depth:'range',layer:'0',reviewLayer:'PRIMARY'}))element(k).value=v;
const catalog={sources:{s:{}},groups:['G0'],tasks:[{sid:'s',fi:0},{sid:'s',fi:7}],models:{streams:{learning_streams:['L3D_seed43'],inference_pressure_streams:[]}},code_sha256:{},viewer_sha256:{}};
const context={document:{getElementById:element},location:{pathname:'/learn/test/',search:'?sid=s&fi=0'},URLSearchParams,Option:class{constructor(t,v){this.text=t;this.value=v;}},console,
fetch:async url=>{if(url.endsWith('catalog'))return {ok:true,json:async()=>catalog};return new Promise(resolve=>pending.push({url,resolve}));}};
vm.createContext(context);vm.runInContext(fs.readFileSync(path.join(__dirname,'view.js'),'utf8'),context);
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture(fi){const projection={};for(const mode of ['range','axial'])Object.assign(projection,{[mode+'_pixels']:[0],[mode+'_layers']:[[0,1]],[mode+'_members']:[0,1],[mode+'_offsets']:[0,2],[mode+'_span']:[1]});return {metadata:{sid:'s',fi,variant:'G0',selected:1,skeleton:{nodes:{},edges:[]}},rows:[0,1],raw:[[1,0,0],[2,0,0]],nominal:[[1,0,0],[2,0,0]],corrected:[[1,0,0],[2,0,0]],selected:[1,0],added:[false,false],removed:[false,false],GT:[-1,-1],projection,reviews:[]};}
function reply(request,value,ok=true){request.resolve({ok,json:async()=>value});}
(async()=>{
 await tick();assert.equal(pending.length,1);
 element('group').value='NOTRUN:L3D_seed43';element('group').onchange();
 reply(pending.shift(),fixture(0));await tick();assert(element('status').textContent.includes('NOT_RUN'));assert.equal(vm.runInContext('frame',context),null);assert(element('selection').textContent.startsWith('0'));
 element('group').value='G0';element('load').onclick();const older=pending.shift();
 element('fi').value='7';element('load').onclick();const newer=pending.shift();
 reply(newer,fixture(7));await tick();reply(older,fixture(0));await tick();assert(element('status').textContent.includes('f7'));assert.equal(element('task').selectedIndex,1);
 element('fi').value='999';element('load').onclick();assert.equal(vm.runInContext('frame',context),null);
 reply(pending.shift(),{error:'Unknown frame'},false);await tick();assert.equal(element('status').textContent,'Unknown frame');assert.equal(vm.runInContext('frame',context),null);
 console.log('PASS: NOT_RUN clears prediction; newest frame wins; failed frame clears old results');
})().catch(e=>{console.error(e);process.exitCode=1;});
