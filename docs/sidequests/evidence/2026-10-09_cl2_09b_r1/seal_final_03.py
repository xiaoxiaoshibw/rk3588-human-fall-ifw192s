"""Validate supplemented review and final test binding before immutable seal."""
import runpy,sys
from prepare import E,load,sha
model=load(E/'opencode_actual_model_03.json')
assert model['models']==['opencode-go/deepseek-v4.1-flash'] and model['last_finish']=='stop' and model['exit_code']==0
review=load(E/'opencode_completion_03.json');assert review['exit_code']==0 and review['marker']
reads=[t for t in review['tool_events'] if t.get('tool')=='read' and t.get('state',{}).get('status')=='completed']
assert len(reads)>=20
command=load(E/'candidate_regression_06_command.json')
assert command['exit_code']==0 and command['test_sha256']==sha(E/'test_selector.py')
assert command['candidate_sha256']==sha(E/'candidate/floor_sheet.py')
assert load(E/'benchmark_no_feasible_command.json')['exit_code']==0
for x in load(E/'snapshot_bindings.json'):
    assert sha(x['origin'])==sha(x['copy'])==x['sha256']
save_record=__import__('prepare').save
save_record('review_03_verification.json',dict(PASS=True,model=model,successful_reads=len(reads),
    source_and_test_bound=True,loopback_verbose_tests=35,original_input_snapshots_match=True,
    scope='Actual model/CLI/source binding verified by Codex; reviewer still did not execute numeric/SHA itself.'))
sys.argv=[str(E/'seal.py'),'final']
runpy.run_path(str(E/'seal.py'),run_name='__main__')
