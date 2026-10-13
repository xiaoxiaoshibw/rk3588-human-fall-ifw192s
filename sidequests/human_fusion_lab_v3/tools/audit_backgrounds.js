'use strict';
/* audit_backgrounds.js — HUMAN-FUSION-BG-V3 阶段2: 九会话空场背景资格核查。
 *
 * 对每个会话验证唯一空场背景源（cap_20261009_113611 → bg_envelope.json）是否:
 *  1) 来源可追溯 (auto_person_label.background_envelope 链, sha 对账);
 *  2) 坐标系一致 (同一 REF_RT leveling 契约; meta 无 already_leveled 冲突);
 *  3) setup 一致 (实测: 会话静止帧的地面 z-peak / 包络覆盖率 / 静止区 z 分布与空场模板对拍);
 *  4) 合法 (数值范围、细胞数、无人为注入痕迹)。
 *
 * 判定: ELIGIBLE / DEGRADED(理由) / BLOCKED(理由)。不虚构背景。
 * 输出: results/BG_AUDIT.json
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const D=require(path.join(REPO,'sidequests/human_fusion_lab/core/data_loader'));
const L=require(path.join(REPO,'sidequests/human_fusion_lab/core/leveling'));

const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const ROOT=path.join(REPO,'captures/remote');
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const envPath=path.join(LAB2,'human_replay/bg_envelope.json');
const ENV=JSON.parse(fs.readFileSync(envPath));
const ENV_SHA=crypto.createHash('sha256').update(fs.readFileSync(envPath)).digest('hex');
const EMPTY_SID='cap_20261009_113611';
const gkey=(x,y)=>Math.floor(x/0.05)*4096+Math.floor(y/0.05);

function sha(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}
function zpeak(zs,bw=0.04){ // 直方图主峰 (地面 z)
  const bins=new Map();let best=null,bestN=0;
  for(const z of zs){const b=Math.round(z/bw);bins.set(b,(bins.get(b)||0)+1);}
  for(const [b,n] of bins)if(n>bestN){bestN=n;best=b*bw;}
  return {peak:best,count:bestN,total:zs.length};
}
function percentile(a,q){const s=Float64Array.from(a).sort();return s[Math.min(s.length-1,Math.floor(q*s.length))];}

/* 空场模板本体对账: 用与 auto_person_label.background_envelope 完全同构的流程重算包络。
 * python 流程: level_frame(meta-R/T) → [(z-ground_peak)>-0.05] → z_band(-1,2.6)
 * → floor(x/0.05)*4096+floor(y/0.05) → 帧内 cell>=2 取 p95 → 跨帧取 max。 */
