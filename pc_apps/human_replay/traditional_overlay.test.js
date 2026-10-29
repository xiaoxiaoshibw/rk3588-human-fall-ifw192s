"use strict";
const assert=require('assert'),fs=require('fs'),vm=require('vm');
const P=require('./human_pipe_lib'),F=require('./fresh_map_lib'),T=require('./traditional_perception');
const c={Float32Array,Map,Set,performance,console,human_pipe_lib:P,fresh_map_lib:F,traditional_perception:T};
vm.createContext(c);vm.runInContext(fs.readFileSync('fresh_overlay.js','utf8'),c);
const O=c.FRESH_OVERLAY,I=c.FRESH_INTERNAL,frames=[],raw=[];
for(let f=0;f<60;f++){
 const start=raw.length/7;raw.push(NaN,0,0,1,0,0,0);
 for(let x=0;x<6;x++)for(let y=0;y<5;y++)for(let z=0;z<12;z++){
  const xx=3+(x-2.5)*.045,yy=1+(y-2)*.045,zz=.2+z*.14,low=f>=20;
  raw.push(low?3+(zz-.97)*.75:xx,yy,low?.34+(xx-3)*1.1:zz,50,0,0,0);
 }
 for(let k=0;k<4000;k++)raw.push(8,8,1,50,0,0,0);
 frames.push({offset_points:start,count_points:raw.length/7-start,bag_time_sec:f*.1});
}
I.set_ref_frames(Array.from({length:8},()=>new Float32Array([8,8,1,50])),'test');O.set_mode('metric3d');O.set_leveled_in_s(true);
const colours=new Float32Array(raw.length/7*3);O.attach_color(colours);
const S={meta:{frames,leveling:{}},idx:0,buf_f32:new Float32Array(raw),geo:{attributes:{color:{updateRange:{}}}},session_gen:O.notify_session()};
for(let f=0;f<60;f++){
 S.idx=f;O.on_frame(S);const a=I.audit(),fr=frames[f];
 assert.strictEqual(a.session_gen,S.session_gen);assert.strictEqual(a.frame,f);
 assert(a.source_rows.every(i=>i>fr.offset_points&&i<fr.offset_points+fr.count_points));
 assert.strictEqual(new Set(a.source_rows).size,a.source_rows.length);
 const claims=new Set(a.source_rows);
 for(let row=fr.offset_points+1;row<fr.offset_points+fr.count_points;row++){
  const rgb=Array.from(colours.subarray(row*3,row*3+3));
  if(claims.has(row))assert(rgb[0]>.15||rgb[2]>.7,'claimed point must be visibly painted');
  else assert(rgb[0]<.1&&rgb[1]<.3,'unclaimed point cannot use claim colours');
 }
 if(f>=8&&f!==20&&f!==21)assert(a.source_rows.length>200,'frame '+f);
 assert.strictEqual(S.geo.attributes.color.updateRange.offset,fr.offset_points*3);
 assert.strictEqual(S.geo.attributes.color.updateRange.count,fr.count_points*3);
}
const a=I.audit();assert.strictEqual(a.tracks.length,1);assert.strictEqual(a.tracks[0].id,1);
assert(a.events.some(e=>e.type==='FALL_CANDIDATE'&&e.confirmed===false));
const hits=a.tracks[0].hits;O.on_frame(S);assert.strictEqual(I.audit().tracks[0].hits,hits);
O.reset();assert.strictEqual(I.audit(),null);S.idx=59;O.on_frame(S);assert.strictEqual(I.audit().tracks.length,0);
S.session_gen--;O.on_frame(S);assert.strictEqual(I.audit().frame,59);
assert.throws(()=>O.set_mode('invalid'));
console.log('PASS: real source rows exclude invalid point, membership exclusive/current-frame, identity/event/reset/generation, partial GPU upload range');
