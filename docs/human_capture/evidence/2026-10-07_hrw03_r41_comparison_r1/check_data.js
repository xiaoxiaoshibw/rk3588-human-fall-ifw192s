"use strict";
const fs=require('fs'),path=require('path'),assert=require('assert'),crypto=require('crypto');
const old=path.resolve(__dirname,'../2026-10-07_hrw03_r39_closeout');
const D=JSON.parse(fs.readFileSync(path.join(__dirname,'comparison_data.js'),'utf8').replace(/^window.COMPARE_DATA=/,'').trim().replace(/;$/,''));
const shadow=JSON.parse(fs.readFileSync(path.join(old,'06_shadow_results.json'),'utf8'));
const sha=p=>crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
for(const [name,value] of Object.entries(D.source_sha256))assert.equal(sha(path.join(old,name)),value,name+' input drift');
assert.equal(D.frames.length,165);assert.equal(D.available.length,153);assert.equal(new Set(D.available.map(f=>f.frame)).size,153);
assert.equal(D.frames.reduce((n,f)=>n+f.loss.length,0),31);assert.equal(D.gate.status,'WARN');
let localPoints=0,paired=0;
const counts=[];
for(const available of D.available){const fr=JSON.parse(fs.readFileSync(path.join(old,'viewer_frames/f'+available.frame+'.js'),'utf8').replace(/^window.HR_FRAME=/,'').trim().replace(/;$/,'')),data=D.frames[available.frame];
    assert.equal(fr.frame,available.frame);assert.equal(fr.seq,available.seq);assert.equal(fr.points.length,available.count);assert.equal(new Set(fr.points.map(p=>p[0])).size,fr.points.length);
    let P=0,S=0,lost=0,gained=0;
    for(const row of fr.points){assert.equal(row.length,16);assert(row.slice(1,7).every(Number.isFinite));P+=row[9];S+=row[10];if(row[9]&&!row[10])lost++;if(row[10]&&!row[9])gained++;
        for(const [ci,name] of [[row[11],'P'],[row[12],'S']])if(ci!==null)assert(ci>=0&&ci<data[name].clusters.length);
        // Both displayed clouds use these exact source coordinates, not a
        // re-estimated transform or native-S geometry mixed with source-P.
        if(row[9]&&row[10])paired++;
    }
    assert.equal(P-S,lost-gained);localPoints+=fr.points.length;
    for(const name of ['P','S']){assert.equal(data[name].post,shadow[name].frames[fr.frame].fg_after_cleanup);assert.equal(data[name].clusters.length,shadow[name].frames[fr.frame].clusters.length);}
    for(const loss of data.loss){assert(fr.points.some(p=>p[0]===loss.index));assert(loss.xyz.every(Number.isFinite));}
    counts.push({frame:fr.frame,local_points:fr.points.length,P_post:P,S_post:S,lost,gained,clean_audit_markers:data.loss.length});
}
const html=fs.readFileSync(path.join(__dirname,'comparison.html'),'utf8');
for(const match of html.matchAll(/(?:src|href)="([^"#]+)"/g)){const target=match[1].split('?')[0];assert(fs.existsSync(path.resolve(__dirname,target)),'Missing dependency '+target);}
assert(html.includes('不是人数')&&html.includes('局部证据')&&html.includes('未包含后续提出的')&&html.includes('安全验收未闭合'));
const result={result:'PASS',source:'diagnostic',checked_input_SHA_files:Object.keys(D.source_sha256).length,local_frames:153,full_stat_frames:165,local_points:localPoints,paired_points:paired,clean_markers:31,counts,production_algorithm_changed:false};
fs.writeFileSync(path.join(__dirname,'03_data_checks.json'),JSON.stringify(result,null,2)+'\n',{flag:'wx'});
console.log(JSON.stringify({...result,counts:undefined}));
