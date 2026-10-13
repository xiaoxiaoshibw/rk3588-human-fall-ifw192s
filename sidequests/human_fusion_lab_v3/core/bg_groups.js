'use strict';
/* bg_groups.js — HUMAN-FUSION-BG-V3 三组背景提取对照 (阶段3)。
 *
 * 三组共用同一空场背景源 (cap_20261009_113611 REF 包络, SHA 28afdaa4…) 与同一批
 * demo session leveled 帧, 逐点给 {group, kept, reason} 判定:
 *
 *  A 现有算法  = 生产 FUSION ref_only 包络热点过滤语义 (engine._fusion_a_chain):
 *    z∈(0.1,2.3), cell 有包络(≥-9), z>env+0.25 → 热点保留, 其余删除。
 *    诚实记录: 无包络细胞、超 z 窗、低 z 各自的删除原因。
 *
 *  B 容差体素背景 = human_pipe_lib.build_reference_map + extract_foreground_fused
 *    (refkeys=空场模板参考体素图, online=null):
 *    3D 体素 (0.15×0.15×0.12) 形心匹配半径 0.12m。容差体现在: 以点对面而不是
 *    单一 z 阈值, 且 3×3×3 邻域匹配吸收配准抖动。不调用在线 build_static_map
 *    (A 链 online 自污染已在 V2 证实), 因此静止人体不可能被 B 的背景更新吸收——
 *    本组背景在 begin_session 时一次性冻结, 运行期只读。
 *
 *  C 带可见性与距离自适应的背景差分:
 *    - 距离自适应阈值 τ(r): 近处包络 z 精度高用小阈值, 远处点稀疏用大阈值
 *      (τ = clamp(τ0 + k·r, τ_min, τ_max), 参数显式, 不是调出来的常数堆)。
 *    - 可见性: 空场模板里每细胞的"期望回波密度" ρ_env(cell)。若当前帧到该细胞的
 *      距离带上存在"应见而未见"的空包络区 (模板有内容, 当前帧完全无点),
 *      说明该射线被更近物体遮挡 — 遮挡点本身按前景候选处理。
 *    - 包络缺失细胞: A 组丢, C 组按距离窗保守保留 (UNKNOWN 不删人)。
 *
 * 原则: 不删静止人体。任何组若删除 GT PERSON 点, 在归因中记 bg_loss, 作为该组
 * 劣化的硬指标 (S8/S6 重点)。
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');

const gkey5=(x,y)=>Math.floor(x/0.05)*4096+Math.floor(y/0.05);

/* ---------- 载入空场 REF 包络 (与 engine.load_ref_envelope 同文件) ---------- */
function loadEnvelope(lab2){
  const p=path.join(lab2,'human_replay/bg_envelope.json');
  return {env:JSON.parse(fs.readFileSync(p)),path:p,
    sha:crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex')};
}

/* ---------- A 组: 生产 ref_only 包络热点语义 (1:1) ---------- */
function groupA(lv,env){
  const n=lv.length/4;
  const keep=new Uint8Array(n),reasons=new Array(n);
  for(let k=0;k<n;k++){
    const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z)){reasons[k]='invalid';continue;}
    if(x===0&&y===0&&z===0){reasons[k]='zero_xyz_stale';continue;} // 带强度零点 (numpy 屏蔽)
    if(z<=0.1){reasons[k]='z_below_0.1';continue;}
    if(z>=2.3){reasons[k]='z_above_2.3';continue;}
    const e=env[gkey5(x,y)];
    if(e===undefined){reasons[k]='no_envelope_cell';continue;}
    if(e<-9){reasons[k]='envelope_sentinel';continue;}
    if(z<=e+0.25){reasons[k]='within_envelope+0.25';continue;}
    keep[k]=1;reasons[k]='hot_above_envelope';
  }
  return {keep,reasons};
}

/* ---------- B 组: 生产容差体素 (build_reference_map + extract_fused) ---------- */
/* 预构建: 每空场一次, 结果冻结复用。返回 {refMap, staticKeys(Map 供删除)}。
 * staticKeys 只收 occ >= min_occ 的体素 (与 reference_static_keys 同律),
 * 低占用(偶发噪声/稀疏)体素不给删除权 — 对齐"不得仅凭瞬时观测删"原则。 */
