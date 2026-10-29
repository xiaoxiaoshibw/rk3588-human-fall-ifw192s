"""Run a session-bound local ground fit or full replay in a fresh output folder."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'pc_apps/range_fall/exp_2d3d'))
from ablate import grid_and_binding
from core.range_contract import load_ground


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--session', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--kind', choices=('ground', 'analysis', 'offline-preview'), required=True)
    parser.add_argument('--ground', type=Path)
    parser.add_argument('--empty-prefix-frames', type=int)
    a = parser.parse_args()
    session, out = a.session.resolve(), a.out.resolve()
    if out.exists() or out == ROOT/'data' or (ROOT/'data').resolve() in out.parents or (ROOT/'captures').resolve() in out.parents:
        raise ValueError('output must be a new directory outside data and captures')
    out.mkdir(parents=True)
    if a.kind == 'ground':
        target = out/'fit'
        command = [sys.executable, '-B', '-W', 'error', str(ROOT/'pc_apps/range_fall/exp_2d3d/ablate.py'),
                   'fit-ground', '--session', str(session), '--out', str(target)]
    elif a.kind == 'offline-preview':
        target = out/'preview'
        command = [sys.executable, '-B', '-W', 'error', str(ROOT/'pc_apps/range_fall/session_compare.py'),
                   '--session', str(session), '--out', str(target), '--no-preview']
    else:
        if not a.empty_prefix_frames or a.empty_prefix_frames < 1:
            raise ValueError('explicit empty-scene prefix required')
        target = out/'run'
        command = [sys.executable, '-B', '-W', 'error', str(ROOT/'pc_apps/range_fall/runtime_replay.py'),
                   '--session', str(session), '--out', str(target), '--empty-prefix-frames', str(a.empty_prefix_frames),
                   '--no-detail', '--alert-variant', 'ground_alert_v1', '--body-candidates']
        if a.ground:
            _, _, binding = grid_and_binding(session)
            load_ground(a.ground, binding)
            command.extend(['--ground', str(a.ground.resolve())])
    with (out/'worker.log').open('w', encoding='utf8') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, cwd=ROOT)
    if result.returncode:
        detail = (out/'worker.log').read_text(encoding='utf8', errors='replace').strip().splitlines()
        raise RuntimeError((detail[-1] if detail else 'local task failed')+'；日志：'+str(out/'worker.log'))
    result = {'kind': a.kind, 'sessionId': session.name}
    if a.kind == 'ground':
        path = target/'BOUND_GROUND.json'
        _, _, binding = grid_and_binding(session)
        ground = load_ground(path, binding)
        result.update(path=str(path), ground={'available': True, 'sessionId': session.name,
            'normal': ground['normal'], 'offsetM': ground['offset_m'], 'frame': ground['frame'],
            'version': hashlib.sha256(path.read_bytes()).hexdigest(),
            'reason': 'offline_geometry_only_physical_unknown'},
            metaSha256=binding['meta_sha256'], pointsSha256=binding['points_sha256'])
    elif a.kind == 'offline-preview':
        summary = json.loads((target/'SUMMARY.json').read_text(encoding='utf8'))
        _, _, binding = grid_and_binding(session)
        if summary.get('session') != session.name or summary.get('source_binding') != binding or not summary.get('honesty', {}).get('non_causal_background'):
            raise ValueError('offline preview source or non-causal declaration mismatch')
        path = target/'index.html'
        if not path.is_file():
            raise RuntimeError('offline preview output unavailable')
        result.update(path=str(path), metaSha256=binding['meta_sha256'], pointsSha256=binding['points_sha256'])
    else:
        path = target/'analysis.json'
        if not path.is_file():
            raise RuntimeError('analysis output unavailable; see '+str(out/'worker.log'))
        result.update(path=str(path))
    (out/'RESULT.json').write_text(json.dumps(result, ensure_ascii=False, allow_nan=False), encoding='utf8')
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(str(error), file=sys.stderr)
        sys.exit(2)
