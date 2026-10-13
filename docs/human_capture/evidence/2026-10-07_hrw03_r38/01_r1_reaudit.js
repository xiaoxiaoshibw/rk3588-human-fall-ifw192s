"use strict";
const fs = require('fs'), path = require('path'), assert = require('assert');
const M = require('../../../../pc_apps/human_replay/registration_method.js');
const root = path.resolve(__dirname, '../../../..');
const ids = ['6bc5aabf8f0041ffa961758b4e84da94','c9712acad48c4fb7a78cb119c08d4cdb','a480b987d176479a89e1730f9d6b7c09','500314ff11484be58f44b3cf11ad033f'];
const tr = ids.map(id => JSON.parse(fs.readFileSync(path.join(root,'captures/leveled',id,'tls/transform.json'))));
const pairs = [];
for(let i=0;i<4;i++) for(let j=i+1;j<4;j++) {
    const R=M.m3.mul(tr[j].R.flat(),M.m3.t(tr[i].R.flat()));
    const u=M.m3.apply(R,...tr[i].t),t=tr[j].t.map((v,k)=>v-u[k]);
    pairs.push({from:ids[i],to:ids[j],euler:M.eulerFromR(R),t,norm:Math.hypot(...t),tz:Math.abs(t[2])});
}
assert(Math.abs(Math.max(...pairs.map(p=>p.norm))-0.0867)<0.00005);
assert(Math.abs(Math.max(...pairs.map(p=>p.tz))-0.0577)<0.00005);
assert.equal(Math.ceil(2*Math.max(...pairs.map(p=>p.norm))/0.05)*0.05,0.20);
assert(Math.abs(Math.ceil(2*Math.max(...pairs.map(p=>p.tz))/0.05)*0.05-0.15)<1e-12);
const spreads=[];
const bySid={};
for(const job of fs.readdirSync(path.join(root,'captures/leveled'))) {
    try {
        const report=JSON.parse(fs.readFileSync(path.join(root,'captures/leveled',job,'report.json')));
        const t=JSON.parse(fs.readFileSync(path.join(root,'captures/leveled',job,'tls/transform.json')));
        (bySid[report.sid] ||= []).push(t.roll_deg);
    } catch(e) { if(e.code!=='ENOENT') throw e; }
}
for(const [sid,values] of Object.entries(bySid)) spreads.push({sid,spread:Math.max(...values)-Math.min(...values)});
assert(Math.abs(Math.max(...spreads.map(s=>s.spread))-1.5442)<0.0001);
console.log(JSON.stringify({status:'PASS',pairs,spreads,translation_limit:0.20,tz_limit:0.15},null,2));
