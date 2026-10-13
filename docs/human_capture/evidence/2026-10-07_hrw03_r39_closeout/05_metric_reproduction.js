"use strict";
const assert=require('assert'),fs=require('fs'),PL=require('../../../../pc_apps/human_replay/human_pipe_lib');
const pts=new Float32Array([1.575,1.575,1.26,1,1.576,1.576,1.26,1,1.725,1.575,1.26,1,1.726,1.576,1.26,1,1.875,1.575,1.26,1,1.876,1.576,1.26,1]);
const o=PL.pipeline_frame(pts,0,{static_keys:null,tracker:new PL.Tracker()});
assert(Array.isArray(o.clusters_before_cleanup));assert.equal(o.clusters_before_cleanup.length,1);
assert.equal(o.clusters_after_cleanup.length,1);assert(Number.isNaN(o.cleanup_split_delta));
const result={bug:'BUG-R39-M01',before_count:1,after_count:1,native_delta_is_nan:Number.isNaN(o.cleanup_split_delta),
    cause:'object array subtraction; count fields also return arrays',proposed_fix:'three diagnostic expressions use array.length; retain arrays for feature/Tracker',in_scope:true};
fs.writeFileSync(__dirname+'/05_metric_reproduction.json',JSON.stringify(result,null,2)+'\n',{flag:'wx'});console.log(result);
