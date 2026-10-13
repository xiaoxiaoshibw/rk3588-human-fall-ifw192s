"use strict";
const assert=require('assert'),fs=require('fs'),PL=require('../../../../pc_apps/human_replay/human_pipe_lib'),OLD=require('./baseline_code/pc_apps/human_replay/human_pipe_lib'),H=require('./audit_lib');
const rows=[],test=(name,fn)=>{try{fn();rows.push({name,result:'PASS'});}catch(e){rows.push({name,result:'FAIL',error:e.stack});}};
const cell=(x,y,z,n)=>Array.from({length:n},(_,i)=>[(x+.5)*.15+i*.0001,(y+.5)*.15+i*.0001,(z+.5)*.12,1]).flat();
test('M01 empty/unchanged/deleted component/leaf/veto; finite cluster counts and conservation',()=>{
    const cases=[[],[...cell(10,10,10,2),...cell(11,10,10,2),...cell(12,10,10,2)],
        [...cell(10,10,10,1),...cell(11,10,13,1),...cell(12,10,16,1)],
        [...cell(10,10,10,2),...cell(11,10,10,2),...cell(12,10,10,2),...cell(13,10,14,1)]];
    for(const v of cases) {
        const a=new Float32Array(v),out=PL.pipeline_frame(a,0,{static_keys:null,tracker:new PL.Tracker()}),
            old=OLD.pipeline_frame(a,0,{static_keys:null,tracker:new OLD.Tracker()}),fg=PL.extract_foreground(PL.denoise(a),null),iso=PL.cleanup_isolated_fg(fg.fg_xyzi);
        assert.equal(out.clusters_before_cleanup,PL.cluster_voxels(fg.vox_fg).length);
        assert.equal(out.clusters_after_cleanup,PL.cluster_voxels(PL.voxelize(iso.xyzi)).length);
        assert(Number.isFinite(out.cleanup_split_delta));assert.equal(out.cleanup_split_delta,out.clusters_after_cleanup-out.clusters_before_cleanup);
        assert.equal(out.topology_regression,out.cleanup_split_delta>0);
        assert.equal(out.fg_before_cleanup-out.fg_after_cleanup,out.actually_removed_points);
        assert.equal(out.isolated_3d_candidates,out.xy_topology_vetoed+out.actually_removed_voxels);
        assert.deepEqual(H.behavior(out),H.behavior(old));assert.deepEqual(PL.cleanup_isolated_fg(a),OLD.cleanup_isolated_fg(a));
    }
    const deleted=PL.pipeline_frame(new Float32Array(cases[2]),0,{static_keys:null,tracker:new PL.Tracker()});
    assert.equal(deleted.clusters_before_cleanup,1);assert.equal(deleted.clusters_after_cleanup,0);assert.equal(deleted.cleanup_split_delta,-1);
});
test('M02 feature/label/Tracker/events unchanged over temporal synthetic sequence',()=>{
    const tracker=new PL.Tracker(),oldTracker=new OLD.Tracker();
    for(let f=0;f<12;f++) {
        const pts=[];for(let x=10;x<13;x++)for(let z=2;z<17;z++)pts.push(...cell(x,10,z,3));
        const buf=new Float32Array(pts);const a=PL.pipeline_frame(buf,f,{static_keys:null,tracker}),b=OLD.pipeline_frame(buf,f,{static_keys:null,tracker:oldTracker});
        assert.deepEqual(H.behavior(a),H.behavior(b));assert.deepEqual(PL.PIPE,OLD.PIPE);
    }
});
test('A01 original-point overlap graph: split/merge/appear/disappear (not centroid identity)',()=>{
    const a=[new Set([1,2,3]),new Set([4]),new Set([5])],b=[new Set([1]),new Set([2,4]),new Set([8])];
    const t=H.topology(a,b);assert.equal(t.split,1);assert.equal(t.merge,1);assert.equal(t.disappeared,1);assert.equal(t.appeared,1);
});
test('A02 first matcher vs global nearest; exact radius/workspace boundaries',()=>{
    const map=new Map([[PL.key_bg(1.575,1.575,1.26),{x:1.575,y:1.575,z:1.26}]]);
    for(const p of [[1.575,1.575,1.26],[1.69,1.575,1.26],[1.70,1.575,1.26]]) {
        assert.equal(!!H.matcher(PL,map,p),PL.extract_foreground(new Float32Array([...p,1]),map).n_fg===0);
        assert(Number.isFinite(H.nearest(map,p).distance));
    }
});
test('A03 labels/GT default UNKNOWN; 31 unique indices and deletion partition',()=>{
    const d=JSON.parse(fs.readFileSync(__dirname+'/01_absorbed_points.json','utf8'));
    assert.equal(new Set(d.points.map(v=>v.id)).size,31);assert(d.points.every(v=>v.semantic_label==='UNKNOWN'&&v.source==='diagnostic'));
    assert.equal(d.points.filter(v=>v.mechanism==='WORKSPACE_CROP').length,30);
    assert.equal(d.points.filter(v=>v.mechanism==='REGISTRATION_TRANSFORM_REFERENCE_MATCH').length,1);
});
fs.writeFileSync(__dirname+'/05_metric_fix_tests.json',JSON.stringify(rows,null,2)+'\n',{flag:'wx'});console.log(JSON.stringify(rows,null,2));
process.exitCode=rows.some(v=>v.result==='FAIL')?1:0;
