/* Read-only feasibility probe: reuse frozen S-A+ bodies without running its historical main. */
"use strict";
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const previous=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1');
const original=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_human_semantic_sa_r2/semantic_sa_review.js');
const source=fs.readFileSync(original,'utf8');
const th=source.match(/const TH = \{[\s\S]*?\};/)[0];
const start=source.indexOf('function sub('),end=source.indexOf('function harvest(');
assert(start>=0&&end>start);
const frozenSource=th+'\n'+source.slice(start,end)+'\n({TH,feats});';
const semantic=new vm.Script(frozenSource,{filename:original+':frozen-bodies'}).runInNewContext();
assert.strictEqual(semantic.TH.w_min,.06);
const binding={classifier_sha256:R.shaFile(original),frozen_bodies_sha256:R.sha(frozenSource),
    pipeline:R.codeBinding(ROOT),region_audit_sha256:R.shaFile(path.join(previous,'region_audit.json'))};
const audit=R.read(path.join(previous,'region_audit.json')),positives=[];
for(const session of audit.sessions) {
    const rows=[];
    for(const row of session.rows) {
        for(const arm of ['rawROI','keptROI']) {
            const features=semantic.feats(row[arm].flat());
            rows.push({ordinal:row.ordinal,arm,n:row[arm].length,
                semantic:features.ok?features.semantic:'UNKNOWN',features});
        }
    }
    positives.push({sid:session.sid,gate:session.gate,scope:'spatial region proxy; not full pipeline cluster or pointwise GT',rows});
    console.log(session.sid,rows.map(r=>r.ordinal+':'+r.arm+'='+r.semantic).join(' '));
}
const levels=R.read(path.join(previous,'leveling_results.json'));
const empty=levels.find(r=>r.sid==='cap_20261008_114819');
const tf=R.read(path.join(previous,'leveling',empty.job,'tls/transform.json'));
assert.strictEqual(R.identity(R.sessionBinding(ROOT,empty.sid)),R.identity({sid:empty.sid,...empty.source}));
const frames=R.loadFrames(ROOT,empty.sid,{tf},true).frames,negatives=[];
for(const ordinal of [0,Math.floor(frames.length/2),frames.length-1]) {
    const ws=PL.extract_foreground(frames[ordinal],null).fg_xyzi;
    const clusters=PL.cluster_voxels(PL.voxelize(ws));
    const owner=new Map();clusters.forEach((c,ci)=>c.keys.forEach(key=>owner.set(key,ci)));
    const points=clusters.map(()=>[]);
    for(let k=0;k<ws.length;k+=4) {
        const ci=owner.get(PL.key_vox(ws[k],ws[k+1]));
        if(ci!==undefined) points[ci].push(ws[k],ws[k+1],ws[k+2]);
    }
    for(let ci=0;ci<points.length;ci++) {
        if(points[ci].length/3<semantic.TH.min_pts) continue;
        const features=semantic.feats(points[ci]);
        negatives.push({ordinal,ci,n:points[ci].length/3,
            center:[clusters[ci].acc.sx/clusters[ci].acc.n,clusters[ci].acc.sy/clusters[ci].acc.n],
            semantic:features.ok?features.semantic:'UNKNOWN',features});
    }
}
assert.strictEqual(R.shaFile(original),binding.classifier_sha256);
assert.strictEqual(R.identity(R.codeBinding(ROOT)),R.identity(binding.pipeline));
const result={thresholds:semantic.TH,binding,positives,empty_sid:empty.sid,negatives,
    empty_human:negatives.filter(r=>r.semantic==='HUMAN_EVIDENCE').length,
    scope:'frozen feasibility only; no parameter change, implementation, artifact, tracker vote replacement or flags'};
fs.writeFileSync(path.join(OUT,'results.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log('EMPTY',negatives.length,'clusters; HUMAN',result.empty_human);
