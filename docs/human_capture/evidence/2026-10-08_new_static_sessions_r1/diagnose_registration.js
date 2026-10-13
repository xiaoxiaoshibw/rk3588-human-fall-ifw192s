/* Diagnostic only: reuse frozen fixedICP/measure. No publish(), loader artifact, or flags. */
"use strict";
const fs = require('fs'), path = require('path'), assert = require('assert');
const OUT = __dirname, ROOT = path.resolve(OUT, '../../../..');
const R = require(path.join(ROOT, 'pc_apps/human_replay/registration.js'));
const M = require(path.join(ROOT, 'pc_apps/human_replay/registration_method.js'));
const PL = require(path.join(ROOT, 'pc_apps/human_replay/human_pipe_lib.js'));
const levels = R.read(path.join(OUT, 'leveling_results.json'));
const write = (name, value) => fs.writeFileSync(path.join(OUT, name), JSON.stringify(value, null, 2) + '\n', {flag:'wx'});
function getLevel(item) {
    assert.strictEqual(item.recommended, 'tls');
    const dir = path.join(OUT, 'leveling', item.job);
    const report = R.read(path.join(dir, 'report.json'));
    const tf = R.read(path.join(dir, 'tls/transform.json'));
    assert.strictEqual(report.sid, item.sid);
    assert.strictEqual(R.identity(tf.source), R.identity(item.source));
    assert.strictEqual(R.identity(R.sessionBinding(ROOT, item.sid)), R.identity({sid:item.sid, ...item.source}));
    assert(R.matrixOK(tf.R.flat(), tf.t));
    return {tf};
}
function transform(buf, A, t) {
    const dst = new Float32Array(buf.length);
    for(let k=0;k<buf.length;k+=4) {
        const v=M.m3.apply(A,buf[k],buf[k+1],buf[k+2]);
        for(let j=0;j<3;j++) dst[k+j]=v[j]+t[j];
        dst[k+3]=buf[k+3];
    }
    return dst;
}
function preview(buf) {
    const step = Math.max(1, Math.ceil(buf.length/4/18000)), out=[];
    for(let k=0;k<buf.length;k+=4*step) {
        if(buf[k+2]<.1 || buf[k+2]>2.5) continue;
        out.push([buf[k],buf[k+1],buf[k+2]].map(v=>+v.toFixed(4)));
    }
    return out;
}
const refItem = levels.find(r=>r.sid==='cap_20261008_114819');
const refLevel = getLevel(refItem);
const ref = R.loadFrames(ROOT, refItem.sid, refLevel, true).frames;
const refmap = PL.build_reference_map(ref);
const refkeys = new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
const code = R.codeBinding(ROOT), results=[];
write('reference_summary.json', {sid:refItem.sid, leveling:refItem.job, binding:R.refBinding(refmap), code});
for(const item of levels.filter(r=>r.sid!==refItem.sid)) {
    if(item.recommended!=='tls') {
        const row={sid:item.sid,name:item.name,state:'BLOCKED',reason:'LEVELING_NOT_RECOMMENDED'};
        write(item.sid+'_registration_blocked.json', row);results.push(row);continue;
    }
    console.log('START', item.sid);
    const sourceLevel=getLevel(item), cur=R.loadFrames(ROOT,item.sid,sourceLevel,true).frames;
    const online=PL.build_static_map(cur), icp=M.fixedICP(online,refmap);
    const A=M.m3.t(icp.R), t=M.m3.apply(A,...icp.t.map(v=>-v));
    assert(R.matrixOK(A,t));
    const tlsR=M.m3.mul(refLevel.tf.R.flat(),M.m3.t(sourceLevel.tf.R.flat()));
    const diagnostics=R.measure(cur,ref,A,t,tlsR);
    const row={sid:item.sid,name:item.name,reference:refItem.sid,leveling_job:item.job,
        gate:diagnostics.gate.status,reasons:diagnostics.gate.reasons,
        support:diagnostics.support,residual:diagnostics.residual,sanity:diagnostics.sanity,
        transform:{rotation_row_major:A,translation_m:t},diagnostics,
        source:item.source,code,artifact_created:false,runtime_enabled:false};
    write(item.sid+'_registration_diagnostic.json',row);results.push(row);
    console.log('GATE',item.sid,row.gate,'inlier',row.support.inlier_ratio,'coverage',row.support.coverage_xy,'reasons',row.reasons);
    const samples=[];
    for(const ordinal of [0,Math.floor(cur.length/2),cur.length-1]) {
        const registered=PL.denoise(transform(cur[ordinal],A,t));
        const rawWS=PL.extract_foreground(registered,null).fg_xyzi;
        const fg=PL.extract_foreground(registered,refkeys).fg_xyzi;
        const cleanup=PL.cleanup_isolated_fg(fg);
        const clusters=PL.cluster_voxels(PL.voxelize(cleanup.xyzi)).map(c=>({
            n:c.acc.n,center:[c.acc.sx/c.acc.n,c.acc.sy/c.acc.n,c.acc.sz/c.acc.n],
            zmin:c.acc.zmin,zmax:c.acc.zmax,keys:c.keys})).sort((a,b)=>b.n-a.n).slice(0,15);
        samples.push({ordinal,workspace_n:rawWS.length/4,reference_remaining_n:fg.length/4,clusters,
            raw:preview(rawWS),remaining:preview(fg)});
    }
    write(item.sid+'_preview.json',{sid:item.sid,reference:refItem.sid,reference_points:preview(ref[Math.floor(ref.length/2)]),samples});
    assert.strictEqual(R.identity(R.codeBinding(ROOT)),R.identity(code));
    getLevel(item);
}
getLevel(refItem);
write('registration_results.json',results);
console.log('DONE',results.map(r=>[r.sid,r.gate??r.state]));
