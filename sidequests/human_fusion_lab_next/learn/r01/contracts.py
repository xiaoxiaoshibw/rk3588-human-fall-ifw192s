"""Source and annotation contracts for the versioned E0 surface; no training."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
PLAN = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_learn_stage_plan_r1'
OLD = ROOT/'sidequests/human_fusion_lab_next/pointset/r01'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def write(p, value):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)


def universe(raw):
    raw = np.asarray(raw)
    if raw.ndim != 2 or raw.shape[1] != 3:
        raise ValueError('N by 3 required')
    r = np.linalg.norm(raw.astype('f8'), axis=1)
    return np.isfinite(raw).all(1) & np.any(raw != 0, axis=1) & (r > .2) & (r < 15)


def angles(raw):
    return np.column_stack((np.arctan2(raw[:, 1], raw[:, 0]),
                            np.arctan2(raw[:, 2], np.hypot(raw[:, 0], raw[:, 1]))))


def project(raw, template, h, w, mode):
    """Two independent depth orderings; sparse CSR retains ALL U, including overflow."""
    if (h, w) not in [(128, 512), (256, 1024)]:
        raise ValueError('Unregistered resolution')
    if mode not in ['range', 'axial']:
        raise ValueError('Unknown depth')
    rows = np.flatnonzero(universe(raw)); q = raw[rows].astype('f8')
    a = angles(q); bounds = np.asarray(template['bounds_radians'], dtype=float)
    if bounds.shape != (2, 2) or not np.isfinite(bounds).all() or np.any(bounds[:, 1] <= bounds[:, 0]):
        raise ValueError('Invalid scan template')
    uv = (a-bounds[:, 0])/(bounds[:, 1]-bounds[:, 0])
    good = ((uv >= 0) & (uv < 1)).all(1)
    if mode == 'axial':
        good &= q[:, 0] > 0
    ids = rows[good]
    pixel = np.floor(uv[good, 1]*h).astype('i4')*w + np.floor(uv[good, 0]*w).astype('i4')
    depth = np.linalg.norm(raw[ids].astype('f8'), axis=1) if mode == 'range' else raw[ids, 0].astype('f8')
    order = np.lexsort((ids, depth, pixel)); members = ids[order]; values = depth[order]
    pixels, starts, counts = np.unique(pixel[order], return_index=True, return_counts=True)
    offsets = np.r_[starts, len(members)].astype('u4')
    layers = np.full((len(pixels), 2), -1, dtype='i4')
    if len(pixels):
        layers[:, 0] = members[starts]
        multi = counts > 1; layers[multi, 1] = members[starts[multi]+1]
    span = np.maximum.reduceat(values, starts)-np.minimum.reduceat(values, starts) if len(starts) else np.empty(0)
    outside = rows[~good]
    if not np.array_equal(np.sort(np.r_[members, outside]), rows):
        raise ValueError('CSR conservation failed')
    return dict(pixels=pixels.astype('u4'), offsets=offsets, members=members.astype('u4'),
                layers=layers, outside=outside.astype('u4'), depth=values.astype('f4'), span=span.astype('f4'))


def projection_stats(pr, raw_count, h, w):
    n = len(pr['members'])+len(pr['outside']); counts = np.diff(pr['offsets'])
    return dict(raw_count=raw_count, U=n, in_view=len(pr['members']), outside=len(pr['outside']),
                outside_fraction=len(pr['outside'])/n if n else None,
                occupied=len(pr['pixels']), empty_fraction=1-len(pr['pixels'])/(h*w),
                collisions=int(np.sum(np.maximum(counts.astype('i8')-1, 0))),
                overflow_K2=int(np.sum(np.maximum(counts.astype('i8')-2, 0))),
                multi_depth_pixels=int(np.count_nonzero(pr['span'] > .17)),
                max_span_m=float(pr['span'].max()) if len(pr['span']) else None)


def resolve_queries(semantic, human_scores, masks):
    """Queries partition semantic H; a tie never reverses semantic membership."""
    sem = np.asarray(semantic); scores = np.asarray(human_scores); masks = np.asarray(masks)
    if scores.shape != (4,) or masks.shape != (len(sem), 4) or not np.isfinite(scores).all() or not np.isfinite(masks).all():
        raise ValueError('Four finite query scores and N by 4 masks required')
    if np.any((masks < 0) | (masks > 1)) or np.any((scores < 0) | (scores > 1)):
        raise ValueError('Probability out of range')
    effective = np.where(scores[None] >= .5, masks, -1)
    order = np.argsort(effective, axis=1); best = effective[np.arange(len(sem)), order[:, -1]]
    second = effective[np.arange(len(sem)), order[:, -2]]
    out = np.full(len(sem), -1, dtype='i4')
    good = (sem == 1) & (best >= .5) & (best-second >= .1)
    out[good] = order[good, -1]
    return out


class Revisions:
    """Append-only reviewer-specific snapshots. Undo writes a new revision."""
    def __init__(self, directory):
        self.directory = Path(directory)

    def records(self, sid, fi):
        records = [read(p) for p in sorted(self.directory.glob('*.json'))]
        return [r for r in records if r['sid'] == sid and r['fi'] == fi]

    def append(self, record, binding, valid_rows):
        r = copy.deepcopy(record)
        if r.get('schema') != 'hfus-label/1' or r.get('source_sha256') != binding:
            raise ValueError('Label source/schema drift')
        if r.get('provenance') != 'HUMAN_REVIEW' or not str(r.get('reviewer', '')).strip() or not str(r.get('reason', '')).strip():
            raise ValueError('Named human reviewer and revision reason required')
        if r.get('layer') not in ['PRIMARY', 'SECONDARY'] or not r.get('visibility') in ['VISIBLE', 'PARTIAL', 'UNKNOWN']:
            raise ValueError('Review layer/visibility required')
        for key in ['full_view_reviewed', 'visible_human_coverage', 'instance_exhaustive_verified']:
            if type(r.get(key)) is not bool:
                raise ValueError('Explicit coverage flags required')
        labels = r.get('labels')
        if not isinstance(labels, list):
            raise ValueError('Labels required')
        seen = set(); valid_rows = set(map(int, valid_rows))
        for label in labels:
            i = label.get('row'); cls = label.get('semantic'); inst = label.get('instance')
            if type(i) is not int or i not in valid_rows or i in seen or cls not in ['TRUSTED_HUMAN', 'VERIFIED_NONHUMAN', 'UNKNOWN']:
                raise ValueError('Invalid/duplicate/outside-U row or class')
            if inst is not None and (cls != 'TRUSTED_HUMAN' or not isinstance(inst, str) or not inst.strip()):
                raise ValueError('Instance needs trusted human membership')
            seen.add(i)
        previous = self.records(r['sid'], r['fi'])
        previous = [x for x in previous if x['reviewer'] == r['reviewer'] and x['layer'] == r['layer']]
        expected = previous[-1]['revision'] if previous else 0
        if r.get('parent_revision') != expected:
            raise ValueError('Stale label revision')
        if r['layer'] == 'SECONDARY':
            primary = [x['reviewer'] for x in self.records(r['sid'], r['fi']) if x['layer'] == 'PRIMARY']
            if r['reviewer'] in primary:
                raise ValueError('Independent second human required')
        elif any(x['reviewer'] == r['reviewer'] and x['layer'] == 'SECONDARY' for x in self.records(r['sid'], r['fi'])):
            raise ValueError('Second reviewer cannot later become primary for the same frame')
        from datetime import datetime, timezone
        r['revision'] = expected+1
        r['saved_utc'] = datetime.now(timezone.utc).isoformat()
        self.directory.mkdir(parents=True, exist_ok=True)
        from uuid import uuid4
        path = self.directory/(r['saved_utc'].replace(':', '')+'_'+uuid4().hex+'.json')
        write(path, r)
        return r


def trusted_labels(records, rows, require_secondary=False, min_coverage=0):
    """Unreviewed/disagreement -> UNKNOWN. Numeric identity is not inferred."""
    latest = {}
    for r in records:
        key = (r['layer'], r['reviewer'])
        if key not in latest or r['revision'] > latest[key]['revision']: latest[key] = r
    primary = [r for (layer, _), r in latest.items() if layer == 'PRIMARY']
    secondary = [r for (layer, _), r in latest.items() if layer == 'SECONDARY']
    result = np.full(len(rows), -1, dtype='i1')
    if (not primary or (require_secondary and not secondary) or
        any(not r['full_view_reviewed'] or not r['visible_human_coverage'] for r in primary+secondary) or
        set(r['reviewer'] for r in primary) & set(r['reviewer'] for r in secondary)):
        return result
    # Multiple reviewers must agree; absence in any complete snapshot stays UNKNOWN.
    maps = [{x['row']: x['semantic'] for x in r['labels']} for r in primary+secondary]
    for j, i in enumerate(rows):
        classes = [m.get(int(i), 'UNKNOWN') for m in maps]
        if all(c == 'TRUSTED_HUMAN' for c in classes): result[j] = 1
        elif all(c == 'VERIFIED_NONHUMAN' for c in classes): result[j] = 0
    if len(result) and np.mean(result >= 0) < min_coverage:
        result[:] = -1
    return result


def label_gate(tasks, frame_rows, records):
    """Batch quality gate independent of E1; no caller boolean can authorize training."""
    frames = []; sid_support = {}; primary_done = secondary_done = 0
    for task in tasks:
        if task['kind'] != 'CORE': continue
        key = (task['sid'], task['fi']); rows = frame_rows.get(key, [])
        recs = records.get(key, []); latest = {}
        for r in recs:
            k = (r['layer'], r['reviewer'])
            if k not in latest or r['revision'] > latest[k]['revision']: latest[k] = r
        primary = [r for (layer, _), r in latest.items() if layer == 'PRIMARY']
        secondary = [r for (layer, _), r in latest.items() if layer == 'SECONDARY']
        reviewed = bool(primary) and all(r['full_view_reviewed'] and r['visible_human_coverage'] for r in primary)
        independent = bool(secondary) and all(r['full_view_reviewed'] and r['visible_human_coverage'] for r in secondary) and not set(r['reviewer'] for r in primary) & set(r['reviewer'] for r in secondary)
        primary_done += reviewed; secondary_done += task['secondary_required'] and reviewed and independent
        gt = trusted_labels(recs, rows, task['secondary_required'])
        coverage = float(np.mean(gt >= 0)) if len(rows) else 0
        support = reviewed and (not task['secondary_required'] or independent) and coverage >= .7 and np.sum(gt == 1) >= 25 and np.any(gt == 0)
        if 'EMPTY' not in task['role']:
            sid_support.setdefault(task['sid'], 0); sid_support[task['sid']] += int(support)
        frames.append(dict(sid=key[0], fi=key[1], primary=reviewed, second=independent, U=len(rows), K=int(np.sum(gt >= 0)),
                           coverage=coverage, human=int(np.sum(gt == 1)), nonhuman=int(np.sum(gt == 0)), qualifies=bool(support)))
    passed = primary_done == 282 and secondary_done == 66 and len(sid_support) == 8 and all(n >= 12 for n in sid_support.values())
    return dict(status='PASS' if passed else 'BLOCKED', primary_reviewed=primary_done, second_reviewed=secondary_done,
                required_primary=282, required_second=66, eligible_frames_per_sid=sid_support, frames=frames,
                E1='SEPARATE_EXPLICIT_AUTHORIZATION_STILL_REQUIRED', instance='SEPARATE_EXHAUSTIVE_MEMBERSHIP_GATE', joints='BLOCKED_NO_INDEPENDENT_JOINT_GT')


def semantic_metrics(gt, pred):
    gt = np.asarray(gt); pred = np.asarray(pred)
    if gt.shape != pred.shape or not np.isin(gt, [-1, 0, 1]).all() or not np.isin(pred, [-1, 0, 1]).all():
        raise ValueError('Semantic shape/classes')
    k = gt >= 0; tp = int(np.sum((gt == 1) & (pred == 1)))
    fn = int(np.sum((gt == 1) & (pred != 1))); fp = int(np.sum((gt == 0) & (pred == 1)))
    bg = int(np.sum(gt == 0))
    div = lambda a, b: a/b if b else None
    return dict(U=len(gt), K=int(k.sum()), X=int((~k).sum()), TP=tp, FN=fn, FP=fp,
                IoU=div(tp, tp+fn+fp), recall=div(tp, tp+fn), precision=div(tp, tp+fp),
                FP_per1000_background=div(fp*1000, bg), known_coverage=div(int(np.sum(k & (pred >= 0))), int(k.sum())),
                unknown_fraction=div(int(np.sum(pred == -1)), len(pred)),
                background_abstention=int(np.sum((gt == 0) & (pred == -1))), outside_K_H=int(np.sum((~k) & (pred == 1))))


def joint_adapter(value=None):
    if value is None:
        return dict(status='NOT_RUN_NO_APPROVED_WEIGHTS', scoring='BLOCKED_NO_JOINT_GT', joints=[])
    if not isinstance(value, dict) or value.get('units') != 'm' or value.get('kind') != 'NETWORK_INFERRED_JOINTS':
        raise ValueError('Explicit inferred joint schema/units required')
    q = np.asarray(value.get('xyz'), dtype=float)
    if q.ndim != 2 or q.shape[1] != 3 or not np.isfinite(q).all() or not value.get('model_sha256'):
        raise ValueError('Finite model-bound joints required')
    return copy.deepcopy(value)
