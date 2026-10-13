"""DET-04: eight deletion forwards; all other analyses reuse frozen DET-03 traces."""
import argparse
import csv
import json
from pathlib import Path
import time

import numpy as np
import torch

from cpu_pointpillars import load_model, Voxelization
from diagnose_low_scores import (ROOT, UP, PRE, FG, SEED_FILE, SamplingProbe,
                                cylinder, context_cloud, load_cloud, sha_bytes,
                                trace_heads, containing)
from experiment import sha

OLD = ROOT.parents[1] / 'docs/sidequests/evidence/2026-10-08_det03_r1'
NEW = ROOT.parents[1] / 'docs/sidequests/evidence/2026-10-08_det04_r1'
BANDS = [.05, .3, .6, .9, 1.2, 1.5, 1.8, 2.3]
GROUND = [-.15, .30]
FRAMES = [32, 33, 33, 28]


def write_json(path, value):
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def cached_trace(row):
    path = Path(row['trace'])
    assert sha(path) == row['trace_sha256'], path
    with np.load(path) as data:
        return {k: data[k].copy() for k in data.files}


def adapted(cloud):
    p = cloud.copy()
    p[:, 2] -= np.float32(1.73)
    p[:, 3] /= np.float32(1023)
    return p


def point_keys(p, base):
    return np.floor((p[:, :3] - base.bounds[:3]) / base.size).astype('i4')


def masks(cloud, coords, base, xy):
    p = adapted(cloud)
    valid = ((p[:, :3] >= base.bounds[:3]) & (p[:, :3] < base.bounds[3:])).all(1)
    keys = point_keys(p, base)
    localkeys = set(map(tuple, keys[valid & cylinder(cloud, xy)]))
    local = np.array([tuple(k) in localkeys for k in coords], dtype=bool)
    groups = {}
    for i in np.flatnonzero(valid):
        groups.setdefault(tuple(keys[i]), []).append(i)
    # Entire occupied pillar must be near ground; mixed wall/furniture pillars excluded.
    ground = np.array([np.all((cloud[groups[tuple(k)], 2] >= GROUND[0]) &
                             (cloud[groups[tuple(k)], 2] <= GROUND[1])) for k in coords])
    return local, ground, groups


def assert_frozen(before, after, keep):
    v, c, n = before
    av, ac, an = after
    np.testing.assert_array_equal(c.numpy(), ac.numpy())
    np.testing.assert_array_equal(v.numpy(), av.numpy())
    np.testing.assert_array_equal(n.numpy()[keep], an.numpy()[keep])
    assert np.all(an.numpy()[~keep] == 0), 'deleted counts must be zero'
    assert np.all(an.numpy()[keep] > 0), 'retained counts must be positive'


class DeletionProbe(SamplingProbe):
    def __init__(self, base, canonical, keep):
        super().__init__(base)
        self.canonical, self.keep = canonical, keep

    def forward(self, points):
        v, c, n = super().forward(points)
        n[~self.keep] = 0
        assert_frozen(self.canonical, (v, c, n), self.keep)
        self.last = (v.clone(), c.clone(), n.clone(), self.last[3])
        # Zero-count pillars would divide by zero upstream. Absent pillars scatter as zero.
        return v[self.keep], c[self.keep], n[self.keep]


def selection(cloud, ids, xy, base, mode):
    probe = SamplingProbe(base)
    probe.mode = mode
    with torch.inference_mode():
        v, c, n = probe(torch.from_numpy(adapted(cloud)))
    slots = np.full(v.shape[:2], -1, dtype='i8')
    cursor = 0
    for j, count in enumerate(n.tolist()):
        slots[j, :count] = probe.selected[cursor:cursor + count]
        cursor += count
    assert cursor == len(probe.selected)
    local, ground, groups = masks(cloud, c.numpy(), base, xy)
    return dict(v=v.numpy(), c=c.numpy(), n=n.numpy(), total=probe.last[3],
                slots=slots, local=local, ground=ground, groups=groups,
                selected=probe.selected, ids=ids)


