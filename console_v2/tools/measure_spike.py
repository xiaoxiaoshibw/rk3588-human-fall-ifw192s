"""Fixed-input R2 measurements, fresh processes, clean PATH, no board calls."""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid
import psutil
from run_spike_command import ROOT, OUT, environment


def measure(label, *, count=500000, duration=10, updates='dynamic', scale=1, screenshot=False,
            single=False, session='cap_20261018_110029', extract=None):
    directory = OUT / label
    directory.mkdir(exist_ok=False)
    report = directory / 'result.json'
    marker = Path(str(report) + '.first.json')
    env = environment()
    qt = ROOT / 'console_v2/spike/package-dev'
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32') if single else str(qt) + os.pathsep + str(Path(os.environ['SystemRoot']) / 'System32')
    env['QT_SCALE_FACTOR'] = str(scale)
    env['QSG_INFO'] = '1'
    env.pop('QML_IMPORT_PATH', None)
    env.pop('QT_PLUGIN_PATH', None)
    if single:
        exe = ROOT / 'console_v2/spike/package-single/SpikeService.exe'
        argv = [str(exe)]
        env.pop('DOTNET_ROOT', None)
        if extract is None:
            extract = ROOT / 'console_v2/.tools/extracted/shared'
        argv += ['--extract-root', str(extract)]
        env['DOTNET_BUNDLE_EXTRACT_BASE_DIR'] = str(ROOT / 'console_v2/.tools/extracted/dotnet-native')
    else:
        argv = [str(ROOT / 'console_v2/.tools/dotnet/dotnet.exe'),
                str(ROOT / 'console_v2/spike/service/bin/Release/net8.0-windows/win-x64/SpikeService.dll'),
                '--host', str(qt / 'QtSpike.exe')]
    argv += ['--session', str(ROOT / 'data/sessions' / session), '--report', str(report), '--count', str(count),
             '--duration', str(duration), '--updates', updates]
    if screenshot:
        argv += ['--screenshot', str(directory / 'window.png')]
    first_ms = None
    peak = 0
    modules = set()
    memory_samples = []
    start = time.perf_counter()
    with (directory / 'stdout.log').open('xb') as stdout, (directory / 'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(argv, cwd=directory, env=env, stdout=stdout, stderr=stderr,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        process = psutil.Process(child.pid)
        captured_modules = False
        while child.poll() is None:
            elapsed = time.perf_counter() - start
            if elapsed > 100:
                for descendant in process.children(recursive=True): descendant.kill()
                child.kill(); child.wait()
                raise TimeoutError(label)
            if first_ms is None and marker.is_file(): first_ms = elapsed * 1000
            rss = 0
            try:
                processes = [process] + process.children(recursive=True)
                for item in processes:
                    try:
                        rss += item.memory_info().rss
                        if first_ms is not None and not captured_modules:
                            modules.update(m.path for m in item.memory_maps() if m.path.lower().endswith('.dll'))
                    except (psutil.NoSuchProcess, psutil.AccessDenied): pass
                if first_ms is not None: captured_modules = True
            except psutil.NoSuchProcess: pass
            peak = max(peak, rss)
            memory_samples.append([round(elapsed, 6), rss])
            time.sleep(.01)
        code = child.returncode
    result = json.loads(report.read_text(encoding='utf-8')) if report.is_file() else None
    data = dict(label=label, argv=argv, exit_code=code, first_frame_observed_upper_bound_ms=first_ms,
                peak_sum_working_set_bytes=peak, memory_sample_interval_s=.01, memory_samples=memory_samples,
                module_paths=sorted(modules), wall_s=time.perf_counter()-start, result=result,
                environment=dict(scale=scale, path=env['PATH'], single_file=single, qt_sdk_on_path=False,
                                 dotnet_root=env.get('DOTNET_ROOT'), extraction_root=str(extract) if extract else None),
                conditions='Fresh process; OS file and driver shader caches not flushed. No screenshots in formal timing unless explicit QA run.')
    (directory / 'MEASUREMENT.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    assert code == 0 and result and any(m.get('event')=='complete' for m in result['messages']), data
    complete = next(m for m in result['messages'] if m.get('event')=='complete')
    print(json.dumps(dict(label=label, first_ms=first_ms, sampled_sum_working_set_bytes=peak, fps=complete['frame_swapped_fps'],
                         heartbeat_excess_p99_ms=complete['ui_heartbeat_excess_ms'].get('p99'),
                         gui_event_work_per_frame_p99_ms=complete['gui_event_work_per_frame_ms'].get('p99')), ensure_ascii=False), flush=True)
    return data


def main():
    mode = sys.argv[1]
    if mode == 'qa':
        measure('qa_native_60', duration=60, screenshot=True)
    elif mode == 'formal':
        records = []
        first_extract = ROOT / 'console_v2/.tools/extracted' / ('first_' + uuid.uuid4().hex)
        records.append(measure('single_first_extract', single=True, duration=1,
                               extract=first_extract))
        for i in range(10):
            records.append(measure('fresh_process_%02d' % i, single=True, duration=1, extract=first_extract))
        for count in [0, 50000, 500000]:
            for i in range(3):
                records.append(measure('dynamic_%d_%d' % (count, i), count=count, single=True))
        records.append(measure('static_500000', count=500000, updates='static', single=True))
        for scale in [1.0, 1.5, 2.0]:
            records.append(measure('dpi_' + str(scale), count=500000, scale=scale, screenshot=True, duration=4, single=True))
        (OUT/'ALL_MEASUREMENTS.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    else:
        raise ValueError(mode)


if __name__ == '__main__':
    main()
