'use strict';
const fs=require('fs'),path=require('path'),crypto=require('crypto');
const ROOT=path.resolve(__dirname,'../../../..'),OLD=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_02_r1'),OUT=path.join(ROOT,'docs/human_fall/evidence/2026-10-13_hf_real_04_r1');
const P=require('../../../../pc_apps/human_replay/human_pipe_lib');
const SID='cap_20261013_094333',seed=[2.2,1.6];
const old=JSON.parse(fs.readFileSync(path.join(OLD,SID+'_foreground.json')));
const blob=fs.readFileSync(path.join(OLD,SID+'_foreground.bin')),all=new Float32Array(blob.buffer,blob.byteOffset,blob.length/4);
if(crypto.createHash('sha256').update(blob).digest('hex')!==old.data_sha256)throw Error('source foreground hash');
const prefix=old.frames.slice(0,5).map(f=>{const p=all.subarray(f.offset*4,(f.offset+f.count)*4),a=[];
 for(let k=0;k<p.length;k+=4)if(Math.hypot(p[k]-seed[0],p[k+1]-seed[1])>.55)a.push(p[k],p[k+1],p[k+2],p[k+3]);return Float32Array.from(a);});
const residual=P.build_static_map(prefix);
for(const sid of [SID,'cap_20261013_131958']){
 const m=JSON.parse(fs.readFileSync(path.join(OLD,sid+'_foreground.json'))),b=fs.readFileSync(path.join(OLD,sid+'_foreground.bin')),a=new Float32Array(b.buffer,b.byteOffset,b.length/4);
 const rb=fs.readFileSync(path.join(OLD,sid+'_source_rows.bin')),originalRows=new Uint32Array(rb.buffer,rb.byteOffset,rb.length/4);
 const chunks=[],rowChunks=[],frames=[];let offset=0;
 for(const f of m.frames){const p=a.subarray(f.offset*4,(f.offset+f.count)*4);const fg=sid===SID?P.extract_foreground(p,residual).fg_xyzi:p;
  const rows=[];let j=0;
  for(let k=0;k<p.length&&j<fg.length;k+=4)if(p[k]===fg[j]&&p[k+1]===fg[j+1]&&p[k+2]===fg[j+2]){rows.push(originalRows[f.offset+k/4]);j+=4;}
  if(j!==fg.length)throw Error('row mapping');chunks.push(Buffer.from(fg.buffer,fg.byteOffset,fg.byteLength));rowChunks.push(Buffer.from(Uint32Array.from(rows).buffer));
  frames.push({...f,offset,count:rows.length,removed_by_static_prefix:f.count-rows.length});offset+=rows.length;
 }
 const data=Buffer.concat(chunks),rows=Buffer.concat(rowChunks),manifest={...m,frames,
  background:{...m.background,startup_residual:{frames:[0,1,2,3,4],protected_seed_xy:seed,protected_radius_m:.55,static_keys:residual.size,
   source:'stable original foreground outside visually initialized person; no per-frame visual labels or future lying frames',applied:sid===SID}},
  data_sha256:crypto.createHash('sha256').update(data).digest('hex'),rows_sha256:crypto.createHash('sha256').update(rows).digest('hex')};
 fs.writeFileSync(path.join(OUT,sid+'_foreground.bin'),data,{flag:'wx'});fs.writeFileSync(path.join(OUT,sid+'_source_rows.bin'),rows,{flag:'wx'});fs.writeFileSync(path.join(OUT,sid+'_foreground.json'),JSON.stringify(manifest,null,2),{flag:'wx'});
 console.log(sid,offset,'points',residual.size,'static residual keys');
}