def verify_pillars(row, sel, base, xy):
    path = Path(row['trace'].replace('_trace.npz', '_pillars.npz'))
    with np.load(path) as old:
        coords = sel['c']
        near = np.sum((coords[:, :2] * base.size[:2] + base.bounds[:2] +
                       base.size[:2] / 2 - xy)**2, axis=1) <= .7**2
        for key, arr in [('coords', coords), ('counts', sel['n']),
                         ('input_counts', sel['total']), ('selected_xyzi', sel['v'])]:
            np.testing.assert_array_equal(old[key], arr[near])


def counts_and_bands(cloud, sel, xy):
    selected = np.concatenate([v[:n] for v, n in zip(sel['v'], sel['n'])]).copy()
    selected[:, 2] += np.float32(1.73)
    bands = np.histogram(selected[cylinder(selected, xy), 2], BANDS)[0].tolist()
    local_counts = [int(cylinder(cloud[sel['groups'][tuple(k)]], xy).sum()) for k in sel['c']]
    return dict(cylinder_points_over32_pillars=sum(n > 32 for n in local_counts),
                intersecting_full_over32_pillars=int(((sel['total'] > 32) & sel['local']).sum()),
                bands=bands, local_counts=local_counts)


def corr(x, y, rank=False):
    x, y = np.asarray(x, dtype=float), np.asarray(y, dtype=float)
    if np.ptp(x) == 0 or np.ptp(y) == 0:
        return None
    if rank:
        def ranks(a):
            _, inverse, counts = np.unique(a, return_inverse=True, return_counts=True)
            return (np.cumsum(counts) - (counts + 1) / 2)[inverse]
        x, y = ranks(x), ranks(y)
    return float(np.corrcoef(x, y)[0, 1])


