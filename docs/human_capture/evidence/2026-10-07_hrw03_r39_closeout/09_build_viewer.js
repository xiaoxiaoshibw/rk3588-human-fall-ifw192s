"use strict";
const fs=require('fs'),path=require('path'),R=require('../../../../pc_apps/human_replay/registration');
const d=R.read(path.join(__dirname,'09_visualization_data.json')),attr=R.read(path.join(__dirname,'03_confirmation_attribution_r2.json'));
const dir=path.join(__dirname,'viewer_frames');fs.mkdirSync(dir);
for(const f of d.frames)fs.writeFileSync(path.join(dir,'f'+f.frame+'.js'),'window.HR_FRAME='+JSON.stringify(f)+';\n',{flag:'wx'});
const manifest={schema:1,session:d.session,artifact_id:d.artifact_id,frame_index_base:0,columns:d.columns,
    frames:d.frames.map(f=>({frame:f.frame,seq:f.seq,clean:f.clean,point_count:f.points.length})),absorbed:d.absorbed,confirmation:attr.rows,
    input_binding:R.read(path.join(__dirname,'01_absorbed_points.json'))};
fs.writeFileSync(path.join(__dirname,'09_viewer_manifest.js'),'window.HR_MANIFEST='+JSON.stringify(manifest)+';\n',{flag:'wx'});
console.log({frames:d.frames.length,points:d.frames.reduce((n,f)=>n+f.points.length,0),lazy_loading:'one frame at a time; original coordinates unrounded'});
