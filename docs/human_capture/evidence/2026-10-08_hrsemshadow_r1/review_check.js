/* Headless logic QA only. This is not a browser UI or human labeling test. */
'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/review.html','utf8');
const payload=html.match(/<script id="payload" type="application\/json">([\s\S]*?)<\/script>/)[1];
const script=html.match(/<script>\s*([\s\S]*?)<\/script>/)[1];
const bundle=JSON.parse(payload),elements=new Map();let drawCalls=0;
function element(id) {if(!elements.has(id))elements.set(id,{value:id==='projection'?'xz':'',checked:false,files:[],children:[],
    textContent:id==='payload'?payload:'',width:1000,height:650,
    selectedOptions:[{textContent:'X/Z'}],append(o){this.children.push(o);if(!this.value)this.value=String(o.value??'');},
    getContext(){return {clearRect(){},fillText(){},fillRect(){drawCalls++;}}},getBoundingClientRect(){return {left:0,top:0,width:1000,height:650};},click(){}});
    return elements.get(id);}
const ctx={document:{getElementById:element,createElement:()=>element('created-'+elements.size)},
    console,TextDecoder,DataView,Uint8Array,URL,Blob};
vm.createContext(ctx);new vm.Script(script,{filename:'review.html:inline'}).runInContext(ctx);
assert(drawCalls>0);assert(element('description').textContent.includes('ordinal'));
for(const r of bundle.cases){element('cases').value=[r.sid,r.mode,r.ordinal].join('/');element('cases').onchange();}
element('label').value='PERSON';element('person').value='';element('save').onclick();
assert(element('status').textContent.includes('person_id'));
assert.strictEqual(vm.runInContext('records.length',ctx),0,'no real human label authored');
element('export').onclick();assert(element('status').textContent.includes('审阅者'));
element('row').value=-1;element('savepoint').onclick();assert(element('status').textContent.includes('删除线索'));
const result={headless_only:true,all_embedded_cases_render_logic:bundle.cases.length,draw_calls:drawCalls,
    person_without_id_rejected:true,export_without_reviewer_rejected:true,unbound_point_rejected:true,
    actual_human_labels_written:0,browser_UI:'BLOCKED_TOOL_LOCAL_ACCESS'};
fs.writeFileSync(__dirname+'/review_check.json',JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify(result,null,2));
