"""Record real child commands, failures and Windows peak working set."""
import argparse
import json
import subprocess
import time
import psutil
from bootstrap import OUT, ROOT, write

if __name__=='__main__':
    ap=argparse.ArgumentParser();ap.add_argument('name');ap.add_argument('--budget',type=float,default=2400)
    ap.add_argument('argv',nargs=argparse.REMAINDER);a=ap.parse_args()
    argv=a.argv[1:] if a.argv[:1]==['--'] else a.argv
    start=time.time();peak=0;failure=None
    with (OUT/(a.name+'.stdout')).open('xb') as stdout,(OUT/(a.name+'.stderr')).open('xb') as stderr:
        child=subprocess.Popen(argv,cwd=ROOT,stdout=stdout,stderr=stderr)
        proc=psutil.Process(child.pid)
        while child.poll() is None:
            try:
                mem=proc.memory_info();peak=max(peak,mem.rss,getattr(mem,'peak_wset',0))
            except psutil.NoSuchProcess:pass
            if time.time()-start>a.budget:
                failure='WALL_BUDGET_EXCEEDED';child.terminate()
            if peak>2147483648:
                failure='RSS_BUDGET_EXCEEDED';child.terminate()
            time.sleep(.05)
        code=child.wait()
    result=dict(argv=argv,cwd=str(ROOT),exit_code=code,seconds=time.time()-start,peak_rss_bytes=peak,
        metric='psutil rss and Windows peak_wset; maximum',failure=failure,budget_seconds=a.budget)
    write(OUT/(a.name+'.command.json'),result)
    print(json.dumps(result))
    raise SystemExit(code if failure is None else 1)
