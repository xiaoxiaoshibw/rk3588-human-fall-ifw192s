"use strict";
const fs = require('fs'), path = require('path'), os = require('os'), crypto = require('crypto');
const root = path.resolve(__dirname, '../../../..');
const E = require(path.join(root, 'pc_apps/human_core/engine.js'));
const S = require(path.join(root, 'pc_apps/human_core/schema.js'));
const D = require(path.join(root, 'pc_apps/human_core/data_loader.js'));
const P = require(path.join(root, 'pc_apps/human_replay/human_pipe_lib.js'));
const B = require(path.join(root, 'pc_apps/human_replay/detect_overlay.js'));
const out = {};
const cl = x => ({ok:true,cx:x,cy:0,cz:1,height_m:1.7,upcos:1,n:100,label:'HUMAN_CANDIDATE',joint:'CONFIRMED_HUMAN'});
B.reset(); const tracker = new P.Tracker();
B._test.associate([cl(0)],10); tracker.tick(0,[cl(0)]);
B._test.associate([cl(0.9)],10); tracker.tick(1,[cl(0.9)]);
out.b_gate = {production_track_ids:B._test.last.tracks.map(t=>t.id), core_track_ids:tracker.tracks.map(t=>t.id)};
B.reset(); const tracker2 = new P.Tracker();
const bclusters=[cl(0),cl(0.2)], aclusters=[cl(0),cl(0.2)];
B._test.associate(bclusters,10); tracker2.tick(0,aclusters);
out.b_one_to_one={production_ids:bclusters.map(c=>c.track_id),core_ids:aclusters.map(c=>c.track_id)};
const rfengine=new E.UnifiedEngine({mode:E.MODE.BASE_B});rfengine.begin_session('intensity');rfengine._ref_env={'81920':0};
let extractedIntensity;
rfengine.rf={extract:(points,intensity)=>{extractedIntensity=Array.from(intensity);return new Float32Array(51);},predict_person:()=>1};
const rfpoints=new Float32Array(31*4);rfpoints.set([NaN,0,1,999],0);
for(let i=1;i<=30;i++)rfpoints.set([1,0,1,10],i*4);
rfengine.tick(S.make_frame_context({session_id:'intensity',frame_index:0,xyzi:rfpoints,already_leveled:true}));
out.intensity_mapping={expected_first:10,actual_first:extractedIntensity[0],candidate_index_is_clean_not_raw:true};
const engine = new E.UnifiedEngine({mode:E.MODE.BASE_B,track_lost_max:30});
engine.begin_session('one'); engine._ref_env={};
const frame = sid => S.make_frame_context({session_id:sid,frame_index:0,xyzi:new Float32Array(0),already_leveled:true});
engine.tick(frame('one')); engine.begin_session('two'); engine.tick(frame('two'));
out.session_reset={session_id:engine.report().session_id,row_sessions:engine.report().rows.map(r=>r.session_id)};
engine.pipe_ctx.tracker.tick(1,[cl(0)]);
for(let i=2;i<=10;i++) engine.pipe_ctx.tracker.tick(i,[]);
out.config_ignored={configured_lost_max:engine.cfg.track_lost_max,actual_pipe_lost_max:P.PIPE.track_lost_max,track_active_after_9_misses:engine.report().tracks[0].active};
const Lev=require(path.join(root,'pc_apps/human_core/leveling.js'));
const already=new Float32Array([2,0,1,100,2,0,1,100,2,0,1,100,2,0,1,100]);
const aengine=new E.UnifiedEngine({mode:E.MODE.BASE_A});aengine.begin_session('leveled');aengine.set_online_background([already,already]);
const afc=S.make_frame_context({session_id:'leveled',frame_index:0,xyzi:already,meta:{leveling:{}}});
const ad=aengine.tick(afc);
out.leveling_mismatch={frame_passed_through:ad.layers[0].out_points===4,background_coordinates:Array.from(aengine.pipe_ctx.static_keys.values()).map(v=>[v.x,v.y,v.z]),frame_coordinates:Array.from(already).slice(0,3)};
const tmp = fs.mkdtempSync(path.join(os.tmpdir(),'unify_review_'));
const meta={point_file:'points.bin',point_stride_bytes:28,point_layout:{stride_bytes:28,fields:['x','y','z','intensity','ring','timestamp']},total_points:1,frames:[{count_points:1,offset_points:0,bag_time_sec:0}]};
try {
 fs.writeFileSync(path.join(tmp,'meta.json'),JSON.stringify(meta));
 fs.writeFileSync(path.join(tmp,'points.bin'),Buffer.alloc(4));
 const it=D.iter_frames_lazy(tmp); const f=it.next(); it.close();
 out.lazy_truncation={rejected:false,decoded_xyzi:Array.from(f.xyzi)};
} catch(err){out.lazy_truncation={rejected:true,error:err.message};}
finally {for(const f of ['meta.json','points.bin'])fs.unlinkSync(path.join(tmp,f));fs.rmdirSync(tmp);}
const old=path.join(root,'docs/human_capture/evidence/2026-10-10_human_unify_r1');
const empty=JSON.parse(fs.readFileSync(path.join(old,'runs/cap_20261009_113611/cap_20261009_113611__U3.json'),'utf8'));
out.empty_u3_summary=empty.session_summary;
const sha=JSON.parse(fs.readFileSync(path.join(old,'02_source_sha/prod_sha256.json'),'utf8'));
out.production_sha={checked:sha.files.length,mismatches:sha.files.filter(f=>crypto.createHash('sha256').update(fs.readFileSync(path.join(root,f.path))).digest('hex')!==f.sha256).map(f=>f.path)};
out.manifests={files:0,mismatches:[]};
for(const sid of fs.readdirSync(path.join(old,'runs'))){
 const dir=path.join(old,'runs',sid), manifest=JSON.parse(fs.readFileSync(path.join(dir,'manifest.json'),'utf8'));
 for(const entry of manifest.sessions){
  out.manifests.files++;
  const file=path.join(dir,path.basename(entry.file));
  const actual=crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex').slice(0,16);
  if(actual!==entry.sha256_16)out.manifests.mismatches.push(path.basename(file));
 }
}
console.log(JSON.stringify(out,null,2));
