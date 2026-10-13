'use strict';
const fs=require('fs'),path=require('path'),E=require('./core/engine_keep_unknown'),{extra}=require('./export');
function treeRF(t,x){let n=0;while(t.feature[n]>=0)n=x[t.feature[n]]<=t.threshold[n]?t.children_left[n]:t.children_right[n];const v=t.value[n];return v[1]/(v[0]+v[1]||1);}
function treeXGB(t,x){while(t.leaf===undefined){const ix=Number(t.split.replace('f',''));const next=!Number.isFinite(x[ix])?t.missing:(x[ix]<Math.fround(t.split_condition)?t.yes:t.no);t=t.children.find(c=>c.nodeid===next);}return t.leaf;}
function createDetector(name='rf51_baseline'){
 const eng=new E.UnifiedEngine({mode:'FUSION'});let fallback=null,actual=name; const unique=['xgb69_dualpath_unique','xgb69_unique'].includes(name);const staticPath=['xgb69_dualpath','xgb69_dualpath_unique','xgb69_dualpath_trained'].includes(name);const modelName=name==='xgb69_dualpath_trained'?'dual_xgb69_candidate':(staticPath||unique?'xgb69_candidate':name);
 /* GEOMETRY：detector层几何决策覆盖(不改冻结engine)。engine FUSION原生无geometry_only(engine.js:100)，
    故插件在tick后用每候选geo_features.label/confidence重算decision；RF概率仍留scores.rf51供对照，
    detector名标'geometry(post)'明示这是后处理覆盖而非engine原生几何模式，不伪装。 */
 if(name==='geometry'){
  const S=require('./core/schema');
  const baseTick=fc=>eng.tick(fc);
  /* Q01：geometry(post) 是研究型后处理对照，不是纯几何生产基线。
   * detector 层覆盖决策后，必须同步 track 显示语义，否则 UI 同时展示互相矛盾的
   * classifier_decision 与 track_confirmed（实测 98.7% 不一致）。这里把候选的
   * track_confirmed 与 _tracks 中受影响 track 的 human_confirmed 按几何决策重算，
   * 保留 _rf_decision 供对照；并显式标记 track_semantics 供审计。 */
  return {name:'geometry(post)',requested:name,fallback:null,engine:eng,begin:sid=>eng.begin_session(sid),track_semantics:'overridden_by_geometry_posthoc',
   tick:fc=>{const d=baseTick(fc);const geoTrack={};
    for(const c of d._candidates){const g=c.geo_features;const lab=g&&(g.label||g.joint);
     const dec=lab==='CONFIRMED_HUMAN'||lab==='person'?S.CLS_DECISION.CONFIRMED_HUMAN:(lab==='HUMAN_CANDIDATE'||c.scores.geometry&&c.scores.geometry.gates>=0.5?S.CLS_DECISION.HUMAN_CANDIDATE:S.CLS_DECISION.NON_HUMAN);
     c._rf_decision=c.classifier_decision;c.classifier_decision=dec;
     if(c.track_id){const confirmed=dec===S.CLS_DECISION.CONFIRMED_HUMAN;c.track_confirmed=confirmed;const m=/^FUS_t(\d+)_(\d+)$/.exec(c.track_id);if(m)geoTrack[+m[2]]=confirmed;}}
    for(const t of d._tracks||[])if(Object.hasOwn(geoTrack,t.id))t.human_confirmed=geoTrack[t.id];
    return d;}};
 }
 if(name!=='rf51_baseline'){
  try{const file=path.join(__dirname,'models',modelName+'.json'),m=JSON.parse(fs.readFileSync(file,'utf8'));if(!['rf','xgb'].includes(m.kind)||![51,69].includes(m.n_features)||!m.trees.length)throw Error('model contract');const extract=eng.rf.extract.bind(eng.rf);
   eng.rf={extract:(sub,it)=>{const b=Array.from(extract(sub,it));return Float32Array.from(m.n_features===69?b.concat(extra(sub)):b);},predict_person:x=>m.kind==='rf'?m.trees.reduce((s,t)=>s+treeRF(t,x),0)/m.trees.length:1/(1+Math.exp(-(m.base_margin+m.trees.reduce((s,t)=>s+treeXGB(t,x),0))))};eng.rf_model_sha=E.hash_file(file);
  }catch(e){fallback=e.message;actual='rf51_baseline';}
 }
 if(staticPath&&!fallback)require('./static_path').addStatic(eng);
 if(unique&&!fallback)require('./unique_tracker').install(eng);
 return {name:actual,requested:name,fallback,engine:eng,begin:sid=>eng.begin_session(sid),tick:fc=>eng.tick(fc)};
}
module.exports={createDetector,treeRF,treeXGB};
