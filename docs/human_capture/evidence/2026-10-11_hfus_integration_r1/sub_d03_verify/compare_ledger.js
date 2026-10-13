'use strict';
// 逐字节 / 逐字段对照 ORIGINAL D03 ledger 与 rerun ledger
// 逐行读取: 既比整体字节, 也忽略 timing 字段对 JSON 做 deep-diff。
const fs=require('fs'),path=require('path'),crypto=require('crypto'),readline=require('readline');
const ORIG='D:/Code/ldiar/docs/human_capture/evidence/2026-10-11_hfus_d03_r1';
const RUN_DIR=process.argv[2]; // absolute dir containing A_*.jsonl / B_*.jsonl
const MODE=process.argv[3];
if(!RUN_DIR||!MODE)throw Error('usage: compare_ledger.js <rerundir> <A|B>');
const sids=['cap_20261010_175227','cap_20261010_175429','cap_20261010_175553','cap_20261010_175804','cap_20261010_175943','cap_20261010_180235','cap_20261010_180337','cap_20261010_180557','cap_20261010_180751'];
function sha256(file){return crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');}
// 时间/他过载字段在timing上不稳定, 归零后再diff
function sanit(o){if(o&&typeof o==='object'){
  if(Array.isArray(o)){for(const v of o)sanit(v);return o;}
  for(const k of Object.keys(o)){
    // metadata/run-variant keys whose presence depends on rerun vs original
    if(k==='schema_version'||k==='evaluation_version'||k==='segment'||k==='timestamp_s'){delete o[k];continue;}
    if(/^(ms|heap_mb|diagnostic_total_ms|layers|total_ms|elapsed_ms|bg_ms)$/.test(k)){o[k]='<T>';continue;}
    // layers contain elapsed_ms per layer → strip; keep identity (layer name, in/out counts)
    if(k==='layers'){o[k]=Array.isArray(o[k])?o[k].map(l=>{const c={...l};for(const q of Object.keys(c))if(/elapsed_ms|ms$/.test(q))c[q]='<T>';return c;}):'<T>';continue;}
    if(k==='performance'){o[k]='<T>';continue;}
    sanit(o[k]);
  }}
  return o;}
function deepEq(a,b,path,diffs){if(a===b)return;const ta=typeof a,tb=typeof b;
 if(ta!==tb){diffs.push(path+': type '+ta+' vs '+tb);return;}
 if(ta==='object'&&a&&b){const ka=Object.keys(a),kb=Object.keys(b);
  for(const k of ka)if(!(k in b)){diffs.push(path+'.'+k+': missing in rerun');continue;}
  for(const k of kb)if(!(k in a)){diffs.push(path+'.'+k+': extra in rerun');continue;}
  for(const k of ka)deepEq(a[k],b[k],path+'.'+k,diffs);return;}
 diffs.push(path+': '+JSON.stringify(a)+' vs '+JSON.stringify(b));}
async function* lines(file){const rl=readline.createInterface({input:fs.createReadStream(file),crlfDelay:Infinity});for await(const l of rl)if(l.trim())yield l;}
(async()=>{
 const rows=[];
 for(const sid of sids){
  const fo=path.join(ORIG,MODE+'_'+sid+'.jsonl');
  const fr=path.join(RUN_DIR,MODE+'_'+sid+'.jsonl');
  const shaO=sha256(fo),shaR=sha256(fr);const szO=fs.statSync(fo).size,szR=fs.statSync(fr).size;
  const byteEq=shaO===shaR&&szO===szR;
  let linesEq=true,jsonEqAll=true,firstDiffLine=-1,nDiffLines=0,diffs=[],numDiffLines=0;
  if(!byteEq){
    let idx=0;const itA=lines(fo),itB=lines(fr);
    while(true){const r=await Promise.all([itA.next(),itB.next()]);
      if(r[0].done&&r[1].done)break;
      if(r[0].done||r[1].done){linesEq=false;if(firstDiffLine<0)firstDiffLine=idx;break;}
      const la=r[0].value,lb=r[1].value;idx++;
      if(la!==lb){linesEq=false;numDiffLines++;if(firstDiffLine<0)firstDiffLine=idx;
        const ja=sanit(JSON.parse(la)),jb=sanit(JSON.parse(lb));const tmp=[];deepEq(ja,jb,'row'+idx,tmp);
        if(tmp.length){jsonEqAll=false;if(diffs.length<12)diffs.push(...tmp.slice(0,12-diffs.length));}
      }}
  }
  rows.push({sid,sid_short:sid.replace('cap_20261010_',''),shaO:shaO.slice(0,16),shaR:shaR.slice(0,16),byteEq,szO,szR,linesEq,numDiffLines,semEqAfterSanitize:jsonEqAll,firstDiffLine,diffs:diffs.slice(0,6)});
 }
 console.log(JSON.stringify(rows,null,1));
})();
