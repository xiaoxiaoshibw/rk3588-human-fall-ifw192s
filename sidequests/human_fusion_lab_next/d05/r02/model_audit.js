'use strict';
// 固定真实候选点集重新提取/预测；诊断与算法推理隔离，不做训练或候选生成。
const fs=require('fs'),path=require('path'),assert=require('assert'),readline=require('readline');
const B=require('../../background/detector_b'),D=require('../../../human_fusion_lab/core/data_loader'),I=require('../../contracts/index_v1'),L=require('../../../human_fusion_lab/core/leveling');
const {subset}=require('../../../human_fusion_lab/export');
const ROOT=B.ROOT,OUT=path.join(ROOT,'docs/human_capture/evidence/2026-10-11_hfus_d05_r2');
async function main(){const ref=B.buildReference(),det=B.createDetector(ref),rf=det.engine.rf,out=[];
    for(const [sid,frames] of [['175553',[5,40,80]],['175804',[75,238]],['175943',[0,52,117,162]],['180235',[98,110,128,187,188]],['175227',[0,40]]]){
        const full='cap_20261010_'+sid,session=D.load_session(path.join(ROOT,'captures/remote',full));
        for(const v of ['base','a06','split']){
            const stream=readline.createInterface({input:fs.createReadStream(path.join(OUT,'runs/full',v,`R02_${v}_${full}.jsonl`)),crlfDelay:Infinity});
            for await(const line of stream){const row=JSON.parse(line);if(!frames.includes(row.frame_index))continue;const lv=I.mapFrame(session.frames[row.frame_index].xyzi,L.REF_RT).leveled_xyzi;
                for(const c of row.candidates){const [sub,it]=subset(lv,c.raw_indices),x=rf.extract(sub,it);assert.equal(x.length,69);assert(Array.from(x).every(Number.isFinite));const prob=rf.predict_person(x);assert(Math.abs(prob-c.prob)<1e-12,'fixed candidate prediction mismatch');
                    const comp=row.raw_components.find(p=>p.pointset_sha256===c.pointset_sha256);
                    out.push({sid:full,f:row.frame_index,variant:v,id:c.id,n:c.n,pointset_sha256:c.pointset_sha256,prob,decision:c.decision,gt_hits:c.gt_hits,features:Array.from(x),geometry:comp?comp.features:null,qualification:row.qualification,diagnostic:'exact saved candidate members; no GT-generated proposal'});
                }
            }
        }
    }
    fs.writeFileSync(path.join(OUT,'FIXED_CANDIDATE_MODEL_AUDIT.json'),JSON.stringify({status:'PASS',model_sha256:det.engine.rf_model_sha,dim:69,samples:out.length,rows:out,model_promotion:'BLOCKED; no independent reviewed negative split; no retraining'},null,2),{flag:'wx'});console.log('FIXED_CANDIDATE_PARITY_PASS',out.length);
}
main().catch(e=>{console.error(e);process.exitCode=1;});
