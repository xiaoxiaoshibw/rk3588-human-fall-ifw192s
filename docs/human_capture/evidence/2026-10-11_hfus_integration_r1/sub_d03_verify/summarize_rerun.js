'use strict';
// 独立复跑 summarize_b: 对 rerun_A / rerun_B 两个目录内的 SUMMARY + ledger 产出 REGRESSION_COMPARISON_V2 与 EVENTS_V2.
// summarize_b.main(out) 需要同目录有 A_SUMMARY.json 与 B_SUMMARY.json, 因此建一个聚合目录把两符号拷贝进去再调。
const fs=require('fs'),path=require('path');
const {main}=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/summarize_b');
const B=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/detector_b');
const out=process.argv[2]||path.join(B.ROOT,'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d03_verify/rerun_sum');
fs.mkdirSync(out,{recursive:true});
const srcA=path.join(B.ROOT,'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d03_verify/rerun_A/A_SUMMARY.json');
const srcB=path.join(B.ROOT,'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d03_verify/rerun_B/B_SUMMARY.json');
fs.copyFileSync(srcA,path.join(out,'A_SUMMARY.json'));
fs.copyFileSync(srcB,path.join(out,'B_SUMMARY.json'));
main(out);
console.log('SUMMARIZE_RERUN_DONE',out);
