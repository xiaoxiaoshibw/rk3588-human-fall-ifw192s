"""Incremental R2 development: build, check, or run without publishing the release exe."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parent.parent
APP = ROOT / 'console_v2'
SESSION = ROOT / 'data/sessions/cap_20261018_110029'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('build', help='Incremental C# and Qt build; prepare directory runtime')
    commands.add_parser('check', help='Build, fixed real-frame differential checks, then native offline smoke')
    preview = commands.add_parser('run', help='Build and open the read-only spike')
    preview.add_argument('--session', type=Path, default=SESSION)
    preview.add_argument('--count', type=int, choices=[0, 50000, 500000], default=0)
    preview.add_argument('--duration', type=int, choices=range(1, 61), default=10, metavar='1..60')
    args = parser.parse_args()

    # Reuse the existing command logger, with a fresh application-owned destination.
    out = APP / '.tools/spike-evidence/dev' / uuid.uuid4().hex
    for parent in out.parents:
        if parent.is_symlink() or parent.is_junction():
            raise ValueError('Development output directory links are rejected: ' + str(parent))
    os.environ['CONSOLEV2_SPIKE_OUT'] = str(out)
    sys.path.insert(0, str(APP / 'tools'))
    from run_spike_command import run

    sdk = APP / '.tools/dotnet/dotnet.exe'
    qt = APP / '.tools/qt/6.5.3/mingw_64'
    compiler = APP / '.tools/qt/Tools/mingw1120_64/bin'
    cmake = shutil.which('cmake')
    service = APP / 'spike/service'
    native = APP / 'spike/build'
    runtime = APP / 'spike/package-dev'
    result = dict(command=args.command, output=str(out), release_publish=False, status='FAILED')

    def execute(label, argv):
        print(label, flush=True)
        code = run(label, [str(a) for a in argv])
        if code:
            raise subprocess.CalledProcessError(code, argv)

    try:
        for tool in [sdk, qt / 'bin/windeployqt.exe', compiler / 'g++.exe', compiler / 'mingw32-make.exe']:
            if not tool.is_file():
                raise FileNotFoundError('Prepare the documented portable R2 toolchain: ' + str(tool))
        if not cmake:
            raise FileNotFoundError('CMake is required on PATH')
        execute('service_build', [sdk, 'build', service / 'SpikeService.csproj', '-c', 'Release', '--no-restore'])
        if not (native / 'CMakeCache.txt').is_file():
            execute('native_configure', [cmake, '-S', APP / 'spike/native', '-B', native, '-G', 'MinGW Makefiles',
                    '-DCMAKE_BUILD_TYPE=Release', '-DCMAKE_CXX_COMPILER=' + str(compiler / 'g++.exe'),
                    '-DCMAKE_MAKE_PROGRAM=' + str(compiler / 'mingw32-make.exe'), '-DCMAKE_PREFIX_PATH=' + str(qt)])
        execute('native_build', [cmake, '--build', native, '--parallel', '8'])
        runtime.mkdir(parents=True, exist_ok=True)
        shutil.copy2(native / 'QtSpike.exe', runtime / 'QtSpike.exe')
        execute('runtime_deploy', [qt / 'bin/windeployqt.exe', '--no-translations', '--no-opengl-sw',
                '--qmldir', APP / 'spike/native', '--dir', runtime, runtime / 'QtSpike.exe'])

        if args.command == 'check':
            execute('codec_differential', [sys.executable, '-B', '-W', 'error', APP / 'tools/verify_spike.py'])
        if args.command in ('check', 'run'):
            report = out / 'preview.json'
            source = args.session.resolve() if args.command == 'run' else SESSION
            execute('native_offline', [sdk, service / 'bin/Release/net8.0-windows/win-x64/SpikeService.dll',
                    '--host', runtime / 'QtSpike.exe', '--session', source, '--report', report,
                    '--count', str(args.count if args.command == 'run' else 0),
                    '--duration', str(args.duration if args.command == 'run' else 1)])
            observed = json.loads(report.read_text('utf-8'))
            complete = next(m for m in observed['messages'] if m['event'] == 'complete')
            if observed['child_exit_code'] != 0 or observed['board_calls'] != 0 or complete['self_checks'] != {
                    'gui_active_event_accounting': True, 'layout_before_mapping': True}:
                raise RuntimeError('Native offline checks failed')
            result['preview_report'] = str(report)
        result['status'] = 'PASS'
        return 0
    except (OSError, subprocess.CalledProcessError, RuntimeError, ValueError, KeyError, StopIteration) as error:
        result['error'] = str(error)
        print(str(error), file=sys.stderr)
        return error.returncode if isinstance(error, subprocess.CalledProcessError) else 2
    finally:
        with (out / 'DEV_RUN.json').open('x', encoding='utf-8') as target:
            json.dump(result, target, ensure_ascii=False, indent=2)
        print('Development logs: ' + str(out), flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
