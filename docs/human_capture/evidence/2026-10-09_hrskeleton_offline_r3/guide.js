'use strict';
// UI-only helper. Reuse the frozen R1 loader/selection/receipt/export implementation.
const partNames={HEAD:'头部',UPPER_TORSO:'上躯干（肩膀下方）',CHEST:'胸部',PELVIS_REGION:'骨盆区域',LOWER_REGION:'下部区域',LOWER_A:'可分开的下部 A',LOWER_B:'可分开的下部 B'};
const kindNames={PERSON:'确定是人',STATIC_OBJECT:'确定是静态物',MIXED:'人和物体混在一起',UNKNOWN:'无法确认'};
const sectionNames={cap_20261008_114205:'第1段：中央静立',cap_20261008_114254:'第2段：桌前',cap_20261008_114340:'固定验证：隔板',cap_20261008_114422:'难例：举手',cap_20261008_114819:'空场对照'};
const g=id=>document.getElementById(id);
const errors=[['ACTUAL_HUMAN_ATTESTATION_REQUIRED','请在导出区勾选“由我本人检查后填写”。'],['REVIEWER_REQUIRED','请填写实际标注者的名字或代号。'],['PERSON_ID_REQUIRED','请给这个人填写一个编号，例如“1号”。'],['CONTINUITY_REQUIRED','连续目标的编号和核对确认还未填写；无法确认时先保留草稿。'],['REGION_ROWS_INVALID','圈选包含不属于当前目标的点，请重新圈选。'],['VISIBLE_REGION_REQUIRED','你选择了“能看见”，还需要在大图圈出对应的点。'],['VISIBILITY_REASON_REQUIRED','请写一句实际观察理由。'],['EMPTY_REVIEW','还没有保存目标。先完成目标标注并按“保存这一目标的标注”。'],['DISPLAY_NOT_VERIFIED','当前数据还未成功加载，暂时不能保存。'],['NO_CLUSTER','这一帧没有可标注目标。'],['DISPLAY_SHA_MISMATCH','数据校验失败，暂时不能标注。']];
function translateError(text){const hit=errors.find(([code])=>text.includes(code));return hit?hit[1]:text;}
function translateOptions(){
 for(const option of g('node').options){const value=option.value;if(partNames[value]&&option.textContent!==partNames[value]){option.value=value;option.textContent=partNames[value];}}
 for(const option of g('frame').options){if(option.dataset.localized)continue;const m=option.textContent.match(/^(cap_\d+_\d+)\/([^/]+)\/(\d+) · (\d+)簇$/);if(m){option.textContent=(sectionNames[m[1]]||m[1])+' · 第'+m[3]+'帧 · '+m[4]+'组点';option.dataset.localized='1';}}
 for(const option of g('cluster').options){const m=option.textContent.match(/^ci (\d+) \/ (\d+) 点$/);if(m)option.textContent='目标 '+(Number(m[1])+1)+'（'+m[2]+'个点）';else if(option.value==='')option.textContent='这一帧没有目标';}
 updateTips();
}
function updateTips(){
 if(g('reason').value==='NOT_REVIEWED')g('reason').value='';
 const n=g('node').value;g('parttip').textContent=n==='HEAD'?'头和举起的手分不清时，选择“我不能确定”。圈点后确认为头部，才点击下面的确认按钮。':'只圈你能辨认的这个部位。无法判断时选择“我不能确定”，写明理由。';
 g('headconfirm').classList.toggle('hidden',n!=='HEAD'||g('visibility').value!=='VISIBLE');
 const rows=g('rows').value.trim();g('selectioncount').textContent=rows?'当前圈选了 '+rows.split(/[\s,]+/).filter(Boolean).length+' 个点。':'当前部位还没圈点。';
}
function view(name){for(const n of ['xy','xz','yz'])g(n).hidden=n!==name;document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===name));}
document.querySelectorAll('[data-view]').forEach(b=>b.addEventListener('click',()=>view(b.dataset.view)));
document.querySelectorAll('[data-kind]').forEach(b=>b.addEventListener('click',()=>{
 g('label').value=b.dataset.kind;g('pickedkind').textContent='你的判断：'+kindNames[b.dataset.kind]+'。这一判断尚未保存。';document.querySelectorAll('[data-kind]').forEach(x=>x.classList.toggle('active',x===b));
}));
g('toParts').addEventListener('click',()=>g('partpanel').scrollIntoView({behavior:'smooth',block:'start'}));
g('headconfirm').addEventListener('click',()=>{g('reason').value='HEAD_CONFIRMED';g('savednote').textContent='你已明确确认头部归属；请再按“保存这个部位”。';});
g('otherUncertain').addEventListener('click',()=>{
 if(!window.skoReview.state().verified)return;
 const savedNode=g('node').value;let count=0;
 let review;try{review=JSON.parse(g('nodedraft').textContent);}catch(_){return;}
 for(const [name,node] of Object.entries(review))if(node.reason==='NOT_REVIEWED'){
  g('node').value=name;g('node').dispatchEvent(new Event('change'));
  g('visibility').value='UNCERTAIN';g('rows').value='';g('reason').value='实际人工审阅：无法确认该部位';g('applynode').click();count++;
 }
 g('node').value=savedNode;g('node').dispatchEvent(new Event('change'));g('savednote').textContent='按你的明确判断，把 '+count+' 个未检查部位记为“无法确认”。';
});
g('node').addEventListener('change',updateTips);g('visibility').addEventListener('change',updateTips);g('rows').addEventListener('input',updateTips);
for(const id of ['applynode','saverecord','export'])g(id).addEventListener('click',()=>{g('error').textContent='';},{capture:true});
g('applynode').addEventListener('click',()=>{if(!g('error').textContent)g('savednote').textContent='当前部位草稿已保存。';updateTips();});
g('cluster').addEventListener('change',()=>{g('pickedkind').textContent='换了目标，请重新判断这整组点。';document.querySelectorAll('[data-kind]').forEach(b=>b.classList.remove('active'));g('savednote').textContent='';});
g('saverecord').addEventListener('click',()=>{if(!g('error').textContent)g('savednote').textContent='目标已保存在本页草稿里，记得下载标注文件。';});
new MutationObserver(()=>{
 const e=g('error');const translated=translateError(e.textContent);if(translated!==e.textContent)e.textContent=translated;
}).observe(g('error'),{childList:true,subtree:true,characterData:true});
new MutationObserver(()=>{
 const text=g('status').textContent;
 if(text.startsWith('SHA verified')){const m=text.match(/(cap_\d+_\d+)\/([^/]+)\/(\d+)/);g('statehint').textContent=m?'数据已核对 · '+(sectionNames[m[1]]||'录制片段')+' · 第'+m[3]+'帧':'数据已核对';if(text.includes('picked row='))updateTips();}
 else g('statehint').textContent='正在读取或核对数据，请稍等。';
}).observe(g('status'),{childList:true,subtree:true,characterData:true});
for(const id of ['frame','cluster','node'])new MutationObserver(translateOptions).observe(g(id),{childList:true});
new MutationObserver(updateTips).observe(g('nodedraft'),{childList:true,subtree:true,characterData:true});
translateOptions();
