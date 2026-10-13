"""Final record/freeze/prefix/scope checks, after the full old-asset SHA audit."""
import hashlib
import json
from pathlib import Path
from record import OUT, ROOT, RETURN, sha, save, git, names

def read(p):
    return json.loads(Path(p).read_text('utf8'))

baseline = read(OUT/'00_baseline.json')
integrity = read(OUT/'integrity_final.json')
assert integrity['pass'] and not integrity['changed'] and not integrity['unexpected_new']
freeze = read(OUT/'freeze_r3.json')
for name, expected in freeze['files'].items():
    assert sha(OUT/name) == expected, name
old = baseline['files'][RETURN.relative_to(ROOT).as_posix()]
assert hashlib.sha256(RETURN.read_bytes()[:old['bytes']]).hexdigest() == old['sha256']
assert sha(RETURN) == read(OUT/'prefix_check.json')['final_sha256']
assert set(names()) == set(baseline['files'])
assert git('rev-parse','HEAD').decode().strip() == baseline['head']
assert git('branch','--show-current').decode().strip() == baseline['branch']
acceptance = read(OUT/'acceptance_status.json')
assert [r['id'] for r in acceptance['rows']] == ['SKO-%02d'%i for i in range(1,19)]
assert acceptance['counts'] == {'PASS':12,'BLOCKED':6} and not acceptance['accepted']
assert read(OUT/'identity_gt.json')['records'] == []
assert read(OUT/'node_review.json')['records'] == []
assert read(OUT/'pass5/digests.json') == read(OUT/'pass6/digests.json')
for run in ['binding_r3','synthetic_tests','binding_tests_final','review_contract_tests','independent_final',
            'corpus_pass5','corpus_pass6','replay_regression','pipe_regression','registration_regression','materials','report','integrity_check']:
    info = read(OUT/(run+'.run.json'))
    assert info['exit_code'] == 0, run
    assert sha(OUT/(run+'.stdout.log')) == info['stdout_sha256']
    assert sha(OUT/(run+'.stderr.log')) == info['stderr_sha256']
save(OUT/'final_checks.json',{'pass':True,'old_asset_full_sha_audit':integrity,'post_append_prefix_verified':True,
     'final_source_freeze_verified':True,'all_18_acceptance_ids':True,'expected_final_logs_verified':True,
     'two_pass_digests_equal':True,'actual_gt_records':0,'status':'SUBMITTED / BLOCKED','accepted':False})
print('FINAL_CHECKS PASS; 18 IDs, final source freeze, scope, logs and return prefix verified')
