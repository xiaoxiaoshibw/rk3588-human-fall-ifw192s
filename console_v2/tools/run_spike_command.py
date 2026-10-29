"""Run a build command with portable tools and save exact argv / result."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(os.environ.get('CONSOLEV2_SPIKE_OUT', str(ROOT / 'console_v2/.tools/spike-evidence/runs' / uuid.uuid4().hex))).absolute()
for parent in [OUT, *OUT.parents]:
    if parent.is_symlink() or parent.is_junction():
        raise ValueError('Output directory links are rejected')
OUT = OUT.resolve()
approved = [ROOT / 'console_v2/.tools/spike-evidence',
            Path(os.environ['LOCALAPPDATA']) / 'ConsoleV2/SpikeEvidence']
if not any(OUT == root.resolve() or OUT.is_relative_to(root.resolve()) for root in approved):
    raise ValueError('Use ConsoleV2 application-owned scratch; historical evidence is read-only')
OUT.mkdir(parents=True, exist_ok=True)


def environment():
    env = os.environ.copy()
    base = ROOT / 'console_v2/.tools'
    paths = [base / 'dotnet', base / 'qt/Tools/mingw1120_64/bin', base / 'qt/6.5.3/mingw_64/bin']
    env['PATH'] = os.pathsep.join(str(p) for p in paths) + os.pathsep + env['PATH']
    env.update(DOTNET_ROOT=str(base / 'dotnet'), DOTNET_CLI_HOME=str(base / 'dotnet-home'),
               NUGET_PACKAGES=str(base / 'nuget'), DOTNET_CLI_TELEMETRY_OPTOUT='1',
               DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1', DOTNET_GENERATE_ASPNET_CERTIFICATE='false', QSG_INFO='1')
    # Acquisition retry uses HTTP/1.1 after a package stall; the transport cause has not been proved.
    env['DOTNET_SYSTEM_NET_HTTP_SOCKETSHTTPHANDLER_HTTP2SUPPORT'] = '0'
    return env


def run(label, argv, cwd=ROOT):
    for suffix in ['.stdout', '.stderr', '.command.json']:
        if (OUT / (label + suffix)).exists():
            raise FileExistsError('Choose a new command label: ' + label)
    start = time.perf_counter()
    with (OUT / (label + '.stdout')).open('xb') as stdout, (OUT / (label + '.stderr')).open('xb') as stderr:
        result = subprocess.run(argv, cwd=cwd, env=environment(), stdout=stdout, stderr=stderr,
                                creationflags=subprocess.CREATE_NO_WINDOW)
    record = dict(argv=argv, cwd=str(cwd), exit_code=result.returncode, elapsed_s=time.perf_counter() - start)
    with (OUT / (label + '.command.json')).open('x', encoding='utf-8') as target:
        json.dump(record, target, ensure_ascii=False, indent=2)
    print(json.dumps(record, ensure_ascii=False), flush=True)
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(run(sys.argv[1], sys.argv[2:]))
