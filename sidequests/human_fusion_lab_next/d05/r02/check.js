'use strict';
const assert=require('assert'),fs=require('fs'),path=require('path');
const B=require('../../background/detector_b'),S=require('../../../human_fusion_lab/core/schema'),D=require('../../../human_fusion_lab/core/data_loader');
const {applyVariant}=require('./run');
const ref=B.buildReference(),session=D.load_session(path.join(B.ROOT,'captures/remote/cap_20261010_175804'));
const results=[];
for(const v of ['base','a06','split']){
    const det=B.createDetector(ref);applyVariant(det.engine,v);let gen=det.begin('contract');
    const fc=(fi,g=gen,sid='contract')=>S.make_frame_context({session_id:sid,session_generation:g,frame_index:fi,timestamp:session.frames[fi].timestamp,xyzi:session.frames[fi].xyzi,meta:session.meta});
    det.tick(fc(0));det.tick(fc(1));assert.throws(()=>det.tick(fc(1)),/重复/);assert.throws(()=>det.tick(fc(0)),/重复|回退/);
    const gap=det.tick(fc(10));assert(gap.notes.includes('gap_reset'));assert.equal(det.engine.track_segment,1);
    assert(Object.values(det.engine.retention.tracks).every(a=>a.frame_index===10),'old retention survives gap');
    const stale=gen;gen=det.begin('contract');assert.throws(()=>det.tick(fc(0,stale)),/过时/);const reset=det.tick(fc(0));
    assert.equal(det.engine.track_segment,0);assert(reset._tracks.every(t=>t.lost===0));
    const sid='other';gen=det.begin(sid);assert.throws(()=>det.tick(fc(0,gen,'contract')),/过时/);const switched=det.tick(fc(0,gen,sid));assert(switched._tracks.every(t=>t.born_frame_idx===0));
    results.push({variant:v,duplicate:'PASS',reverse:'PASS',gap:'PASS',reset:'PASS',cross_session:'PASS',note:'seek/reverse require begin; Demo reads immutable sequential rows'});
}
console.log(JSON.stringify({status:'PASS',checks:results}));
