/* Read-only imports; never invoke r1 main/run. Independent full-data comparison. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert'),readline=require('readline');
const OUT=__dirname,ROOT=path.resolve(OUT,'../../../..'),R1=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_hrsemshadow_r1');
const H=require(path.join(R1,'shadow.js')),S=require(path.join(R1,'semantic.js'));
const PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const R=require(path.join(ROOT,'pc_apps/human_replay/registration.js'));
const PREV=path.join(ROOT,'docs/human_capture/evidence/2026-10-08_new_static_sessions_r1');
const binding=R.read(path.join(R1,'pass3/binding.json')),regs=R.read(path.join(PREV,'registration_results.json'));
const save=(n,x)=>fs.writeFileSync(path.join(OUT,n),JSON.stringify(x,null,2)+'\n');
const inc=(o,k)=>o[k]=(o[k]||0)+1;
const key=x=>[x.sid,x.mode,x.ordinal].join('/');
async function index(filename){const m=new Map();for await(const l of readline.createInterface({input:fs.createReadStream(filename),crlfDelay:Infinity})){if(!l)continue;const r=JSON.parse(l),k=key(r);if(!m.has(k))m.set(k,[]);m.get(k).push(r);}return m;}
function rawXYZ(data,frame,row){const at=(frame.info.start_pts+row)*28,x=[0,1,2].map(j=>data.readFloatLE(at+4*j));return x;}
async function main(){
 assert.deepStrictEqual(R.codeBinding(ROOT),binding.pipeline);assert.deepStrictEqual(PL.PIPE,binding.parameters);
 assert.strictEqual(S.TH.w_min,.06);console.log('semantic selfcheck',JSON.stringify(S.selfcheck()));
 const expected=await index(path.join(R1,'pass3/clusters.jsonl')),votes=await index(path.join(R1,'pass3/votes.jsonl'));
 const stage=R.read(path.join(OUT,'stage_hashes.json'));
 const refB=binding.sessions.at(-1),ref=H.load(refB.sid,H.level(refB.sid,refB.job,path.join(PREV,'leveling',refB.job)));
 const refmap=PL.build_reference_map(ref.frames.map(f=>f.buf));assert.deepStrictEqual(R.refBinding(refmap),R.read(path.join(PREV,'reference_summary.json')).binding);
 const refkeys=new Map([...refmap.voxels].filter(([,v])=>v.occ>=PL.PIPE.bg_ref_occ_min));
 const result={source:'independent review recomputation',frames:0,clusters:0,stage_comparisons:0,cluster_exact_comparisons:0,vote_exact_comparisons:0,raw_coordinate_comparisons:0,sessions:[],cases:[]};
 for(const b of binding.sessions){
  const lev=H.level(b.sid,b.job,path.join(PREV,'leveling',b.job));assert.deepStrictEqual(lev.sha,b.leveling_sha);assert.deepStrictEqual(lev.source,b.source);
  const reg=regs.find(x=>x.sid===b.sid);if(reg){assert.deepStrictEqual(reg.transform,b.transform);assert.strictEqual(R.gate(reg.diagnostics).status,b.gate);assert.deepStrictEqual(reg,R.read(path.join(PREV,b.sid+'_registration_diagnostic.json')));}
  const data=b.sid===refB.sid?ref:H.load(b.sid,lev,b.transform),online=PL.build_static_map(data.frames.map(f=>f.buf));
  const raw=fs.readFileSync(path.join(ROOT,'captures/remote',b.sid,'points.bin'));
  for(const mode of b.sid===refB.sid?['V2_IDENTITY','WORKSPACE']:[b.gate==='PASS'?'V2':'REF_SHADOW']){
   const tracker=new PL.Tracker(),fv=new H.FrameVotes(),sum={sid:b.sid,mode,frames:data.frames.length,clusters:0,semantic:{},bins:{},any_human:0,no_cluster:0,collision:0,stale:0,invalid_candidates:0};
   for(let fi=0;fi<data.frames.length;fi++){
    const f=data.frames[fi],ws=H.subset(f,PL.extract_foreground(f.buf,null).fg_xyzi),rf=H.subset(f,PL.extract_foreground(f.buf,refkeys).fg_xyzi);
    const fg=H.subset(f,mode==='WORKSPACE'?ws.buf:mode==='REF_SHADOW'?rf.buf:PL.extract_foreground_fused(f.buf,refkeys,online).fg_xyzi);
    const c=H.clusterFrame(f,fg,fi,tracker),k=[b.sid,mode,fi].join('/'),e=expected.get(k)||[];
    assert.strictEqual(c.cs.length,e.length,k+' candidates');
    for(const [name,rows] of Object.entries({workspace:ws.rows,foreground:fg.rows,cleanup:c.clean.rows})){
      assert.strictEqual(R.identity(rows),stage[k][name],k+'/'+name);result.stage_comparisons++;
    }
    const rset=new Set(rf.rows),fgset=new Set(fg.rows),clset=new Set(c.clean.rows);
    for(const [name,rows] of Object.entries({reference_removed:ws.rows.filter(r=>!rset.has(r)),online_supported_removed:rf.rows.filter(r=>!fgset.has(r)),cleanup_removed:fg.rows.filter(r=>!clset.has(r))})){
      assert.strictEqual(R.identity(rows),stage[k][name],k+'/'+name);result.stage_comparisons++;
    }
    for(let ci=0;ci<c.cs.length;ci++){
      const actual=c.cs[ci],want=e[ci];for(const name of Object.keys(actual))assert.deepStrictEqual(actual[name],want[name],k+'/'+ci+'/'+name);
      // Independently reconstruct coordinates from global raw row with float32 after each transform.
      const xyz=[];for(const row of want.rows){let x=rawXYZ(raw,f,row);const rt=(a,t)=>[0,1,2].map(j=>Math.fround(a[j*3]*x[0]+a[j*3+1]*x[1]+a[j*3+2]*x[2]+t[j]));x=rt(lev.tf.R.flat(),lev.tf.t);if(b.transform)x=rt(b.transform.rotation_row_major,b.transform.translation_m);xyz.push(...x);result.raw_coordinate_comparisons++;}
      assert.strictEqual(R.identity(xyz),want.xyz_sha256,k+'/'+ci+'/raw xyz');
      sum.clusters++;inc(sum.semantic,want.semantic.semantic);inc(sum.bins,want.n<200?'60-199':want.n<400?'200-399':'>=400');sum.invalid_candidates+=want.invalid_rows.length;result.cluster_exact_comparisons++;
    }
    const vr=fv.tick(fi,c.cs.map(x=>({...x.old,semantic:x.semantic.semantic})));assert.deepStrictEqual(vr,votes.get(k)[0].reference,k+'/reference votes');result.vote_exact_comparisons++;
    const orig=votes.get(k)[0].original;
    assert.deepStrictEqual(c.output.tracks.map(t=>({id:t.id,votes:t.votes,human_confirmed:!!t.human_confirmed,age:fi-t.born_idx+1,lost:t.lost,last_seen:t.last_seen})),orig.map(t=>({id:t.id,votes:t.original_votes,human_confirmed:t.original_human_confirmed,age:t.age,lost:t.lost,last_seen:t.last_seen})),k+'/original tracker');
    if(orig.some(t=>t.collision_this_frame))sum.collision++;
    if(orig.some(t=>t.original_human_confirmed&&!t.normalized_old_confirmed))sum.stale++;
    if(!c.cs.length)sum.no_cluster++;if(c.cs.some(x=>x.semantic.semantic==='HUMAN_EVIDENCE'))sum.any_human++;
    if(['114205','114422'].includes(b.sid.slice(-6))&&fi===Math.floor(data.frames.length/2))result.cases.push(...e.map(x=>({sid:x.sid,mode,ordinal:fi,ci:x.ci,n:x.n,roi_overlap:x.roi_overlap,semantic:x.semantic})));
    result.frames++;result.clusters+=c.cs.length;
    if(fi%80===0)console.log('RECOMPUTE',b.sid,mode,fi);
   }
   result.sessions.push(sum);console.log('SUMMARY',JSON.stringify(sum));save('recompute_progress.json',result);
  }
 }
 assert.strictEqual(result.frames,1561);assert.strictEqual(result.clusters,4311);save('recompute.json',result);console.log('FULL_RECOMPUTE_PASS',result.frames,result.clusters);
}
main().catch(e=>{console.error(e);process.exitCode=1;});
