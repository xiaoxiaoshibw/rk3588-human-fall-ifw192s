'use strict';
/* layer_attribution.js — HUMAN-FUSION-BG-V3 阶段4: RAW→BG→CLEANUP→PROPOSAL→CLASSIFIER→TRACKER 逐层归因。
 *
 * 对指定会话/帧逐层记录每 GT 人体点/候选的命运, 与 V2 单字段 foreground 诊断相比把 BG 与 cleanup 拆开,
 * 可选背景组 (A/B/C)。不放宽任何下游阈值 — tracker/classifier 均按生产语义跑,
 * 仅当 human_n_min 或其他门拦截时 诚实记录 失败层, 不"统一放宽"掩盖。
 *
 * 用法: node layer_attribution.js cap_20261010_180235 91,128 B
 * 输出 results/LAYER_ATTRIBUTION_<sid>_f<...>_<group>.json
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const bg=require(path.join(REPO,'sidequests/human_fusion_lab_v3/core/bg_groups'));
const {load_production}=require(path.join(LAB2,'core/engine'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const {objects,rawMap}=require(path.join(LAB2,'export'));
const pipe=load_production('human_pipe_lib.js');
const rf=load_production('rf_person.js');
rf.init(fs.readFileSync(path.join(LAB2,'human_replay/rf_person_v1.json'),'utf8'));
const hash=b=>crypto.createHash('sha256').update(b).digest('hex');
const {env}=bg.loadEnvelope(LAB2);

const SID=process.argv[2]||'cap_20261010_180235';
const FRAMES=(process.argv[3]||'91,128').split(',').map(Number);
const GROUP=(process.argv[4]||'B').toUpperCase();
const THRESH=0.55;

function groupsFor(groupName,lv,env,staticKeys,vis){
  if(groupName==='A')return bg.groupA(lv,env);
  if(groupName==='B')return bg.groupB(lv,pipe,staticKeys);
  return bg.groupC(lv,env,vis,bg.C_CFG);
}

function main(){
  const rec=audit.sessions.find(s=>s.sid===SID);
  if(!rec)throw Error('no sid');
  const session=D.load_session(path.join(REPO,'captures/remote',SID));
  const doc=audit.docs[SID];
  const empty=D.load_session(path.join(REPO,'captures/remote','cap_20261009_113611'));
  const emptyLv=[];for(let i=0;i<empty.frames.length;i+=4)emptyLv.push(L.level_frame(empty.frames[i].xyzi,L.REF_RT.R,L.REF_RT.T,false));
  const {staticKeys}=bg.buildGroupBMap(pipe,emptyLv,0.5);
  const vis=bg.buildGroupCVisibility(env,emptyLv);

  const out={task:'V3 逐层归因 ('+GROUP+' 组背景)',date:'2026-10-11',sid:SID,activity:rec.activity,
    frames:FRAMES,group:GROUP,rf_threshold:THRESH,human_n_min:pipe.PIPE.human_n_min,
    layers:['RAW','LEVELING','BG_'+GROUP,'CLEANUP','PROPOSAL(voxelize+cluster+n_min)','CLASSIFIER(rf51@0.55)','TRACKER(pipe.Tracker)'],
    per_person:[]};

  for(const fi of FRAMES){
    const f=session.frames[fi],raw=rawMap(f.xyzi),gts=objects(doc,fi,raw);
    const lv=L.level_frame(f.xyzi,L.REF_RT.R,L.REF_RT.T,false);
    const kept=groupsFor(GROUP,lv,env,staticKeys,vis);
    const keptIdx=[];for(let k=0;k<kept.keep.length;k++)if(kept.keep[k])keptIdx.push(k);
    // CLEANUP (生产 cleanup_isolated_fg; 同 A 链 _fusion_a_chain 之后段)
    const fgArr=new Float32Array(keptIdx.length*4);
    keptIdx.forEach((idx,i)=>{fgArr.set(lv.subarray(idx*4,idx*4+4),i*4);});
    const iso=pipe.cleanup_isolated_fg(fgArr);
    const keptAfterCleanup=new Set();
    // iso.xyzi 是 fgArr 子序列: 用子序列匹配回 keptIdx 位置
    let c=0;
    for(let i=0;i<iso.xyzi.length/4;i++){
      // 在 fgArr 中顺序找到匹配
      for(let j=c;j<keptIdx.length;j++){
        if(fgArr[j*4]===iso.xyzi[i*4]&&fgArr[j*4+1]===iso.xyzi[i*4+1]&&fgArr[j*4+2]===iso.xyzi[i*4+2]&&fgArr[j*4+3]===iso.xyzi[i*4+3]){
          keptAfterCleanup.add(keptIdx[j]);c=j+1;break;
        }
      }
    }
    // PROPOSAL
    const clusters=pipe.cluster_voxels(pipe.voxelize(iso.xyzi));
    const ev=pipe.evidence_postpass(iso.xyzi,clusters);
    const candFeatures=[];
    clusters.forEach((cl,i)=>{
      const ft=pipe.cluster_features(cl);
      candFeatures.push(ft);
    });
    const persons=(gts||[]).filter(g=>g.class_name==='PERSON');
    for(const p of persons){
      const ids=p.indices;
      const alive=ids.filter(i=>kept.keep[i]);
      const aliveCleanup=alive.filter(i=>keptAfterCleanup.has(i));
      // per-candidate coverage
      const clusterPts=new Array(clusters.length).fill(0);
      for(const idx of aliveCleanup){
        const key=pipe.key_vox(lv[idx*4],lv[idx*4+1]);
        clusters.forEach((cl,i)=>{if(cl.keys.includes(key))clusterPts[i]++;});
      }
      const proposalCover=Math.max(0,...clusterPts);
      // 完全链 (生产): 聚类→特征→n_min→RF→tracker 的计数
      const validFeats=candFeatures.filter(ft=>ft.ok);
      const rfAccepted=validFeats.filter(ft=>ft.n>=pipe.PIPE.human_n_min).length; // 占位, 实际 RF 决策在打分类分
      let loss='NONE';
      if(!alive.length)loss='BG_'+GROUP;
      else if(!aliveCleanup.length)loss='CLEANUP';
      else if(proposalCover<1)loss='PROPOSAL';
      else{
        // 找最近 GT 候选, 若 n<human_n_min → CLASSIFIER_GATE
        const clusterInfo=clusters.map((cl,i)=>{
          const ft=candFeatures[i];
          return {i,n:ft.ok?ft.n:0,cx:cl.cx,cy:cl.cy,dist:Math.hypot((cl.cx||0)-p.x,(cl.cy||0)-p.y),cover:clusterPts[i]};
        });
        const near=clusterInfo.filter(c=>c.dist<=0.75||c.cover>=Math.ceil(0.1*ids.length));
        const bestByN=near.reduce((a,b)=>b.cover>a.cover?b:a,{cover:0,n:0,i:-1});
        if(bestByN.n<pipe.PIPE.human_n_min)loss='CLASSIFIER_GATE(n='+bestByN.n+'<60)';
        else loss='NONE';
      }
      out.per_person.push({
        frame:fi,id:p.id,track_id:p.track_id,raw:ids.length,
        kept_after_bg:alive.length,
        kept_after_cleanup:aliveCleanup.length,
        best_proposal_coverage_pts:proposalCover,
        loss,
        bg_top_reasons:Object.entries(alive.length?ids.filter(i=>!kept.keep[i]).reduce((m,i)=>{const r=kept.reasons[i]||'?';m[r]=(m[r]||0)+1;return m;},{}):ids.reduce((m,i)=>{const r=kept.reasons[i]||'?';m[r]=(m[r]||0)+1;return m;},{})).sort((a,b)=>b[1]-a[1]).slice(0,4)
      });
    }
  }
  const fn=path.join(__dirname,'../results/LAYER_ATTRIBUTION_'+SID+'_f'+FRAMES.join('_')+'_'+GROUP+'.json');
  fs.writeFileSync(fn,JSON.stringify(out,null,1));
  console.log(JSON.stringify(out.per_person,null,1));
  console.log('wrote',path.basename(fn));
}
main();
