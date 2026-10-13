/* Frozen S-A+ v1 adapter: exact source bodies, no historical main, no production import. */
'use strict';
const fs=require('fs'), path=require('path'), vm=require('vm'), assert=require('assert'), crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../../../..');
const original=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_human_semantic_sa_r2/semantic_sa_review.js');
const source=fs.readFileSync(original,'utf8');
const th=source.match(/const TH = \{[\s\S]*?\};/)[0];
const start=source.indexOf('function sub('), end=source.indexOf('function harvest(');
assert(start>=0&&end>start);
const frozenSource=th+'\n'+source.slice(start,end)+'\n({TH,feats});';
const hash=s=>crypto.createHash('sha256').update(s).digest('hex');
const frozen=new vm.Script(frozenSource,{filename:original+':frozen-bodies'}).runInNewContext();
const saved=JSON.parse(fs.readFileSync(path.join(ROOT,'docs/human_capture/evidence/2026-10-08_semantic_new_holdout_r1/results.json'),'utf8'));
assert.strictEqual(hash(source),saved.binding.classifier_sha256);
assert.strictEqual(hash(frozenSource),saved.binding.frozen_bodies_sha256);
assert.strictEqual(JSON.stringify(frozen.TH),JSON.stringify(saved.thresholds));
Object.freeze(frozen.TH);

function classify(pts) {
    assert(pts.length%3===0);
    const f=pts.every(Number.isFinite) ? frozen.feats(pts) : {ok:false,n:pts.length/3,reason:'INVALID_XYZ'};
    const flags={HEAD:f.ok?f.head:null,NECK:null,TORSO:f.ok?f.torso:null,LEGS:f.ok?f.legsOK:null,
        ARM:f.ok?f.arm:null,SLAB:f.ok?f.slab:null,FLAT_TOP:f.ok?f.flat:null};
    // Diagnostics only: expose unrounded measurements without modifying feats or thresholds.
    const bands=[];
    const section=(lo,hi)=>{
        const xyz=[];
        for(let i=0;i<pts.length;i+=3) if(pts[i+2]>=lo&&pts[i+2]<hi) xyz.push(pts[i],pts[i+1],pts[i+2]);
        const n=xyz.length/3,c=[0,0,0],s=[0,0];
        for(let i=0;i<xyz.length;i+=3) for(let j=0;j<3;j++) c[j]+=xyz[i+j]/n;
        for(let i=0;i<xyz.length;i+=3) for(let j=0;j<2;j++) s[j]+=(xyz[i+j]-c[j])**2/n;
        return {n,center:n?c:null,sx:n?Math.sqrt(s[0]):null,sy:n?Math.sqrt(s[1]):null};
    };
    if(pts.length && pts.every(Number.isFinite)) for(let lo=.1;lo<2.5;lo+=.1) bands.push({lo,hi:lo+.1,...section(lo,lo+.1)});
    return {semantic:f.ok?f.semantic:'UNKNOWN',reason:f.reason,flags,features:JSON.parse(JSON.stringify(f)),bands,
        neck_status:'NOT_EXPLICITLY_CLASSIFIED_BY_FROZEN_V1',
        conflict_observed:!!(f.ok && ((f.head||f.arm) && (f.slab||f.flat))),
        source:'diagnostic',version:'S-A+ v1'};
}
function selfcheck() {
    for(const n of [0,60,199,200,399]) {
        const r=classify(Array(n*3).fill(.5));
        assert.strictEqual(r.semantic,'UNKNOWN'); assert.strictEqual(r.reason,'POINTS_LOW');
        assert(Object.values(r.flags).every(v=>v===null));
    }
    assert.strictEqual(classify([NaN,0,1]).reason,'INVALID_XYZ');
    let checks=0;
    for(const s of saved.positives) for(const r of s.rows) {
        const audit=JSON.parse(fs.readFileSync(path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1/region_audit.json'),'utf8'));
        const pts=audit.sessions.find(x=>x.sid===s.sid).rows.find(x=>x.ordinal===r.ordinal)[r.arm].flat();
        assert.strictEqual(JSON.stringify(frozen.feats(pts)),JSON.stringify(r.features));checks++;
    }
    return {checks:checks+6,positive_feature_reconciliation:checks,thresholds:frozen.TH,
        original_sha256:hash(source),frozen_bodies_sha256:hash(frozenSource),adapter_sha256:hash(fs.readFileSync(__filename))};
}
module.exports={classify,feats:frozen.feats,TH:frozen.TH,selfcheck,
    binding:{original:path.relative(ROOT,original),original_sha256:hash(source),frozen_bodies_sha256:hash(frozenSource),
        adapter_sha256:hash(fs.readFileSync(__filename)),thresholds:frozen.TH}};
if(require.main===module) console.log(JSON.stringify(selfcheck(),null,2));
