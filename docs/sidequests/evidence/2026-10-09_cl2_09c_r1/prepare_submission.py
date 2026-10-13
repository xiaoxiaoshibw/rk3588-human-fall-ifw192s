"""Pre-review bindings, final candidate bytes, previous evidence/input guards."""
import difflib
import importlib.util
import sys
from prepare import E,B,load,save,sha

sys.path[:0]=[str(E/'candidate'),str(E/'frozen')]
import floor_sheet
before=(E/'baseline/floor_sheet.py').read_text(encoding='utf8')
after=(E/'candidate/floor_sheet.py').read_text(encoding='utf8')
patch=''.join(difflib.unified_diff(before.splitlines(True),after.splitlines(True),
             fromfile='a/pc_apps/human_replay/floor_sheet.py',tofile='b/pc_apps/human_replay/floor_sheet.py'))
(E/'02_fix.patch').write_text(patch,encoding='utf8')
save('candidate_version.json',dict(variant_id='cl209c_exact_roi_search_v1',
     baseline_id='cl209b_feasible_roi_v1',baseline_sha256=sha(E/'baseline/floor_sheet.py'),
     source_sha256=sha(E/'candidate/floor_sheet.py'),production_integrated=False,thresholds_unchanged=True))
assert sha(E/'baseline/floor_sheet.py')==sha(B/'candidate/floor_sheet.py')
unchanged={}
for directory in ['candidate','frozen','input_snapshot']:
    for path in (E/directory).rglob('*'):
        if not path.is_file() or '__pycache__' in path.parts:continue
        relative=path.relative_to(E)
        if relative.as_posix()=='candidate/floor_sheet.py':continue
        assert sha(path)==sha(B/relative),relative
        unchanged[relative.as_posix()]=sha(path)
guard=load(E/'01_baseline.json')['guards']
failures={path:dict(before=digest,after=sha(path)) for path,digest in guard.items() if sha(path)!=digest}
assert not failures,failures
save('source_summary.json',dict(baseline_sha256=sha(E/'baseline/floor_sheet.py'),
     candidate_sha256=sha(E/'candidate/floor_sheet.py'),unchanged_dependencies=unchanged,
     protected_assets_verified=len(guard),protected_assets_changed=failures,
     baseline_manifest=sha(B/'10_evidence_manifest.json'),baseline_test_sha256=sha(B/'test_selector.py'),
     regression_test_sha256=sha(E/'test_selector.py'),differential_test_sha256=sha(E/'test_equivalence.py'),
     final_regression=load(E/'05_regression_03_command.json'),
     final_runtime_matches_benchmark=load(E/'04_benchmark.json')['candidate_sha256']==sha(E/'candidate/floor_sheet.py')))
session=load(E/'06_session121647.json')
cells=[{'key':key} for key in session['clean_keys']]
final=floor_sheet._roi_metrics(cells)
assert final==session['candidate_selector']==session['original_selector']
save('06_session_final_binding.json',dict(candidate_sha256=sha(E/'candidate/floor_sheet.py'),
     clean_cell_reconstruction_sha256=sha(E/'06_session121647.json'),exact_full_dict_equal=True,result=final,
     p95_m=session['ROI2_ordinal72']['p95_m'],effective_TLS='BLOCKED',new_TLS_estimation=False,
     basis='Replay exact clean keys from current-turn raw reconstruction. Success path unchanged between r1/r2.'))
print('PRE_SUBMISSION_GUARDS_PASS',len(guard),len(unchanged),flush=True)
