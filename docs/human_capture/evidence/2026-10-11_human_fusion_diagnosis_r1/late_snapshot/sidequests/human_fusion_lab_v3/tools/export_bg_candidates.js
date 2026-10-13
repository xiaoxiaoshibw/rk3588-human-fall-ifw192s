'use strict';
/* export_bg_candidates.js — HUMAN-FUSION-BG-V3 阶段5: 用 B 组背景导出候选行 (阶段5训练用).
 *
 * 与 human_fusion_lab/export.js exportSession 的候选行同构, 但:
 *  - 前景提取用 B 组 (build_reference_map + extract_foreground_fused 语义内联);
 *  - 后段 (cleanup → voxelize → cluster → 特征 → 51+18 维) 1:1 复用生产函数;
 *  - label 用冻结 GT 同规则 (GT person purity>=0.8 → 1, furniture>=0.8 → 0, 其余 null);
 *  - 对 S9 (blocked) 会保留 label 但标注 blocked=true 并在训练侧仅取负样本。
 *
 * 不修改生产, 不回写 lab2/results; 输出 sidequests/human_fusion_lab_v3/results/<sid>_bg.jsonl
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const S=require(path.join(LAB2,'core/schema'));
const E=require(path.join(LAB2,'core/engine'));
const bg=require(path.join(REPO,'sidequests/human_fusion_lab_v3/core/bg_groups'));
const {objects,rawMap,subset,extra}=require(path.join(LAB2,'export'));
const {load_production}=E;
const pipe=load_production('human_pipe_lib.js');
const rf=load_production('rf_person.js');
rf.init(fs.readFileSync(path.join(LAB2,'human_replay/rf_person_v1.json'),'utf8'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');

function main(){
  const onlySid=process.argv[2]||null;
  const empty=D.load_session(path.join(REPO,'captures/remote','cap_20261009_113611'));
  const emptyLv=[];for(let i=0;i<empty.frames.length;i+=4)emptyLv.push(L.level_frame(empty.frames[i].xyzi,L.REF_RT.R,L.REF_RT.T,false));
  const {staticKeys}=bg.buildGroupBMap(pipe,emptyLv,0.5);
  for(const rec of audit.sessions){
    if(onlySid&&rec.sid!==onlySid)continue;
    const sid=rec.sid;
    const session=D.load_session(path.join(REPO,'captures/remote',sid));
    // GT 绑定验证 (同 v2_runtime)
    let doc=audit.docs[sid]||null;
    const valid=rec.eligible&&doc&&doc.session_id===sid&&doc.review_status==='reviewed'
      &&fs.existsSync(rec.gt_path)&&hash(fs.readFileSync(rec.gt_path))===rec.gt_sha256
      &&doc.session_sha256?.meta===session.meta_sha256&&doc.session_sha256?.points===session.points_sha256;
    if(!valid)doc=null;
    const rows=[];
    for(const f of session.frames){
      const lv=L.level_frame(f.xyzi,L.REF_RT.R,L.REF_RT.T,false);
      const oB=bg.groupB(lv,pipe,staticKeys);
      const keptIdx=[];for(let k=0;k<oB.keep.length;k++)if(oB.keep[k])keptIdx.push(k);
      const fg=new Float32Array(keptIdx.length*4);
      keptIdx.forEach((idx,i)=>{fg.set(lv.subarray(idx*4,idx*4+4),i*4);});
      const iso=pipe.cleanup_isolated_fg(fg);
      const clusters=pipe.cluster_voxels(pipe.voxelize(iso.xyzi));
      const ev=pipe.evidence_postpass(iso.xyzi,clusters);
      // iso.xyzi → keptIdx 子序列映射 (与 cleanup 后 raw 索引)
      const keptAfterCleanup=[];
      let c=0;
      outer: for(let i=0;i<iso.xyzi.length/4;i++){
        for(let j=c;j<keptIdx.length;j++){
          if(fg[j*4]===iso.xyzi[i*4]&&fg[j*4+1]===iso.xyzi[i*4+1]&&fg[j*4+2]===iso.xyzi[i*4+2]&&fg[j*4+3]===iso.xyzi[i*4+3]){
            keptAfterCleanup.push(keptIdx[j]);c=j+1;continue outer;
          }
        }
      }
      // raw GT object per frame
      const raw=rawMap(f.xyzi),obs=doc?objects(doc,f.index,raw):null;
      // 同 v2_runtime: cluster→特征→RF; members 回溯到 keptAfterCleanup
      const owners=new Map(),members=clusters.map(()=>[]);
      clusters.forEach((cl,i)=>{cl.keys.forEach(k=>owners.set(k,i));});
      for(let p=0;p<keptAfterCleanup.length;p++){
        const owner=owners.get(pipe.key_vox(iso.xyzi[p*4],iso.xyzi[p*4+1]));
        if(owner!==undefined)members[owner].push(p);
      }
      clusters.forEach((cl,ci)=>{
        const ft=pipe.cluster_features(cl);
        if(!ft.ok)return;
        const mem=members[ci];
        if(!mem.length)return;
        const sub={n:mem.length,x:new Float32Array(mem.length),y:new Float32Array(mem.length),z:new Float32Array(mem.length)},inten=new Float32Array(mem.length);
        mem.forEach((pp,mi)=>{sub.x[mi]=iso.xyzi[pp*4];sub.y[mi]=iso.xyzi[pp*4+1];sub.z[mi]=iso.xyzi[pp*4+2];inten[mi]=iso.xyzi[pp*4+3];});
        const feature=Array.from(rf.extract(sub,inten)),ext=extra(sub);
        const ids=mem.map(pp=>keptAfterCleanup[pp]);
        // 与 exportSession label 同规则
        const hits=(obs||[]).map(o=>{const set=new Set(o.indices),inter=ids.filter(i=>set.has(i)).length;
          return {id:o.id,class_name:o.class_name,intersection:inter,purity:inter/ids.length,coverage:inter/o.indices.length};}).filter(o=>o.intersection);
        const p1=hits.filter(o=>o.class_name==='PERSON'),neg=hits.filter(o=>o.class_name==='FURNITURE');
        let label=null;
        if(obs&&p1.length===1&&p1[0].purity>=.8&&!hits.some(o=>o.class_name!=='PERSON'&&o.purity>.2))label=1;
        else if(obs&&!p1.length&&neg.some(o=>o.purity>=.8))label=0;
        rows.push({sid,frame_index:f.index,id:'b_bg_'+f.index+'_'+ci,label,
          label_status:label===null?'UNKNOWN':'OVERLAP_DERIVED_REVIEWED_GT',
          blocked:!valid, gt_hits:hits,
          features:feature,extended:ext,point_count:ids.length,
          baseline_prob:rf.predict_person(rf.extract(sub,inten))});
      });
    }
    const fname=path.join(__dirname,'../results',sid+'_bg.jsonl');
    fs.writeFileSync(fname,rows.map(v=>JSON.stringify(v)).join('\n')+'\n');
    console.log(sid,rec.activity,'rows='+rows.length,
      'pos='+rows.filter(r=>r.label===1).length,'neg='+rows.filter(r=>r.label===0).length,'blocked='+rows.filter(r=>r.blocked).length);
  }
}
main();
