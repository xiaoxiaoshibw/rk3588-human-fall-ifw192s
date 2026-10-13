/* 回放策略：跳帧重置，回退/循环必须begin_session，所有tick携带代际。 */
'use strict';
const assert=require('assert'),E=require('./engine.js'),S=require('./schema.js');
let checks=0;
function check(name,fn){fn();checks++;console.log('PASS: '+name);}
function engine(policy){const e=new E.UnifiedEngine({mode:'BASE_B',replay_policy:policy||'strict'});e.begin_session('one');e._ref_env={'81920':0};e.rf={extract:()=>[],predict_person:()=>1};return e;}
function cloud(){return Float32Array.from(Array.from({length:30},()=>[1,0,1,10]).flat());}
function frame(e,i,xyzi,sid,generation){return S.make_frame_context({session_id:sid||e.session_id,session_generation:generation||e.generation,frame_index:i,timestamp:i/10,xyzi:xyzi||cloud(),already_leveled:true});}
check('连续三帧age确认',()=>{const e=engine();for(let i=0;i<3;i++)e.tick(frame(e,i));assert.equal(e.report().tracks[0].human_confirmed,true);assert.equal(e.report().rows.length,3);});
check('同帧strict抛错且不累计',()=>{const e=engine(),f=frame(e,0);e.tick(f);assert.throws(()=>e.tick(f),/重复帧/);assert.equal(e.report().rows.length,1);});
check('同帧lenient忽略且有诊断',()=>{const e=engine('lenient'),f=frame(e,0);e.tick(f);assert(e.tick(f).notes.includes('duplicate_frame_ignored'));assert.equal(e.report().rows.length,1);assert.equal(e.report().tracks[0].age,1);});
check('换会话清报告/track/保留/背景',()=>{const e=engine();e.tick(frame(e,0));e.retention.tracks[1]={x:1};e.begin_session('two');assert.equal(e.report().rows.length,0);assert.equal(e.report().tracks.length,0);assert.equal(Object.keys(e.retention.tracks).length,0);assert.equal(e.pipe_ctx.static_keys,null);e.tick(frame(e,0));assert.deepEqual(e.report().rows.map(r=>r.session_id),['two']);});
check('异sid旧帧不得污染新会话',()=>{const e=engine(),f=frame(e,0);e.begin_session('two');assert.throws(()=>e.tick(f),/过时session/);assert.equal(e.report().rows.length,0);});
check('同sid循环代际拒绝旧回调',()=>{const e=engine(),f=frame(e,0);e.tick(f);e.begin_session('one');assert.throws(()=>e.tick(f),/代际/);e.tick(frame(e,0));assert.equal(e.report().tracks[0].age,1);assert.equal(e.report().rows.length,1);});
check('缺少代际拒绝',()=>{const e=engine();const f=S.make_frame_context({session_id:'one',frame_index:0,xyzi:cloud()});assert.throws(()=>e.tick(f),/代际/);});
check('跳帧清票窗/保留，身份带segment',()=>{const e=engine();for(let i=0;i<3;i++)e.tick(frame(e,i));e.retention.tracks[1]={x:1};const d=e.tick(frame(e,30));assert(d.notes.includes('gap_reset'));assert.equal(e.report().tracks[0].age,1);assert.equal(e.report().tracks[0].human_confirmed,false);assert.equal(Object.keys(e.retention.tracks).length,0);assert.equal(e.report().rows[3].track_segment,1);assert.deepEqual(e.report().track_ids,['0:1','1:1']);});
check('未见过的倒序索引也拒绝',()=>{const e=engine();e.tick(frame(e,10));assert.throws(()=>e.tick(frame(e,5)),/回退/);assert.equal(e.report().rows.length,1);});
check('B缺帧15次仍存活，第16次删除',()=>{const e=engine();e.tick(frame(e,0));for(let i=1;i<=15;i++)e.tick(frame(e,i,new Float32Array(0)));assert.equal(e.report().tracks.length,1);assert.equal(e.report().tracks[0].lost,15);assert.equal(e.report().tracks[0].human_confirmed,false);e.tick(frame(e,16,new Float32Array(0)));assert.equal(e.report().tracks.length,0);});
check('切换/循环reason记录',()=>{const e=engine();e.begin_session('two');e.begin_session('two');assert.deepEqual(e.track_log.map(x=>x.reason),['new','session_switch','loop_back']);});
console.log('== replay_contract: '+checks+' PASS, 0 FAIL ==');
