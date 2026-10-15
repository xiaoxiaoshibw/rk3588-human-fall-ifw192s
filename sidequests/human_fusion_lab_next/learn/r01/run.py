"""Exclusive E0 run. Inputs are read-only; every phase refuses existing outputs."""
import argparse
import copy
import ctypes
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
from contracts import ROOT, PLAN, OLD, read, sha, write, universe, angles, project, projection_stats

sys.path.insert(0, str(OLD))
from next_contract import validate_meta
from actions import load
from core import R, T, cluster, skeleton, voxelize
from next_dev import CausalSelection, node_metrics, quant
from scene_change import FrozenSurfaces
from scene_static import static_reference_mask
from research_scene_change import domain
from research_actions import frame_points
from next_temporal import RecentNonLowEvent

HERE = Path(__file__).resolve().parent


def peak_bytes():
    if os.name == 'nt':
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb', wintypes.DWORD), ('PageFaultCount', wintypes.DWORD)]+[(n, ctypes.c_size_t) for n in
                       ['PeakWorkingSetSize', 'WorkingSetSize', 'QuotaPeakPagedPoolUsage', 'QuotaPagedPoolUsage',
                        'QuotaPeakNonPagedPoolUsage', 'QuotaNonPagedPoolUsage', 'PagefileUsage', 'PeakPagefileUsage']]
        c = Counters(); c.cb = ctypes.sizeof(c)
        kernel = ctypes.WinDLL('kernel32'); kernel.GetCurrentProcess.restype = wintypes.HANDLE
        function = ctypes.WinDLL('psapi').GetProcessMemoryInfo
        function.argtypes = [wintypes.HANDLE, ctypes.POINTER(Counters), wintypes.DWORD]
        function.restype = wintypes.BOOL
        if not function(kernel.GetCurrentProcess(), ctypes.byref(c), c.cb):
            raise OSError('GetProcessMemoryInfo')
        return int(c.PeakWorkingSetSize)
    import resource
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024


def code_hashes():
    # Numeric execution never imports the UI or console. Bind their publication
    # separately so concurrent console work cannot re-sign or block numerics.
    paths = [HERE/n for n in ['run.py', 'audit.py', 'contracts.py', 'models.py', 'temporal.py']]
    paths += [OLD/n for n in ['core.py', 'actions.py', 'next_dev.py', 'next_contract.py', 'next_temporal.py',
                              'scene_change.py', 'scene_static.py', 'research_actions.py', 'research_scene_change.py']]
    return {str(p.relative_to(ROOT)).replace('\\', '/'): sha(p) for p in paths}


