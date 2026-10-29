"""Audit Go v2 transport metadata and reconstruct SHA-proven failed versions."""
import json
import subprocess
import sys
import hashlib
from common import ROOT, EV, HERE, read, save, sha

def capture(label):
    status=read(EV/(label+'_STATUS.json'));sid=status['sessions'][0]
    cmd=[r'C:\Users\30680\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe','session','export','--standalone',sid]
    cp=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,encoding='utf8',timeout=60)
    save(label+'_SESSION_EXPORT_R3.json',cp.stdout)
    save(label+'_SESSION_EXPORT_R3.stderr',cp.stderr)
    data=json.loads(cp.stdout) if cp.returncode==0 else {}
    models=set()
    def walk(obj):
        if isinstance(obj,dict):
            if obj.get('type')=='assistant' and isinstance(obj.get('model'),dict):
                m=obj['model'];models.add(m.get('providerID','')+'/'+m.get('modelID',m.get('id','')))
            if obj.get('role')=='assistant' and obj.get('modelID'):
                models.add(obj.get('providerID','')+'/'+obj['modelID'])
            for value in obj.values():walk(value)
        elif isinstance(obj,list):
            for value in obj:walk(value)
    walk(data)
    events=[json.loads(line) for line in (EV/(label+'.jsonl')).read_text(encoding='utf8').splitlines() if line.startswith('{')]
    parts=[e['part'] for e in events if e.get('type')=='tool_use']
    reads=[p['state']['input'].get('path',p['state']['input'].get('filePath','')).replace('\\','/').lower() for p in parts if p.get('tool')=='read' and p['state'].get('status')=='completed']
    request=(EV/(label+'_REQUEST.md')).as_posix().lower()
    result=dict(command=cmd,export_exit=cp.returncode,actual_models=sorted(models),session_id=sid,request_read_observed=request in reads,ponytail_read_observed=any('ponytail/skill.md' in path for path in reads),tools=sorted({p['tool'] for p in parts}),read_only_tools=all(p['tool'] in ('read','glob','grep','list') for p in parts),independent_execution='NOT_RUN',source_unchanged=status['source_unchanged'],correction='Go v2 input.path and session export; original legacy parser status preserved')
    save(label+'_TRANSPORT_AUDIT_R3.json',result);print(result,flush=True)

def reconstruct():
    out=EV/'SHA_VERIFIED_FAILING_SOURCE';out.mkdir()
    code=(HERE/'regions.py').read_text(encoding='utf8')
    block='''    # Canonical source-row order keeps reduction/quantile boundary behavior
    # invariant to input iteration order; this changes no geometric threshold.
    order=np.argsort(np.asarray(source_rows),kind='stable')
    p=p[order];source_rows=[source_rows[i] for i in order]
'''
    assert code.count(block)==1;oldcode=code.replace(block,'')
    test=(HERE/'test_regions.py').read_text(encoding='utf8')
    start=test.index('    def test_transverse_ambiguity_and_horizontal_contract(self):')
    end=test.index("\nif __name__=='__main__':",start)
    oldtest=test[:start]+test[end:]
    expected=read(EV/'REGIONS_UNIT_RUN.json')['source_sha'];check={}
    for name,text in (('regions.py',oldcode),('test_regions.py',oldtest)):
        digest=hashlib.sha256(text.encode('utf8')).hexdigest()
        want=expected[(HERE/name).relative_to(ROOT).as_posix().replace('/','\\')] if (HERE/name).relative_to(ROOT).as_posix().replace('/','\\') in expected else expected[(HERE/name).relative_to(ROOT).as_posix()]
        # The recorded exact hash, not memory or prose, determines acceptance.
        assert digest==want,(name,digest,want)
        with (out/(name+'.txt')).open('xb') as f:f.write(text.encode('utf8'))
        check[name]=dict(recorded_sha=want,reconstructed_sha=digest,exact=True)
    save('FAILING_SOURCE_RECONSTRUCTION.json',dict(method='Reconstruct from exact edit history, accept only exact SHA equality with pre-command REGIONS_UNIT_RUN.json; original failure log retained.',files=check,changes=dict(regions='only canonical source row sort, no numerical threshold change',test_regions='original allclose atol1e-12 rtol0 retained; added extra ambiguity/horizontal contract case'),initial_baseline=dict(command='python -B -W error sidequests/hfus_tcms_02/realdev/r11/register.py',aborted_process=read(EV/'BASELINE_ATTEMPT1_ABORTED.json'),reason='serial all-tree SHA scanning too slow; own process stopped before registration or experiments; restarted eight-thread full inventory',original_runtime_source_sha='UNRECORDED; no retrospective claim of original source sealing',current_baseline='BASELINE_ALL.json is subsequent single exclusive complete baseline; registration completed before all experiment commands')))

if __name__=='__main__':
    if sys.argv[1]=='reconstruct':reconstruct()
    else:capture(sys.argv[1])
