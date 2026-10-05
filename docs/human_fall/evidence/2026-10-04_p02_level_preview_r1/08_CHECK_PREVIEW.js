const fs=require('fs'),vm=require('vm'),assert=require('assert');
const html=fs.readFileSync(__dirname+'/06_PREVIEW.html','utf8');
const script=html.match(/<script>([\s\S]*?)<\/script>/)[1];
const context=new Proxy({}, {get:()=>()=>{}});
const values={frame:'0',before:'source',mode:'reference',pitch:'26',tz:'1.340'};
const elements={};
for(const [key,value] of Object.entries(values))elements[key]={value,append(){},disabled:false};
elements.info={textContent:''};elements.plot={getContext:()=>context};
const sandbox={document:{querySelector:s=>elements[s.slice(1)],createElement:()=>({})}};
vm.createContext(sandbox);vm.runInContext(script+';globalThis.payload=DATA;',sandbox);
const data=sandbox.payload;
assert.equal(data.model.physical_measurement.height_m,1.14);
assert.equal(data.reference.display_z_translation_m,1.34);
assert.equal(data.model.runtime_eligible,false);
let maximum=0;
for(const f of data.frames)for(let i=0;i<f.source.length;i++){
 const p=f.source[i],a=26*Math.PI/180,c=Math.cos(a),s=Math.sin(a);
 const q=[c*p[0]+s*p[2],p[1],-s*p[0]+c*p[2]+1.34];
 for(let k=0;k<3;k++)maximum=Math.max(maximum,Math.abs(q[k]-f.before[i][k]));
}
assert(maximum<1e-12);
elements.pitch.value='25';elements.tz.value='1.20';elements.pitch.oninput();
assert(elements.info.textContent.includes('25.00')&&elements.info.textContent.includes('1.200'));
assert.equal(data.model.physical_measurement.height_m,1.14);
elements.mode.value='local';elements.mode.onchange();assert(elements.pitch.disabled&&elements.tz.disabled);
for(let i=0;i<data.frames.length;i++){elements.frame.value=String(i);elements.frame.onchange();assert(elements.info.textContent.includes(data.frames[i].name));}
elements.mode.value='reference';elements.mode.onchange();assert(!elements.pitch.disabled&&!elements.tz.disabled);
elements.pitch.value='Infinity';elements.pitch.oninput();assert(elements.info.textContent.includes('合法'));
console.log(JSON.stringify({status:'PASS',preview_frames:data.frames.length,reference_scalar_max_error_m:maximum,controls_and_physical_record_checks:'PASS',browser_rendering:'NOT_RUN_node_canvas_mock_only'}));
