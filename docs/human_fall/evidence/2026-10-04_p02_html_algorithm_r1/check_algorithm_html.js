const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const target=path.resolve(__dirname,'../2026-10-04_p02_level_preview_r1/06_PREVIEW.html');
const extract=html=>html.match(/<script>([\s\S]*?)<\/script>/)[1];
const oldScript=extract(fs.readFileSync(__dirname+'/02_PREVIEW_BEFORE.html','utf8'));
const oldData=JSON.parse(oldScript.match(/const DATA=([\s\S]*?);\r?\nconst frame=/)[1]);
const elements={};for(const [name,value] of Object.entries({frame:'0',before:'source',mode:'reference',pitch:'26',tz:'1.340',estimator:'tls',algorithmButton:''}))elements[name]={value,disabled:false,textContent:'',append(){}};
elements.info={textContent:''};elements.algorithmInfo={textContent:''};elements.plot={getContext:()=>new Proxy({}, {get:()=>()=>{}})};
const sandbox={document:{querySelector:s=>elements[s.slice(1)],createElement:()=>({})}};
vm.createContext(sandbox);vm.runInContext(extract(fs.readFileSync(target,'utf8'))+';globalThis.payload=DATA;globalThis.calculate=algorithmPoints;',sandbox);
const data=sandbox.payload;
assert.deepStrictEqual(JSON.parse(JSON.stringify(data.frames)),oldData.frames);
assert.equal(data.model.physical_measurement.height_m,1.14);
assert.equal(data.reference.display_z_translation_m,1.34);
assert.equal(data.model.runtime_eligible,false);
assert(elements.estimator.disabled&&!elements.pitch.disabled);
elements.algorithmButton.onclick();assert.equal(elements.mode.value,'local');assert(elements.pitch.disabled&&!elements.estimator.disabled);
let tlsError=0,scalarError=0;
for(const name of ['tls','svd','ransac']){
 elements.estimator.value=name;elements.estimator.onchange();assert(elements.info.textContent.includes(name.toUpperCase()));
 const m=data.algorithm_models[name],n=m.normal_source;
 const rn=m.rotation.map(row=>row.reduce((v,x,i)=>v+x*n[i],0));assert(Math.max(Math.abs(rn[0]),Math.abs(rn[1]),Math.abs(rn[2]-1))<1e-12);
 for(let fi=0;fi<data.frames.length;fi++){
  elements.frame.value=String(fi);elements.frame.onchange();assert(elements.info.textContent.includes(data.frames[fi].name));
  const frame=data.frames[fi],dst=sandbox.calculate(frame.source,name);
  for(let i=0;i<dst.length;i++){
   const q=frame.source[i];const z=n[0]*q[0]+n[1]*q[1]+n[2]*q[2]+m.d_source_m;scalarError=Math.max(scalarError,Math.abs(dst[i][2]-z));
   if(name==='tls')for(let k=0;k<3;k++)tlsError=Math.max(tlsError,Math.abs(dst[i][k]-frame.after[i][k]));
  }
 }
 assert.equal(data.model.physical_measurement.height_m,1.14);
}
assert(tlsError<1e-12&&scalarError<1e-12);
elements.mode.value='reference';elements.mode.onchange();assert(!elements.pitch.disabled&&elements.estimator.disabled);
elements.pitch.value='25';elements.tz.value='1.20';elements.pitch.oninput();assert(elements.info.textContent.includes('25.00')&&elements.info.textContent.includes('1.200'));
elements.pitch.value='';elements.pitch.oninput();assert(elements.info.textContent.includes('合法'));
elements.algorithmButton.onclick();assert(elements.info.textContent.includes('RANSAC')); // empty manual values do not block algorithm mode
elements.mode.value='reference';elements.mode.onchange();elements.pitch.value='Infinity';elements.pitch.oninput();assert(elements.info.textContent.includes('合法'));
console.log(JSON.stringify({status:'PASS',frames:data.frames.length,estimators:3,tls_matches_previous_model_max_error_m:tlsError,algorithm_z_scalar_max_error_m:scalarError,physical_record_preserved:true,all_source_samples_unchanged:true,browser_rendering:'NOT_RUN_node_mock_only'}));
