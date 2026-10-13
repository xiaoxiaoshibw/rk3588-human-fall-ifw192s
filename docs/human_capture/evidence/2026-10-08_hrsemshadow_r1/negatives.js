/* Read-only old negative coverage. Historical region attribution is not full-cluster human GT. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const H=require('./shadow.js'),S=require('./semantic.js');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..');
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js')),PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const golden='docs/human_capture/evidence/2026-10-06_hrw03_r3/11_user_verdict.md';
const oldsa='docs/human_capture/evidence/2026-10-08_human_semantic_sa_r1/semantic_sa.js';
const settings=[
    {sid:'cap_20261002_223757',job:'015df3ff4e9743e38ea2236ea7da2d74',modes:['P','WORKSPACE'],empty:false,
        regions:[{id:'WD01',attribution:'USER_LOCKED_STATIC_REGION',source:golden,
            predicate:(x,y,z)=>Math.hypot(x-3.5,y+.76)<=.55&&z>=.05&&z<=2}]},
    {sid:'cap_20261004_203349',job:'c9712acad48c4fb7a78cb119c08d4cdb',modes:['WORKSPACE'],empty:true,
        regions:[{id:'WD02',attribution:'USER_LOCKED_EMPTY_FAR_FIELD',source:golden,
            predicate:(x,y,z)=>Math.hypot(x,y)>8&&z>=.1&&z<=2.5}]},
    {sid:'cap_20261007_233658',job:'3c793d7bda0f4ced86b20ac8076e7b0e',modes:['WORKSPACE'],empty:true,regions:[]},
    {sid:'cap_20261007_215540',job:'21666bec7e7b44b2bdbbaa790bf4501b',modes:['WORKSPACE'],empty:false,
        regions:[{id:'crates',attribution:'HISTORICAL_DIAGNOSTIC_NOT_HUMAN',source:oldsa,
            predicate:(x,y,z)=>x>=2.35&&x<=3.30&&y>=-1.25&&y<=-.5&&z>=.05&&z<=1.6},
            {id:'low_bar',attribution:'HISTORICAL_DIAGNOSTIC_NOT_HUMAN',source:oldsa,
                predicate:(x,y,z)=>x>=3.3&&x<=5.2&&y>=-1.3&&y<=-.6&&z>=.05&&z<=.9}]}
];
const base=path.join(OUT,process.argv[2]);fs.mkdirSync(base);
const fd=fs.openSync(path.join(base,'negative_clusters.jsonl'),'wx'),rdf=fs.openSync(path.join(base,'negative_regions.jsonl'),'wx');
const emit=(f,v)=>fs.writeSync(f,JSON.stringify(v)+'\n');
const inc=(o,k)=>o[k]=(o[k]||0)+1,summary=[],binding=[];
for(const setting of settings) {
    let lev;
    try {lev=H.level(setting.sid,setting.job,path.join(ROOT,'captures/leveled',setting.job));}
    catch(error) {
        const blocked={sid:setting.sid,job:setting.job,status:'BLOCKED_INPUT_BINDING',reason:String(error),
            scope:'This historical input is not used; no job substituted and no re-signing.'};
        binding.push(blocked);summary.push(blocked);console.log('BLOCKED_INPUT',JSON.stringify(blocked));continue;
    }
    const data=H.load(setting.sid,lev);
    binding.push({sid:setting.sid,job:setting.job,source:lev.source,leveling_sha:lev.sha,
        regions:setting.regions.map(({predicate,...r})=>({...r,source_sha256:R.shaFile(path.join(ROOT,r.source))}))});
    const online=PL.build_static_map(data.frames.map(f=>f.buf));
    for(const mode of setting.modes) {
        const tracker=new PL.Tracker(),stats={sid:setting.sid,mode,frames:data.frames.length,clusters:0,semantic:{},size_bins:{},
            known_empty:setting.empty,human_frames:0,no_cluster_frames:0,regions:{},raw_invalid_candidates:0};
        for(let fi=0;fi<data.frames.length;fi++) {
            const f=data.frames[fi],ws=H.subset(f,PL.extract_foreground(f.buf,null).fg_xyzi),fg=mode==='P'?H.subset(f,PL.extract_foreground(f.buf,online).fg_xyzi):ws;
            const c=H.clusterFrame(f,fg,fi,tracker);
            if(!c.cs.length)stats.no_cluster_frames++;
            if(c.cs.some(x=>x.semantic.semantic==='HUMAN_EVIDENCE'))stats.human_frames++;
            for(const cluster of c.cs) {
                stats.clusters++;inc(stats.semantic,cluster.semantic.semantic);inc(stats.size_bins,cluster.n<200?'60-199':cluster.n<400?'200-399':'>=400');
                stats.raw_invalid_candidates+=cluster.invalid_rows.length;
                emit(fd,{sid:setting.sid,mode,ordinal:fi,seq:f.info.seq,stamp_sec:f.info.stamp_sec,stamp_nanosec:f.info.stamp_nanosec,...cluster,
                    identity:setting.empty?{label:'STATIC_OBJECT',basis:'documented empty scene',source:'historical_scene_attribution'}:
                        {label:'UNKNOWN',source:'diagnostic',status:'BLOCKED_FULL_CLUSTER_GT'}});
            }
            for(const reg of setting.regions) {
                const points=[],rows=[];
                for(let i=0;i<c.clean.rows.length;i++) {const xyz=Array.from(c.clean.buf.subarray(4*i,4*i+3));
                    if(!f.invalid.has(c.clean.rows[i])&&reg.predicate(...xyz)){points.push(...xyz);rows.push(c.clean.rows[i]);}}
                const sem=S.classify(points),st=stats.regions[reg.id]||(stats.regions[reg.id]={frames:0,semantic:{},zero_points:0,source:reg.source,attribution:reg.attribution});
                st.frames++;inc(st.semantic,sem.semantic);if(!rows.length)st.zero_points++;
                emit(rdf,{sid:setting.sid,mode,ordinal:fi,seq:f.info.seq,id:reg.id,rows,semantic:sem,source:'diagnostic',
                    attribution:reg.attribution,attribution_source:reg.source,
                    scope:'historical spatial subset, not entire candidate identity; no newly authored human labels'});
            }
            if(fi%80===0)console.log(setting.sid,mode,fi);
        }
        summary.push(stats);console.log('NEGATIVE_SUMMARY',JSON.stringify(stats));
    }
}
fs.closeSync(fd);fs.closeSync(rdf);
const write=(n,v)=>fs.writeFileSync(path.join(base,n),JSON.stringify(v,null,2)+'\n',{flag:'wx'});
write('summary.json',summary);write('binding.json',binding);
write('coverage.json',{grating:{status:'NOT_RUN',reason:'no distinct grating session/row identity found in existing evidence; low_bar is not relabeled grating'},
    crates:{status:'BLOCKED_GT',reason:'historical calibration region exercised; full instance attribution not human-reviewed'},
    WD01:{status:'BLOCKED_GT_FOR_WHOLE_CLUSTER',reason:'historical locked static spatial region exercised, whole intersecting component may be mixed'},
    WD02:{status:summary.some(s=>s.sid==='cap_20261004_203349'&&s.status)?'BLOCKED_INPUT_BINDING':'RUN',
        reason:'fixed historical job only; no alternative job selected to bypass code mismatch'}});
write('digests.json',Object.fromEntries(['negative_clusters.jsonl','negative_regions.jsonl','summary.json','binding.json','coverage.json'].map(n=>[n,R.shaFile(path.join(base,n))])));
