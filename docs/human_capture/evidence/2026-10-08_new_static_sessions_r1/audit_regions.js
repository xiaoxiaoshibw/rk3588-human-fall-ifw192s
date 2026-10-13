/* Read-only spatial audit. Fixed diagnostic windows are proxies, never human/table GT. */
"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const M=require(path.join(ROOT,'pc_apps/human_replay/registration_method.js'));
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const levels=R.read(path.join(OUT,'leveling_results.json'));
const regs=R.read(path.join(OUT,'registration_results.json'));
const retention=R.read(path.join(OUT,'retention_results.json'));
function frames(sid) {
    const r=levels.find(r=>r.sid===sid);
    return R.loadFrames(ROOT,sid,{tf:R.read(path.join(OUT,'leveling',r.job,'tls/transform.json'))},true).frames;
}
const ref=frames('cap_20261008_114819');
const refkeys=new Map([...PL.build_reference_map(ref).voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
const index=M.build_vox_index([...refkeys.values()],.15);
const windows={positive_y_furniture:[.8,3.5,.45,1.8,.65,1.3],negative_y_furniture:[1.8,3.5,-1.8,-1.05,.65,1.3]};
const key=(buf,k)=>[buf[k],buf[k+1],buf[k+2],buf[k+3]].join(',');
const stat=values=>{const a=values.slice().sort((x,y)=>x-y);return {n:a.length,p50:a.length?a[Math.floor(a.length*.5)]:null,p90:a.length?a[Math.floor(a.length*.9)]:null};};
const data=[];
for(const reg of regs.filter(r=>r.gate)) {
    const cur=frames(reg.sid),roi=retention.find(r=>r.sid===reg.sid);
    const rows=[];
    for(const ordinal of [0,Math.floor(cur.length/2),cur.length-1]) {
        const buf=new Float32Array(cur[ordinal].length);
        for(let k=0;k<buf.length;k+=4) {
            const q=M.m3.apply(reg.transform.rotation_row_major,cur[ordinal][k],cur[ordinal][k+1],cur[ordinal][k+2]);
            for(let j=0;j<3;j++) buf[k+j]=q[j]+reg.transform.translation_m[j];buf[k+3]=cur[ordinal][k+3];
        }
        const clean=PL.denoise(buf),ws=PL.extract_foreground(clean,null).fg_xyzi;
        const fg=PL.extract_foreground(clean,refkeys).fg_xyzi,kept=new Set();
        for(let k=0;k<fg.length;k+=4) kept.add(key(fg,k));
        const rawROI=[],keptROI=[],lostROI=[],bounds={};
        for(const name of Object.keys(windows)) bounds[name]={raw:0,remaining:0,distances:[],no_neighbor_within_60cm:0};
        for(let k=0;k<ws.length;k+=4) {
            const x=ws[k],y=ws[k+1],z=ws[k+2],isKept=kept.has(key(ws,k));
            if(Math.hypot(x-roi.center[0],y-roi.center[1])<=roi.radius&&z>=.1&&z<=2.3) {
                const xyz=[x,y,z];rawROI.push(xyz);(isKept?keptROI:lostROI).push(xyz);
            }
            for(const [name,[xl,xh,yl,yh,zl,zh]] of Object.entries(windows)) {
                if(x<xl||x>xh||y<yl||y>yh||z<zl||z>zh) continue;
                const b=bounds[name];b.raw++;if(isKept) b.remaining++;
                const hit=M.nn_query(index,x,y,z,.6);
                if(hit) b.distances.push(hit.d);else b.no_neighbor_within_60cm++;
            }
        }
        for(const b of Object.values(bounds)) {b.nearest_distance_m=stat(b.distances);delete b.distances;b.deleted_pct=100*(b.raw-b.remaining)/Math.max(1,b.raw);}
        rows.push({ordinal,rawROI,keptROI,lostROI,furniture_windows:bounds});
    }
    data.push({sid:reg.sid,center:roi.center,radius:roi.radius,gate:reg.gate,rows});
    console.log(reg.sid, rows.map(r=>({ordinal:r.ordinal,roi_raw:r.rawROI.length,roi_lost:r.lostROI.length,windows:r.furniture_windows})));
}
fs.writeFileSync(path.join(OUT,'region_audit.json'),JSON.stringify({windows,semantics:'sampled spatial proxies, not pointwise GT or physical table alignment proof',sessions:data},null,2)+'\n',{flag:'wx'});
assert(data.length===4);
