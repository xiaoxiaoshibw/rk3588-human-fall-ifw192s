'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const B=require('../../background/detector_b'),I=require('../../contracts/index_v1');
require('../../../human_fusion_lab/core/fusion');require('../hook_unknown');require('./hook_split');
function sourceManifest() {
    const paths=new Set(Object.keys(require.cache).filter(p=>p.startsWith(B.ROOT)));
    for(const dir of ['sidequests/human_fusion_lab/human_replay','sidequests/human_fusion_lab/models'])
        for(const n of fs.readdirSync(path.join(B.ROOT,dir)))if(/\.(js|json)$/.test(n))paths.add(path.join(B.ROOT,dir,n));
    return [...paths].sort().map(p=>({path:path.relative(B.ROOT,p).replaceAll('\\','/'),sha256:B.sha(p)}));
}
function trace(e) {
    let cls=[];const oc=e.pipe.cluster_voxels,oa=e._fusion_a_chain,ol=e._level,oe=e.rf.extract,op=e.rf.predict_person;
    e._level=function(...a){e._model_calls=[];return ol.apply(this,a);};
    e.rf.extract=function(...a){const f=oe.apply(this,a);e._model_calls.push({n:a[0].n,features:Array.from(f),sha256:crypto.createHash('sha256').update(Buffer.from(f.buffer,f.byteOffset,f.byteLength)).digest('hex')});return f;};
    e.rf.predict_person=function(f){const p=op.call(this,f);e._model_calls[e._model_calls.length-1].prob=p;return p;};
    e.pipe.cluster_voxels=function(v){cls=oc.call(this,v);return cls;};
    e._fusion_a_chain=function(...a){const out=oa.apply(this,a),keys=new Map();cls.forEach((c,j)=>c.keys.forEach(k=>{assert(!keys.has(k),'overlapping post partition keys');keys.set(k,j);}));
        const ids=cls.map(()=>[]);out.final_ids.forEach((r,j)=>{const k=e.pipe.key_vox(out.fg_final[j*4],out.fg_final[j*4+1]),c=keys.get(k);if(c!==undefined)ids[c].push(r);});
        e._post_components=cls.map((c,j)=>{const f=e.pipe.cluster_features(c);return {id:'post_pa_'+j,path:'PA',raw_indices:ids[j],pointset_sha256:I.pointsetSha(ids[j]),hard_gate_pass:f.ok&&!(e.cfg.hard_gate_n500&&f.n<500),rejection_reasons:f.ok?[]:[f.reason],features:f};});
        // PB shadow components are appended later; PA uses actual partition membership.
        return out;
    };
    const ob=e._fusion_b_chain;e._fusion_b_chain=function(...a){const out=ob.apply(this,a);e._post_components.push(...e._ledger.components.filter(c=>c.path==='PB'));return out;};
}
function stages(e) {
    const n=e._mapped.raw_to_compact.length,bd=e._bg_diagnostics,bg=e._ledger.background_ids,clean=e._ledger.cleanup_ids,final=e._ledger.final_ids,bs=new Set(bg),cs=new Set(clean);
    return {valid_ids:Array.from(e._mapped.compact_to_raw),bg_kept_ids:bg,cleanup_kept_ids:clean,final_ids:final,
        cleanup_deleted_ids:bg.filter(i=>!cs.has(i)),retained_ids:final.filter(i=>!cs.has(i)),
        bg_deleted_ids:Array.from({length:n},(_,i)=>i).filter(i=>e._mapped.raw_to_compact[i]>=0&&!bs.has(i)),
        readmitted_ids:bd.reasons.map((r,i)=>r==='adaptive_r0.6_readmit'?i:-1).filter(i=>i>=0),
        reason_ids:Object.fromEntries([...new Set(bd.reasons)].map(r=>[r,bd.reasons.map((v,i)=>v===r?i:-1).filter(i=>i>=0)]))};
}
module.exports={trace,stages,sourceManifest};
