import ast,difflib,json,os,subprocess,sys,time
from pathlib import Path
from prepare import E,save,sha,load

env=os.environ.copy();env['PYTHONPATH']=os.pathsep.join([str(E/'candidate'),str(E/'frozen'),str(E)])
temporary=E/'test_tmp';temporary.mkdir(exist_ok=True)
env['TEMP']=str(temporary);env['TMP']=str(temporary)
label=sys.argv[1] if len(sys.argv)>1 else 'candidate_regression'
stages=[(label,['-m','unittest','-v','test_selector','floor_detector_test','floor_sheet_test','floor_roi_test','leveling_test'])]
for label,args in stages:
    argv=[sys.executable,'-X','utf8','-B','-W','error']+args
    begin=time.perf_counter()
    with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
        p=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
    save(label+'_command.json',dict(argv=argv,cwd=str(E),pythonpath=env['PYTHONPATH'],exit_code=p.returncode,elapsed_sec=time.perf_counter()-begin,test_sha256=sha(E/'test_selector.py'),candidate_sha256=sha(E/'candidate/floor_sheet.py')))
    print(label,p.returncode,flush=True)
    if p.returncode:raise SystemExit(p.returncode)
old=(E/'frozen/floor_sheet.py').read_text(encoding='utf8');new=(E/'candidate/floor_sheet.py').read_text(encoding='utf8')
diff=''.join(difflib.unified_diff(old.splitlines(True),new.splitlines(True),fromfile='a/pc_apps/human_replay/floor_sheet.py',tofile='b/pc_apps/human_replay/floor_sheet.py'))
if (E/'02_fix.patch').exists():assert (E/'02_fix.patch').read_text(encoding='utf8')==diff
else:(E/'02_fix.patch').write_text(diff,encoding='utf8')
if (E/'candidate_version.json').exists():assert load(E/'candidate_version.json')['source_sha256']==sha(E/'candidate/floor_sheet.py')
else:save('candidate_version.json',dict(variant_id='cl209b_feasible_roi_v1',source_sha256=sha(E/'candidate/floor_sheet.py'),frozen_sha256=sha(E/'frozen/floor_sheet.py'),production_integrated=False,profile_thresholds_unchanged=True))