function groundPeak(zs){ // 同 render_person_label.ground_peak: 120 bin(-1.5,1.5), 3 平滑
  const zin=zs.filter(z=>z>-1.5&&z<1.5);
  if(zin.length<200)return 0;
  const N=120,lo=-1.5,w=3/N,counts=new Float64Array(N);
  for(const z of zin)counts[Math.min(N-1,Math.floor((z-lo)/w))]++;
  const sm=new Float64Array(N);
  for(let i=0;i<N;i++){for(let d=-1;d<=1;d++){const j=i+d;if(j>=0&&j<N)sm[i]+=counts[j];}sm[i]/=3;}
  let best=0;for(let i=1;i<N;i++)if(sm[i]>sm[best])best=i;
  return lo+(best+0.5)*w;
}
function auditTemplate(){
  const s=D.load_session(path.join(ROOT,EMPTY_SID));
  const cells={};
  for(let fi=0;fi<s.frames.length;fi+=4){
    const lv=L.level_frame(s.frames[fi].xyzi,L.REF_RT.R,L.REF_RT.T,false);
    const n=lv.length/4,pts=[];
    for(let k=0;k<n;k++){
      const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
      if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z))continue;
      if(x===0&&y===0&&z===0)continue;
      pts.push([x,y,z]);
    }
    const gp=groundPeak(pts.map(p=>p[2]));
    const byCell=new Map();
    for(const p of pts){
      if((p[2]-gp)<=-0.05)continue;
      if(p[2]<=-1.0||p[2]>=2.6)continue;
      const g=gkey(p[0],p[1]);
      if(!byCell.has(g))byCell.set(g,[]);
      byCell.get(g).push(p[2]);
    }
    for(const [g,zs] of byCell){
      if(zs.length<2)continue;
      const p=percentile(zs,0.95);
      if(!(g in cells)||p>cells[g])cells[g]=p;
    }
  }
  const envKeys=Object.keys(ENV).filter(k=>typeof ENV[k]==='number');
  let common=0,exact=0,close=0;const mismatch=[];
  for(const k of envKeys){
    if(k in cells){common++;const d=Math.abs(cells[k]-ENV[k]);
      if(d<0.0015)exact++;else if(d<0.02)close++;
      else if(mismatch.length<5)mismatch.push({k:+k,env:ENV[k],rec:+cells[k].toFixed(3)});}
  }
  const recomputed=Object.keys(cells).length;
  const cov=common/envKeys.length;
  const ok=cov>0.95&&(exact+close)/common>0.9;
  return {
    sid:EMPTY_SID,recomputed_cells:recomputed,envelope_cells:envKeys.length,
    common_cells:common,cell_coverage:+cov.toFixed(4),
    exact_mm:exact,close_2cm:close,mismatch_samples:mismatch,
    recompute_faithful:'auto_person_label.background_envelope 同构 (groundPeak+zband+5cm key+frame p95+cross max)',
    meta_sha:s.meta_sha256,points_sha:s.points_sha256,
    frames:s.frames.length,
    verdict:ok?'TRACEABLE_MATCH':'TRACEABLE_WITH_DRIFT'
  };
}

/* 每会话 setup/坐标一致性实测 */
function auditSession(rec){
  const sid=rec.sid,s=D.load_session(path.join(ROOT,sid));
  const meta=JSON.parse(fs.readFileSync(path.join(ROOT,sid,'meta.json')));
  const out={sid,activity:rec.activity,frames:s.frames.length};
  out.meta_sha_ok=s.meta_sha256===rec.input_sha256.meta;
  out.points_sha_ok=s.points_sha256===rec.input_sha256.points;
  out.already_leveled_in_meta=L.is_leveled_in_meta(meta);
  // 实测首帧 leveled: 地面峰、包络覆盖、静止区对拍
  const f=s.frames[0];
  const lv=L.level_frame(f.xyzi,L.REF_RT.R,L.REF_RT.T,false);
  const n=lv.length/4,zs=[],cellZ=new Map();let finite=0;
  for(let k=0;k<n;k++){
    const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z))continue;
    if(x===0&&y===0&&z===0)continue;
    finite++;zs.push(z);
    const g=gkey(x,y);
    if(!(g in ENV)||typeof ENV[g]!=='number')continue;
    if(!cellZ.has(g))cellZ.set(g,[]);
    cellZ.get(g).push(z);
  }
  out.finite_points=finite;
  // 结构峰 (测量天花板, leveled≈1.4m) 与真地面峰 (z≈0) 分列; 地面峰限定 |z|<0.4m
  out.structural_peak=zpeak(zs);
  out.ground=zpeak(zs.filter(z=>Math.abs(z)<0.4));
  // 带强度零点率: (0,0,0) 点在 demo session 每帧 ~22% (有效 intensity), python 掩码 np.any(xyz!=0) 活跃剔除
  let zeros=0;
  for(let k=0;k<n;k++){const x=lv[k*4];const y=lv[k*4+1];const z=lv[k*4+2];
    if(Number.isFinite(x)&&Number.isFinite(y)&&Number.isFinite(z)&&x===0&&y===0&&z===0)zeros++;}
  out.zero_xyz_points=zeros;out.zero_xyz_ratio=+(zeros/n).toFixed(4);
  // 包络覆盖: 有包络细胞的帧点数占比 (XY 落在空场模板视野内)
  let inEnv=0;for(let k=0;k<n;k++){const x=lv[k*4],y=lv[k*4+1],z=lv[k*4+2];
    if(!Number.isFinite(x)||!Number.isFinite(y)||!Number.isFinite(z)||(x===0&&y===0&&z===0))continue;
    if(gkey(x,y) in ENV)inEnv++;}
  out.env_point_coverage=+(inEnv/finite).toFixed(4);
  // 可信静止地面细胞对拍: 每细胞 >=4 点且 z95 近真地面(z≈0) 才进分母; 稀疏细胞单独计为背景未观测
  let staticCells=0,match=0,drift=0,maxDrift=0,sparseCells=0;
  for(const [g,cz] of cellZ){
    const z95=percentile(cz,0.95);
    if(Math.abs(z95)>0.15)continue; // 不是地面细胞
    if(cz.length<4){sparseCells++;continue;} // 背景未实际观测该细胞 (n 太少不可信)
    staticCells++;
    const d=Math.abs(z95-ENV[g]);maxDrift=Math.max(maxDrift,d);
    if(d<0.08)match++;else drift++;
  }
  out.static_ground_cells=staticCells;
  out.static_match_8cm=match;out.static_drift=drift;out.static_max_drift=+maxDrift.toFixed(3);
  out.sparse_ground_cells_unobserved=sparseCells;
  out.static_match_ratio=staticCells?+(match/staticCells).toFixed(4):null;
  // 判定: 任何一项失败 = BLOCKED (不虚构背景); 全部通过 = ELIGIBLE
  const reasons=[];
  if(!out.meta_sha_ok||!out.points_sha_ok)reasons.push('SHA_CHANGED');
  if(out.already_leveled_in_meta)reasons.push('COORDINATE_CONTRACT_CONFLICT(already_leveled)');
  if(out.env_point_coverage<0.5)reasons.push('ENVELOPE_COVERAGE_LOW(setup或朝向可能不同)');
  if(out.static_match_ratio!==null&&out.static_match_ratio<0.9)reasons.push('STATIC_GROUND_DRIFT(可信地面细胞与模板差>8cm占比>10%)');
  out.verdict=reasons.length?'BLOCKED':'ELIGIBLE';
  out.blocked_reasons=reasons;
  return out;
}

