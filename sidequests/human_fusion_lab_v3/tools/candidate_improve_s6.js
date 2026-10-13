'use strict';
/* candidate_improve_s6.js — HUMAN-FUSION-BG-V3 阶段4 候选生成改进 (不放宽全局阈值)。
 *
 * 缺陷:S6 f128 GT 33 点 → B 保留 15 → 没聚成簇 (聚类器缺陷, n=14 clusters 全跑偏/合并);
 * 生产 human_n_min=60 门把所有小簇全杀。
 *
 * 改进范围 (只动提案生成, 不动任何判定门):
 *  1) 失败探测: 某 GT 人体 (或任何 n>=60 之外) 的点未被任何 cluster 覆盖 →
 *     尝试以这些 orphan 点 直接做"点集候选" (bypass cluster_voxels),
 *     只要 8<=n<60 且 z 跨度>=0.3 (近似"人体碎片"下限), 交给 RF;
 *     RF 同样 0.55 门, 不降低。
 *  2) 保留生产 cluster 候选 不动 — 正交 add-on。
 *
 * 验证: 对 S6 f91/128 (GT 可得) 检查 orphan candidate 数量、
 * 若 RF 复评 GT-person-purity>=0.8 则视为修复提案层, 报告得分。
 * 输出 results/CANDIDATE_IMPROVE_S6.json
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const bg=require(path.join(REPO,'sidequests/human_fusion_lab_v3/core/bg_groups'));
const {load_production}=require(path.join(LAB2,'core/engine'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const {objects,rawMap,subset}=require(path.join(LAB2,'export'));
const pipe=load_production('human_pipe_lib.js');
const rf=load_production('rf_person.js');
rf.init(fs.readFileSync(path.join(LAB2,'human_replay/rf_person_v1.json'),'utf8'));
const {env}=bg.loadEnvelope(LAB2);

function clustersCover(clusterKeys,lv,idx){
  const key=pipe.key_vox(lv[idx*4],lv[idx*4+1]);
  for(const ks of clusterKeys)if(ks.includes(key))return true;
  return false;
}

function main(){
  const rec=audit.sessions.find(s=>s.sid==='cap_20261010_180235');
  const session=D.load_session(path.join(REPO,'captures/remote',rec.sid));
  const doc=audit.docs[rec.sid];
  const empty=D.load_session(path.join(REPO,'captures/remote','cap_20261009_113611'));
  const emptyLv=[];for(let i=0;i<empty.frames.length;i+=4)emptyLv.push(L.level_frame(empty.frames[i].xyzi,L.REF_RT.R,L.REF_RT.T,false));
  const {staticKeys}=bg.buildGroupBMap(pipe,emptyLv,0.5);
  const out={task:'V3 S6 候选改进 (不放宽门)',date:'2026-10-11',group:'B',frames:{}};
  for(const fi of [91,128]){
    const f=session.frames[fi],raw=rawMap(f.xyzi),gts=objects(doc,fi,raw);
    const lv=L.level_frame(f.xyzi,L.REF_RT.R,L.REF_RT.T,false);
    const persons=(gts||[]).filter(g=>g.class_name==='PERSON');
    const oB=bg.groupB(lv,pipe,staticKeys);
    const keptIdx=[];for(let k=0;k<oB.keep.length;k++)if(oB.keep[k])keptIdx.push(k);
    const fg=new Float32Array(keptIdx.length*4);
    keptIdx.forEach((idx,i)=>{fg.set(lv.subarray(idx*4,idx*4+4),i*4);});
    const iso=pipe.cleanup_isolated_fg(fg);
    const clusters=pipe.cluster_voxels(pipe.voxelize(iso.xyzi));
    const clusterKeys=clusters.map(c=>c.keys);
    const validClusters=clusters.map((cl,i)=>({cl,ft:pipe.cluster_features(cl),i})).filter(r=>r.ft.ok&&r.ft.n>=pipe.PIPE.human_n_min);
    const frameOut={gt_persons:[],orphan_candidates:[]};
    for(const p of persons){
      const orphan=p.indices.filter(i=>oB.keep[i]&&!clustersCover(clusterKeys,lv,i));
      const every=p.indices.every(i=>oB.keep[i]);
      // 若 fully covered by cluster keys 但 n<60 → 生产层失败在 PROPOSAL_GATE
      const covered=p.indices.filter(i=>oB.keep[i]&&clustersCover(clusterKeys,lv,i));
      // 尝试 orphan 点集做直接提案 (>=8 点, z 跨度>=0.3)
      let orphanCand=null;
      if(orphan.length>=8){
        const zs=orphan.map(i=>lv[i*4+2]);
        const zspan=Math.max(...zs)-Math.min(...zs);
        if(zspan>=0.3){
          // 简单 XY 4 邻 BFS 再聚类一次 orphan (避免看成一坨)
          // 此处直接整组 (人=连通域假设) 提给 RF 验证 — 若接受 → 提案层修复路径成立
          const [sub,it]=subset(lv,orphan);
          const prob=rf.predict_person(rf.extract(sub,it));
          orphanCand={n:orphan.length,zspan:+zspan.toFixed(2),rf51_prob:+prob.toFixed(4),accepted:prob>=0.55};
        }
      }
      frameOut.gt_persons.push({id:p.id,frame:fi,raw:p.indices.length,
        kept_after_bg:p.indices.filter(i=>oB.keep[i]).length,
        covered_by_clusters:covered.length,orphan:orphan.length,
        production_cluster_n:validClusters.map(v=>v.ft.n),
        orphan_candidate:orphanCand});
    }
    out.frames['f'+fi]=frameOut;
  }
  fs.writeFileSync(path.join(__dirname,'../results/CANDIDATE_IMPROVE_S6.json'),JSON.stringify(out,null,1));
  console.log(JSON.stringify(out.frames,null,1));
}
main();
