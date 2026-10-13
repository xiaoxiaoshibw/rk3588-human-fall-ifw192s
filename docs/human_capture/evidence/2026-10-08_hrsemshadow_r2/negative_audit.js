'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),readline=require('readline');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..'),R1=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1');
const H=require(path.join(R1,'shadow.js')),S=require(path.join(R1,'semantic.js')),PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js')),R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const key=x=>[x.sid,x.mode,x.ordinal].join('/');
async function index(n){const m=new Map();for await(const l of readline.createInterface({input:fs.createReadStream(path.join(R1,'negative4',n)),crlfDelay:Infinity})){const r=JSON.parse(l),k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r);}return m;}
async function main(){
 const expected=await index('negative_clusters.jsonl'),regions=await index('negative_regions.jsonl'),bind=R.read(path.join(R1,'negative4/binding.json'));
 const result={frames:0,clusters:0,region_exact_checks:0,WD02:'NOT_RUN; contract diagnosis only',representatives:[],WD01_hits:[]};
 for(const b of bind.filter(b=>b.source)){
  const lev=H.level(b.sid,b.job,path.join(ROOT,'captures/leveled',b.job));assert.deepStrictEqual(lev.sha,b.leveling_sha);assert.deepStrictEqual(lev.source,b.source);
  const data=H.load(b.sid,lev),online=PL.build_static_map(data.frames.map(f=>f.buf));
  for(const mode of b.sid.endsWith('223757')?['P','WORKSPACE']:['WORKSPACE']){
   const tracker=new PL.Tracker();for(let fi=0;fi<data.frames.length;fi++){
    const f=data.frames[fi],ws=H.subset(f,PL.extract_foreground(f.buf,null).fg_xyzi),fg=mode==='P'?H.subset(f,PL.extract_foreground(f.buf,online).fg_xyzi):ws;
    const chain=H.clusterFrame(f,fg,fi,tracker),k=[b.sid,mode,fi].join('/'),wanted=expected.get(k)||[];
    assert.strictEqual(chain.cs.length,wanted.length,k);for(let ci=0;ci<chain.cs.length;ci++)for(const n of Object.keys(chain.cs[ci]))assert.deepStrictEqual(chain.cs[ci][n],wanted[ci][n],k+'/'+ci+'/'+n);
    for(const rg of regions.get(k)||[]){
     const predicate=rg.id==='WD01'?(x,y,z)=>Math.hypot(x-3.5,y+.76)<=.55&&z>=.05&&z<=2:rg.id==='crates'?(x,y,z)=>x>=2.35&&x<=3.30&&y>=-1.25&&y<=-.5&&z>=.05&&z<=1.6:(x,y,z)=>x>=3.3&&x<=5.2&&y>=-1.3&&y<=-.6&&z>=.05&&z<=.9;
     const xyz=[],rows=[];for(let i=0;i<chain.clean.rows.length;i++){const r=chain.clean.rows[i],x=Array.from(chain.clean.buf.subarray(i*4,i*4+3));if(!f.invalid.has(r)&&predicate(...x)){rows.push(r);xyz.push(...x);}}
     assert.deepStrictEqual(rows,rg.rows);assert.deepStrictEqual(S.classify(xyz),rg.semantic);result.region_exact_checks++;
     if(rg.id==='WD01'&&rg.semantic.semantic==='HUMAN_EVIDENCE'){
      const rs=new Set(rows);result.WD01_hits.push({mode,ordinal:fi,roi_points:rows.length,whole_clusters:chain.cs.map(c=>({ci:c.ci,n:c.n,overlap:c.rows.filter(r=>rs.has(r)).length,semantic:c.semantic.semantic})).filter(c=>c.overlap)});
     }
    }
    if(b.sid.endsWith('223757')&&[2,42,150].includes(fi)){const c=chain.cs.slice().sort((a,b)=>Math.hypot(a.center[0]-3.5,a.center[1]+.76)-Math.hypot(b.center[0]-3.5,b.center[1]+.76))[0];result.representatives.push({mode,ordinal:fi,ci:c.ci,n:c.n,center:c.center,semantic:c.semantic.semantic});}
    result.frames++;result.clusters+=chain.cs.length;if(fi%80===0)console.log('NEGATIVE_RECOMPUTE',b.sid,mode,fi);
   }
  }
 }
 // Exact 12 historical empty samples use workspace components before cleanup, as the frozen probe did.
 const p=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1'),sid='cap_20261008_114819',job='6e87c6e4146f48ba84e24c801820e5e1';
 const data=H.load(sid,H.level(sid,job,path.join(p,'leveling',job))),probe=R.read(path.join(ROOT,'docs/human_capture/evidence/2026-10-08_semantic_new_holdout_r1/results.json'));
 let checks=0;for(const fi of [0,142,284]){const ws=PL.extract_foreground(data.frames[fi].buf,null).fg_xyzi,cs=PL.cluster_voxels(PL.voxelize(ws)),owner=new Map();cs.forEach((c,ci)=>c.keys.forEach(k=>owner.set(k,ci)));const xyz=cs.map(()=>[]);
  for(let i=0;i<ws.length;i+=4){const ci=owner.get(PL.key_vox(ws[i],ws[i+1]));if(ci!==undefined)xyz[ci].push(ws[i],ws[i+1],ws[i+2]);}
  for(let ci=0;ci<xyz.length;ci++)if(xyz[ci].length/3>=S.TH.min_pts){assert.strictEqual(R.identity(S.feats(xyz[ci])),R.identity(probe.negatives.find(x=>x.ordinal===fi&&x.ci===ci).features));checks++;}
 }
 assert.strictEqual(checks,12);result.frozen_empty_samples_reconciled=checks;
 fs.writeFileSync(path.join(OUT,'negative_recompute.json'),JSON.stringify(result,null,2)+'\n');console.log('NEGATIVE_AND_FROZEN_SAMPLE_PASS',JSON.stringify({frames:result.frames,clusters:result.clusters,regions:result.region_exact_checks,empty_samples:checks}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
