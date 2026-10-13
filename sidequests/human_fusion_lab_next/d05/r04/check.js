'use strict';
const assert=require('assert'),old=require('../hook_unknown'),fast=require('./hook_unknown_fast');
let seed=17;const rand=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed/4294967296;};
let checked=0;
for(const minLocal of [1,2,4])for(const minRef of [1,2])for(const r of [.3,.6])for(let trial=0;trial<10;trial++){
 const n=trial?150:4,lv=new Float32Array(n*4),columns=new Map(),keep=new Uint8Array(n),bare=new Uint8Array(n),reasons=[];
 for(let i=0;i<n;i++){lv[i*4]=rand()*3-1.5;lv[i*4+1]=rand()*3-1.5;lv[i*4+2]=i%5?rand()*2:.1;bare[i]=i%4?1:0;keep[i]=i%11?0:1;reasons.push(keep[i]?'bg_voxel_match':'no_reference_XY_support_UNKNOWN');if(i%2){const x=lv[i*4]+.05,y=lv[i*4+1]-.05,k=Math.floor(x/.15)+','+Math.floor(y/.15);if(!columns.has(k))columns.set(k,[]);columns.get(k).push({x,y});}}
 const engine=()=>({_bgB:{columns,select(){return {keep:keep.slice(),bare_keep:bare.slice(),reasons:reasons.slice(),states:[]};}}});
 const a=engine(),b=engine(),cfg={r,link_xy_m:.3,min_ref_support:minRef,min_local_pts:minLocal};old.applyUnknown(a,cfg);fast.applyUnknown(b,cfg);
 assert.deepStrictEqual(b._bgB.select(lv),a._bgB.select(lv));assert.deepStrictEqual(b._unknown_hook_stats,a._unknown_hook_stats);checked++;
}
console.log('R04_SHORT_CIRCUIT_COUNTEREXAMPLES_PASS',checked);
