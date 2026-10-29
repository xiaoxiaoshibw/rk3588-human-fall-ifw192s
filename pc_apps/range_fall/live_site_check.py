"""One 45-second read-only upstream window, after build and Qt subscription.

No build, raw recording, background learning, board commands, or automatic retry.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import shutil
import uuid

ROOT=Path(__file__).resolve().parents[2]


def run(args):
    out=args.out.resolve()
    if any(out==p.resolve() or p.resolve() in out.parents for p in (ROOT/'data',ROOT/'captures')):
        raise ValueError('evidence must be outside data')
    out.mkdir(parents=True,exist_ok=False)
    build=args.build.resolve()
    host=build/'runtime/ConsoleV2.exe';dll=build/'service/AppService.dll'
    if not host.is_file() or not dll.is_file():raise ValueError('build and privately copy service before running')
    qt_out=ROOT/'console_v2/.tools/app-evidence'/('live_site_'+uuid.uuid4().hex)
    qt_out.mkdir()
    bridge=[sys.executable,'-u','-B','-W','error',str(ROOT/'pc_apps/range_fall/live_bridge.py'),
        '--background-url',args.background_url,'--background-manifest',str(args.background_manifest.resolve()),
        '--site-id',args.site_id,'--fit-ground-out',str(out/'ground'),'--duration','45','--wait-client',
        '--body-candidates','--port','0','--ready',str(out/'READY.json'),'--report',str(out/'BRIDGE.json')]
    pinned=[ROOT/'pc_apps/range_fall'/n for n in ('live_site_check.py','live_bridge.py','live_engine.py','live_ground.py')]
    pinned+=list((ROOT/'src/human_fall_detection/core').glob('*.py'))
    pinned+=list((ROOT/'pc_apps/human_replay').glob('floor*.py'))+list((ROOT/'pc_apps/human_replay').glob('leveling*.py'))
    pinned+=list((ROOT/'pc_apps/human_replay/leveling_estimators').glob('*.py'))
    pinned+=[ROOT/'console_v2/app/native/main.cpp',ROOT/'console_v2/app/native/Main.qml',host,dll]
    source={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in pinned}
    (out/'SOURCE_SHA256.json').write_text(json.dumps(source,indent=2),'utf8')
    env=dict(os.environ,DOTNET_ROOT=str(ROOT/'console_v2/.tools/dotnet'),DOTNET_CLI_TELEMETRY_OPTOUT='1')
    with (out/'bridge.stdout').open('xb') as stdout,(out/'bridge.stderr').open('xb') as stderr:
        process=subprocess.Popen(bridge,cwd=ROOT,stdout=stdout,stderr=stderr,env=env)
        try:
            deadline=time.monotonic()+15
            while not (out/'READY.json').exists():
                if process.poll() is not None:raise RuntimeError('bridge failed before READY')
                if time.monotonic()>deadline:raise TimeoutError('bridge READY timeout')
                time.sleep(.05)
            ready=json.loads((out/'READY.json').read_text())
            qt=[str(ROOT/'console_v2/.tools/dotnet/dotnet.exe'),str(dll),
                '--session',str(ROOT/'data/sessions/cap_20261018_110029'),
                '--host',str(host),'--report',str(qt_out/'run.json'),'--smoke',
                '--smoke-live',ready['url'],'--live-duration-ms','49000','--screenshot',str(qt_out/'window.png')]
            (out/'COMMANDS.json').write_text(json.dumps(dict(bridge=bridge,qt=qt,durationSeconds=45,
                rawCloudsRecorded=False,boardMutations=0,upstreamWindowStarts='Qt subscriptions ready'),indent=2),'utf8')
            with (out/'qt.stdout').open('xb') as qo,(out/'qt.stderr').open('xb') as qe:
                result=subprocess.run(qt,cwd=ROOT,env=env,stdout=qo,stderr=qe,timeout=70)
            if result.returncode:raise RuntimeError('Qt startup/run failed before successful completion; see qt.stderr')
            code=process.wait(timeout=15)
            (out/'EXIT.json').write_text(json.dumps(dict(bridge=code,qt=result.returncode)),encoding='utf8')
            if code or result.returncode:raise RuntimeError('live check failed; see logs')
        finally:
            if process.poll() is None:
                process.terminate();process.wait(timeout=10)
            for p in qt_out.iterdir():
                if p.is_file():shutil.copy2(p,out/p.name)
    changed=[name for name,sha in source.items() if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=sha]
    (out/'SOURCE_CHANGED.json').write_text(json.dumps(changed),'utf8')
    if changed:raise RuntimeError('source changed during live window')
    print(str(out),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--out',type=Path,required=True);p.add_argument('--build',type=Path,required=True)
    p.add_argument('--background-url',required=True);p.add_argument('--background-manifest',type=Path,required=True)
    p.add_argument('--site-id',required=True)
    run(p.parse_args())
