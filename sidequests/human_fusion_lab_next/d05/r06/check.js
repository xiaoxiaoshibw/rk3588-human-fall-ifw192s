'use strict';
const assert=require('assert'),{applyBankAnchor,proof}=require('./hook_bank_anchor');
const S=require('../../../human_fusion_lab/core/schema');
function check(enabled,x) {
    const c=(id,source,p,cx)=>({candidate_id:id,track_id:1,foreground_source:source,rf51_prob:p,centroid:{x:cx,y:0}});
    const candidates=[c('merged',S.CAND_SRC.MERGED,.99,8),c('a1',S.CAND_SRC.FG,.8,2),c('a0',S.CAND_SRC.FG,.8,0)];
    const record={x,y:0,timestamp:1,frame_index:3,confirmations:3};
    const engine={cfg:{rf51_threshold:.55,retention:{hot_cell_radius_m:.4}},retention:{tracks:{}},
        _fusion_a_chain(){return {cands:candidates};},_fusion_b_chain(){return 'B_UNCHANGED';},
        _tick_fusion(fc){this._fusion_a_chain();this.retention.tracks[1]={...record};return this._fusion_b_chain(fc);}};
    applyBankAnchor(engine,enabled,false);
    assert.equal(engine._tick_fusion({frame_index:3,timestamp:1}),'B_UNCHANGED');
    assert.deepStrictEqual(engine.retention.tracks[1],{...record,x:enabled&&Math.abs(x)>.4?0:x});
    assert.equal(proof(candidates,1,.55).candidate_id,'a0');
    assert.equal(proof(candidates.filter(c=>c.foreground_source!==S.CAND_SRC.FG),1,.55),null);
}
for(const x of [.399,.4,.400001,-.4,-.400001]){check(false,x);check(true,x);}
console.log('R06_EXISTING_RADIUS_BOUNDARY_AND_ONLY_XY_PASS');
