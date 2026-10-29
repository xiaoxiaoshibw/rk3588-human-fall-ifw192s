"""PC-only protocol v2 synthetic selfcheck; v1 commands remain unchanged.

No output is AI_GT_FROZEN. Oracle/contract runs do not measure an annotator.
"""
import argparse
import json
import math
import platform
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
import ai_gt as v1

PROTOCOL = Path(__file__).with_name('protocol_v2.json')
BINS = ((4.0, 5.5), (5.5, 7.0), (7.0, 8.5))


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    with Path(path).open('x', encoding='utf-8') as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2, allow_nan=False)


def fresh_output(path):
    path = Path(path).resolve()
    root = Path(__file__).resolve().parents[2]
    protected = [root / 'data', root / 'captures']
    # resolve() also resolves Windows junctions, including captures/* -> data/*.
    if any(p.resolve() == path or p.resolve() in path.parents for p in protected):
        raise ValueError('data/captures output forbidden')
    path.mkdir(parents=True, exist_ok=False)
    return path


def projected_centroid(points, camera):
    """Equal weight per finite, in-frustum source row, before raster overlap."""
    pts = np.asarray(points, dtype=float)
    if pts.ndim != 2 or pts.shape[1] != 3:
        raise ValueError('expected Nx3 points')
    pts = pts[np.isfinite(pts).all(axis=1)]
    u, v, ok = v1.project(pts, camera)
    ok &= (u >= 0) & (u < camera['W']) & (v >= 0) & (v < camera['H'])
    if not ok.any():
        raise ValueError('no visible target rows')
    return [float(u[ok].mean()), float(v[ok].mean())]


def range_bin(distance):
    if not math.isfinite(distance):
        return None
    return next((i for i, (lo, hi) in enumerate(BINS) if lo <= distance < hi), None)


