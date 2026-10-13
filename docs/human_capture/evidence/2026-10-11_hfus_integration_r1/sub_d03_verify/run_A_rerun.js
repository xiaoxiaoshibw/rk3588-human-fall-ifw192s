'use strict';
// 独立复跑 HFUS-D03 mode A (legacy xgb69_candidate fixed detector)
// 逐帧回放生成本模式 ledger, 复刻 run_b.js 的 run('A', ...) 内部逻辑,
// 唯一差别: 默认输出目录改到 sub_d03_verify。BG-B 引用仍构建 (run_b 同一构建路径), A 模式不用 select。
const path=require('path'),fs=require('fs'),B=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/detector_b');
const {run}=require('D:/Code/ldiar/sidequests/human_fusion_lab_next/background/run_b');
const out=process.argv[2]||path.join(B.ROOT,'docs/human_capture/evidence/2026-10-11_hfus_integration_r1/sub_d03_verify/rerun_A');
fs.mkdirSync(out,{recursive:true});
const report=run('A',out,process.argv[3]?process.argv[3].split(','):null);
console.log('A_RERUN_DONE',out);
