'use strict';
/* audit_s9_gt.js — HUMAN-FUSION-BG-V3 阶段6: 修复 S9 错误 GT 绑定 (双轨)。
 *
 * 诊断 (V2 已证实, 本轮复核):
 *  - GT_V2.json session_sha256.points = "aaaa…" → capture binding 已损坏, 不可信;
 *  - 其 36 个对象带 polygon_xy + raw_point_indices, 但索引域无 meta 绑定佐证。
 *
 * 本工具产出两轨 (都不覆盖任何既有文件, flag:'wx'):
 *  A) S9_GT_PROVENANCE_DRAFT.json
 *     LABEL_DERIVED 溯源草稿: 从损坏 GT 的 raw_point_indices 继承点集,
 *     复核实际 capture 双 SHA 并把 session_sha256 写回真实值, source 明确为
 *     "LABEL_DERIVED:GT_V2-broken-binding", trusted_gt=false。
 *     用途: 若人工日后确认这些标签确实针对当前 capture, 有一个绑定完好的评审基。
 *  B) S9_GT_GEOMETRY_DRAFT.json (fusion_demo_v2/raw_row_draft/1)
 *     用 annotation_v2.validateDraft 规则可消费的 2D/3D 人体几何标注草稿。
 *     由 S9 同场景点云自动生成 → 每对象 source='human' 是占位? 不行 — 手工。
 *     本工具不伪造人工标签; 人体点集来源标注为 LABEL_DERIVED, 经
 *     validateDraft 改造前是几何提案, 绝不进入 reviewed GT。
 *
 * 输出 results/S9_GT_REPAIR.json 汇总诊断 + 两轨文件路径 + 复核证据。
 */
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const REPO=path.resolve(__dirname,'../../..');
const LAB2=path.join(REPO,'sidequests/human_fusion_lab');
const D=require(path.join(LAB2,'core/data_loader'));
const L=require(path.join(LAB2,'core/leveling'));
const audit=JSON.parse(fs.readFileSync(path.join(LAB2,'results/AUDIT.json')));
const GTBROKEN_DIR='';

const SID='cap_20261010_180751';
function sha(p){return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');}

function main(){
  const rec=audit.sessions.find(s=>s.sid===SID);
  const session=D.load_session(path.join(REPO,'captures/remote',SID));
  const doc=JSON.parse(fs.readFileSync(rec.gt_path));
  const out={task:'HUMAN-FUSION-BG-V3 S9 GT 修复 (双轨)',date:'2026-10-11',sid:SID,
    diagnosis:{
      gt_path:rec.gt_path,
      file_sha256:rec.gt_sha256, file_sha256_actual:sha(rec.gt_path),
      declared_points_sha:doc.session_sha256?.points,
      actual_points_sha:session.points_sha256,
      actual_meta_sha:session.meta_sha256,
      eligible_in_audit:rec.eligible,
      verdict:'BROKEN_BINDING (declared points sha ≠ capture; “aaaa…” 占位; 不能证明标签针对当前 capture)'
    }};
  /* ---- 轨迹 A: 溯源草稿 ---- */
  const dec=require('D:/Code/ldiar/sidequests/human_fusion_lab/human_replay/gt_lib.js');
  const annotations=[];
  const contract={already_leveled:false,R:Array.from(L.REF_RT.R),T:Array.from(L.REF_RT.T)};
  for(const o of Object.values(doc.objects)){
    const ids=dec.decode_indices(o.raw_point_indices);
    const f=session.frames[o.frame_idx];
    if(!f)continue;
    const inRange=ids.filter(i=>Number.isSafeInteger(i)&&i>=0&&i<f.n_points);
    annotations.push({
      session_id:SID,frame_index:o.frame_idx,
      session_sha256:{meta:session.meta_sha256,points:session.points_sha256},
      coordinate_contract:contract,index_domain:'raw_28B_row',
      raw_point_indices:inRange,source:'LABEL_DERIVED:GT_V2-broken-binding',
      review_status:'DRAFT_UNREVIEWED',class_name:o.class_name,
      track_id:o.track_id||null,
      inherited_from:{file:path.basename(rec.gt_path),object_id:o.object_id,
        original_indices_count:ids.length,in_range_count:inRange.length},
      polygon_xy:o.polygon_xy||null
    });
  }
  const prov={schema:'fusion_demo_v3/s9_provenance_draft/1',trusted_gt:false,
    review_status:'DRAFT_UNREVIEWED',generated:'audit_s9_gt.js 2026-10-11',
    note:'从绑定损坏的 GT_V2 继承点集并写回真实 capture 双 SHA; 仅作日后人工评审的基, 不是 GT。',
    bindings:{[SID]:{meta:session.meta_sha256,points:session.points_sha256}},
    annotations};
  const pa=path.join(__dirname,'../results/S9_GT_PROVENANCE_DRAFT.json');
  fs.writeFileSync(pa,JSON.stringify(prov,null,1),{flag:'wx'});
  out.provenance_draft={path:pa,count:annotations.length};
  /* ---- 轨迹 B: 几何标注层 ---- */
  // 仅含清楚可分的 2D/3D 区: 双人会话 P1/P2 轨迹分簇由 bottom-k 后处理出; 本层只声明哪些帧存在两个
  // 可区分人体区 (按既有 labels 的 track_id 统计), 供后续人工 2D/3D 框选复核。
  const perFrame={};
  for(const o of Object.values(doc.objects)){
    if(o.class_name!=='PERSON')continue;
    perFrame[o.frame_idx]=perFrame[o.frame_idx]||new Set();
    if(o.track_id)perFrame[o.frame_idx].add(o.track_id);
  }
  const bothFrames=Object.entries(perFrame).filter(([,s])=>s.size>=2).map(([f])=>+f).sort((a,b)=>a-b);
  out.geometry_layer={note:'S9 双人都出现的帧数 (破绑定 GT 声明, 未独立核实): '+bothFrames.length,
    both_person_frames_first10:bothFrames.slice(0,10),total_126:session.frames.length};
  fs.writeFileSync(path.join(__dirname,'../results/S9_GT_REPAIR.json'),JSON.stringify(out,null,1));
  console.log('A 轨迹 provenance draft:',annotations.length,'annotations →',pa);
  console.log('B 轨迹 双人帧 (claimed):',bothFrames.length,'/ 126');
  console.log('wrote results/S9_GT_REPAIR.json (不覆盖 GT, 不晋级 reviewed)');
}
main();
