"""Build/run the native read-only application without changing the R2 spike package."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

APP = Path(__file__).resolve().parent
ROOT = APP.parent


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['build','check','run'])
    p.add_argument('--session', type=Path, default=ROOT/'data/sessions/cap_20261018_110029')
    p.add_argument('--analysis', type=Path, action='append', default=[])
    p.add_argument('--frame', type=int, default=0, help='initial replay frame')
    p.add_argument('--joint-url')
    p.add_argument('--annotator-url', help='reuse an existing local annotation server; otherwise start on demand')
    p.add_argument('--live-url', help='explicit read-only Foxglove connection at startup')
    p.add_argument('--qml-file', type=Path, help='dev mode: load this QML from disk with hot reload')
    p.add_argument('--gt-root', type=Path, help='private annotation store root (default pc_apps/annotator_v2/gt_store_v2)')
    p.add_argument('--annotation-report', type=Path, help='run the native annotation page self-check into this new file')
    p.add_argument('--tour-report', type=Path, help='run the startup + feature-page tour self-check into this new file')
    p.add_argument('--smoke-reload', action='store_true', help='self-test one watcher-driven QML reload')
    p.add_argument('--isolated-run', action='store_true', help='copy current build into a private runtime; existing windows can stay open')
    a = p.parse_args(argv)
    out = APP/'.tools/app-evidence'/uuid.uuid4().hex
    out.mkdir(parents=True)
    print('Application logs: '+str(out),flush=True)
    sdk = APP/'.tools/dotnet/dotnet.exe'
    qt = APP/'.tools/qt/6.5.3/mingw_64'
    gcc = APP/'.tools/qt/Tools/mingw1120_64/bin'
    env = dict(os.environ, DOTNET_ROOT=str(sdk.parent), DOTNET_SKIP_FIRST_TIME_EXPERIENCE='1',
               DOTNET_GENERATE_ASPNET_CERTIFICATE='false', DOTNET_CLI_TELEMETRY_OPTOUT='1')
    env['PATH'] = str(gcc)+os.pathsep+str(qt/'bin')+os.pathsep+env['PATH']
    joint_server = joint_recorder = None
    def run(label, argv):
        import json
        print(label,flush=True)
        with (out/(label+'.stdout')).open('xb') as stdout, (out/(label+'.stderr')).open('xb') as stderr:
            r = subprocess.run([str(v) for v in argv], env=env, cwd=ROOT, stdout=stdout, stderr=stderr)
        (out/(label+'.command.json')).write_text(json.dumps(dict(argv=[str(v) for v in argv], exit_code=r.returncode)), 'utf-8')
        if r.returncode:
            print((out/(label+'.stdout')).read_text('utf-8',errors='replace'))
            print((out/(label+'.stderr')).read_text('utf-8',errors='replace'))
            raise subprocess.CalledProcessError(r.returncode, argv)
    try:
        service = APP/'app/service/bin/Release/net8.0-windows'
        service_args = [sdk,'build',APP/'app/service/AppService.csproj','-c','Release','--ignore-failed-sources']
        if a.isolated_run:
            service = APP/'.tools/app-build/service'
            service_args += ['--output',service]
        run('service_build', service_args)
        build = APP/'app/build'
        run('configure', [shutil.which('cmake') or 'cmake','-S',APP/'app/native','-B',build,'-G','MinGW Makefiles',
            '-DCMAKE_BUILD_TYPE=Release','-DCMAKE_CXX_COMPILER='+str(gcc/'g++.exe'),
            '-DCMAKE_MAKE_PROGRAM='+str(gcc/'mingw32-make.exe'),'-DCMAKE_PREFIX_PATH='+str(qt)])
        run('native_build', ['cmake','--build',build,'--parallel','8'])
        runtime = out/'runtime' if a.isolated_run else APP/'app/runtime'
        runtime.mkdir(exist_ok=True)
        shutil.copy2(build/'ConsoleV2.exe',runtime/'ConsoleV2.exe')
        run('deploy_runtime', [qt/'bin/windeployqt.exe','--no-translations','--no-opengl-sw','--qmldir',APP/'app/native',
            '--dir',runtime,runtime/'ConsoleV2.exe'])
        if a.command != 'build':
            if not a.joint_url and a.command == 'run':
                sys.path.insert(0,str(ROOT/'pc_apps/console'))
                import joint_capture
                joint_server,joint_recorder=joint_capture.start_server(
                    joint_capture.DEFAULT_OUTPUT_ROOT,ROOT/'pc_apps/console/joint_capture.html',
                    fetch_dir=ROOT/'pc_apps/human_replay')
                a.joint_url='http://127.0.0.1:%d/' % joint_server.server_port
            if a.isolated_run:
                # Build cache is never executed: a running .NET/Qt process cannot lock the next build.
                shutil.copytree(service,out/'service')
                service = out/'service'
            args = [sdk,service/'AppService.dll','--session',a.session.resolve(),
                '--host',runtime/'ConsoleV2.exe','--report',out/'run.json','--frame',a.frame]
            if a.command == 'run': args += ['--auto-level']
            for path in a.analysis: args += ['--analysis',path.resolve()]
            if a.joint_url: args += ['--joint-url',a.joint_url]
            args += ['--python',sys.executable]
            if a.annotator_url: args += ['--annotator-url',a.annotator_url]
            if a.live_url: args += ['--live-url',a.live_url]
            if a.qml_file: args += ['--qml-file',a.qml_file.resolve()]
            if a.gt_root: args += ['--gt-root',a.gt_root.resolve()]
            if a.annotation_report: args += ['--annotation-report',a.annotation_report.resolve()]
            if a.tour_report: args += ['--tour-report',a.tour_report.resolve()]
            if a.smoke_reload: args += ['--smoke-reload']
            if a.command == 'check':
                run('all_frame_decode',args+['--check'])
                args[args.index('--report')+1]=out/'native.json'
                args += ['--smoke','--screenshot',out/'window.png']
            run('native',args)
        return 0
    except (OSError,subprocess.CalledProcessError) as error:
        print(str(error),file=sys.stderr)
        return 2
    finally:
        if joint_recorder is not None: joint_recorder.close()
        if joint_server is not None:
            joint_server.shutdown();joint_server.server_close()
        print('Application logs: '+str(out),flush=True)


if __name__ == '__main__':
    raise SystemExit(main())
