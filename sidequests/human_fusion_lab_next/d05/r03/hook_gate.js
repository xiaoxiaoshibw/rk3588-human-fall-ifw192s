'use strict';
// 单一分类因素：原始69D模型照算；仅拒绝同时宽且近水平的真实候选。
// 不读取GT或历史标注；不能把被拒绝/高分候选叫家具或真人。
function geometry(f) {
    if(f.length!==69||!Array.from(f).every(Number.isFinite))throw Error('invalid 69D model input');
    const radius=Math.sqrt(2*(Math.max(0,f[26])+Math.max(0,f[29]))),upcos=f[39];
    return {radius,upcos,veto:radius>.45&&upcos<.5,reason:radius>.45&&upcos<.5?'BROAD_HORIZONTAL_VETO':'UNCHANGED_MODEL_DECISION'};
}
function applyGate(engine) {
    const original=engine._raw_predict||engine.rf.predict_person,log=[];
    engine._gate_calls=log;
    engine.rf.predict_person=function(f){const raw_prob=original.call(this,f),g=geometry(f),effective_prob=g.veto?0:raw_prob;
        log.push({raw_prob,effective_prob,...g});return effective_prob;};
    const level=engine._level;
    engine._level=function(...a){log.length=0;return level.apply(this,a);};
    return {version:'r03-broad-horizontal-v1',radius_gt:.45,upcos_lt:.5,feature_indices:[26,29,39],model_unchanged:true};
}
function rawPredict(engine,f){return engine._raw_predict.call(engine.rf,f);}
module.exports={geometry,applyGate,rawPredict};