function buildGroupBMap(pipe,refFrames,minOcc){
  const refMap=pipe.build_reference_map(refFrames,{drop_ground:true});
  const thr=minOcc===undefined?0.5:minOcc;
  const staticKeys=new Map();
  refMap.voxels.forEach(function(rec,key){if(rec.occ>=thr)staticKeys.set(key,rec);});
  return {refMap,staticKeys};
}
function groupB(lv,pipe,staticKeys){
  const n=lv.length/4;
  const keep=new Uint8Array(n),reasons=new Array(n);
  // 与 extract_foreground_fused(refkeys=staticKeys,online=null) 1:1 内联, 但保留逐点原因
  const mr2=pipe.PIPE.bg_match_radius*pipe.PIPE.bg_match_radius;
  const vx=pipe.PIPE.bg_voxel_xy,vz=pipe.PIPE.bg_voxel_z;
  // human_pipe_lib._bg_key_ijk 同构: ((ix+4096)*8192+(iy+4096))*8192+(iz+4096)
  const key=(ix,iy,iz)=>((ix+4096)*8192+(iy+4096))*8192+(iz+4096);
  for(let k=0;k<n;k++){
    const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z)){reasons[k]='invalid';continue;}
    if(x===0&&y===0&&z===0){reasons[k]='zero_xyz_stale';continue;}
    if(z<pipe.PIPE.ground_keep_below_m){reasons[k]='z_below_ground';continue;}
    if(z>pipe.PIPE.z_max_m){reasons[k]='z_above_max';continue;}
    const ix=Math.floor(x/vx),iy=Math.floor(y/vx),iz=Math.floor(z/vz);
    let hit=null;
    outer: for(let a=-1;a<=1;a++)for(let b=-1;b<=1;b++)for(let c=-1;c<=1;c++){
      const rec=staticKeys.get(key(ix+a,iy+b,iz+c));
      if(!rec)continue;
      const dx=rec.x-x,dy=rec.y-y,dz=rec.z-z;
      if(dx*dx+dy*dy+dz*dz<mr2){hit=rec;break outer;}
    }
    if(hit){reasons[k]='bg_voxel_match';continue;}
    keep[k]=1;reasons[k]='no_bg_voxel_match';
  }
  return {keep,reasons};
}

/* ---------- C 组: 可见性 + 距离自适应差分 ---------- */
/* 参数 (显式, 对应 C 设计说明; 默认未调优, 初值取物理直觉):
 *  tau0=0.15m 基础阈值 (近距, 包络 z95 噪声量级)
 *  tau_k=0.05 /m 距离斜率 (激光测距噪声随距离增长)
 *  tau_min=0.12 tau_max=0.45
 *  occ_band=0.3m 遮挡判定距离带
 */
const C_CFG=Object.freeze({tau0:0.15,tau_k:0.05,tau_min:0.12,tau_max:0.45,occ_band:0.3});
/* 空场模板的可见性档案: 每 5cm cell 的 {z_env, npts_total, frame_support}。
 * frame_support = 该 cell 在多少空场帧有≥2点 — 高 support 的细胞才可信其包络。 */
function buildGroupCVisibility(env,emptyLeveledFrames){
  const vis=new Map(); // gkey → {npts, fsupport}
  for(const lv of emptyLeveledFrames){
    const n=lv.length/4,frameCells=new Map();
    for(let k=0;k<n;k++){
      const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
      if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z))continue;
      if(x===0&&y===0&&z===0)continue;
      const g=gkey5(x,y);
      frameCells.set(g,(frameCells.get(g)||0)+1);
    }
    for(const [g,c] of frameCells){
      if(c<2)continue;
      let v=vis.get(g);
      if(!v){v={npts:0,fsupport:0};vis.set(g,v);}
      v.npts+=c;v.fsupport++;
    }
  }
  // 附加包络 z
  for(const [g,v] of vis){if(typeof env[g]==='number')v.z_env=env[g];}
  return vis;
}
function groupC(lv,env,vis,cfg){
  cfg=cfg||C_CFG;
  const n=lv.length/4;
  const keep=new Uint8Array(n),reasons=new Array(n);
  for(let k=0;k<n;k++){
    const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z)){reasons[k]='invalid';continue;}
    if(x===0&&y===0&&z===0){reasons[k]='zero_xyz_stale';continue;}
    if(z<=0.1){reasons[k]='z_below_0.1';continue;}
    if(z>=2.3){reasons[k]='z_above_2.3';continue;}
    const g=gkey5(x,y);
    const e=env[g];
    const r=Math.hypot(x,y);
    const tau=Math.max(cfg.tau_min,Math.min(cfg.tau_max,cfg.tau0+cfg.tau_k*r));
    if(e===undefined){
      // 包络未覆盖细胞 (模板未观测该 XY; 可能是远端/盲区): 距离自适应保守
      // — 若 z 已超过"人体可到高度"上沿仍删 (天花板/吊柜), 否则保留不删人
      if(z>1.9){reasons[k]='no_envelope_cell_z_above_reach';continue;}
      keep[k]=1;reasons[k]='no_envelope_cell_keep_unknown';continue;
    }
    if(e<-9){keep[k]=1;reasons[k]='envelope_sentinel_keep_unknown';continue;}
    if(z>e+tau){keep[k]=1;reasons[k]='hot_above_tau(r='+r.toFixed(2)+',tau='+tau.toFixed(2)+')';continue;}
    // 可见性: 低帧支撑细胞 (fsupport<3) 包络不可靠 → 也保
    const v=vis.get(g);
    if(v&&v.fsupport<3){keep[k]=1;reasons[k]='low_cell_support_keep_unknown';continue;}
    reasons[k]='within_adaptive_envelope';continue;
  }
  return {keep,reasons};
}

module.exports={gkey5,loadEnvelope,groupA,groupB,buildGroupBMap,groupC,buildGroupCVisibility,C_CFG};
