'use strict';
// Synthetic UI checks only; no human sidecar and no writes to frozen R1.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert'),crypto=require('crypto');
const maps=new Map();
function el(id){if(!maps.has(id))maps.set(id,{value:'',textContent:'',hidden:false,options:[],dataset:{},classList:{toggle(){}},addEventListener(){},scrollIntoView(){},dispatchEvent(){},click(){}});return maps.get(id);}
const option=(value,text)=>({value,textContent:text,dataset:{}});
el('node').options=['HEAD','UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION','LOWER_A','LOWER_B'].map(n=>option(n,n));el('node').value='HEAD';
el('frame').options=[option('0','cap_20261008_114205/REF_SHADOW/112 · 2簇')];
el('cluster').options=[option('0','ci 0 / 975 点')];
const sandbox={document:{getElementById:el,querySelectorAll:()=>[]},window:{skoReview:{state:()=>({verified:true})}},
 MutationObserver:class{constructor(){}observe(){}},Event:class{},console};
vm.createContext(sandbox);vm.runInContext(fs.readFileSync(path.join(__dirname,'guide.js'),'utf8'),sandbox);
assert.deepStrictEqual(el('node').options.map(o=>o.value),['HEAD','UPPER_TORSO','CHEST','PELVIS_REGION','LOWER_REGION','LOWER_A','LOWER_B']);
assert.equal(el('node').options[2].textContent,'胸部');
assert.equal(el('frame').options[0].value,'0');assert(el('frame').options[0].textContent.includes('第112帧'));
assert.equal(el('cluster').options[0].value,'0');assert(el('cluster').options[0].textContent.includes('目标 1'));
const once=JSON.stringify(el('node').options);vm.runInContext('translateOptions()',sandbox);assert.equal(JSON.stringify(el('node').options),once);
assert.equal(vm.runInContext("translateError('VISIBLE_REGION_REQUIRED')",sandbox),'你选择了“能看见”，还需要在大图圈出对应的点。');
el('rows').value='1,2,3';vm.runInContext('updateTips()',sandbox);assert.equal(el('selectioncount').textContent,'当前圈选了 3 个点。');
vm.runInContext("view('yz')",sandbox);assert.equal(el('xz').hidden,true);assert.equal(el('yz').hidden,false);assert.equal(el('xy').hidden,true);
const html=fs.readFileSync(path.join(__dirname,'review.html'),'utf8');
for(const id of ['frame','cluster','node','label','rows','reviewer','person','epoch','continuity','attest','saverecord','export','import','status','identity','nodedraft','output','xy','xz','yz','prev','next','home','error','visibility','reason','clearrows','applynode'])assert.equal((html.match(new RegExp('id="'+id+'"','g'))||[]).length,1,id);
assert(html.includes('<summary>数据来源与原始诊断'));
assert(html.includes('src="/r1/review.js"')&&html.includes('src="/r1/review_config_final.js"'));
const R1=path.join(__dirname,'../2026-10-09_hrskeleton_offline_r1'),manifest=JSON.parse(fs.readFileSync(path.join(R1,'delivery_manifest.json'),'utf8'));
for(const name of ['review.js','review_config_final.js','input_manifest.json','prototype_params_v1.json','skeleton.py','run_offline.py'])assert.equal(crypto.createHash('sha256').update(fs.readFileSync(path.join(R1,name))).digest('hex'),manifest.files[name].sha256,name);
const resultName=process.argv[2]||'guide_test_results.json';assert(/^[a-z_]+\.json$/.test(resultName));
fs.writeFileSync(path.join(__dirname,resultName),JSON.stringify({source:'synthetic',pass:true,checks:10,
 expectations:['Chinese node labels preserve enums','frame label preserves ordinal index','cluster label preserves ci','translation is idempotent','error text translated','point count shown','single view switch','all original core IDs unique','diagnostic hidden and frozen core reused','R1 source/input/params SHA match'],real_gt_created:0})+'\n',{flag:'wx'});
console.log('GUIDE_TESTS_PASS 10; original bindings, enums and R1 SHA preserved');
