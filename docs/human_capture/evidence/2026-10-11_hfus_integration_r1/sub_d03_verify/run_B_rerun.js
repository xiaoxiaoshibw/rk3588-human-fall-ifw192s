'use strict';
// 独立复跑 HFUS-D03 mode B (BG-B reference UNKNOWN 门 + FUSION tracker)
// 同 run_b.run('B', outdir, filter) 逻辑, 输出到 sub_d03_verify。
const path=require('path'),fs=require('fs'),B=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/detector_b');
const {run}=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/run_b');
const out=process.argv[2]||path.join(B.ROOT,'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d03_verify/rerun_B');
fs.mkdirSync(out,{recursive:true});
const report=run('B',out,process.argv[3]?process.argv[3].split(','):null);
console.log('B_RERUN_DONE',out);