def receptive_bounds(anchor_id, head_width=216):
    y, x = divmod(anchor_id // 6, head_width)
    bounds = []
    # Invert neck's non-overlapping 1/2/4 transpose convolution then every backbone conv.
    for branch, up in enumerate([1, 2, 4]):
        lo, hi = np.array([x // up, y // up]), np.array([x // up, y // up])
        for b in range(branch, -1, -1):
            for _ in range([3, 5, 5][b]):
                lo -= 1
                hi += 1
            lo, hi = lo * 2 - 1, hi * 2 + 1
        bounds.append([lo.tolist(), hi.tolist()])
    return bounds


def anchor_rows(before, after, xy):
    amap = {int(i): j for j, i in enumerate(before['anchor_ids'])}
    bmap = {int(i): j for j, i in enumerate(after['anchor_ids'])}
    rows = []
    for anchor in sorted(amap.keys() & bmap.keys()):
        a, b = amap[anchor], bmap[anchor]
        local = np.sum((before['anchors'][a, :2] - xy)**2) <= .55**2
        delta = float(after['raw_cls_scores'][b, 0] - before['raw_cls_scores'][a, 0])
        if delta != 0:
            rows.append(dict(anchor_id=anchor, local=bool(local), base=float(before['raw_cls_scores'][a, 0]),
                             zrank=float(after['raw_cls_scores'][b, 0]), delta=delta,
                             base_containing=bool(containing(before['decoded_boxes'][a:a+1], xy)[0]),
                             zrank_containing=bool(containing(after['decoded_boxes'][b:b+1], xy)[0])))
    la = set(before['anchor_ids'][np.sum((before['anchors'][:, :2] - xy)**2, 1) <= .55**2].tolist())
    lb = set(after['anchor_ids'][np.sum((after['anchors'][:, :2] - xy)**2, 1) <= .55**2].tolist())
    assert la == lb, 'cached local anchor set must be complete on both sides'
    def winner(d):
        local = np.sum((d['anchors'][:, :2] - xy)**2, 1) <= .55**2
        j = np.flatnonzero(local)[np.argmax(d['raw_cls_scores'][local, 0])]
        return dict(anchor_id=int(d['anchor_ids'][j]), score=float(d['raw_cls_scores'][j, 0]),
                    anchor=d['anchors'][j].tolist(), decoded=d['decoded_boxes'][j].tolist())
    return dict(changed=rows, local_count=len(la), base_winner=winner(before), zrank_winner=winner(after),
                top100_added=sorted(set(after['top100'].tolist()) - set(before['top100'].tolist())),
                top100_removed=sorted(set(before['top100'].tolist()) - set(after['top100'].tolist())),
                scope='Complete local set plus common cached candidates; unsaved global anchors NOT assessed')


def column_detail(cloud, ids, source_rows, xy, a, b, support):
    details = []
    for j in np.flatnonzero(support):
        full = np.asarray(a['groups'][tuple(a['c'][j])])
        sa, sb = a['slots'][j, :a['n'][j]], b['slots'][j, :b['n'][j]]
        details.append(dict(coord=a['c'][j].tolist(), input_count=int(a['total'][j]),
                            cylinder_count=int(cylinder(cloud[full], xy).sum()),
                            selected_count=int(a['n'][j]), full_z_min=float(cloud[full, 2].min()),
                            full_z_max=float(cloud[full, 2].max()),
                            full_bands=np.histogram(cloud[full, 2], BANDS)[0].tolist(),
                            first32_z=cloud[sa, 2].tolist(), zrank32_z=cloud[sb, 2].tolist(),
                            first32_bands=np.histogram(cloud[sa, 2], BANDS)[0].tolist(),
                            zrank32_bands=np.histogram(cloud[sb, 2], BANDS)[0].tolist(),
                            first32_prepared_ids=ids[sa].tolist(), zrank32_prepared_ids=ids[sb].tolist(),
                            first32_raw_global_rows=source_rows[ids[sa]].tolist(),
                            zrank32_raw_global_rows=source_rows[ids[sb]].tolist()))
    return details


def main(out):
    out.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(4)
    fg, pre = read_json(FG / 'manifest.json'), read_json(PRE / 'manifest.json')
    assert fg['input_manifest_sha256'] == sha(PRE / 'manifest.json')
    truth = {s['session']: s['xy_m'] for s in read_json(SEED_FILE)['sessions']}
    old_rows = [json.loads(s) for s in (OLD / 'det03_all_r1_rows.jsonl').read_text(encoding='utf-8').splitlines()]
    reps = read_json(OLD / 'det03_representative_r2_rows.json')
    negatives = read_json(OLD / 'det03_negative_controls_r1_rows.json')
    lookup = {(r['sid'], r['index'], r['variant'], r['experiment']): r for r in old_rows}
    sessions = {s['sid']: s for s in fg['sessions']}
    raw = {s['sid']: s for s in pre['sessions']}
    base = Voxelization([.16, .16, 4], [0, -39.68, -3, 69.12, 39.68, 1], 32, (16000, 40000))

    def load(sid, index, variant):
        return load_cloud(sessions[sid], sessions[sid]['frames'][index], variant, raw[sid])

    def raw_rows(sid, index):
        r = raw[sid]['frames'][index]
        path = PRE / sid / (r['file'] + '.rows')
        assert sha(path) == r['rows_sha256']
        return np.fromfile(path, dtype='<i8')

    def rep(sid, variant, experiment):
        return next(r for r in reps if r.get('sid') == sid and r.get('variant') == variant and r.get('experiment') == experiment)

    # Audit BEFORE the only new variants. Existing families below reuse all network artifacts.
    audit = []
    for sid, index in zip(sessions, FRAMES):
        assert sessions[sid]['frames'][len(sessions[sid]['frames']) // 2]['index'] == index
        b, bids = load(sid, index, 'B_workspace')
        for other in ['C_reference', 'E_cleanup']:
            cloud, ids = context_cloud(b, bids, *load(sid, index, other), truth[sid])
            for name in ['context_points', 'context_pillars']:
                r = rep(sid, other, name)
                assert sha_bytes(cloud) == r['input_sha256'] and sha_bytes(ids) == r['ids_sha256']
                cached_trace(r)
                audit.append(dict(sid=sid, index=index, variant=other, experiment=name,
                                  input_sha256=r['input_sha256'], ids_sha256=r['ids_sha256'],
                                  source='B scan values/order; C/E only selects retained source IDs',
                                  foreign_xyzi_injected=False, reused=True))
    existing = [p for p in (ROOT / 'artifacts').glob('det*/**/*rows*.json*') if 'det04' not in str(p)]
    matches = []
    for p in existing:
        if 'outside_zero' in p.read_text(encoding='utf-8'):
            matches.append(str(p))
    assert not matches, 'same-family existing artifact requires reuse: ' + str(matches)
    write_json(NEW / '01_artifact_audit.json', dict(context=audit, deletion_matches=matches,
               searched=[str(p) for p in existing], reused_forward_families=['baseline/context', 'all506', 'negative7', 'empty3/real4'],
               new_forward_limit=8))
    config = dict(script_sha256=sha(Path(__file__)), plan_sha256=sha(NEW.parents[1] / 'DET04_PLAN.md'),
                  acceptance_sha256=sha(NEW.parents[1] / 'DET04_ACCEPTANCE.md'),
                  shared_sha256={p.name: sha(p) for p in [ROOT/'diagnose_low_scores.py', ROOT/'cpu_pointpillars.py']},
                  checkpoint_sha256=sha(UP/'epoch_160.pth'), source_hashes={str(p): sha(p) for p in [FG/'manifest.json', PRE/'manifest.json', SEED_FILE]},
                  ground_band=GROUND, ground_rule='ALL valid original leveled points in pillar, inclusive',
                  frames=FRAMES, sampling='first32 only for deletion',
                  score=.1, nms=.01, top100=100, max50=50, voxel=[.16,.16,4], max_points=32,
                  model_z=-1.73, intensity_divisor=1023, new_forwards=8,
                  other_new_forwards=0, physical=False, registration='WARN unchanged')
    write_json(out/'config.json', config)
    write_json(NEW/'02_config.json', config)
    print('AUDIT PASS: 16 archived context hashes; no injected foreign XYZI; new forward cap=8', flush=True)

    # H-B: no model is even loaded until all descriptive/negative/FP analyses finish.
    doses, neg = [], []
    for key, b in lookup.items():
        sid, index, variant, experiment = key
        if experiment != 'base':
            continue
        z = lookup[(sid, index, variant, 'zrank')]
        assert b['input_sha256'] == z['input_sha256'] and b['ids_sha256'] == z['ids_sha256']
        cloud, ids = load(sid, index, variant)
        a = selection(cloud, ids, truth[sid], base, 'first32')
        dose = counts_and_bands(cloud, a, truth[sid])
        assert dose['bands'] == b['after']['bands']
        verify_pillars(b, a, base, truth[sid])
        row = dict(sid=sid, index=index, variant=variant, input_sha256=b['input_sha256'],
                   head_delta=z['local_anchor_max']-b['local_anchor_max'],
                   cylinder_over32=dose['cylinder_points_over32_pillars'],
                   intersecting_full_over32=dose['intersecting_full_over32_pillars'],
                   upper_band_gain=z['after']['bands'][5]-b['after']['bands'][5],
                   before_bands=b['before']['bands'], first32_bands=b['after']['bands'], zrank_bands=z['after']['bands'])
        doses.append(row)
        if sid.endswith('215643') and row['head_delta'] < 0:
            zz = selection(cloud, ids, truth[sid], base, 'z_rank32')
            verify_pillars(z, zz, base, truth[sid])
            assert counts_and_bands(cloud, zz, truth[sid])['bands'] == z['after']['bands']
            aa = anchor_rows(cached_trace(b), cached_trace(z), truth[sid])
            coverage = (sum(n > 0 for n in z['after']['bands']) > sum(n > 0 for n in b['after']['bands']) or
                        row['upper_band_gain'] > 0 or z['after']['top'] > b['after']['top'])
            detail = column_detail(cloud, ids, raw_rows(sid, index), truth[sid], a, zz, a['local'])
            write_json(out / (b['tag']+'_negative.json'), dict(dose=row, pillars=detail, anchors=aa))
            neg.append(dict(**row, coverage_improved=coverage,
                            attribution='proxy coverage improved, specific local anchor negative response' if coverage else 'proxy coverage did not improve',
                            base_winner=aa['base_winner'], zrank_winner=aa['zrank_winner'],
                            local_changed=sum(r['local'] for r in aa['changed']),
                            most_negative_local=min((r for r in aa['changed'] if r['local']), key=lambda r:r['delta']),
                            pillars=detail, anchors=aa, base_after=b['after'], zrank_after=z['after']))
    assert len(doses) == 506
    assert sum(r['variant']=='B_workspace' for r in neg) == 2 and len(neg) == 7
    summaries = []
    for sid in sessions:
        for variant in ['B_workspace', 'E_cleanup']:
            g = [r for r in doses if r['sid']==sid and r['variant']==variant]
            cs = {}
            for field in ['cylinder_over32', 'intersecting_full_over32', 'upper_band_gain']:
                x, y = [r[field] for r in g], [r['head_delta'] for r in g]
                cs[field] = dict(min=min(x), max=max(x), pearson=corr(x,y), spearman=corr(x,y,True),
                                 null_reason='constant dose or response' if corr(x,y) is None else None)
            summaries.append(dict(sid=sid, variant=variant, n=len(g), correlations=cs))
    write_json(NEW/'03_dose_rows.json', doses)
    with (NEW/'03_dose_pairs.csv').open('x',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(doses[0]));w.writeheader();w.writerows(doses)
    write_json(NEW/'03_dose_summary.json', dict(groups=summaries, new_forwards=0,
                interpretation='descriptive within session/input; correlated consecutive frames; no significance or causal claim'))
    write_json(NEW/'04_negative_anatomy.json', dict(rows=neg, new_forwards=0, note='Cylinder includes furniture; complete LOCAL anchor changes, cached common global candidates only'))
    print('B/C PASS: 506 descriptive pairs; all 2 B + 5 E negatives retained; zero forwards',flush=True)

    # H-D: potential support defined by network receptive field, not causal attribution.
    fps = []
    controls = [(None,i,next(r for r in negatives if r['tag']==f'empty_{i}_z_rank32')) for i in [17,35,53]]
    controls += [(sid,i,rep(sid,'B_workspace','zrank')) for sid,i in zip(sessions,FRAMES)]
    for sid, index, r in controls:
        empty = sid is None
        sid = pre['sessions'][0]['sid'] if empty else sid
        if empty:
            rec=raw[sid]['frames'][index];path=PRE/sid/rec['file'];assert sha(path)==rec['sha256']
            cloud=np.fromfile(path,dtype='<f4').reshape(-1,4);ids=np.arange(len(cloud),dtype='i8');xy=[2.1,-.5]
            baseline=next(q for q in negatives if q['tag']==f'empty_{index}_first32')
        else:
            cloud,ids=load(sid,index,'B_workspace');xy=truth[sid];baseline=rep(sid,'B_workspace','base')
        assert sha_bytes(cloud)==r['input_sha256'] and sha_bytes(adapted(cloud))==r['adapted_sha256']
        t=cached_trace(r);bt=cached_trace(baseline)
        if empty:
            scores=torch.from_numpy(t['cls_logits']).permute(1,2,0).reshape(-1,3).sigmoid().numpy()
            anchor=int(np.argmax(scores[:,0]));assert anchor==int(t['global_top_anchor_id'][0])
        else:
            local=np.sum((t['anchors'][:,:2]-xy)**2,1)<=.55**2
            anchor=int(t['anchor_ids'][np.flatnonzero(local)[np.argmax(t['raw_cls_scores'][local,0])]])
        j=int(np.flatnonzero(t['anchor_ids']==anchor)[0]);bj=int(np.flatnonzero(bt['anchor_ids']==anchor)[0])
        a=selection(cloud,ids,xy,base,'first32');z=selection(cloud,ids,xy,base,'z_rank32')
        verify_pillars(r,z,base,xy);verify_pillars(baseline,a,base,xy)
        ranges=receptive_bounds(anchor);support=np.zeros(len(a['c']),bool)
        for lo,hi in ranges:support|=((a['c'][:,:2]>=lo)&(a['c'][:,:2]<=hi)).all(1)
        centers=a['c'][:,:2]*base.size[:2]+base.bounds[:2]+base.size[:2]/2
        box=t['decoded_boxes'][j]
        dx,dy=centers[:,0]-box[0],centers[:,1]-box[1];c,s=np.cos(box[6]),np.sin(box[6])
        foot=(np.abs(c*dx-s*dy)<=box[3]/2)&(np.abs(s*dx+c*dy)<=box[4]/2)
        support_ids=np.concatenate([z['slots'][k,:z['n'][k]] for k in np.flatnonzero(support)])
        full_support=np.concatenate([np.asarray(z['groups'][tuple(z['c'][k])]) for k in np.flatnonzero(support)])
        rows=raw_rows(sid,index)
        np.savez_compressed(out/(r['tag']+'_support.npz'),coords=z['c'][support],counts=z['n'][support],input_counts=z['total'][support],
                            first32_voxels=a['v'][support],zrank_voxels=z['v'][support],
                            first32_prepared_ids=ids[np.concatenate([a['slots'][k,:a['n'][k]] for k in np.flatnonzero(support)])],
                            zrank_prepared_ids=ids[support_ids],zrank_raw_global_rows=rows[ids[support_ids]],
                            full_prepared_ids=ids[full_support],full_raw_global_rows=rows[ids[full_support]])
        detail=column_detail(cloud,ids,rows,xy,a,z,support|foot)
        fp=dict(sid=sid,index=index,tag=r['tag'],role='empty global raw winner' if empty else 'human seed local raw winner',
                anchor_id=anchor,anchor=t['anchors'][j].tolist(),decoded=box.tolist(),score=float(t['raw_cls_scores'][j,0]),
                first32_same_anchor_score=float(bt['raw_cls_scores'][bj,0]),
                final_kept=any(d['anchor_id']==anchor and d['label']==0 for d in r['stages']['clockwise']['detections']),
                support_bounds=ranges,support_pillars=int(support.sum()),footprint_pillars=int(foot.sum()),
                support_source_points=len(full_support),support_selected_points=len(support_ids),
                support_full_bands=np.histogram(cloud[full_support,2],BANDS)[0].tolist(),
                support_first32_bands=np.histogram(cloud[np.concatenate([a['slots'][k,:a['n'][k]] for k in np.flatnonzero(support)]),2],BANDS)[0].tolist(),
                support_zrank_bands=np.histogram(cloud[support_ids,2],BANDS)[0].tolist(),
                footprint_coords=a['c'][foot].tolist(),pillar_details=detail,
                scope='Structural receptive field potential support; NOT saliency, GT, FP rate or a causal pillar attribution')
        fps.append(fp)
    write_json(NEW/'05_fp_anatomy.json',dict(rows=fps,new_forwards=0,scope='3 held frames of one confirmed empty template; 4 same-person sessions, no FP rate'))
    print('D PASS: 3 empty + 4 human anchor support records; zero forwards',flush=True)

    # Only H-A loads/runs the network. No recomputation of archived baselines.
    model=load_model(UP/'epoch_160.pth',UP)
    assert (model.score_thr,model.nms_thr,model.nms_pre,model.max_num)==(.1,.01,100,50)
    actual_base=model.pillar_layer.voxel_layer
    arows=[];comparisons=[]
    with (out/'rows.jsonl').open('x',encoding='utf-8') as log:
        for sid,index in zip(sessions,FRAMES):
            xy=truth[sid];cloud,ids=load(sid,index,'B_workspace');p=adapted(cloud)
            with torch.inference_mode():canonical=actual_base(torch.from_numpy(p))
            v,c,n=canonical;local,ground,groups=masks(cloud,c.numpy(),actual_base,xy)
            s=selection(cloud,ids,xy,actual_base,'first32');verify_pillars(rep(sid,'B_workspace','base'),s,actual_base,xy)
            with torch.inference_mode():
                bc=torch.cat([torch.zeros((len(c),1),dtype=torch.long),c.long()],1)
                canvas=model.pillar_encoder(v,bc,n).clone()
            for name,keep in [('outside_zero',local),('outside_zero_ground_kept',local|ground)]:
                probe=DeletionProbe(actual_base,canonical,keep);model.pillar_layer.voxel_layer=probe
                captured=[];canvases=[]
                h=model.head.register_forward_hook(lambda m,i,o:captured.extend(t.detach() for t in o))
                eh=model.pillar_encoder.register_forward_hook(lambda m,i,o:canvases.append(o.detach()))
                start=time.perf_counter()
                try:
                    with torch.inference_mode():model([torch.from_numpy(p)],mode='test')
                finally:h.remove();eh.remove()
                actual=canvases[0]
                assert torch.isfinite(actual).all()
                np.testing.assert_array_equal(actual[0,:,c[keep,1],c[keep,0]].numpy(),canvas[0,:,c[keep,1],c[keep,0]].numpy())
                assert torch.count_nonzero(actual[0,:,c[~keep,1],c[~keep,0]])==0
                tag=sid+'_'+str(index)+'_'+name
                with torch.inference_mode():row=trace_heads(model,captured,xy,out/(tag+'_trace.npz'),True)
                av,ac,an,_=probe.last
                source_slots=np.full(s['slots'].shape,-1,dtype='i8');valid=s['slots']>=0;source_slots[valid]=ids[s['slots'][valid]]
                np.savez_compressed(out/(tag+'_pillars.npz'),voxels=av.numpy(),coords=ac.numpy(),counts=an.numpy(),
                                    baseline_counts=n.numpy(),retained=keep,local_frozen=local,ground=ground,
                                    prepared_ids=source_slots,raw_global_rows=np.where(valid,raw_rows(sid,index)[np.maximum(source_slots,0)],-1))
                row.update(sid=sid,index=index,experiment=name,tag=tag,seconds=time.perf_counter()-start,
                           input_sha256=sha_bytes(cloud),adapted_sha256=sha_bytes(p),ids_sha256=sha_bytes(ids),
                           baseline_pillars=len(n),retained_pillars=int(keep.sum()),deleted_pillars=int((~keep).sum()),
                           local_frozen_pillars=int(local.sum()),outside_ground_pillars=int((ground&~local).sum()),
                           retained_voxels_exact=True,retained_counts_exact=True,source_ids_exact=True,
                           retained_canvas_exact=True,deleted_canvas_zero=True,
                           local_tensor_sha256=sha_bytes(av.numpy()[local]),local_counts_sha256=sha_bytes(an.numpy()[local]),
                           local_canvas_sha256=sha_bytes(actual[0,:,c[local,1],c[local,0]].numpy()))
                arows.append(row);log.write(json.dumps(row,ensure_ascii=False)+'\n');log.flush()
                print(json.dumps({k:row[k] for k in ['tag','local_anchor_max','raw_containing_max','retained_pillars']},ensure_ascii=False),flush=True)
            comparisons.extend([dict(sid=sid,index=index,variant=v,experiment=name,reused=True,
                                    **{k:rep(sid,v,name)[k] for k in ['local_anchor_max','raw_containing_max','global_raw_ped_max','stages']})
                                for v,name in [('B_workspace','base'),('C_reference','base'),('E_cleanup','base'),
                                               ('C_reference','context_points'),('C_reference','context_pillars'),
                                               ('E_cleanup','context_points'),('E_cleanup','context_pillars')]])
    assert len(arows)==8
    write_json(out/'rows.json',arows);write_json(NEW/'06_deletion_rows.json',arows)
    write_json(NEW/'06_comparisons.json',comparisons)
    attribution=[]
    for sid in sessions:
        rows={r['experiment']:r for r in arows if r['sid']==sid}
        b=rep(sid,'B_workspace','base')['local_anchor_max']
        ce=[rep(sid,v,'context_pillars')['local_anchor_max'] for v in ['C_reference','E_cleanup']]
        x=rows['outside_zero']['local_anchor_max'];g=rows['outside_zero_ground_kept']['local_anchor_max']
        dist=max(min(ce)-x,0,x-max(ce))
        attribution.append(dict(sid=sid,base=b,ce_range=[min(ce),max(ce)],outside_zero=x,ground_kept=g,
                                B_like=abs(x-b)<=.02,CE_like=dist<=.02,baseline_contrast_insufficient=min(abs(b-q) for q in ce)<=.04,
                                ground_delta=g-x,ground_effect=abs(g-x)>.02,
                                external_content_claim='NOT supported: archived contexts inject no foreign point values'))
    write_json(NEW/'07_attribution.json',dict(rows=attribution,new_forwards=8,other_new_forwards=0))
    print('DONE: H-A 8 new forwards; H-B/C/D 0 new forwards',flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True)
    main(p.parse_args().out)
