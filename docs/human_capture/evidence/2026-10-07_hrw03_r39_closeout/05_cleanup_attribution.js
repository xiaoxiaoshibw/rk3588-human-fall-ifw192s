"use strict";
const fs=require('fs'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const old=R.read(__dirname+'/../2026-10-07_hrw03_r38/04_shadow_results_r3.json'),now=R.read(__dirname+'/06_shadow_results.json');
const results={};
for(const name of ['P','S']) {
    const frames=old[name].frames.map((f,i)=>{
        const before=f.clusters_before_cleanup,after=f.clusters_after_cleanup,aset=after.map(c=>new Set(c.keys)),bset=before.map(c=>new Set(c.keys));
        const edge=[];bset.forEach((b,bi)=>aset.forEach((a,ai)=>{let n=0;for(const k of a)if(b.has(k))n++;if(n)edge.push({before:bi,after:ai,shared_xy_cells:n});}));
        const split=bset.filter((_,bi)=>edge.filter(e=>e.before===bi).length>1).length,
            merge=aset.filter((_,ai)=>edge.filter(e=>e.after===ai).length>1).length,
            dropped=bset.filter((_,bi)=>!edge.some(e=>e.before===bi)).map((s,j)=>({keys:[...s],note:'component entirely removed or shrunk below fixed >=3 XY-cell candidate support'}));
        assert.equal(now[name].frames[i].clusters_before_cleanup,before.length);assert.equal(now[name].frames[i].clusters_after_cleanup,after.length);
        return {frame:i,before:before.length,after:after.length,count_delta:after.length-before.length,actual_split:split,actual_merge:merge,dropped_components:dropped};
    });
    results[name]={frames,summary:{before:frames.reduce((n,v)=>n+v.before,0),after:frames.reduce((n,v)=>n+v.after,0),
        nonzero_count_delta_frames:frames.filter(v=>v.count_delta!==0).length,positive_delta_frames:frames.filter(v=>v.count_delta>0).length,
        actual_split:frames.reduce((n,v)=>n+v.actual_split,0),actual_merge:frames.reduce((n,v)=>n+v.actual_merge,0),
        dropped_components:frames.reduce((n,v)=>n+v.dropped_components.length,0)}};
}
fs.writeFileSync(__dirname+'/05_cleanup_attribution.json',R.serialize(results),{flag:'wx'});console.log(JSON.stringify({P:results.P.summary,S:results.S.summary},null,2));
