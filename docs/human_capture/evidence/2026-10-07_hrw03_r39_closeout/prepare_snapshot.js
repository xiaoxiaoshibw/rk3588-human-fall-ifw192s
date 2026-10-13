"use strict";
const fs=require('fs'),path=require('path'),R=require('../../../../pc_apps/human_replay/registration');
const root=R.ROOT,snap=path.join(__dirname,'baseline_code');
const p=R.read(path.join(root,'captures/registration/cap_20261002_223757__to__cap_20261004_203349/provenance.json'));
const list=[];
for(const b of [p.source_session,p.reference_session])for(const name of ['meta.json','points.bin'])list.push('captures/remote/'+b.sid+'/'+name);
for(const b of [p.source_leveling,p.reference_leveling])for(const name of ['report.json','manifest.json','tls/transform.json'])list.push('captures/leveled/'+b.job_id+'/'+name);
const rows=[];
for(const f of list) {
    const from=path.join(root,f),to=path.join(snap,f);fs.mkdirSync(path.dirname(to),{recursive:true});
    fs.copyFileSync(from,to,fs.constants.COPYFILE_EXCL);
    const sha=R.shaFile(from);if(R.shaFile(to)!==sha)throw Error('snapshot mismatch');rows.push({path:f,sha256:sha,bytes:fs.statSync(to).size});
}
fs.writeFileSync(path.join(__dirname,'00_snapshot_inputs.json'),R.serialize(rows),{flag:'wx'});
console.log(JSON.stringify({files:rows.length,bytes:rows.reduce((n,v)=>n+v.bytes,0),purpose:'historical code-bound offline replay; ordinary file copies, no links to captures'}));
