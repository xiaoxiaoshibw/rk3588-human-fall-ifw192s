"""Final manifest and guard, append-only historical return handled separately."""
from prepare import E,R,I,H,sha,load,save,inventory
import sys

def critical():
    b=load(E/'01_baseline.json')
    assert inventory(I)==b['isolated_all_files']
    for p,d in {**b['historical_files'],**b['input_files']}.items():assert sha(p)==d,p
    for x in b['source_bindings']:
        assert sha(x['origin'])==sha(x['frozen'])==x['sha256']
    for name in ['extra_fixture_bindings.json','validation_fixture_binding.json']:
        x=load(E/name)
        for item in x.get('bindings',[x]):
            assert sha(item['origin'])==item['sha256']
            dest=E/'frozen'/__import__('pathlib').Path(item['origin']).name
            assert sha(dest)==item['sha256']
    assert sha(R/'pc_apps/human_replay/floor_sheet.py')==b['main_floor_sheet_sha256']
    frozen={p.relative_to(E/'frozen').as_posix():sha(p) for p in (E/'frozen').rglob('*') if p.is_file()}
    candidate={p.relative_to(E/'candidate').as_posix():sha(p) for p in (E/'candidate').rglob('*') if p.is_file()}
    assert set(frozen)==set(candidate)
    assert [k for k in frozen if frozen[k]!=candidate[k]]==['floor_sheet.py']
    assert candidate['floor_sheet.py']==load(E/'candidate_version.json')['source_sha256']
    return frozen,candidate

if sys.argv[1]=='append':
    critical()
    target=H.parent/'returns/CLUSTER-01.md';prior=(E/'return_before.bin').read_bytes();current=target.read_bytes()
    assert current.startswith(prior)
    addition=(E/'return_append.md').read_bytes()
    assert addition not in current
    with target.open('ab') as f:f.write(addition)
    assert target.read_bytes()==current+addition
    save('return_append_record.json',dict(path=str(target),before_sha256=__import__('hashlib').sha256(current).hexdigest(),after_sha256=sha(target),original_prefix_sha256=sha(E/'return_before.bin'),append_only=True))
    print('CLUSTER01_APPEND_ONLY_PASS')
elif sys.argv[1]=='final':
    f,c=critical()
    meta=load(E/'opencode_actual_model_02.json');assert meta['models']==['opencode-go/deepseek-v4.1-flash'] and meta['last_finish']=='stop' and meta['exit_code']==0
    tools=load(E/'opencode_completion_02.json')['tool_events']
    reads=[t for t in tools if t.get('tool')=='read' and t.get('state',{}).get('status')=='completed']
    assert len(reads)>=15
    assert load(E/'candidate_regression_05_command.json')['exit_code']==0
    assert load(E/'session_probe_command.json')['exit_code']==0 and load(E/'benchmark_command.json')['exit_code']==0
    ret=H.parent/'returns/CLUSTER-01.md';assert ret.read_bytes().startswith((E/'return_before.bin').read_bytes())
    assert sha(ret)==load(E/'return_append_record.json')['after_sha256']
    for p in E.glob('*.json'):load(p)
    save('final_integrity.json',dict(PASS=True,frozen_and_original_critical_SHA=True,candidate_changed_files=['floor_sheet.py'],
        runtime_files=len(c),only_read_review_completed=len(reads),CLI_tool_errors=[t for t in tools if t.get('state',{}).get('status')=='error'],
        original_TLS_121647='BLOCKED',production_integrated=False,return_append_only=True,return_sha256=sha(ret),
        main_concurrent_context=load(E/'09_integrity.json')['main_context_changes']))
    files={p.relative_to(E).as_posix():sha(p) for p in sorted(E.rglob('*')) if p.is_file() and p.name!='10_evidence_manifest.json'}
    save('10_evidence_manifest.json',dict(files=files,return_path=str(ret),return_sha256=sha(ret),excludes='This manifest itself, no externally signed chain of custody.',scope='Offline candidate and source/evidence audit; production/physical not accepted.'))
    assert all(sha(E/k)==d for k,d in files.items())
    print('FINAL_MANIFEST_SHA_PASS',len(files),'files',len(reads),'CLI reads')
