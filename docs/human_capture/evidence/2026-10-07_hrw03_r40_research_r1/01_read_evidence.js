"use strict";
// Diagnostic only: consume every old evidence file; never write into that directory.
const fs=require('fs'),path=require('path'),crypto=require('crypto'),assert=require('assert');
const old=path.resolve(__dirname,'../2026-10-07_hrw03_r39_closeout');
const rows=[];
function walk(dir) {
    for(const ent of fs.readdirSync(dir,{withFileTypes:true})) {
        const p=path.join(dir,ent.name);
        if(ent.isDirectory()) {walk(p);continue;}
        const b=fs.readFileSync(p),s=b.toString('utf8');
        const row={file:path.relative(old,p).replaceAll('\\','/'),bytes:b.length,sha256:crypto.createHash('sha256').update(b).digest('hex')};
        let value;
        if(ent.name.endsWith('.json')) value=JSON.parse(s);
        else if(s.startsWith('window.HR_FRAME=')||s.startsWith('window.HR_MANIFEST=')) value=JSON.parse(s.slice(s.indexOf('=')+1).trim().replace(/;$/,''));
        if(value!==undefined) {
            row.parse='FULL_JSON';row.keys=Object.keys(value);row.arrays=Object.fromEntries(Object.entries(value).filter(([,v])=>Array.isArray(v)).map(([k,v])=>[k,v.length]));
        } else {row.read='FULL_BYTES_AND_TEXT';row.lines=s.split('\n').length;}
        rows.push(row);
    }
}
walk(old);
const result={source:'diagnostic',superseded:'03_confirmation_attribution.json; current=03_confirmation_attribution_r2.json',files:rows.length,bytes:rows.reduce((n,r)=>n+r.bytes,0),rows};
assert(rows.some(r=>r.file==='09_visualization_data.json'&&r.parse==='FULL_JSON'));
fs.writeFileSync(path.join(__dirname,'01_evidence_read.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({files:result.files,bytes:result.bytes,important:rows.filter(r=>/^(01_absorbed|03_confirmation|06_shadow_results|07_gate_samples|09_gt_pending|09_visualization)/.test(r.file))},null,2));
