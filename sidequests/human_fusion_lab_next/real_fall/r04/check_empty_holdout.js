'use strict';
const fs=require('fs'),path=require('path');
const ROOT=path.resolve(__dirname,'../../../..'),out=path.resolve(process.argv[2]);
const P=require(path.join(ROOT,'pc_apps/human_replay/human_pipe_lib'));
const {cloud,subset}=require('./background_ab');
const read=p=>JSON.parse(fs.readFileSync(p,'utf8'));
const rows=[];const ground=P.PIPE.ground_keep_below_m;
try{P.PIPE.ground_keep_below_m=-.25;
for(const sid of ['cap_20261013_094333','cap_20261010_180557']){
 const m=read(path.join(out,sid+'_ab_manifest.json'));
 const frames=cloud(m.reference,m.refR,m.refT,m.alignment);
 const map=P.build_reference_map(m.split.FIT.map(i=>frames[i].buf),{drop_ground:false});
 const keys=new Map([...map.voxels].filter(([,v])=>v.occ>=P.PIPE.bg_ref_occ_min));
 const tracker=new P.Tracker();
 let confirmed=0,events=0,candidates=0;
 const perFrame=[];
 for(const i of m.split.HOLDOUT){
  const input=frames[i],fg=P.extract_foreground_fused(input.buf,keys,null);
  // Existing shape/evidence/tracking functions, explicit diagnostic result consumer.
  // Full existing pipeline operates only on already extracted FG, with no second deletion.
  const result=P.pipeline_frame(fg.fg_xyzi,i,{static_keys:new Map(),tracker});
  const nConfirmed=result.tracks.filter(t=>t.human_confirmed).length;
  confirmed+=nConfirmed;events+=result.events.length;candidates+=result.clusters.length;
  perFrame.push({frame:i,foreground_points:fg.n_fg,source_indices:subset(input,fg.fg_xyzi),
                candidates:result.clusters.length,human_confirmed:nConfirmed,events:result.events.length});
 }
 rows.push({reference:m.reference,holdout_frames:m.split.HOLDOUT.length,fit_frames:m.split.FIT.length,
            calibration_frames:m.split.CALIBRATION.length,candidates,confirmed_track_observations:confirmed,event_emissions:events,
            perFrame,kind:'ISOLATED_EXISTING_XY_PIPELINE_DIAGNOSTIC; not HF06 confirmed',
            threshold_tuning_on_holdout:false,geometry_and_identity:'UNKNOWN_PHYSICAL_REVIEW'});
}
fs.writeFileSync(path.join(out,'EMPTY_HOLDOUT.json'),JSON.stringify(rows,null,2),{flag:'wx'});
console.log(rows.map(r=>({reference:r.reference,holdout:r.holdout_frames,candidates:r.candidates,confirmed:r.confirmed_track_observations,event_emissions:r.event_emissions})));
}finally{P.PIPE.ground_keep_below_m=ground;}
