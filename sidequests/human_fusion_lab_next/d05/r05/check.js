'use strict';
const assert=require('assert'),{applyBankAnchor,proof}=require('./hook_bank_anchor');
const S=require('../../../human_fusion_lab/core/schema');
function fake(anchored) {
    const c=(id,source,p,x)=>({candidate_id:id,track_id:1,foreground_source:source,rf51_prob:p,centroid:{x,y:0},point_indices:[0],_pipe_f:{},classifier_decision_auc:'CONFIRMED_HUMAN'});
    const candidates=[c('a2',S.CAND_SRC.MERGED,.99,8),c('a1',S.CAND_SRC.FG,.8,2),c('a0',S.CAND_SRC.FG,.8,3)];
    const engine={cfg:{rf51_threshold:.55},retention:{tracks:{}},pipe_ctx:{tracker:{tracks:[]}},
        _fusion_a_chain(){return {cands:candidates};},_fusion_b_chain(){return 'UNCHANGED_B';},
        _tick_fusion(fc){this._fusion_a_chain();this.retention.tracks[1]={x:8,y:0,timestamp:fc.timestamp,frame_index:fc.frame_index,confirmations:3};return this._fusion_b_chain(fc);}};
    applyBankAnchor(engine,anchored,false);
    assert.equal(engine._tick_fusion({frame_index:3,timestamp:1}),'UNCHANGED_B');
    assert.equal(engine.retention.tracks[1].x,anchored?3:8);
    assert.equal(engine.retention.tracks[1].confirmations,3);
    assert.equal(engine.retention.tracks[1].timestamp,1);
    assert.equal(proof(candidates,1,.55).candidate_id,'a0');
    assert.equal(proof(candidates.filter(c=>c.foreground_source!==S.CAND_SRC.FG),1,.55),null);
}
fake(false);fake(true);console.log('R05_BANK_ANCHOR_SINGLE_FACTOR_CHECK_PASS');
