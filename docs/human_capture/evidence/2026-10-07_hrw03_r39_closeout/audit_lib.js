"use strict";
const assert=require('assert');
const DIAGNOSTIC=['clusters_before_cleanup','clusters_after_cleanup','cleanup_split_delta','topology_regression'];
function behavior(frame) { return Object.fromEntries(Object.entries(frame).filter(([k])=>!DIAGNOSTIC.includes(k))); }
function key(a,k=0) { return [a[k],a[k+1],a[k+2],a[k+3]].join(','); }
function xyz(a,k=0) { return [a[k],a[k+1],a[k+2]].join(','); }
function pointSet(a,coordinatesOnly=false) { const s=new Set();for(let k=0;k<a.length;k+=4)s.add((coordinatesOnly?xyz:key)(a,k));return s; }
function ownership(PL,fg,out,raw) {
    const iso=PL.cleanup_isolated_fg(fg),post=pointSet(iso.xyzi),pre=pointSet(fg);
    const cs=PL.cluster_voxels(PL.voxelize(iso.xyzi)).filter(c=>c.acc.n>=PL.PIPE.human_n_min);
    assert.equal(cs.length,out.clusters.length);
    const owner=new Map();cs.forEach((c,i)=>{assert.equal(c.acc.n,out.clusters[i].n);c.keys.forEach(k=>owner.set(k,i));});
    const ids=cs.map(()=>new Set()),status=[];
    for(let k=0;k<raw.length;k+=4) {
        const before=pre.has(key(raw,k)),after=post.has(key(raw,k));
        const ci=after?owner.get(PL.key_vox(raw[k],raw[k+1])):undefined;
        if(ci!==undefined)ids[ci].add(k/4);
        status.push({foreground:before,after_cleanup:after,cluster:ci??null,track:ci===undefined?null:out.clusters[ci].track_id});
    }
    assert(ids.every((s,i)=>s.size===out.clusters[i].n),'source point identities must be unique');
    return {ids,status,iso};
}
function overlaps(a,b) {
    const edges=[];
    a.forEach((p,i)=>b.forEach((s,j)=>{let n=0;for(const k of p)if(s.has(k))n++;if(n)edges.push({P:i,S:j,shared:n,P_fraction:n/p.size,S_fraction:n/s.size});}));
    return edges;
}
function topology(a,b,edges=overlaps(a,b)) {
    const pd=a.map((_,i)=>edges.filter(e=>e.P===i).length),sd=b.map((_,i)=>edges.filter(e=>e.S===i).length);
    return {before:a.length,after:b.length,split:pd.filter(n=>n>1).length,merge:sd.filter(n=>n>1).length,
        disappeared:pd.filter(n=>!n).length,appeared:sd.filter(n=>!n).length,
        definition:'point-identity overlap graph of output-eligible clusters (n>=60); any shared point is an edge; diagnostic adjacency, not GT identity',edges};
}
function nearest(map,p) {
    let best=null;
    for(const [k,v] of map) {const d=Math.hypot(v.x-p[0],v.y-p[1],v.z-p[2]);if(!best||d<best.distance)best={key:k,distance:d,...v};}
    return best;
}
function matcher(PL,map,p) {
    // Diagnostic copy of original iteration order; validated against extract_foreground below.
    const ix=Math.floor(p[0]/PL.PIPE.bg_voxel_xy),iy=Math.floor(p[1]/PL.PIPE.bg_voxel_xy),iz=Math.floor(p[2]/PL.PIPE.bg_voxel_z);
    for(let a=-1;a<=1;a++)for(let b=-1;b<=1;b++)for(let c=-1;c<=1;c++) {
        const k=((ix+a+4096)*8192+(iy+b+4096))*8192+(iz+c+4096),v=map.get(k);
        if(v) {const d2=(v.x-p[0])**2+(v.y-p[1])**2+(v.z-p[2])**2;
            if(d2<PL.PIPE.bg_match_radius**2)return {key:k,distance:Math.sqrt(d2),...v};}
    }
    return null;
}
function summarize(c,sourceCentroid=null) {
    if(!c)return null;
    return {track_id:c.track_id,centroid:[c.cx,c.cy,c.cz],source_centroid:sourceCentroid??[c.cx,c.cy,c.cz],point_count:c.n,
        height:c.height_m,width:c.width_m,depth:c.depth_m,radius:c.radius_m,upcos:c.upcos,zmin:c.zmin,zmax:c.zmax,
        label:c.label,joint:c.joint,track_confirmed:c.track_confirmed,evidence:c.evidence,evidence_tag:c.evidence_tag,reasons:c.reasons};
}
function category({change,staticWindow,referenceRemoved,p,s,edges,Pidx,Sidx,removedCleanup}) {
    if(staticWindow&&referenceRemoved>0&&change==='disappeared')return 'STATIC_REMOVAL_EXPECTED';
    if((Pidx!==null&&edges.filter(e=>e.P===Pidx).length>1)||(Sidx!==null&&edges.filter(e=>e.S===Sidx).length>1))return 'CLUSTER_TOPOLOGY_CHANGE';
    if(removedCleanup>0&&(!p||!s))return 'CLEANUP_SIDE_EFFECT';
    if(!s&&referenceRemoved>0)return 'REFERENCE_ABSORPTION';
    if(p&&s&&p.joint===s.joint&&p.track_confirmed===s.track_confirmed&&p.track_id!==s.track_id)return 'TRACK_ID_REASSIGNMENT';
    if(s&&(s.label==='HUMAN_CANDIDATE'||s.joint==='CONFIRMED_HUMAN')&&(!p||p.label!=='HUMAN_CANDIDATE'||(s.joint==='CONFIRMED_HUMAN'&&p.joint!=='CONFIRMED_HUMAN')))return 'HUMAN_CANDIDATE_GAIN';
    if(p&&(!s||s.label!=='HUMAN_CANDIDATE'||(p.joint==='CONFIRMED_HUMAN'&&s.joint!=='CONFIRMED_HUMAN')))return 'HUMAN_CANDIDATE_LOSS';
    return 'UNKNOWN';
}
module.exports={DIAGNOSTIC,behavior,key,xyz,pointSet,ownership,overlaps,topology,nearest,matcher,summarize,category};