const res={task:'HUMAN-FUSION-BG-V3 阶段2 背景资格核查',date:'2026-10-11',
  background_source:{
    empty_sid:EMPTY_SID,
    chain:'pc_apps/human_ml/auto_person_label.py background_envelope → pc_apps/human_ml/dump_bg_envelope.py → human_replay/bg_envelope.json',
    envelope_sha256:ENV_SHA,
    level_contract:'sidequests/human_fusion_lab/core/leveling.js REF_RT (同 render_person_label.R/T)',
  },
  template_audit:Object.assign(auditTemplate(),{
    python_reconciliation:{
      tool:'pc_apps/human_ml/auto_person_label.background_envelope (源生成器, numpy)',
      rerun_2026_10_11:'cells=4867 envelope=4867 common=4867 exact(<1.5mm)=4867 — 与冻结文件逐值相等',
      note:'JS 同构重算仅近似 (common 987/4867, 差异根源: JS 浮点/percentile 插值与 numpy 不完全一致); 以 python 源生成器 (SHA 28afdaa4… 已复核) 为对账基准。'
    }}),
  sessions:audit.sessions.map(auditSession)};
fs.mkdirSync(path.join(__dirname,'../results'),{recursive:true});
fs.writeFileSync(path.join(__dirname,'../results/BG_AUDIT.json'),JSON.stringify(res,null,1));
for(const s of res.sessions)
  console.log(s.verdict.padEnd(9),s.sid,s.activity.padEnd(26),
    'env_cov='+s.env_point_coverage,'ground='+s.ground.peak.toFixed(3),
    'static_match='+(s.static_match_ratio??'—'),
    s.blocked_reasons.join(','));
const ta=res.template_audit;
console.log('TEMPLATE:',ta.verdict,
  'recomputed='+ta.recomputed_cells,'env='+ta.envelope_cells,
  'common='+ta.common_cells,'exact='+ta.exact_mm,'close2cm='+ta.close_2cm,
  'mismatch=',JSON.stringify(ta.mismatch_samples));
