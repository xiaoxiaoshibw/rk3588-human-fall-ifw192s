'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const E=require('./engine_b'),L=require('../../human_fusion_lab/core/leveling'),I=require('../contracts/index_v1');
const BG=require('../../human_fusion_lab_v3/core/bg_groups'),D=require('../../human_fusion_lab/core/data_loader');
const {extra}=require('../../human_fusion_lab/export'),{treeXGB}=require('../../human_fusion_lab/detector'),{UniqueTracker}=require('../../human_fusion_lab/unique_tracker');
const ROOT=path.resolve(__dirname,'../../..'),LAB=path.join(ROOT,'sidequests/human_fusion_lab');
function sha(p){return E.hash_file(p);}
function buildReference(){
 const source=path.join(ROOT,'captures/remote/cap_20261009_113611');
 const s=D.load_session(source),pipe=E.load_production('human_pipe_lib.js'),frames=[];
 for(let fi=0;fi<s.frames.length;fi+=4)frames.push(I.mapFrame(s.frames[fi].xyzi,{...L.REF_RT,already_leveled:false}).compact_leveled_xyzi);
 const built=BG.buildGroupBMap(pipe,frames,.5);
 const columns=new Map();for(const rec of built.staticKeys.values()){const key=Math.floor(rec.x/.15)+','+Math.floor(rec.y/.15);if(!columns.has(key))columns.set(key,[]);columns.get(key).push(rec);}
 return {staticKeys:built.staticKeys,columns,coordinate:{...L.REF_RT,already_leveled:false},manifest:{source,meta_sha:s.meta_sha256,points_sha:s.points_sha256,frames:s.frames.length,sample_step:4,sampled:frames.length,min_occ:.5,voxels:built.refMap.voxels.size,static_keys:built.staticKeys.size,coordinate:L.REF_RT,pipe:pipe.PIPE,ray_coverage:'UNKNOWN',FREE_available:false,unknown_support:{kind:'observed_reference_XY_neighborhood',radius_m:.4,scale_source:'existing retention hot_cell_radius_m; preregistered not tuned',not_ray_FREE:true}}};
}
function select(lv,pipe,keys,columns){
 const out=BG.groupB(lv,pipe,keys);
 out.bare_keep=out.keep.slice();
 if(columns){for(let r=0;r<out.keep.length;r++){if(!out.keep[r])continue;const x=lv[r*4],y=lv[r*4+1],ix=Math.floor(x/.15),iy=Math.floor(y/.15);let support=false;outer:for(let a=-3;a<=3;a++)for(let b=-3;b<=3;b++){const list=columns.get((ix+a)+','+(iy+b));if(list&&list.some(c=>(c.x-x)**2+(c.y-y)**2<=.4**2)){support=true;break outer;}}if(!support){out.keep[r]=0;out.reasons[r]='no_reference_XY_support_UNKNOWN';}else out.reasons[r]='no_bg_match_supported_XY_UNKNOWN';}}
 out.states=out.reasons.map(r=>r==='bg_voxel_match'?'OCCUPIED':'UNKNOWN');
 out.policy='UNKNOWN may only enter fixed workspace/cleanup/component-quality gates, never directly HUMAN; missing full reference BLOCKED; no FREE claim';
 return out;
}
function createDetector(reference){
 assert(reference&&reference.staticKeys&&reference.staticKeys.size,'missing reference UNKNOWN/BLOCKED');
 const e=new E.UnifiedEngine({mode:'FUSION'});
 e._bgB={...reference,select:(lv,pipe,keys)=>select(lv,pipe,keys,reference.columns)};
 const modelFile=path.join(LAB,'models/xgb69_candidate.json'),m=JSON.parse(fs.readFileSync(modelFile)),extract=e.rf.extract.bind(e.rf);
 e.rf={extract:(sub,it)=>Float32Array.from(Array.from(extract(sub,it)).concat(extra(sub))),predict_person:x=>1/(1+Math.exp(-(m.base_margin+m.trees.reduce((s,t)=>s+treeXGB(t,x),0))))};
 e.rf_model_sha=sha(modelFile);
 e._level=function(x,opts){const co=L.resolve_contract(opts,this.cfg.leveling_rt);if(JSON.stringify(co.R)!==JSON.stringify(reference.coordinate.R)||JSON.stringify(co.T)!==JSON.stringify(reference.coordinate.T)||co.already_leveled)throw Error('BG-B coordinate mismatch UNKNOWN/BLOCKED');if(this._coordinate_contract&&JSON.stringify(co)!==JSON.stringify(this._coordinate_contract))throw Error('coordinate changed');this._coordinate_contract=co;this._mapped=I.mapFrame(x,co);return this._mapped.leveled_xyzi;};
 const tick=e._tick_fusion;e._tick_fusion=function(...args){if(!(this.fusion_ctx.tracker instanceof UniqueTracker))this.fusion_ctx.tracker=new UniqueTracker(this.cfg.fusion_cfg);return tick.apply(this,args);};
 return {engine:e,begin:s=>e.begin_session(s),tick:fc=>e.tick(fc)};
}
module.exports={ROOT,LAB,buildReference,createDetector,select,sha};
if(require.main===module){assert.throws(()=>createDetector(null));const pipe=E.load_production('human_pipe_lib.js'),lv=new Float32Array([1,1,1,1,NaN,NaN,NaN,1]),o=select(lv,pipe,new Map());assert.equal(o.states[0],'UNKNOWN');assert.equal(o.keep[1],0);assert.equal(o.states[1],'UNKNOWN');console.log('BG_B_BOUNDARY_PASS');}
