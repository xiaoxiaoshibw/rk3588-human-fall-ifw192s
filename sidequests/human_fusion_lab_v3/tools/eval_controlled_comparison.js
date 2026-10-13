'use strict';
/* eval_controlled_comparison.js — HUMAN-FUSION-BG-V3 阶段5: 受控同点集模型对照.
 *
 * 严格对照纪律 (C1 教训, 不与完整管线比较混淆):
 *  - 对同一冻结候选行 (A 链 S1..S8 jsonl + V3 B 组 S9 候选行),
 *    逐行用 "同一 features+extended 向量" 喂给各模型, 得 prob; 判定 0.55 门;
 *    再与 label (GT 重叠) 对账. 不跨帧, 不tracker, 不改权重。
 *  - 模型: rf51_baseline (V1 冻结), rf51_candidate (V2), rf69_candidate (V2),
 *    xgb69_candidate (V2), rf51_bg_candidate (V3, 加 B 组 S9 家具负样本训练).
 *  - 报告按 split × model 给 tp/fp/fn/tn + recall/precision/specificity。
 *  - 独立家具负样本 (S9, blocked) 全新评估: 不在任何训练 split 内。
 *
 * 输出 results/CONTROLLED_COMPARISON.json
 */
const fs=require('fs'),path=require('path');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const {treeRF,treeXGB}=require(path.join(LAB2,'detector'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const SPLITS=audit.splits;

const MODELS=[
 {name:'rf51_baseline',path:path.join(LAB2,'human_replay/rf_person_v1.json'),kind:'rf',nf:51},
 {name:'rf51_candidate',path:path.join(LAB2,'models/rf51_candidate.json'),kind:'rf',nf:51},
 {name:'rf69_candidate',path:path.join(LAB2,'models/rf69_candidate.json'),kind:'rf',nf:69},
 {name:'xgb69_candidate',path:path.join(LAB2,'models/xgb69_candidate.json'),kind:'xgb',nf:69},
 /* rf51_bg_candidate 已删除: +608 B-neg 同会话训练在 validation/test/stress 的
    召回在 0.034..0.738 间随种子大幅漂移 (3 个种子结果全记录 TRAIN_BG_REPORT),
    不可信, 不进入对照 (不把不稳定模型当修复)。 */
];
function score(m,x){
  if(m.kind==='rf')return m.trees.reduce((s,t)=>s+treeRF(t,x),0)/m.trees.length;
  return 1/(1+Math.exp(-(m.base_margin+m.trees.reduce((s,t)=>s+treeXGB(t,x),0))));
}
function loadModel(m){
  if(m.name==='rf51_baseline'){
    const w=JSON.parse(fs.readFileSync(m.path));
    return {kind:'rf',trees:w.trees,n_features:w.n_features||51};
  }
  return JSON.parse(fs.readFileSync(m.path));
}
function metric(rs,probs,thr){
  let tp=0,fp=0,fn=0,tn=0;
  rs.forEach((r,i)=>{if(r.label===null)return;const p=probs[i]>=thr;
    if(r.label===1&&p)tp++;else if(r.label===1)fn++;
    else if(r.label===0&&p)fp++;else if(r.label===0)tn++;});
  return {tp,fp,fn,tn,recall:+(tp/Math.max(1,tp+fn)).toFixed(4),precision:+(tp/Math.max(1,tp+fp)).toFixed(4),specificity:+(tn/Math.max(1,tn+fp)).toFixed(4)};
}

function main(){
  const models=MODELS.map(m=>({...m,w:loadModel(m)})).filter(m=>m.w);
  console.log('loaded models:',models.map(m=>m.name).join(', '));
  const report={task:'V3 受控同点集模型对照',date:'2026-10-11',thr:0.55,splits:{}};
  for(const split of Object.keys(SPLITS)){
    if(split==='blocked')continue;
    const rows=[];
    for(const sid of SPLITS[split]){
      const p=path.join(LAB2,'results',sid+'.jsonl');
      if(!fs.existsSync(p))continue;
      for(const line of fs.readFileSync(p,'utf8').split('\n')){
        if(!line.trim())continue;
        const r=JSON.parse(line);
        if(r.label===null)continue;
        rows.push(r);
      }
    }
    const X=rows.map(r=>Float32Array.from(r.features.concat(r.extended)));
    report.splits[split]={n:rows.length,pos:rows.filter(r=>r.label===1).length,neg:rows.filter(r=>r.label===0).length,models:{}};
    for(const m of models){
      const probs=X.map(x=>score(m.w,m.nf===51?x.slice(0,51):x));
      report.splits[split].models[m.name]=metric(rows,probs,0.55);
    }
    console.log(split,'n='+rows.length,'pos='+report.splits[split].pos,'neg='+report.splits[split].neg);
    for(const m of models){const mm=report.splits[split].models[m.name];
      console.log('  ',m.name.padEnd(24),'R='+mm.recall,'P='+mm.precision,'Spec='+mm.specificity,'(tp/fp/fn/tn='+mm.tp+'/'+mm.fp+'/'+mm.fn+'/'+mm.tn+')');}
  }
  /* 独立家具负样本: V3 B 组 S9 (blocked, 未入训练 split) */
  const p=path.join(__dirname,'../results/cap_20261010_180751_bg.jsonl');
  if(fs.existsSync(p)){
    const rows=[];
    for(const line of fs.readFileSync(p,'utf8').split('\n')){
      if(!line.trim())continue;
      const r=JSON.parse(line);
      if(r.label===0)rows.push(r); // 家具 neg (GT 80% 重叠)
    }
    if(rows.length){
      const X=rows.map(r=>Float32Array.from(r.features.concat(r.extended)));
      report.s9_independent_furniture={n:rows.length,models:{}};
      for(const m of models){
        const probs=X.map(x=>score(m.w,m.nf===51?x.slice(0,51):x));
        const asOne=rows.map(r=>({...r,label:0}));
        report.s9_independent_furniture.models[m.name]=metric(asOne,probs,0.55);
        const mm=report.s9_independent_furniture.models[m.name];
        console.log('S9-ind-furniture',m.name.padEnd(24),'Spec='+mm.specificity,'(fp='+mm.fp+' tn='+mm.tn+')');
      }
    }
  }
  fs.writeFileSync(path.join(__dirname,'../results/CONTROLLED_COMPARISON.json'),JSON.stringify(report,null,1));
}
main();
