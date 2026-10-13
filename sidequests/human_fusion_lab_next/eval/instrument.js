'use strict';
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const LAB=path.resolve(__dirname,'../../human_fusion_lab');
const {pointsetSha}=require('../contracts/index_v1');
function shadow(name,oldText,newText){const src=fs.readFileSync(path.join(LAB,'human_replay',name),'utf8');assert(src.includes(oldText),'instrumentation source changed '+name);const m={exports:{}};vm.compileFunction(src.replace(oldText,newText),['module','globalThis'],{filename:'diagnostic:'+name})(m,{});return m.exports;}
function instrument(eng){
 const allPipe=shadow('human_pipe_lib.js','return clusters.filter(function (c) { return c.keys.length >= PIPE.cluster_min_voxels; });','return clusters;');Object.assign(allPipe.PIPE,eng.pipe.PIPE);
 // Shadow only: expose PB components dropped by n gate and top-4 budget without changing actual function.
 const src=fs.readFileSync(path.join(LAB,'human_replay/detect_overlay.js'),'utf8').replace('if (members.length >= 30) comps.push(members);','comps.push(members);').replace('comps.slice(0, 4).map','comps.map');
 const mod={exports:{}};vm.compileFunction(src,['module','globalThis'])(mod,{});const pbShadow=mod.exports;
 let rawPA=[], rawPB=[],voxelCloud=null,currentA=null,background=[],clean=[];
 const voxelize=eng.pipe.voxelize;eng.pipe.voxelize=function(x){voxelCloud=x;return voxelize.call(this,x);};
 const cluster=eng.pipe.cluster_voxels;eng.pipe.cluster_voxels=function(v){rawPA=allPipe.cluster_voxels(v);return cluster.call(this,v);};
 const cleanup=eng.pipe.cleanup_isolated_fg;eng.pipe.cleanup_isolated_fg=function(x){background=x;const r=cleanup.call(this,x);clean=r.xyzi;return r;};
 const pa=eng._fusion_a_chain;eng._fusion_a_chain=function(...args){const a=pa.apply(this,args);currentA=a;eng._ledger={components:[],final_ids:a.final_ids.slice(),background_ids:subsequence(args[1],background),cleanup_ids:subsequence(args[1],clean)};
  for(let i=0;i<rawPA.length;i++){const cl=rawPA[i],keys=new Set(cl.keys),ids=a.final_ids.filter((r,j)=>keys.has(eng.pipe.key_vox(a.fg_final[j*4],a.fg_final[j*4+1]))),f=eng.pipe.cluster_features(cl),reasons=[];if(cl.keys.length<eng.pipe.PIPE.cluster_min_voxels)reasons.push('voxels<'+eng.pipe.PIPE.cluster_min_voxels);if(!f.ok)reasons.push(f.reason||'cluster_features_not_ok');if(eng.cfg.hard_gate_n500&&f.n<500)reasons.push('hard_gate_n500');eng._ledger.components.push({id:'pa_component_'+i,path:'PA',raw_indices:ids,pointset_sha256:pointsetSha(ids),hard_gate_pass:!reasons.length,rejection_reasons:reasons});}
  return a;
 };
 const find=eng.overlay._test.find_clusters;eng.overlay._test.find_clusters=function(frame,hot){rawPB=pbShadow._test.find_clusters(frame,hot);const actual=find(frame,hot),sets=new Set(actual.map(c=>pointsetSha(c.members)));for(let i=0;i<rawPB.length;i++){const cl=rawPB[i],ids=cl.members.map(j=>currentA.final_ids[j]),pass=sets.has(pointsetSha(cl.members));eng._ledger.components.push({id:'pb_component_'+i,path:'PB',raw_indices:ids,pointset_sha256:pointsetSha(ids),hard_gate_pass:pass,rejection_reasons:pass?[]:[cl.n<30?'points<30':'top4_budget']});}return actual;};
 return eng;
}
function subsequence(source,subset){const ids=[];let cursor=0;for(let i=0;i<subset.length/4;i++){while(cursor<source.length/4&&!Array.from({length:4},(_,d)=>Object.is(source[cursor*4+d],subset[i*4+d])).every(Boolean))cursor++;assert(cursor<source.length/4,'point subsequence identity mismatch');ids.push(cursor++);}return ids;}
module.exports={instrument,subsequence};
