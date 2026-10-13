'use strict';
/* R3 统一复跑入口（CC 主线）。一次性产出本轮全部离线实测证据。
 * 用法: node run_r3_all.js   （在 sidequests/human_fusion_lab 下）
 * 产出去向：results/R3_*.json、results/R3_VIZ/*.svg、evidence/2026-10-11_cc_mainline_r1/{skeleton_adapt,skeleton_coarse}
 * 只读 fusion/skeleton/captures；不修改任何既有源文件或旧证据。 */
const cp=require('child_process'),path=require('path');
const steps=[
  ['重复ID/漏检/几何一致性逐帧诊断','run_r3_diagnostics.js'],
  ['缺陷帧三视图可视化(JSON->SVG)','render_r3_frames.js'],
  ['粗骨架可观测性适配探测','run_skeleton_adapt.js'],
  ['可验证粗骨架节点图','render_skeleton_coarse.js']
];
for(const [label,script] of steps){
  console.log('=== '+label+' ('+script+') ===');
  const r=cp.spawnSync('node',[path.join(__dirname,script)],{stdio:'inherit',env:process.env});
  if(r.status!==0){console.error('STEP FAILED:',script);process.exit(r.status||1);}
}
console.log('R3_ALL_DONE');