def prepare(e):
    pointer = read(PLAN/'CURRENT_PLAN.json')
    if pointer['review_decision'] != 'PLAN_PASS': raise ValueError('No PLAN_PASS')
    for n, h in pointer['sha256'].items():
        if sha(PLAN/n) != h: raise ValueError('Plan drift: '+n)
    if sha(PLAN/pointer['review']) != pointer['review_sha256']: raise ValueError('Review drift')
    if shutil.disk_usage(e).free < 90*1024**3: raise ValueError('RESOURCE_BLOCKED: free disk <90GiB')
    expected = read(PLAN/'DATA_PREFLIGHT_V2.json'); checks = []
    for rec in expected['checks']:
        sid = rec['sid']; m, raw, hashes = load(sid)
        validate_meta(m, (ROOT/'captures/remote'/sid/'points.bin').stat().st_size)
        if hashes != rec['sha256'] or len(m['frames']) != rec['frame_count']: raise ValueError('Source drift')
        checks.append(dict(sid=sid, frames=len(m['frames']), sha256=hashes, bytes=(ROOT/'captures/remote'/sid/'points.bin').stat().st_size,
                           stride=28, offsets_count_time='PASS', total_points=m['total_points']))
        del raw
    prior = read(ROOT/'docs/human_capture/evidence/2026-10-15_hfus_next_dev_r1/RUN_MANIFEST.json')
    assets = prior['background_assets']; transforms = prior['transforms']
    for x in assets:
        if sha(x['path']) != x['sha256']: raise ValueError('Background drift')
    for p, h in transforms.items():
        if sha(p) != h: raise ValueError('Registration drift')
    split = read(PLAN/'EXPERIMENT_SPLIT_V2.json'); queue = read(PLAN/'ANNOTATION_QUEUE_V2.json')
    # Read all contracts before deriving any run configuration.
    for n in ['EXPERIMENT_BUDGET_V2.json', 'OUTPUT_BUDGET_V2.json', 'FOLD_SAMPLE_COUNTS.json', 'EXPERIMENT_STREAMS.json']:
        read(PLAN/n)
    oldsid = ROOT/'captures/remote/cap_20261013_131958'
    write(e/'DATA_PREFLIGHT.json', dict(checks=checks, background_assets=assets, transforms=transforms, R=R.tolist(), T=T.tolist(),
                                     old131958=dict(meta=(oldsid/'meta.json').exists(), points=(oldsid/'points.bin').exists(),
                                                    CAL='BLOCKED_ORIGINAL_NOT_RECREATED', old32='CACHED_XYZ_ONLY')))
    manifest = dict(schema='hfus-learn/1', run_id=e.name, mode='E0', authorities_sha256=sha(e/'AUTHORITIES.json'),
                    plan=pointer, split=split, sources={x['sid']:x for x in checks},
                    cfg=copy.deepcopy(prior['config']), controls=copy.deepcopy(prior['controls']), limits=prior['limits'],
                    old_tau=prior['old_tau'], new_tau=prior['new_tau'], backgrounds=assets, transforms=transforms,
                    source_sha256=code_hashes(), python=platform.python_version(), numpy=np.__version__,
                    ui_source_sha256={str(p.relative_to(ROOT)).replace('\\', '/'):sha(p) for p in
                                      [HERE/'server.py', HERE/'view.js', HERE/'view.html', ROOT/'pc_apps/console/console_gui.py']},
                    E1='NOT_GRANTED', labels='BLOCKED_NO_CURRENT_TRUSTED_HUMAN_REVIEWS', default='R1_UNCHANGED',
                    budget=read(PLAN/'EXPERIMENT_BUDGET_V2.json'), streams=read(PLAN/'EXPERIMENT_STREAMS.json'),
                    outputs='sparse npz common + four geometry streams; no learned inference',
                    disk_free_bytes=shutil.disk_usage(e).free, timestamp=time.time())
    write(e/'RUN_MANIFEST.json', manifest)
    tasks = []
    for sid, task in queue['tasks'].items():
        for kind, frames in [('CORE', task['core_review']), ('PROPOSAL', task['proposal_extra'])]:
            for fi in frames:
                tasks.append(dict(sid=sid, fi=fi, kind=kind, role=task['label_role'], secondary_required=fi in task['secondary_review'],
                                  source_sha256=manifest['sources'][sid]['sha256'], status='UNREVIEWED', semantic='UNKNOWN'))
    if len(tasks) != 474 or sum(t['kind'] == 'CORE' for t in tasks) != 282 or sum(t['secondary_required'] for t in tasks) != 66:
        raise ValueError('Queue drift')
    write(e/'ANNOTATION_TASKS.json', tasks)
    write(e/'LABEL_MANIFEST.json', dict(core=282, proposals=192, secondary=66, reviewed=0, trusted_K=0,
                                       X='ALL_U_UNREVIEWED', semantic='BLOCKED', instance='BLOCKED', joints='BLOCKED',
                                       human_pending='282 primary core reviews + 66 independent second human reviews; 192 proposals never gold',
                                       schema='hfus-label/1; labels per source row; immutable reviewer snapshots; absent/conflicts UNKNOWN'))
    jobs = []
    for family in ['L3D', 'L2D', 'LFUSION']:
        for width in [0, 1]:
            for fold in range(4): jobs.append(dict(id=f'{family}_cfg{width}_fold{fold}', family=family, width=width, fold=fold, seed=43, phase='screen', train_samples=72, validation=24))
        for seed in [19, 43, 97]: jobs.append(dict(id=f'{family}_final_seed{seed}', family=family, seed=seed, phase='final', train_samples=96))
    for name in ['no_bg_risk', 'hard_bg', 'causal_GRU']: jobs.append(dict(id='MAIN_'+name, phase='ablation'))
    for job in jobs: job.update(status='BLOCKED', reason='NO_E1_AND_NO_TRUSTED_LABEL_GATE', optimizer_steps=0, wall_s=0, weights=None)
    write(e/'EXPERIMENT_MATRIX.json', dict(jobs=jobs, count=len(jobs), actual_fit_count=0, training_wall_s=0,
                                         streams=manifest['streams'], learned_inference='NOT_RUN', winner='NO_ELIGIBLE_MODEL'))
    write(e/'INFERENCE_MATRIX.json', [dict(stream=s, status='NOT_RUN', reason='NO_ELIGIBLE_TRAINED_MAIN_WEIGHTS',
                                         applicability=manifest['streams']['applicability'].get(s, 'requires actual trained weights'))
                                    for s in manifest['streams']['learning_streams']+manifest['streams']['inference_pressure_streams']])
    m, raw, hashes = load(split['empty_sid']); ext = []
    for fi in split['empty_fit']:
        f = m['frames'][fi]; q = raw[f['offset_points']:f['offset_points']+f['count_points']]
        a = angles(q[universe(q)]); ext.append(np.stack([a.min(0), a.max(0)]))
    lower = np.min(np.stack(ext)[:, 0], axis=0); upper = np.max(np.stack(ext)[:, 1], axis=0)
    # Inclusive FIT extrema with fixed tiny pad; no comparison input affects bounds.
    bounds = np.column_stack([lower-1e-6, upper+1e-6])
    write(e/'SCAN_TEMPLATE.json', dict(schema='hfus-scan/1', fit_sid=split['empty_sid'], fit_frames=split['empty_fit'],
                                      source_sha256=hashes, bounds_radians=bounds.tolist(), resolutions=[[128, 512], [256, 1024]],
                                      K=2, physical_calibration='UNVERIFIED_ANGULAR_GRID_FROM_FIT_ONLY',
                                      axes='raw yaw atan2(Y,X), elevation atan2(Z,hypot(X,Y)); axial +X positive', opaque_bytes='12:28_UNINTERPRETED'))
    archive = e/'EXECUTED_SOURCE'
    for p in HERE.glob('*'):
        if p.is_file():
            archive.mkdir(exist_ok=True); shutil.copyfile(p, archive/p.name)
    for name, digest in {**manifest['source_sha256'], **manifest['ui_source_sha256']}.items():
        source = ROOT/name
        if sha(source) != digest: raise ValueError('Source changed during archive')
        dest = e/'EXECUTED_DEPENDENCIES'/name; dest.parent.mkdir(parents=True, exist_ok=True); shutil.copyfile(source, dest)
    write(e/'PREPARE_COMPLETE.json', dict(status='PASS', source_files=len(checks)*2, sessions=len(checks),
                                         frames=sum(r['frames'] for r in checks), E1='BLOCKED', peak_bytes=peak_bytes()))
    print('PREPARE PASS 18 raw hashes; 474 tasks; no labels/no training', flush=True)


