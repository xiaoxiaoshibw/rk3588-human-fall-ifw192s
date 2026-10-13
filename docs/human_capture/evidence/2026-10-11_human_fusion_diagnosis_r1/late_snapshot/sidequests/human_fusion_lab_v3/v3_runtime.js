'use strict';
/* v3_runtime.js — HUMAN-FUSION-BG-V3 Demo V3 运行时: 包装 v2_runtime, 注入 A/B/C 三组诊断.
 *
 * 不改 V2; 每次 frame() 在同一会话/帧上并行计算:
 *  - A/B/C 三组 keep mask (同一份 leveled raw28B 序点云, 位置一一对应 raw 索引);
 *  - bg_diff_per_group: 由 GT 对象点级出数 (PERSON/FURNITURE × 组 × kept/lost);
 *  - point_trace: 首个 GT 人体前 24 点在 A/B/C 每组的 kept+reason (逐点追溯);
 *  - 保留 v2 frame() 原返回的所有字段 (candidates, tracks, layer_observations…)。
 *
 * 三组共享空场背景源 (cap_20261009_113611 → bg_envelope.json) 只在启动时构建一次。
 */
const fs=require('fs'),path=require('path');
const REPO=path.resolve(__dirname,'../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const V2=require(path.join(LAB2,'v2_runtime'));
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const E=require(path.join(LAB2,'core/engine'));
const bg=require(path.join(__dirname,'core/bg_groups'));
const gtLib=require(path.join(LAB2,'human_replay/gt_lib.js'));
const pipe=E.load_production('human_pipe_lib.js');

const audit=V2.audit,MODELS=V2.MODELS;
const {env,sha:envSha}=bg.loadEnvelope(LAB2);
const empty=D.load_session(path.join(REPO,'captures/remote','cap_20261009_113611'));
const emptyLv=[];
for(let i=0;i<empty.frames.length;i+=4)emptyLv.push(L.level_frame(empty.frames[i].xyzi,L.REF_RT.R,L.REF_RT.T,false));

/* GT 索引域 (gt_fill_static._select_idx_in_frame_np + annotator 契约):
 *  raw_point_indices = 帧内合法点序号 (= export.rawMap 序号):
 *  原始 28B 行 → 遍历时仅保留 finite 且 (x|y|z) 任一非零 → 压缩序号。
 *  转换 xyzi 行需： 帧级 rawMap[GT序号] = xyzi 下标。
 */
const {staticKeys,refMap}=bg.buildGroupBMap(pipe,emptyLv,0.5);
const vis=bg.buildGroupCVisibility(env,emptyLv);
const bMapInfo={voxels:refMap.voxels.size,static_keys:staticKeys.size,min_occ:0.5,
  input_empty_sha:empty.meta_sha256+'/'+empty.points_sha256};

class Runtime extends V2.Runtime {
  frame(sid,model,index){
    const r=super.frame(sid,model,index);
    const lv=r.xyzi;
    const outs={A:bg.groupA(lv,env),B:bg.groupB(lv,pipe,staticKeys),C:bg.groupC(lv,env,vis,bg.C_CFG)};
    r.bg_groups={input_empty:'cap_20261009_113611',envelope_sha:envSha,b_map_info:bMapInfo,
      c_cfg:bg.C_CFG,active:'B'};
    r.bg_masks={};
    for(const g of ['A','B','C']){
      const o=outs[g];
      let kept=0;for(let k=0;k<o.keep.length;k++)kept+=o.keep[k];
      r.bg_masks[g]={keep:Array.from(o.keep),reasons:o.reasons,kept_total:kept};
    }
    // 便捷 keep 原始下标列表 (与前端前景层一致)
    for(const g of ['A','B','C'])r['foreground_'+g]=idxOf(outs[g].keep);
    // GT 点级对照: doc objects 的 raw_point_indices 域是 rawMap(xyzi) 子集序
    // (export.objects → GT.decode_indices(...) → map[i] 即 raw28B 序的 xyzi 下标)
    // 需要同帧 rawMap 转换。lv 与 xyzi 位置一一对应, 共享 raw 映射。
    // GT 索引映射必须用 *未 leveling* 的 raw xyzi (data_loader session.frames[index].xyzi)
    // 因为 rawMap 过滤 (0,0,0), leveling 会把 (0,0,0)+T → (0,0,1.38) 非零, 恒等化映射错误。
    this._sessionForGT=this._sessionForGT||{};
    let sessRaw=this._sessionForGT[sid];
    if(!sessRaw){
      const session=D.load_session(path.join(REPO,'captures/remote',sid));
      // 预计算每帧 rawMap (只算一次, 后续帧共享)
      const rawMaps=session.frames.map(f=>{
        const m=[];
        for(let i=0;i<f.n_points;i++){
          const a=f.xyzi[i*4],b=f.xyzi[i*4+1],c=f.xyzi[i*4+2];
          if(Number.isFinite(a)&&Number.isFinite(b)&&Number.isFinite(c)&&(a!==0||b!==0||c!==0))m.push(i);
        }
        return m;
      });
      sessRaw={session,rawMaps};this._sessionForGT[sid]=sessRaw;
    }
    const rawMap=sessRaw.rawMaps[index];
    r.bg_diff_per_group=frameGroupGT(sid,r.index,rawMap,lv,outs);
    r.point_trace=pointTrace(sid,r.index,rawMap,lv,outs);
    return r;
  }
}
function idxOf(keep){
  const out=[];
  for(let k=0;k<keep.length;k++)if(keep[k])out.push(k);
  return out;
}
/* GT 索引域转换: GT.raw_point_indices 是「帧内合法点序号」 (export.rawMap 域,
 * 基于原始传感 xyzi, 未 leveling — leveling 会把 (0,0,0) 映射到非零 T, 破坏 map). */
// rawMap 已移到 Runtime._sessionForGT 预缓存 (每会话一次)

function frameGroupGT(sid,frameIndex,raw,lv,outs){
  const doc=audit.docs[sid];
  if(!doc)return null;
  const ids=(doc.frames_objects||{})[String(frameIndex)]||[];
  if(!ids.length)return null;
  const per={};
  for(const g of ['A','B','C'])per[g]={};
  for(const objId of ids){
    const o=doc.objects[objId];
    if(!o)continue;
    let dec;
    try{dec=gtLib.decode_indices(o.raw_point_indices);}catch(e){continue;}
    const xyzi_ids=dec.filter(li=>Number.isSafeInteger(li)&&li>=0&&li<raw.length).map(li=>raw[li]);
    for(const g of ['A','B','C']){
      if(!per[g][o.class_name])per[g][o.class_name]={raw:0,kept:0,lost:0};
      const slot=per[g][o.class_name];
      slot.raw+=xyzi_ids.length;
      for(const i of xyzi_ids){
        if(outs[g].keep[i])slot.kept++;else slot.lost++;
      }
    }
  }
  return per;
}
function pointTrace(sid,frameIndex,raw,lv,outs){
  const doc=audit.docs[sid];
  if(!doc)return [];
  const ids=(doc.frames_objects||{})[String(frameIndex)]||[];
  const persons=ids.map(id=>doc.objects[id]).filter(o=>o&&o.class_name==='PERSON');
  if(!persons.length)return [];
  let dec;
  try{dec=gtLib.decode_indices(persons[0].raw_point_indices);}catch(e){return [];}
  return dec.slice(0,24).filter(li=>li>=0&&li<raw.length).map(li=>{
    const xi=raw[li];
    const out={gt_frame_legal_seq:li,xyzi_index:xi,
      x:+lv[xi*4].toFixed(4),y:+lv[xi*4+1].toFixed(4),z:+lv[xi*4+2].toFixed(4)};
    for(const g of ['A','B','C'])out[g]={kept:outs[g].keep[xi],reason:outs[g].reasons[xi]};
    return out;
  });
}
module.exports={Runtime,audit,MODELS,bMapInfo};
