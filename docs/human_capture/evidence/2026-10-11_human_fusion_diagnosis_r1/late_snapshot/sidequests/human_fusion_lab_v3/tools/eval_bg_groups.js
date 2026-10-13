'use strict';
/* eval_bg_groups.js — HUMAN-FUSION-BG-V3 阶段3评估: A/B/C 三组背景对照。
 *
 * 对每会话逐帧:
 *  1) RAW → leveling → groupA/B/C keep mask + 逐点 reason;
 *  2) 以冻结 GT (AUDIT 绑定, 双 SHA 复核) 的 PERSON/FURNITURE 原始行索引为参照:
 *     - 人体损失: GT PERSON 点被组删除的比例 (bg_loss); 静止人体 (S8) 单列。
 *     - 家具残留: GT FURNITURE 点被组保留的比例 (家具 = 假前景的来源)。
 *  3) 总前景点数 (保留/全帧) 作为噪声水平代理。
 *
 * 对照同帧同 GT, 不跨帧插值、不放宽判定。帧 GT UNKNOWN → 该帧不计 GT 指标,
 * 仍计前景量。输出 results/BG_GROUPS_EVAL.json + per-session per-frame CSV 摘要。
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const bg=require(path.join(REPO,'sidequests/human_fusion_lab_v3/core/bg_groups'));
const {load_production}=require(path.join(LAB2,'core/engine'));

const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const pipe=load_production('human_pipe_lib.js');
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');

/* 冻结 GT 读 (objects/rawMap 与 v2_runtime 同源: export.js) */
const {objects,rawMap}=require(path.join(LAB2,'export'));

function loadValidDoc(sid,session,rec){
  let doc=audit.docs[sid]||null;
  const valid=rec.eligible&&doc&&doc.session_id===sid&&doc.review_status==='reviewed'
    &&fs.existsSync(rec.gt_path)&&hash(fs.readFileSync(rec.gt_path))===rec.gt_sha256
    &&doc.session_sha256?.meta===session.meta_sha256&&doc.session_sha256?.points===session.points_sha256;
  return valid?doc:null;
}

function main(){
  const {env,sha:envSha}=bg.loadEnvelope(LAB2);
  // B 参考图 + C 可见性档案: 空场模板 leveled 帧 (step=4 与生成器一致)
  const empty=D.load_session(path.join(REPO,'captures/remote','cap_20261009_113611'));
  const emptyLv=[];
  for(let i=0;i<empty.frames.length;i+=4)emptyLv.push(L.level_frame(empty.frames[i].xyzi,L.REF_RT.R,L.REF_RT.T,false));
  const {refMap,staticKeys}=bg.buildGroupBMap(pipe,emptyLv,0.5);
  const vis=bg.buildGroupCVisibility(env,emptyLv);
  console.log('B staticKeys(occ>=0.5):',staticKeys.size,'of',refMap.voxels.size,'voxels; C vis cells:',vis.size);

  const report={task:'HUMAN-FUSION-BG-V3 三组背景对照',date:'2026-10-11',
    envelope_sha:envSha, gate_m:0.75,
    b_map:{voxels:refMap.voxels.size,static_keys:staticKeys.size,min_occ:0.5},
    c_cfg:bg.C_CFG, sessions:[]};

  for(const rec of audit.sessions){
    const sid=rec.sid;
    const session=D.load_session(path.join(REPO,'captures/remote',sid));
    const doc=loadValidDoc(sid,session,rec);
    const srow={sid,activity:rec.activity,frames:session.frames.length,
      gt:doc?'REVIEWED_BOUND_OBSERVATION':'UNKNOWN', groups:{}, frames:[]};
    for(const g of ['A','B','C'])srow.groups[g]={person_raw:0,person_lost:0,person_kept:0,
      furniture_raw:0,furniture_kept:0,furniture_removed:0, fg_points_total:0, in_points_total:0,
      reason_hist:{}};
    for(let fi=0;fi<session.frames.length;fi++){
      const f=session.frames[fi];
      const raw=rawMap(f.xyzi); // raw28B 原始行索引 (GT 同域)
      const lv=L.level_frame(f.xyzi,L.REF_RT.R,L.REF_RT.T,false);
      const gts=doc?objects(doc,fi,raw):null; // export.objects(doc,frame_index,rawMap) — raw28B 索引域
      const outs={A:bg.groupA(lv,env),B:bg.groupB(lv,pipe,staticKeys),C:bg.groupC(lv,env,vis,bg.C_CFG)};
      const frow={fi,n:f.n_points,gt:!!gts};
      for(const [g,o] of Object.entries(outs)){
        let kept=0;for(let k=0;k<o.keep.length;k++)kept+=o.keep[k];
        const G=srow.groups[g];
        G.fg_points_total+=kept;G.in_points_total+=f.n_points;
        for(let k=0;k<o.reasons.length;k++){const r=o.reasons[k];G.reason_hist[r]=(G.reason_hist[r]||0)+1;}
        frow[g]={kept,ratio:+(kept/f.n_points).toFixed(4)};
      }
      if(gts){
        const persons=gts.filter(t=>t.class_name==='PERSON'),furns=gts.filter(t=>t.class_name==='FURNITURE');
        for(const p of persons){
          for(const [g,o] of Object.entries(outs)){
            const G=srow.groups[g];
            let lost=0;
            for(const idx of p.indices){if(!o.keep[idx])lost++;}
            G.person_raw+=p.indices.length;G.person_lost+=lost;G.person_kept+=p.indices.length-lost;
          }
        }
        for(const fu of furns){
          for(const [g,o] of Object.entries(outs)){
            const G=srow.groups[g];
            let kept=0;
            for(const idx of fu.indices){if(o.keep[idx])kept++;}
            G.furniture_raw+=fu.indices.length;G.furniture_kept+=kept;G.furniture_removed+=fu.indices.length-kept;
          }
        }
      }
      srow.frames.push(frow);
    }
    // 汇总
    for(const g of ['A','B','C']){
      const G=srow.groups[g];
      G.person_loss_ratio=G.person_raw?+(G.person_lost/G.person_raw).toFixed(4):null;
      G.furniture_residual_ratio=G.furniture_raw?+(G.furniture_kept/G.furniture_raw).toFixed(4):null;
      G.fg_ratio=+(G.fg_points_total/G.in_points_total).toFixed(4);
      G.reason_hist=Object.fromEntries(Object.entries(G.reason_hist).sort((a,b)=>b[1]-a[1]).slice(0,8));
    }
    report.sessions.push(srow);
    console.log(sid,rec.activity,
      ['A','B','C'].map(g=>{const G=srow.groups[g];
        return g+':fg='+(G.fg_ratio*100).toFixed(1)+'% ploss='+(G.person_loss_ratio===null?'—':(G.person_loss_ratio*100).toFixed(1)+'%')+' fres='+(G.furniture_residual_ratio===null?'—':(G.furniture_residual_ratio*100).toFixed(1)+'%');}).join('  '));
  }
  fs.mkdirSync(path.join(__dirname,'../results'),{recursive:true});
  fs.writeFileSync(path.join(__dirname,'../results/BG_GROUPS_EVAL.json'),JSON.stringify(report,null,1));
  console.log('wrote results/BG_GROUPS_EVAL.json');
}
main();
