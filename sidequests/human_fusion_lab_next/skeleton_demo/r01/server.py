"""本机真实点云几何骨架预览；不修改检测器、不生成人工标签。"""
import argparse
import hashlib
import importlib.util
import json
from functools import lru_cache
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
EVIDENCE = ROOT / 'docs/human_capture/evidence/2026-10-12_hr_skeleton_demo_01_r1'
OLD = ROOT / 'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1'
PROVIDER = ROOT / 'sidequests/human_fusion_lab_next/d05/r06/demo_v2/demo_server.py'
BASELINE = json.loads((EVIDENCE / 'BASELINE_BEFORE.json').read_text(encoding='utf-8'))
BASE_SHA = {r['path']: r['sha256'] for r in BASELINE['files']}


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def load_existing(name, path):
    if digest(path) != BASE_SHA[path.relative_to(ROOT).as_posix()]:
        raise ValueError('EXISTING_SOURCE_CHANGED: ' + str(path))
    spec = importlib.util.spec_from_file_location(name, str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


provider = load_existing('skeleton_demo_evidence_provider', PROVIDER)
geometry = load_existing('skeleton_demo_existing_geometry', OLD / 'skeleton.py')
PARAMS = json.loads((OLD / 'prototype_params_v1.json').read_text(encoding='utf-8'))
if digest(OLD / 'prototype_params_v1.json') != BASE_SHA[(OLD / 'prototype_params_v1.json').relative_to(ROOT).as_posix()]:
    raise ValueError('PARAMS_CHANGED')
SLOTS = ['TOP_REGION', 'UPPER_TORSO', 'CHEST', 'PELVIS_REGION', 'LOWER_REGION', 'LOWER_A', 'LOWER_B']
LABELS = ['顶部候选（头/手待确认）', '上身中心', '胸部区域', '骨盆区域', '下部中心', '下部 A', '下部 B']
BANDS = [(0.88, 1.01), (0.70, 0.88), (0.52, 0.70), (0.33, 0.52), (-0.03, 0.33)]
EDGES = [('TOP_REGION', 'UPPER_TORSO'), ('UPPER_TORSO', 'CHEST'), ('CHEST', 'PELVIS_REGION'), ('PELVIS_REGION', 'LOWER_REGION'), ('PELVIS_REGION', 'LOWER_A'), ('PELVIS_REGION', 'LOWER_B')]
SESSIONS = {s['sid']: s for s in provider.load(provider.reportpath('control'))['sessions']}


def estimate(points, rows, offset=0):
    """只调用通用点集数学能力，不构造review，不调用旧process资格入口。"""
    xyz = np.asarray(points, dtype=np.float64).reshape(-1, 3)
    norm = geometry.normalize({'receipt': {'rows': rows}, 'global_rows': [offset + r for r in rows],
                               'xyz': xyz.tolist(), 'invalid_source_rows': []}, PARAMS)
    out = {k: geometry.unknown('LOW_SUPPORT') for k in SLOTS}
    good = np.asarray(norm['xyz'], dtype=np.float64).reshape(-1, 3)
    if len(good) < 30:
        return out, 'INSUFFICIENT_POINTS'
    span = np.ptp(good, axis=0)
    if span[2] < 0.85 or span[2] > 2.5 or max(span[:2]) > 1.5:
        return {k: geometry.unknown('UPRIGHT_EXTENT_CONFLICT') for k in SLOTS}, 'UPRIGHT_EXTENT_CONFLICT'
    low, high = np.quantile(good[:, 2], [0.02, 0.98])
    if high - low < 0.65:
        return out, 'VERTICAL_STRUCTURE_UNKNOWN'
    z = (good[:, 2] - low) / (high - low)
    # ponytail: relative upright regions only; anatomical arms/joints require separate evidence.
    for name, (lo, hi) in zip(SLOTS[:5], BANDS):
        ids = np.flatnonzero((z >= lo) & (z < hi)).tolist()
        out[name] = geometry.observe(norm, ids, PARAMS)
    ix = [i for i, r in enumerate(norm['rows']) if r in set(out['LOWER_REGION']['support_rows'])]
    if len(ix) >= 12 and out['LOWER_REGION']['valid']:
        xy = good[ix, :2]
        centered = xy - xy.mean(axis=0)
        values, vectors = np.linalg.eigh(centered.T.dot(centered) / len(xy))
        if values[-1] > 1e-12 and values[-1] > PARAMS['axis_eigen_ratio_min'] * max(values[0], 1e-12):
            axis = vectors[:, -1]
            if axis[np.argmax(np.abs(axis))] < 0:
                axis = -axis
            projection = xy.dot(axis)
            order = np.argsort(projection, kind='stable')
            gap = np.diff(projection[order])
            split = int(np.argmax(gap)) + 1
            if gap[split - 1] >= PARAMS['lower_gap_m']:
                pair = [geometry.observe(norm, [ix[int(i)] for i in group], PARAMS) for group in (order[:split], order[split:])]
                if all(n['valid'] for n in pair) and np.linalg.norm(np.array(pair[0]['xyz'])[:2] - np.array(pair[1]['xyz'])[:2]) >= PARAMS['lower_min_separation_m']:
                    out['LOWER_A'], out['LOWER_B'] = pair
    for name, node in out.items():
        node['semantic_status'] = 'UNREVIEWED_GEOMETRY'
        if name == 'TOP_REGION' and node['valid']:
            node['reason'] = 'HEAD_OR_HAND_NOT_VERIFIED'
    return out, 'GEOMETRY_PREVIEW_ONLY'


def validate_request(sid, fi):
    if sid not in SESSIONS:
        raise ValueError('UNKNOWN_SESSION')
    if not 0 <= fi < SESSIONS[sid]['frames']:
        raise ValueError('FRAME_OUT_OF_RANGE')


@lru_cache(maxsize=4)
def frame_geometry(sid, fi, stamp):
    verification = provider.verification(sid)
    rec = provider.row(provider.ledgerpath('control', sid), fi)
    meta = provider.load(ROOT / 'captures/remote' / sid / 'meta.json')['frames'][fi]
    if rec['timestamp_s'] != meta['bag_time_sec'] or rec['sid'] != sid:
        raise ValueError('FRAME_BINDING_MISMATCH')
    with (ROOT / 'captures/remote' / sid / 'points.bin').open('rb') as stream:
        stream.seek(meta['offset_points'] * 28)
        raw = stream.read(meta['count_points'] * 28)
    if len(raw) != meta['count_points'] * 28:
        raise ValueError('TRUNCATED_FRAME')
    source = np.ndarray((meta['count_points'], 3), dtype='<f4', buffer=raw, strides=(28, 4)).astype(np.float64)
    valid = np.isfinite(source).all(axis=1) & np.any(source != 0, axis=1)
    ref = provider.load(provider.reportpath('control'))['reference']['coordinate']
    xyz = (source.dot(np.asarray(ref['R']).reshape(3, 3).T) + np.asarray(ref['T'])).astype(np.float32)
    environment_rows = np.flatnonzero(valid).tolist()
    step = max(1, (len(environment_rows) + 7999) // 8000)
    environment_rows = environment_rows[::step]
    candidates = []
    for c in rec['candidates']:
        rows = c['raw_indices']
        if len(rows) != len(set(rows)) or any(not isinstance(r, int) or r < 0 or r >= len(source) for r in rows):
            raise ValueError('INVALID_CANDIDATE_MEMBERS')
        good_rows = [r for r in rows if valid[r]]
        cloud = xyz[good_rows]
        nodes, reason = estimate(cloud, good_rows, meta['offset_points'])
        extent = {'min': cloud.min(axis=0).tolist(), 'max': cloud.max(axis=0).tolist()} if len(cloud) else None
        candidates.append({'id': c['id'], 'track_id': c['track_id'], 'prob': c['prob'], 'decision': c['decision'],
                           'observed': c['id'] in rec['visible_candidates'], 'pointset_sha256': c['pointset_sha256'],
                           'member_rows': good_rows, 'excluded_invalid_n': len(rows) - len(good_rows),
                           'points': cloud.tolist(), 'bbox': extent, 'nodes': nodes, 'reason': reason,
                           'identity_status': 'MODEL_CANDIDATE_NOT_HUMAN_GROUND_TRUTH'})
    # 候选选择与估计都不读GT；示例帧是人工导航，不参与算法。
    ranked = sorted(candidates, key=lambda c: (c['observed'], sum(n['valid'] for n in c['nodes'].values()), c['prob']), reverse=True)
    return {'sid': sid, 'frame': fi, 'frames': SESSIONS[sid]['frames'], 'timestamp_s': rec['timestamp_s'],
            'candidates': candidates, 'default_candidate': ranked[0]['id'] if ranked else None,
            'environment': xyz[environment_rows].tolist(), 'environment_display_step': step,
            'edges': EDGES, 'labels': dict(zip(SLOTS, LABELS)), 'geometry_status': 'UNREVIEWED_UPRIGHT_REGIONS',
            'qualification': verification['qualification'], 'raw_frame_sha256': hashlib.sha256(raw).hexdigest(),
            'source_ledger_sha256': verification['records']['control']['ledger_sha256'],
            'coordinate': ref, 'verification': verification['status'], 'ground_truth_used_by_estimator': False}


def get_frame(sid, fi):
    validate_request(sid, fi)
    # 先核验再命中缓存，源文件变化不能继续展示旧结果。
    verification = provider.verification(sid)
    return frame_geometry(sid, fi, json.dumps(verification, sort_keys=True))


class Handler(provider.Handler):
    def do_GET(self):
        u = urlsplit(self.path)
        q = parse_qs(u.query)
        try:
            if u.path in ('/', '/app.js'):
                p = HERE / ('index.html' if u.path == '/' else 'app.js')
                return self.send(p.read_bytes(), 'text/html; charset=utf-8' if u.path == '/' else 'application/javascript; charset=utf-8')
            if u.path == '/OrbitControls.js':
                return self.send((ROOT / 'pc_apps/human_replay/vendor/OrbitControls.js').read_bytes(), 'application/javascript')
            if u.path == '/api/sessions':
                return self.send(json.dumps({'sessions': [{'sid': s['sid'], 'activity': s['activity'], 'frames': s['frames']} for s in SESSIONS.values()]}).encode())
            if u.path == '/api/skeleton':
                packet = get_frame(q.get('sid', [''])[0], int(q.get('f', ['-1'])[0]))
                body = json.dumps(packet, ensure_ascii=False, allow_nan=False, separators=(',', ':')).encode('utf-8')
                return self.send(body, extra={'X-Content-SHA256': hashlib.sha256(body).hexdigest()})
            if u.path == '/favicon.ico':
                return self.send(b'', 'image/x-icon', status=204)
            if u.path == '/three.min.js':
                return super().do_GET()
            raise ValueError('UNKNOWN_ENDPOINT')
        except (ValueError, AssertionError, OSError, KeyError) as exc:
            return self.send(json.dumps({'error': str(exc)}).encode(), status=400)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8925)
    args = parser.parse_args()
    print('真实点云粗骨架 http://127.0.0.1:%d/ 仅本机只读' % args.port, flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
