import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()
def manifest():
    names=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=ROOT).decode().split('\0')
    files={}
    for name in names:
        if not name or name.startswith(OUT.relative_to(ROOT).as_posix()+'/'):
            continue
        try:
            if (ROOT/name).is_file():files[name]=sha(ROOT/name)
        except OSError as exc:
            files[name]='UNREADABLE:'+str(exc.winerror)
    return files
start=manifest()
submitted=json.loads((OUT.parent/'17_source_manifest.json').read_text())
checks={name:sha(ROOT/name)==value for section in ['sources','acceptance','data']
        for name,value in submitted[section].items()}
(OUT/'00_baseline.json').write_text(json.dumps(dict(head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip(),
    files=start,submitted_sha=checks,python=sys.version),indent=2),encoding='utf-8')
assert all(checks.values()),checks
print('All submitted source/evidence/acceptance/data SHA match',flush=True)
jobs=[('10_prior_geometry',['docs/human_fall/evidence/2026-10-02_gl03_r1/codex_geometry_checks.py']),
      ('11_prior_reference',['docs/human_fall/evidence/2026-10-02_gl03_r2/codex_reference_checks.py']),
      ('12_prior_failures',['docs/human_fall/evidence/2026-10-02_gl03_r3/codex_review_01/review_checks.py']),
      ('13_worker_checks',['docs/human_fall/evidence/2026-10-02_gl03_r4/06_r4_checks.py']),
      ('14_context_checks',[str(OUT/'context_checks.py')]),
      ('15_fall',['-m','unittest','discover','-s','src/human_fall_detection/tests','-v']),
      ('16_follow',['-m','unittest','discover','-s','src/human_follow_calibration/tests','-v'])]
results={}
for name,args in jobs:
    command=[sys.executable,'-B','-W','error']+args
    with (OUT/(name+'.txt')).open('w',encoding='utf-8') as log:
        log.write('COMMAND: '+repr(command)+'\n');log.flush()
        result=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT)
        log.write('\nEXIT='+str(result.returncode)+'\n')
    results[name]=result.returncode
    print(name,'EXIT=',result.returncode,flush=True)
(OUT/'17_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
end=manifest()
deltas={name:[start.get(name),end.get(name)] for name in sorted(set(start)|set(end)) if start.get(name)!=end.get(name)}
(OUT/'18_end_deltas.json').write_text(json.dumps(deltas,indent=2),encoding='utf-8')
print('Live baseline deltas:',list(deltas),flush=True)
