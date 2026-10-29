"""Recompute R2 statistics and read-only continuity checks; never rewrite raw runs."""
import ast
import hashlib
import json
import math
from pathlib import Path
import subprocess
import sys
from run_spike_command import ROOT, OUT

PREFIX = sys.argv[2] if len(sys.argv) > 2 else ''

def sha(path):
    value = hashlib.sha256()
    with path.open('rb') as source:
        for block in iter(lambda: source.read(1 << 20), b''):
            value.update(block)
    return value.hexdigest()


def save(name, value):
    with (OUT / (PREFIX + name)).open('x', encoding='utf-8') as target:
        json.dump(value, target, ensure_ascii=False, indent=2)


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)]


def main():
    measurements = (Path(sys.argv[1]) if len(sys.argv) > 1 else OUT / 'ALL_MEASUREMENTS.json').resolve()
    runs = json.loads(measurements.read_text('utf-8'))
    rows = []
    for run in runs:
        assert run['exit_code'] == run['result']['child_exit_code'] == 0
        complete = next(m for m in run['result']['messages'] if m['event'] == 'complete')
        assert complete['self_checks'] == {'gui_active_event_accounting': True, 'layout_before_mapping': True}
        for key in ['interval_ms', 'qt_copy_submit_ms', 'gui_event_work_per_frame_ms', 'ui_heartbeat_excess_ms']:
            raw, dist = complete[key + '_raw'], complete[key]
            assert len(raw) == dist['n']
            if raw:
                for name, q in [('p50', .5), ('p95', .95), ('p99', .99)]:
                    assert percentile(raw, q) == dist[name], (run['label'], key, name)
                assert max(raw) == dist['max']
        assert all(m['dpr'] == complete['dpr'] for m in run['result']['messages'] if m['event'] == 'first_frame' and 'dpr' in m)
        assert complete['qt_version'] == '6.5.3'
        assert run['environment']['single_file'] and not run['environment']['dotnet_root']
        rows.append(dict(label=run['label'], first_frame_upper_ms=run['first_frame_observed_upper_bound_ms'],
                         fps=complete['frame_swapped_fps'], points=complete['points'],
                         gui_work_p99_ms=complete['gui_event_work_per_frame_ms']['p99'],
                         gui_work_max_ms=complete['gui_event_work_per_frame_ms']['max'],
                         interval_p99_ms=complete['interval_ms']['p99'],
                         copy_p99_ms=complete['qt_copy_submit_ms'].get('p99'), dpr=complete['dpr'],
                         width=complete['width'], height=complete['height'],
                         sampled_sum_working_set_bytes=run['peak_sum_working_set_bytes']))
    fresh = [r['first_frame_upper_ms'] for r in rows if r['label'].startswith(('cold_', 'fresh_process_'))]
    assert len(fresh) == 10
    budget = {}
    for count, threshold in [(50000, 60), (500000, 30)]:
        cases = [r for r in rows if r['label'].startswith('dynamic_%s_' % count)]
        assert len(cases) == 3
        budget[str(count)] = dict(fps_min=min(r['fps'] for r in cases),
                                 gui_work_p99_max_ms=max(r['gui_work_p99_ms'] for r in cases),
                                 pass_fps=all(r['fps'] >= threshold for r in cases),
                                 pass_gui_p99=all(r['gui_work_p99_ms'] <= 16 for r in cases))
    save('PERFORMANCE_SUMMARY.json', dict(rows=rows, fresh_process_p95_ms=percentile(fresh, .95),
         fresh_process_pass=percentile(fresh, .95) <= 2500, true_cold_status='NOT_RUN',
         startup_over_2500ms=[dict(label=r['label'], upper_ms=r['first_frame_upper_ms']) for r in rows
                              if r['first_frame_upper_ms'] > 2500],
         startup_all_cases_p95_ms=percentile([r['first_frame_upper_ms'] for r in rows], .95),
         startup_all_cases_max_ms=max(r['first_frame_upper_ms'] for r in rows),
         source=str(measurements.relative_to(ROOT)), budget=budget, percentile='nearest rank',
         startup_scope='Fresh process only; OS file / GPU shader caches retained; external marker observation upper bound',
         memory_scope='10ms requested sampling; actual gaps recorded; concurrent sum working sets, shared pages counted per process; excludes VRAM'))

    before = json.loads((OUT / 'DATA_SHA_BEFORE.json').read_text('utf-8'))
    after = {str(p.relative_to(ROOT)): dict(bytes=p.stat().st_size, sha256=sha(p))
             for d in sorted((ROOT / 'data/sessions').iterdir()) if d.is_dir()
             for p in sorted(d.iterdir()) if p.is_file()}
    save('DATA_SHA_AFTER.json', after)
    source = json.loads((OUT / 'SOURCE_SHA.json').read_text('utf-8'))
    changed_source = [n for n, s in source.items() if sha(ROOT / n) != s]
    baseline = json.loads((OUT / 'WORKTREE_SHA.json').read_text('utf-8'))
    historical = {n: v for n, v in baseline.items() if n.startswith(('docs/evidence/2026-10-24_console_v2_r0/',
                                                                   'docs/evidence/2026-10-24_console_v2_r1/'))}
    changed_historical = [n for n, v in historical.items() if not (ROOT / n).is_file() or
                          (ROOT / n).stat().st_size != v['bytes'] or sha(ROOT / n) != v['sha256']]
    query = 'Get-Item captures/remote,captures/leveled,captures/registration | Select-Object FullName,LinkType,Target | ConvertTo-Json'
    links = json.loads(subprocess.check_output(['powershell', '-NoProfile', '-Command', query], cwd=ROOT).decode('utf-8-sig'))
    old_links = json.loads((OUT / 'JUNCTIONS.json').read_text('utf-8-sig'))
    save('JUNCTIONS_AFTER.json', links)
    assert before == after and not changed_source and not changed_historical and links == old_links
    native = json.loads((OUT / 'NATIVE_MODULES.json').read_text('utf-8'))
    save('CONTINUITY.json', dict(status='PASS', session_files=len(after), source_files=len(source),
         historical_evidence_files=len(historical), data_equal=before == after, source_changed=changed_source,
         historical_changed=changed_historical, junctions_equal=links == old_links,
         branch=subprocess.check_output(['git', 'branch', '--show-current'], cwd=ROOT).decode().strip(),
         head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
         module_probe_exit=native['exit_code']))
    paths = [p for p in (ROOT / 'console_v2').rglob('*') if p.is_file() and not any(
        x.startswith(('.tools', 'package', 'build')) or x in ('bin', 'obj', '__pycache__') for x in p.relative_to(ROOT / 'console_v2').parts)
        and p.suffix in ('.py', '.cs', '.h', '.cpp', '.qml', '.txt', '.csproj', '.md', '.Config')]
    for path in paths:
        if path.suffix == '.py': ast.parse(path.read_text('utf-8'), filename=str(path))
    paths += [ROOT / 'console_v2/spike/package-single/SpikeService.exe']
    save('FINAL_SOURCE_SHA.json', {str(p.relative_to(ROOT)): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in paths})
    print('R2: raw percentiles exact; 54 session files / old source / R0-R1 evidence / junctions unchanged', flush=True)


if __name__ == '__main__':
    main()
