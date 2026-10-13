'use strict';
// 续跑 mode B 缺的会话 (180557, 180751). run_b.js 会在写入 *_SUMMARY.json 前 refuse overwrite,
// 故续跑需把产物落一个 staging 子目录, 再合并 per-session artifacts 回 rerun_B/.
// 传入 args: out_rerun_B_dir  src_resume_dir  [sid1,sid2]
const path=require('path'),fs=require('fs');
const B=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/detector_b');
const {run}=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/run_b');
const out_rerun_B=process.argv[2];
const stage=process.argv[3];
const filter=process.argv[4]?process.argv[4].split(','):null;
fs.mkdirSync(stage,{recursive:true});
const rep=run('B',stage,filter);
// 把 stage 的 per-sid ledger / S6 svg/flow 挪到 rerun_B (不覆盖已有会话)
const a=JSON.parse(fs.readFileSync(path.join(stage,'B_SUMMARY.json'),'utf8'));
let movedSessionRows=[];
for(const s of a.sessions){
  const base='B_'+s.sid+'.jsonl';
  fs.renameSync(path.join(stage,base),path.join(out_rerun_B,base));
  movedSessionRows.push(s);
}
// 把 stage 内的 S6 viz/源码碎件 全部保留在 stage 不动; rerun_B 已有 SOURCE_BEFORE 与 S6 viz
fs.copyFileSync(path.join(stage,'B_SUMMARY.json'),path.join(out_rerun_B,'B_SUMMARY_resume_part2.json'));
console.log('RESUME_DONE moved=' + movedSessionRows.map(s=>s.sid).join(','));
