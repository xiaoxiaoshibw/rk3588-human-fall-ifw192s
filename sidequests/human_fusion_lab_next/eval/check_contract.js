'use strict';
const assert=require('assert'),I=require('../contracts/index_v1'),E=require('../contracts/strict_v2');
const co={R:[1,0,0,0,1,0,0,0,1],T:[0,0,1.38],already_leveled:false},x=Float32Array.from([0,0,0,1,1,2,3,5,1,2,3,5,NaN,0,1,0,0,Infinity,1,0]);
const m=I.mapFrame(x,co);assert.deepStrictEqual(Array.from(m.compact_to_raw),[1,2]);assert.deepStrictEqual(Array.from(m.raw_to_compact),[-1,0,1,-1,-1]);assert(Number.isNaN(m.leveled_xyzi[2]));assert.deepStrictEqual(I.compactIdsToRaw([1,0],m),[2,1]);assert.throws(()=>I.compactIdsToRaw([2],m));
const gt=[{id:'g',class_name:'PERSON',indices:[1,2,3,4]}],c=[{id:'c',indices:[1,2,3],accepted:true,track_id:'FUS_t0_1'}],t=[{id:1,track_segment:0,human_confirmed:true,lost:0}];
let v=E.evaluateFrame({gt,candidates:c,raw_components:c,tracks:t,qualification:'PARTIAL'});assert.equal(v.observed_confirmed.tp,1);assert.equal(v.proposal.tp,1);assert.equal(v.observed_confirmed.fn,0);assert.equal(E.count(gt,c.concat(c),false).unmatched_unknown,1);assert.equal(E.count(gt,[],false).fn,1);
v=E.evaluateFrame({gt:null,candidates:c,tracks:t});assert.deepStrictEqual(v.observed_ids,[1]);t[0].lost=1;v=E.evaluateFrame({gt,candidates:c,tracks:t,qualification:'PARTIAL'});assert.deepStrictEqual(v.coast_ids,[1]);assert.equal(v.observed_confirmed.fn,1);
assert.equal(E.count([], [{id:'p',indices:[9]}],false,[{class_name:'FURNITURE',indices:[9],source:'human'}]).fp,1); // count receives already-qualified negatives only.
v=E.evaluateFrame({gt:[{class_name:'FURNITURE',indices:[9],source:'human'}],candidates:[{id:'p',indices:[9],accepted:true}],qualification:'PARTIAL'});assert.equal(v.accepted.fp,0);assert.equal(v.accepted.unmatched_unknown,1);
console.log('CONTRACT_CHECK_PASS index invalid/duplicate identity; one-to-one; missing proposal FN; partial unknown; current support; coast; negative qualification');