def profile_one(e, family, wide, h):
    import torch
    from models import Frontend, state_sha, point_inputs, image_inputs
    torch.set_num_threads(2); torch.manual_seed(43)
    mfest = read(e/'RUN_MANIFEST.json'); queue = read(PLAN/'ANNOTATION_QUEUE_V2.json'); split = mfest['split']
    candidates = []
    fold = split['folds'][2]
    for sid in fold['train_sids']:
        meta = read(ROOT/'captures/remote'/sid/'meta.json')
        for fi in queue['tasks'][sid]['core_review']: candidates.append((meta['frames'][fi]['count_points'], sid, fi))
    _, sid, fi = max(candidates); m, raw, hashes = load(sid)
    if hashes != mfest['sources'][sid]['sha256']: raise ValueError('Resource probe source drift')
    validate_meta(m, (ROOT/'captures/remote'/sid/'points.bin').stat().st_size)
    f = m['frames'][fi]
    raw = np.array(raw[f['offset_points']:f['offset_points']+f['count_points']], dtype='f4'); rows = np.flatnonzero(universe(raw))
    started = time.perf_counter(); point = point_inputs(raw[rows]); template = read(e/'SCAN_TEMPLATE.json')
    prs = [project(raw, template, h, h*4, mode) for mode in ['range', 'axial']]
    image, mapping = image_inputs(raw, rows, prs, h, h*4)
    prep_s = time.perf_counter()-started
    net = Frontend(family, bool(wide)); net.eval(); before = state_sha(net); samples = []
    # All graphs include backward throughput, synthetic scalar only. No optimizer exists.
    for i in range(13):
        start = time.perf_counter(); net.zero_grad(set_to_none=True)
        out = net(point, image, mapping); loss = out['logit'].square().mean()+out['mask_logit'].square().mean()
        loss.backward()
        elapsed = time.perf_counter()-start
        if i >= 3: samples.append(elapsed)
        if time.perf_counter()-started > 290: break
    after = state_sha(net)
    if before != after: raise ValueError('Probe changed state_dict including buffers')
    record = dict(family=family, wide=wide, resolution=[h, h*4], sid=sid, fi=fi, raw=len(raw), U=len(rows),
                  parameters=sum(p.numel() for p in net.parameters()), prep_s=prep_s, step_s=quant(samples),
                  peak_working_set_bytes=peak_bytes(), state_before=before, state_after=after, optimizer_steps=0,
                  role='SYNTHETIC_LOSS_NO_UPDATE_NO_SEMANTIC_PREDICTIONS', times=len(samples), threads=2)
    write(e/'profiles'/f'{family}_{wide}_{h}.json', record)
    print(json.dumps(record), flush=True)