def render(points, camera, path):
    w, h = camera['W'], camera['H']
    image = Image.new('RGB', (w, h), (10, 12, 16))
    draw = ImageDraw.Draw(image)
    for x in range(0, w, 25):
        draw.line([(x, 0), (x, h)], fill=(32, 36, 44) if x % 100 == 0 else (20, 24, 30))
    for y in range(0, h, 25):
        draw.line([(0, y), (w, y)], fill=(32, 36, 44) if y % 100 == 0 else (20, 24, 30))
    for x in range(100, w, 100):
        draw.text((x + 2, 2), str(x), fill=(100, 105, 115))
    for y in range(100, h, 100):
        draw.text((2, y + 2), str(y), fill=(100, 105, 115))
    draw.line([(w // 2 - 8, h // 2), (w // 2 + 8, h // 2)], fill=(100, 105, 115))
    draw.line([(w // 2, h // 2 - 8), (w // 2, h // 2 + 8)], fill=(100, 105, 115))
    u, v, ok = v1.project(points, camera)
    for x, y in zip(u[ok], v[ok]):
        if 0 <= x < w and 0 <= y < h:
            draw.ellipse((x - 2, y - 2, x + 2, y + 2), fill=(232, 236, 240))
    image.save(path, 'PNG')


def build_suite(seed):
    rng = np.random.default_rng(seed)
    cam = v1.default_camera()
    cases = []
    # Eight cases/bin: six people (two adjacent), two empty. Names conceal strata.
    for lo, hi in BINS:
        for index in range(8):
            horizontal = float(rng.uniform(lo + 0.1, hi - 0.2))
            az = math.radians(float(rng.uniform(-20, 20)))
            cx, cy = horizontal * math.cos(az), horizontal * math.sin(az)
            points = [v1._floor(rng)]
            entry = {'has_person': index < 6}
            if index < 6:
                person = v1._cylinder(rng, cx, cy)
                points.append(person)
                center = person.mean(axis=0)
                rr = float(np.linalg.norm(center - np.asarray(cam['C'])))
                px = projected_centroid(person, cam)
                direction = v1.ray_dir(cam, *px)
                pu, pv, _ = v1.project(np.asarray([center]), cam)
                entry.update(truth_px=px, range_m=rr, dir=direction.tolist(),
                             centroid_xyz=center.tolist(),
                             project_mean_xyz_px=[float(pu[0]), float(pv[0])],
                             adjacent=index < 2)
                if range_bin(rr) != range_bin((lo + hi) / 2):
                    raise ValueError('generated target outside intended bin')
            if index < 2 or index >= 6:
                points.append(v1._box(rng, cx + 0.4, cy + 0.65))
            cases.append((np.vstack(points), entry))
    return [cases[int(i)] for i in rng.permutation(len(cases))]


def sources():
    return {p.name: v1.sha256_file(p) for p in (Path(__file__), Path(v1.__file__), PROTOCOL)}


def render_suite(out, seed):
    protocol = read(PROTOCOL)
    if seed != protocol['development_seed']:
        raise ValueError('only development seed authorized; holdout remains NOT_RUN')
    suite = build_suite(seed)
    out = fresh_output(out)
    (out / 'renders').mkdir()
    (out / 'truth').mkdir()
    cam = v1.default_camera()
    entries = []
    for i, (points, truth) in enumerate(suite):
        name = 'case_%03d' % i
        render(points, cam, out / 'renders' / (name + '.png'))
        entries.append(dict(truth, case=name))
    write(out / 'camera.json', cam)
    write(out / 'protocol.json', protocol)
    write(out / 'truth' / 'truth.json', {'camera': cam, 'cases': entries})
    write(out / 'RENDER_RUN.json', {'seed': seed, 'sources': sources(), 'python': platform.python_version(),
                                  'numpy': np.__version__, 'argv': sys.argv})
    hashes = {p.relative_to(out).as_posix(): v1.sha256_file(p)
              for p in sorted(out.rglob('*')) if p.is_file()}
    write(out / 'MANIFEST.json', {'schema': 'ai_gt_suite_v2', 'files': hashes})
    print(json.dumps({'cases': len(entries), 'out': str(out)}))


def verify_suite(suite):
    manifest = read(suite / 'MANIFEST.json')
    if manifest.get('schema') != 'ai_gt_suite_v2':
        raise ValueError('unsupported suite')
    expected = {'camera.json', 'protocol.json', 'RENDER_RUN.json', 'truth/truth.json'}
    expected |= {'renders/case_%03d.png' % i for i in range(24)}
    if set(manifest['files']) != expected:
        raise ValueError('incomplete suite manifest')
    for name, digest in manifest['files'].items():
        if v1.sha256_file(suite / name) != digest:
            raise ValueError('suite hash mismatch: ' + name)
    if read(suite / 'protocol.json') != read(PROTOCOL):
        raise ValueError('protocol changed')
    if read(suite / 'RENDER_RUN.json')['sources'] != sources():
        raise ValueError('source changed since render')
    return manifest


def validate_picks(doc, cases, camera):
    entries = doc.get('picks')
    if not isinstance(entries, list):
        raise ValueError('picks must be a list')
    result = {}
    for p in entries:
        key = p['case']
        if key in result or key not in cases:
            raise ValueError('duplicate or unknown case')
        if 'u' not in p or 'v' not in p:
            raise ValueError('explicit u/v required, null/null means absent')
        u, v = p['u'], p['v']
        if (u is None) != (v is None):
            raise ValueError('partial null')
        if u is not None:
            if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in (u, v)):
                raise ValueError('non-finite or non-numeric pick')
            if not (0 <= u < camera['W'] and 0 <= v < camera['H']):
                raise ValueError('pick outside image')
        result[key] = p
    if set(result) != set(cases):
        raise ValueError('incomplete case coverage')
    return result


def score_suite(suite, picks_path, out):
    suite = Path(suite)
    verify_suite(suite)
    truth = read(suite / 'truth' / 'truth.json')
    doc = read(picks_path)
    # Explicit suite hash prevents accidental use of picks from another seed/version.
    if doc.get('suite_manifest_sha256') != v1.sha256_file(suite / 'MANIFEST.json'):
        raise ValueError('picks suite binding mismatch')
    kinds = ('oracle', 'injected_contract', 'model_unverified')
    if doc.get('kind') not in kinds or not isinstance(doc.get('annotator'), dict) or not doc['annotator'].get('model_id'):
        raise ValueError('kind and annotator.model_id required')
    cases, cam = truth['cases'], truth['camera']
    picks = validate_picks(doc, {c['case'] for c in cases}, cam)
    rows = [v1._score_case(c, picks[c['case']], cam) for c in cases]
    tp = [r for r in rows if r['status'] == 'TP']
    counts = {k.lower(): sum(r['status'] == k for r in rows) for k in ('TP', 'FN', 'FP', 'TN')}
    bins = []
    for i, bounds in enumerate(BINS):
        selected = [r for r in tp if range_bin(r['range_m']) == i]
        bins.append({'bin_m': list(bounds), 'n_tp': len(selected),
                     'n_person': sum(c['has_person'] and range_bin(c['range_m']) == i for c in cases),
                     'px': v1._stats([r['px'] for r in selected]),
                     'lateral_m': v1._stats([r['lateral_m'] for r in selected])})
    report = {'schema': 'ai_gt_selfcheck_v2', 'kind': doc['kind'], 'n_cases': len(rows),
              **counts, 'by_range': bins, 'per_case': rows,
              'px_err': v1._stats([r['px'] for r in tp]),
              'lateral_m': v1._stats([r['lateral_m'] for r in tp]),
              'annotator': doc['annotator'], 'eligible_for_gt': False,
              'model_blind_validation': 'NOT_RUN', 'holdout_validation': 'NOT_RUN',
              'usage': 'Observed synthetic TP errors only; no CI, safety bound or real-session guarantee. '
                       'FN/FP separate. No extrapolation across bins/models/camera/prompt/protocol. '
                       '2D centroid is not a source row or a 3D coordinate truth.',
              'bindings': {'suite_manifest_sha256': v1.sha256_file(suite / 'MANIFEST.json'),
                           'picks_sha256': v1.sha256_file(Path(picks_path)), 'sources': sources()},
              'python': platform.python_version(), 'argv': sys.argv}
    out = fresh_output(out)
    write(out / 'SELFCHECK.json', report)
    write(out / 'ENVELOPE.json', {k: value for k, value in report.items() if k != 'per_case'})
    print(json.dumps(dict(counts, out=str(out))))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='mode', required=True)
    r = sub.add_parser('render')
    r.add_argument('--out', required=True)
    r.add_argument('--seed', type=int, default=20261019)
    s = sub.add_parser('score')
    s.add_argument('--suite', required=True)
    s.add_argument('--picks', required=True)
    s.add_argument('--out', required=True)
    args = parser.parse_args(argv)
    try:
        if args.mode == 'render':
            render_suite(args.out, args.seed)
        else:
            score_suite(args.suite, args.picks, args.out)
    except (ValueError, KeyError, OSError, TypeError) as exc:
        parser.exit(2, str(exc) + '\n')


if __name__ == '__main__':
    main()
