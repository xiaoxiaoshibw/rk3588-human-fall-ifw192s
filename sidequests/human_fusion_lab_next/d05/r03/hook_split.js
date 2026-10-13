'use strict';
// ponytail: 只拆两个有间隔的密集上层核心；单核/细稀人体不改。XY cell互斥，保留全部点。
const assert = require('assert');
const CFG = Object.freeze({ z: 1.3, high_points: 10, cells: 3, points: 60, separation: .45, expansion: .30 });
function neighbors(k) { const [x,y]=k.split(',').map(Number); return [[x-1,y],[x+1,y],[x,y-1],[x,y+1]].map(v=>v.join(',')); }
function components(keys) {
    const left=new Set(keys), out=[];
    while(left.size) { const q=[left.values().next().value], part=[]; left.delete(q[0]);
        while(q.length) { const k=q.pop(); part.push(k); for(const n of neighbors(k)) if(left.delete(n)) q.push(n); }
        out.push(part);
    } return out;
}
function combine(keys, voxels) {
    const acc={n:0,sx:0,sy:0,sz:0,sxx:0,syy:0,szz:0,sxy:0,sxz:0,syz:0,zmin:Infinity,zmax:-Infinity};
    for(const k of keys) { const v=voxels.get(k); for(const d of Object.keys(acc)) if(d==='zmin')acc[d]=Math.min(acc[d],v[d]);else if(d==='zmax')acc[d]=Math.max(acc[d],v[d]);else acc[d]+=v[d]; }
    return {keys,acc};
}
function partition(cl, voxels, high, cell) {
    const seeds=components(cl.keys.filter(k=>(high.get(k)||0)>=CFG.high_points))
        .filter(ks=>ks.length>=CFG.cells && ks.reduce((n,k)=>n+(high.get(k)||0),0)>=CFG.points);
    if(seeds.length<2)return [cl];
    const centers=seeds.map(ks=>ks.reduce((a,k)=>{const v=k.split(',').map(Number);return [a[0]+v[0]/ks.length,a[1]+v[1]/ks.length];},[0,0]));
    if(!centers.some((c,i)=>centers.some((d,j)=>j>i&&Math.hypot(c[0]-d[0],c[1]-d[1])*cell>=CFG.separation)))return [cl];
    const groups=seeds.map(()=>[]), rest=[];
    for(const k of cl.keys) { const p=k.split(',').map(Number); let best=-1,dist=Infinity;
        seeds.forEach((ks,i)=>{for(const s of ks){const q=s.split(',').map(Number),d=Math.hypot(p[0]-q[0],p[1]-q[1])*cell;if(d<dist){dist=d;best=i;}}});
        if(dist<=CFG.expansion+1e-9)groups[best].push(k);else rest.push(k);
    }
    const parts=groups.concat(components(rest)).filter(ks=>ks.length).map(ks=>combine(ks,voxels));
    assert.equal(parts.reduce((n,c)=>n+c.acc.n,0),cl.acc.n,'point conservation');
    assert.equal(new Set(parts.flatMap(c=>c.keys)).size,cl.keys.length,'key exclusivity');
    return parts;
}
function applySplit(engine) {
    const pipe=engine.pipe, ov=pipe.voxelize, oc=pipe.cluster_voxels; let high=new Map();
    pipe.voxelize=function(x) { high=new Map(); for(let i=0;i<x.length;i+=4)if(x[i+2]>=CFG.z){const k=pipe.key_vox(x[i],x[i+1]);high.set(k,(high.get(k)||0)+1);}return ov.call(this,x); };
    pipe.cluster_voxels=function(voxels) { const before=oc.call(this,voxels), log=[];
        const out=before.flatMap((cl,i)=>{const parts=partition(cl,voxels,high,pipe.PIPE.voxel_m);if(parts.length>1)log.push({parent:i,parent_points:cl.acc.n,parts:parts.map(c=>({keys:c.keys,points:c.acc.n}))});return parts;});
        engine._split_log=log;
        return out.filter(c=>c.keys.length>=pipe.PIPE.cluster_min_voxels);
    }; return {kind:'density_upper_core_partition',...CFG};
}
module.exports={applySplit,partition,combine,CFG};
if(require.main===module) {
    const vox=new Map(), high=new Map();
    for(let x=0;x<=10;x++){const k=x+',0';vox.set(k,{n:20,sx:20*x*.15,sy:0,sz:20,sxx:0,syy:0,szz:20,sxy:0,sxz:0,syz:0,zmin:.2,zmax:1.8});if(x<=2||x>=8)high.set(k,20);}
    const cl=combine([...vox.keys()],vox),parts=partition(cl,vox,high,.15);
    assert(parts.length>=2);assert.equal(parts.reduce((n,c)=>n+c.acc.n,0),220);
    assert.strictEqual(partition(cl,vox,new Map(),.15)[0],cl);
    console.log('R02_SPLIT_CONSERVATION_PASS');
}
