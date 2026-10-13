"""Exclusive command capture and executable/input SHA bindings."""
import os
import subprocess
import sys
import time
from prepare import E,save,sha

label=sys.argv[1];args=sys.argv[2:]
env=os.environ.copy()
env['PYTHONPATH']=os.pathsep.join([str(E/'candidate'),str(E/'frozen'),str(E)])
temporary=E/'test_tmp';temporary.mkdir(exist_ok=True)
env['TEMP']=str(temporary);env['TMP']=str(temporary)
argv=[sys.executable,'-X','utf8','-B','-W','error']+args
files={str(p):sha(p) for root in [E/'candidate',E/'frozen',E/'baseline'] for p in root.rglob('*.py')}
files.update({str(p):sha(p) for p in E.glob('*.py')})
start=time.perf_counter()
with (E/(label+'.stdout')).open('xb') as out,(E/(label+'.stderr')).open('xb') as err:
    process=subprocess.run(argv,cwd=E,env=env,stdout=out,stderr=err)
save(label+'_command.json',dict(argv=argv,cwd=str(E),exit_code=process.returncode,
     elapsed_sec=time.perf_counter()-start,pythonpath=env['PYTHONPATH'],TEMP=env['TEMP'],TMP=env['TMP'],
     code_sha256_at_start=files,code_sha256_at_end={p:sha(p) for p in files},
     code_unchanged=all(sha(p)==digest for p,digest in files.items())))
print(label,process.returncode,flush=True)
raise SystemExit(process.returncode)