def profiles(e):
    results = []
    for family in ['L3D', 'L2D', 'LFUSION']:
        for wide in [0, 1]:
            for h in [128, 256]:
                cmd = [sys.executable, '-B', '-W', 'error', str(HERE/'run.py'), 'profile_one', '--evidence', str(e), '--family', family, '--wide', str(wide), '--height', str(h)]
                path = e/f'PROFILE_{family}_{wide}_{h}.log'
                with path.open('x', encoding='utf8') as log:
                    try: p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=300); code = p.returncode
                    except subprocess.TimeoutExpired: code = 'TIMEOUT_300s'
                results.append(dict(command=cmd, exit_code=code, log=path.name))
                print(family, wide, h, code, flush=True)
    write(e/'RESOURCE_PROBE_COMMANDS.json', results)
    recs = [read(p) for p in (e/'profiles').glob('*.json')]
    feasible = []
    for h in [256, 128]:
        group = [r for r in recs if r['resolution'][0] == h]
        # Validation <= training step bound; explicit data prep plus 1.5 safety.
        if len(group) != 6: continue
        worst = max((r['step_s']['P95']+r['prep_s'])*1.5 for r in group)
        screen_epoch = worst*(72+24); final_epoch = worst*96
        if max(r['peak_working_set_bytes'] for r in group) <= 4*1024**3 and screen_epoch*10 <= 1800 and final_epoch*15 <= 5400:
            feasible.append(dict(resolution=[h, h*4], E_screen=min(40, int(1800/screen_epoch)), E_final=min(40, int(5400/final_epoch)),
                                 screen_epoch_upper_s=screen_epoch, final_epoch_upper_s=final_epoch))
    write(e/'RESOLVED_CONFIG.json', dict(status='RESOURCE_FROZEN' if feasible else 'RESOURCE_BLOCKED',
                                       config=feasible[0] if feasible else None, label_scores_consumed=False, batch=1, voxel_m=.05, knn=16,
                                       budget=read(PLAN/'EXPERIMENT_BUDGET_V2.json'), probes=len(results),
                                       training='BLOCKED_NO_E1_NO_TRUSTED_LABELS', output_schema='sparse common/projection/member NPZ; no dense embeddings'))


