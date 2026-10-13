"use strict";
const fs=require('fs'),path=require('path'),cp=require('child_process'),assert=require('assert'),R=require('../../../../pc_apps/human_replay/registration');
const root=R.ROOT,snap=path.join(__dirname,'baseline_code'),item='docs/human_capture/evidence/2026-10-06_hrw03_r8/10_r36_registration.js';
for(const f of ['pc_apps/human_replay/human_pipe_lib.test.js','pc_apps/human_replay/human_detect.js','pc_apps/human_replay/human_detect.html',
    item,'docs/human_capture/evidence/2026-10-06_hrw03_r7/02_attribution_results.json']) {
    const to=path.join(snap,f);fs.mkdirSync(path.dirname(to),{recursive:true});fs.copyFileSync(path.join(root,f),to,fs.constants.COPYFILE_EXCL);
}
const archived=R.read(path.join(root,'docs/human_capture/evidence/2026-10-06_hrw03_r8/03_results.json'));
const baseline=cp.spawnSync(process.execPath,[path.join(snap,item),'--digest-only'],{encoding:'utf8',maxBuffer:10<<20});
fs.writeFileSync(path.join(__dirname,'05_r36_historical.stdout.log'),baseline.stdout,{flag:'wx'});fs.writeFileSync(path.join(__dirname,'05_r36_historical.stderr.log'),baseline.stderr,{flag:'wx'});
const digest=baseline.stdout.match(/DIGEST=([0-9a-f]{64})/)?.[1];
assert.equal(baseline.status,0);assert.equal(digest,archived.digest,'original R3.6 digest under original source SHA');
// The unmodified historical script is also run with live fixed PL. New outputs are written only here.
const out=path.join(__dirname,'r36_after');fs.mkdirSync(out);
const after=cp.spawnSync(process.execPath,[path.join(root,item),'--outdir='+out],{encoding:'utf8',maxBuffer:10<<20});
fs.writeFileSync(path.join(__dirname,'05_r36_after.stdout.log'),after.stdout,{flag:'wx'});fs.writeFileSync(path.join(__dirname,'05_r36_after.stderr.log'),after.stderr,{flag:'wx'});
assert.equal(after.status,0);const now=R.read(path.join(out,'03_results.json'));
for(const k of ['conditions','c_registration_qa','params','conservation','baseline','micro','groups','frames','human_safety','person_centers','checks','r35_gate','outputs'])assert.deepEqual(now[k],archived[k],k+' algorithm/result projection');
assert.equal(now.checks.length,19);assert(now.checks.every(v=>v.pass));
const result={historical:{exit_code:baseline.status,digest,expected:archived.digest,exact_digest_equal:true},
    after_metric_fix:{exit_code:after.status,digest:now.digest,exact_digest_equal:now.digest===archived.digest,
        evidence_identity_change:'full digest includes PL source SHA; expected change, no rebind of old artifact',algorithm_result_projection_equal:true,checks:now.checks},
    input_shas_before_after_equal:now.provenance.inputs_unchanged,raw_original_script_sha:R.shaFile(path.join(root,item))};
fs.writeFileSync(path.join(__dirname,'05_r36_equivalence.json'),R.serialize(result),{flag:'wx'});console.log(JSON.stringify(result,null,2));
