/* Synthetic mechanical repro only, no physical/person evidence and no production patch. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const ROOT=path.resolve(__dirname,'../../../..'),PL=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib.js'));
const H=require('./shadow.js');
const c=(positive,x=1)=>({ok:true,cx:x,cy:0,cz:1,height_m:1.8,upcos:1,n:1000,label:'HUMAN_CANDIDATE',
    joint:positive?'CONFIRMED_HUMAN':'NON_HUMAN',semantic:positive?'HUMAN_EVIDENCE':'UNKNOWN'});
const rows=[];
let original=new PL.Tracker(),reference=new H.FrameVotes();
for(let f=0;f<3;f++) {
    const cs=f===2?[c(true,.9),c(true,1),c(true,1.1)]:[c(false)];
    original.tick(f,cs);const ref=reference.tick(f,cs);
    rows.push({case:'same_actual_frame_three_candidates',ordinal:f,original:JSON.parse(JSON.stringify(original.tracks)),reference:ref});
}
assert(original.tracks.some(t=>t.human_confirmed));
assert(rows.at(-1).reference.assigned.every(a=>a.status==='UNKNOWN_ASSOCIATION'));
original=new PL.Tracker();reference=new H.FrameVotes();
for(let f=0;f<=9;f++) {
    const cs=[0,1,9].includes(f)?[c(true)]:[];
    original.tick(f,cs);const ref=reference.tick(f,cs);
    rows.push({case:'f0_f1_gap_f9',ordinal:f,original:JSON.parse(JSON.stringify(original.tracks)),reference:ref});
}
assert(original.tracks.some(t=>t.human_confirmed));
assert.strictEqual(rows.at(-1).reference.windows[0].semantic_confirmed,false);
assert.strictEqual(rows.at(-1).reference.windows[0].semantic_votes,1);
fs.writeFileSync(__dirname+'/vote_repro.json',JSON.stringify({source:'synthetic',scope:'mechanical only',checks:'PASS',rows},null,2)+'\n',{flag:'wx'});
console.log('PASS: original tracker collision and stale-window reproduced; frame reference withholds confirmation');
