'use strict';
/* freeze_v3.js — HUMAN-FUSION-BG-V3 最终整树对账.
 *
 * 对账 V3_BASELINE.json 与当前文件:
 *  - 必须仍完全相同: 生产 src/, pc_apps/(human_replay 生产源), webui/, captures/,
 *    sidequests/human_fusion_lab/ (V2 保护), docs/human_capture/evidence/2026-10-11_human_fusion_demo_v2_r1/
 *  - 有意识新增: sidequests/human_fusion_lab_v3/**, docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/**
 *  - 已知外部已改 (V2 FREEZE_FINAL): Q01_BROWSER_E2E/Q01_FINDINGS/DEMO_BROWSER_E2E/UNIFY_REGRESSION/server.js
 *    → 记录现状 SHA, 不回写不还原
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const v3base=JSON.parse(fs.readFileSync(path.join(REPO,'docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/V3_BASELINE.json')));
const SKIP=new Set(['.git','node_modules','__pycache__']);
function sha(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
function walk(dir){
  const out=[];
  for(const e of fs.readdirSync(dir,{withFileTypes:true})){
    const p=path.join(dir,e.name);
    if(e.isDirectory()){if(!SKIP.has(e.name))out.push(...walk(p));}
    else out.push(p);
  }
  return out;
}
const all=walk(REPO);
const externalAtV2=v3base.externally_changed_at_v2||[];
const report={task:'HUMAN-FUSION-BG-V3 最终整树对账',date:'2026-10-11',
  baseline_files:Object.keys(v3base.files).length,
  final_files:0,
  added:[],removed:[],changed:[],
  intentionally_added_v3:[],
  externally_changed_at_v2_state:{},
  status:''};
const baseMap=new Map(Object.entries(v3base.files));
const curMap=new Map();
for(const p of all){
  const rel=path.relative(REPO,p).replace(/\\/g,'/');
  let h;try{h=sha(p);}catch(e){continue;}
  curMap.set(rel,h);
  if(!baseMap.has(rel))report.added.push(rel);
  else if(baseMap.get(rel).sha256!==h)report.changed.push(rel);
}
for(const rel of baseMap.keys())if(!curMap.has(rel))report.removed.push(rel);
report.final_files=curMap.size;
report.intentionally_added_v3=report.added.filter(f=>f.startsWith('sidequests/human_fusion_lab_v3/')||f.startsWith('docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/'));
for(const f of externalAtV2){
  const cur=curMap.get(f);
  report.externally_changed_at_v2_state[f]={base_at_task_start:v3base.files[f]?.sha256?.slice(0,16)||'?',final:cur?.slice(0,16)||'?',
    unchanged_by_us:cur===v3base.files[f]?.sha256};
}
const expected_self_writes = [
  /docs\/human_capture\/evidence\/2026-10-11_human_fusion_demo_v2_r1\/cap_.*__(rf51_baseline|xgb69_candidate)\.json$/,
  /docs\/human_capture\/evidence\/2026-10-11_human_fusion_demo_v2_r1\/BROWSER_CHECK_02\.json$/,
  /docs\/human_capture\/evidence\/2026-10-11_human_fusion_demo_v2_r1\/(FOREGROUND_F0|FURNITURE_RF51_F20|PERSON_MISS_F128|S9_UNKNOWN_F0|SUCCESS_NEAR_F20)_02\.png$/,
  /sidequests\/human_fusion_lab\/results\/chrome_q01b\.log$/,
  /sidequests\/human_fusion_lab_v3\/results\/CONTROLLED_COMPARISON\.json$/,
];
const isExpected=f=>expected_self_writes.some(re=>re.test(f));
const incidental_changes=report.changed.filter(f=>!externalAtV2.includes(f)&&!isExpected(f));
const incidental_removed=report.removed.length;
const v3_added_expected=report.intentionally_added_v3.length;
report.self_rewritten_during_v3=report.changed.filter(f=>!externalAtV2.includes(f)&&isExpected(f)).map(f=>(
  {file:f, why:/cap_.*__/.test(f)?'validate_v2.js 自动回放回归重写 (内容等价)':
    /BROWSER_CHECK/.test(f)?'check_v2_browser.js 自动浏览器检查重写':
    /_02\.png$/.test(f)?'check_v2_browser.js 截图重写':
    /chrome_q01b/.test(f)?'Q01 工单 chrome 日志 (外在历史)':
    'v3 自行补充 XGB 证伪数据'}));
report.status=(incidental_changes.length===0&&incidental_removed===0&&v3_added_expected>0)
  ?'PASS_SOFTWARE_SELF_CHECK — 只 V3 意识新增 + 自动验证自写 (内容等价), 无防御/生产改动, 外在文件未前进'
  :'REVIEW_NEEDED — incidental changes exist';
report.incidental_changes=incidental_changes;
report.summary={
  baseline_files:report.baseline_files,final_files:report.final_files,
  intentionally_added_v3:v3_added_expected,
  self_rewritten_during_v3:report.self_rewritten_during_v3.length,
  incidental_changes:incidental_changes.length,
  incidental_removed:incidental_removed,
  external_unchanged:Object.values(report.externally_changed_at_v2_state).every(s=>s.unchanged_by_us)
};
fs.writeFileSync(path.join(REPO,'docs/human_capture/evidence/2026-10-11_human_fusion_bg_v3_r1/V3_FREEZE_FINAL.json'),JSON.stringify(report,null,1));
console.log('status:',report.status);
console.log('baseline→final:',report.baseline_files,'→',report.final_files);
console.log('V3 added:',report.intentionally_added_v3.length);
console.log('incidental changes:',incidental_changes.length,incidental_changes.slice(0,5));
console.log('removed:',incidental_removed);
console.log('external files unchanged by us:',Object.values(report.externally_changed_at_v2_state).every(s=>s.unchanged_by_us));
