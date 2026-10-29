"""Run registered stages A and B in order, preserving expected failure."""
import subprocess
import sys
import time
from register import ROOT, EV, HERE

while not (EV/'REGISTRATION.json').exists():time.sleep(1)
for label, script, extra, expected in [
    ('BINDINGS','bindings.py',[],0),
    ('FROZEN_REPRO','reproduce.py',[],1),
    ('UNIT','test_s07.py',['-v'],0),
    ('REPLAY','replay.py',[],0),
    ('FOREGROUND','experiment.py',['ledger'],0),
    ('RAW_OLD','experiment.py',['raw_old'],0),
    ('FG_OLD','experiment.py',['fg_old'],0),
]:
    command=[sys.executable,'-B','-W','error',str(HERE/'execute.py'),label,str(HERE/script)]+extra
    result=subprocess.run(command,cwd=ROOT)
    if result.returncode!=expected:raise SystemExit(label+' unexpected exit '+str(result.returncode))
