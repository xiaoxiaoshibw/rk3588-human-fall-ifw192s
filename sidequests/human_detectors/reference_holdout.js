/* Empty-template calibration holdout diagnostic only; does not replace the locked experiment map. */
'use strict';
const fs=require('fs'),path=require('path'),assert=require('assert');
const PL=require('./artifacts/det02_code/human_pipe_lib.js');
const [input,outfile]=process.argv.slice(2);
const manifest=JSON.parse(fs.readFileSync(path.join(input,'manifest.json'),'utf8'));
assert(manifest.empty_template_confirmed);
const s=manifest.sessions.find(v=>v.role==='empty_reference');
const held=new Set([Math.floor((s.frames.length-1)/3),Math.floor(2*(s.frames.length-1)/3),s.frames.length-1]);
const frames=s.frames.map(f=>{const b=fs.readFileSync(path.join(input,s.sid,f.file));return PL.denoise(new Float32Array(b.buffer,b.byteOffset,b.byteLength/4));});
const ref=PL.build_reference_map(frames.filter((_,i)=>!held.has(i)));
const map=new Map([...ref.voxels].filter(([,r])=>r.occ>=PL.PIPE.bg_ref_occ_min));
const rows=[...held].map(i=>{const crop=PL.extract_foreground(frames[i],null),fg=PL.extract_foreground(frames[i],map);return {index:i,seq:s.frames[i].seq,workspace_points:crop.n_fg,remaining_points:fg.n_fg,removed_fraction:1-fg.n_fg/crop.n_fg};});
fs.writeFileSync(outfile,JSON.stringify({source:s.source,template_fit_frames:frames.length-held.size,holdouts:rows,
    scope:'same-session frame holdout background deletion diagnostic, not cross-scene generalization'},null,2),{flag:'wx'});
console.log(JSON.stringify(rows));