def replay(e, target):
    """Fresh complete geometry pipelines; no prior winners are used as inputs."""
    from sklearn.cluster import HDBSCAN
    manifest = read(e/'RUN_MANIFEST.json')
    if manifest['source_sha256'] != code_hashes(): raise ValueError('Current code drift: create a new run manifest')
    target.mkdir(exist_ok=False)
    cfg = copy.deepcopy(manifest['cfg']); template = read(e/'SCAN_TEMPLATE.json'); split = manifest['split']
    surfaces = {}
    for name, asset, tau in [('old', manifest['backgrounds'][0], manifest['old_tau']), ('new', manifest['backgrounds'][1], manifest['new_tau'])]:
        if sha(asset['path']) != asset['sha256']: raise ValueError('Background drift')
        with np.load(asset['path']) as d: surfaces[name] = FrozenSurfaces(d['xyz'], tau, copy.deepcopy(manifest['controls']))
    groups_ids = ['R1_legacy', 'A', 'G0', 'G1']; stats = {g: [] for g in groups_ids}; projections = []; files = {}; equality = []
    for sid, source in manifest['sources'].items():
        meta, mapped, hashes = load(sid)
        if hashes != source['sha256']: raise ValueError('Source drift')
        empty = sid == split['empty_sid']; frames = split['empty_report'] if empty else range(len(meta['frames']))
        registration = None if empty else read(Path(cfg['background_experiment'])/(sid+'_registration.json'))
        if registration and sha(Path(cfg['background_experiment'])/(sid+'_registration.json')) != manifest['transforms'][str(Path(cfg['background_experiment'])/(sid+'_registration.json'))]: raise ValueError('Transform drift')
        states = {g: CausalSelection(cfg) for g in groups_ids}; events = {g: RecentNonLowEvent(cfg) for g in groups_ids}; previous = {}
        for fi in frames:
            wall = time.perf_counter(); cpu = time.process_time(); f = meta['frames'][fi]
            raw, nominal = frame_points(mapped, f, registration); valid = universe(raw)
            anchor = static_reference_mask(nominal, domain(raw, nominal, cfg), cfg['roi_xy'])
            _, vibration = surfaces['old'].compensate(nominal[anchor], manifest['limits'])
            corrected = nominal@np.array(vibration['R']).T+vibration['t']; fixed_domain = domain(raw, corrected, cfg)
            common = target/'common'/sid/f'{fi:04d}.npz'; common.parent.mkdir(parents=True, exist_ok=True)
            np.savez(common, raw=raw.astype('f4'), nominal=nominal, corrected=corrected, U=valid, source_rows=np.arange(len(raw), dtype='u4'))
            files[common.relative_to(target).as_posix()] = sha(common)
            for h, w in template['resolutions']:
                arrays = {}
                for mode in ['range', 'axial']:
                    pr = project(raw, template, h, w, mode)
                    arrays.update({mode+'_'+k:v for k, v in pr.items()})
                    projections.append(dict(sid=sid, fi=fi, h=h, w=w, mode=mode, **projection_stats(pr, len(raw), h, w)))
                path = target/'projection'/sid/f'{fi:04d}_{h}.npz'; path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(path, **arrays); files[path.relative_to(target).as_posix()] = sha(path)
            prep_wall = time.perf_counter()-wall; prep_cpu = time.process_time()-cpu
            t = f['stamp_sec']+f['stamp_nanosec']*1e-9
            for g in groups_ids:
                start = time.perf_counter(); cp = time.process_time()
                p = nominal if g == 'R1_legacy' else corrected
                if g == 'R1_legacy':
                    dom = domain(raw, p, cfg); distances = np.full(len(raw), np.inf)
                    distances[dom] = surfaces['old'].tree.query(p[dom])[0]
                    fg = np.flatnonzero(dom & (distances > manifest['old_tau']))
                else:
                    fg, _, distances, _, _ = surfaces['old' if g == 'A' else 'new'].split_pose_hypotheses(nominal, p, fixed_domain)
                if g == 'G1' and len(fg):
                    _, centers, inv, _ = voxelize(p[fg], .05)
                    lab = HDBSCAN(min_cluster_size=4, min_samples=4, allow_single_cluster=True, n_jobs=1, copy=True).fit_predict(centers) if len(centers) >= 4 else np.full(len(centers), -1)
                    groups = [ix for k in np.unique(lab) if k >= 0 for ix in [np.flatnonzero(lab[inv] == k)] if len(ix) >= cfg['cluster_min_points']]
                else: groups, _ = cluster(p[fg], cfg)
                ids, identity, posture, reset = states[g].update(t, groups, p, fg)
                sk = skeleton(p[ids], ids, cfg); metrics = node_metrics(sk, previous.get(g), identity, t, cfg)
                previous[g] = dict(sk=sk, identity=identity, t=t)
                event = events[g].update(t, fi, identity, p, ids)
                labels = np.full(len(raw), -1, dtype='i4')
                for j, ix in enumerate(groups): labels[fg[ix]] = j
                selected = np.zeros(len(raw), dtype='u1'); selected[ids] = 1
                # Every predicted row belongs to U; old gates are prediction hypotheses only.
                if not valid[ids].all(): raise ValueError('Prediction outside U')
                path = target/'runs'/g/sid/f'{fi:04d}.npz'; path.parent.mkdir(parents=True, exist_ok=True)
                np.savez(path, selected=selected, cluster=labels)
                files[path.relative_to(target).as_posix()] = sha(path)
                row = dict(sid=sid, fi=fi, variant=g, time=t, source=hashes, source_frame=f,
                           U=int(valid.sum()), K=0, X=int(valid.sum()), semantic='BLOCKED_NO_TRUSTED_GT', selected=len(ids),
                           foreground=len(fg), clusters=len(groups), identity=identity, reset=reset, skeleton=sk, event=event,
                           network_joints='NOT_RUN', display_smoothing='NOT_USED', vibration=vibration,
                           distance_m=float(np.linalg.norm(np.median(p[ids], axis=0))) if len(ids) else None,
                           visibility='UNKNOWN_NO_GT', role='TRAIN_FIT_VISUAL_ONLY' if sid in split['dev_sids'] else 'COMPARE_CONSUMED_GEOMETRY_ONLY',
                           stage_wall_ms=(time.perf_counter()-start)*1000, stage_cpu_ms=(time.process_time()-cp)*1000,
                           shared_wall_ms=prep_wall*1000, shared_cpu_ms=prep_cpu*1000, peak_bytes=peak_bytes(), **metrics)
                path = path.with_suffix('.json'); write(path, row); files[path.relative_to(target).as_posix()] = sha(path)
                stats[g].append({k:v for k, v in row.items() if k not in ['skeleton', 'event', 'source_frame', 'vibration']})
                if g == 'G0':
                    old_path = ROOT/'docs/human_capture/evidence/2026-10-15_hfus_next_dev_r1/runs/B'/sid/f'{fi:04d}_members.npz'
                    with np.load(old_path) as d: old_ids = d['selected']
                    equality.append(dict(sid=sid, fi=fi, equal=bool(np.array_equal(np.sort(ids), np.sort(old_ids))),
                                         added=len(np.setdiff1d(ids, old_ids)), removed=len(np.setdiff1d(old_ids, ids))))
            if fi % 60 == 0: print(sid, fi, 'complete; peak MiB', round(peak_bytes()/1024**2), flush=True)
        print('SESSION COMPLETE', sid, len(list(frames)), flush=True)
        # Rehash the original bytes after each complete session, not just before.
        for name, key in [('meta.json', 'meta'), ('points.bin', 'points')]:
            if sha(ROOT/'captures/remote'/sid/name) != hashes[key]: raise ValueError('Source changed during replay')
    write(target/'ALL_STATS.json', stats); write(target/'PROJECTION_STATS.json', projections)
    write(target/'G0_FROZEN_B_EQUALITY.json', equality)
    write(target/'INDEX.json', dict(schema='hfus-learn-output/1', run_manifest_sha256=sha(e/'RUN_MANIFEST.json'), files=files,
                                    complete_frames=2024, geometry_streams=groups_ids, actual_peak_bytes=peak_bytes(), code=code_hashes()))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('phase', choices=['prepare', 'profiles', 'profile_one', 'replay'])
    p.add_argument('--evidence', type=Path, required=True); p.add_argument('--target', type=Path)
    p.add_argument('--family'); p.add_argument('--wide', type=int); p.add_argument('--height', type=int)
    a = p.parse_args(); e = a.evidence.resolve()
    if a.phase == 'profile_one': profile_one(e, a.family, a.wide, a.height)
    elif a.phase == 'replay': replay(e, a.target.resolve())
    else: globals()[a.phase](e)
