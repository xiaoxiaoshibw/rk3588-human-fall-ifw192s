"""Read-only closeout and source-bound diagnostics; no training or GT promotion."""
import argparse
import hashlib
import importlib.util
import json
import os
import platform
import subprocess
import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[4]
HERE = Path(__file__).resolve().parent
PS = ROOT/'sidequests/human_fusion_lab_next/pointset/r01'
OLD = ROOT/'docs/human_fall/evidence/2026-10-13_hf_real_04_r1'


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def sha(p):
    h = hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda: f.read(1024*1024), b''):
            h.update(b)
    return h.hexdigest()


def dump(p, value):
    with Path(p).open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)


def module(name, p):
    spec = importlib.util.spec_from_file_location(name, p)
    obj = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


def source(sid):
    folder = ROOT/'captures/remote'/sid
    meta = read(folder/'meta.json')
    hashes = {'meta': sha(folder/'meta.json'), 'points': sha(folder/'points.bin')}
    if meta['point_stride_bytes'] != 28 or (folder/'points.bin').stat().st_size != meta['total_points']*28:
        raise ValueError('source stride/size')
    stamps = [f['stamp_sec']+f['stamp_nanosec']*1e-9 for f in meta['frames']]
    end = 0
    for f in meta['frames']:
        if f['offset_points'] != end or f['count_points'] < 0:
            raise ValueError('source offsets')
        end += f['count_points']
    if end != meta['total_points'] or not np.isfinite(stamps).all() or np.any(np.diff(stamps) <= 0):
        raise ValueError('source time/total')
    buf = np.memmap(folder/'points.bin', dtype='u1', mode='r')
    xyz = np.ndarray((meta['total_points'], 3), dtype='<f4', buffer=buf, strides=(28, 4))
    return meta, xyz, hashes


def baseline(out):
    files, errors = {}, []
    for folder, dirs, names in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d != '.git']
        for name in names:
            p = Path(folder)/name
            if p.is_relative_to(out) or p.is_symlink():
                continue
            try:
                files[p.relative_to(ROOT).as_posix()] = sha(p)
            except OSError as exc:
                errors.append({'path': str(p), 'error': str(exc)})
    def git(*args):
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True, timeout=60).stdout.decode('utf8', errors='replace')
    dump(out/'BASELINE_BEFORE.json', {'files': files, 'errors': errors, 'head': git('rev-parse','HEAD'),
         'branch': git('branch','--show-current'), 'status': git('status','--short'),
         'environment': {'python': sys.version, 'numpy': np.__version__, 'platform': platform.platform()},
         'command': sys.argv, 'skill': 'C:/Users/30680/.codex/skills/ponytail/SKILL.md'})
    print('baseline', len(files), 'files', len(errors), 'errors', flush=True)


def audit(out):
    process = read(OLD/'process.json')
    sid = process['sid']
    meta, raw, hashes = source(sid)
    m = read(OLD/(sid+'_foreground.json'))
    assert m['source'] == {'meta_sha256': hashes['meta'], 'bin_sha256': hashes['points']}
    assert sha(OLD/(sid+'_foreground.bin')) == m['data_sha256']
    assert sha(OLD/(sid+'_source_rows.bin')) == m['rows_sha256']
    points = np.fromfile(OLD/(sid+'_foreground.bin'), dtype='<f4').reshape(-1,4)
    indices = np.fromfile(OLD/(sid+'_source_rows.bin'), dtype='<u4')
    R, t = np.array(m['transform']['R']), np.array(m['transform']['t'])
    records, max_error, valid, predicted, support = [], 0., 0, 0, 0
    for row, f, original in zip(process['rows'], m['frames'], meta['frames']):
        ids = indices[f['offset']:f['offset']+f['count']]
        assert len(ids) == len(set(ids.tolist())) and np.all(ids < original['count_points'])
        xyz = raw[original['offset_points']+ids].astype('f8')@R.T+t
        error = float(np.max(np.abs(xyz-points[f['offset']:f['offset']+f['count'],:3]))) if len(ids) else 0.
        max_error = max(max_error,error)
        assert error < 2e-6
        target_ids = ids[row['source_fg_indices']]
        nodes = row['skeleton']['nodes']
        for node in nodes.values():
            if node['valid']:
                assert node['support_n'] == len(node['support_rows'])
                assert set(node['support_rows']).issubset(set(target_ids.tolist()))
                assert len(node['support_rows']) >= 1
                valid += 1
                support += len(node['support_rows'])
            predicted += int(node.get('display_predicted',False))
        records.append({'frame':row['frame'],'t':row['t'],'target_points':len(target_ids),
                        'current_valid_nodes':sum(n['valid'] for n in nodes.values()),
                        'display_predicted_nodes':sum(n.get('display_predicted',False) for n in nodes.values()),
                        'axis_prior_reference':row['skeleton'].get('axis_prior_reference',False),
                        'source_coordinate_error_max_m':error})
    empty = read(OLD/'cap_20261013_131958_tracking.json')
    comp = read(OLD/'COMPARISON.json')
    summary = {'frames':len(records),'observed':sum(r['observed'] for r in process['rows']),
               'events':process['events'],'confirmed_enabled':process['confirmed_enabled'],
               'current_valid_node_observations':valid,'display_predicted_node_observations':predicted,
               'node_slots_denominator':13*len(records),'current_support_point_memberships':support,
               'source_coordinate_error_max_m':max_error,'weak_frames':[records[i] for i in [47,109,118]],
               'empty_frames':len(empty['rows']),'empty_locked':sum(r['observed'] for r in empty['rows']),
               'empty_events':len(empty['events']),'empty_limitation':'SELF_REFERENCE: all 97 reference frames used in old map',
               'startup_limitation':'r04 prefix frames 0..4 from action; f0..3 use future initialization. Historical diagnostic only.',
               'comparison':comp,'GT':'BLOCKED_NO_REVIEWED_MEMBERSHIP_OR_ANATOMICAL_TRUTH'}
    dump(out/'R04_AUDIT.json',summary)
    with (out/'r04_frame_results.jsonl').open('x',encoding='utf8') as f:
        for row in records:f.write(json.dumps(row)+'\n')
    print('r04 source/node audit',len(records),'frames',flush=True)


def data(out):
    core = module('pointset_contract',PS/'core.py')
    a = read(ROOT/'sidequests/human_fusion_lab/results/AUDIT.json')
    catalog = read(PS/'output/catalog.json')
    sessions, scoring = [], []
    queue = read(ROOT/'docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/09_gt_pending.json')
    review = {'status':'PROPOSED','human_review_completed':False,
              'w03_unknown_points':{'unit':'POINT','count':len(queue['point_ids']),'items':queue['point_ids']},
              'w03_confirmation_rows':{'unit':'COMPARISON_ROW','count':len(queue['confirmation_rows']),'items':queue['confirmation_rows']},
              'w03_viewer':str(ROOT/'docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/09_point_review.html'),
              'windows':[],'hf_real':{'sid':'cap_20261013_094333','frames':list(range(164)),
              'priority_frames':[0,4,10,18,20,40,47,71,72,73,108,109,118,130,163],
              'event_review':'UNVERIFIED_PROTOTYPE; visible body parts UNKNOWN', 'url':'http://127.0.0.1:8932/'}}
    for rec, cat in zip(a['sessions'],catalog['sessions']):
        sid=rec['sid'];meta,raw,hashes=source(sid)
        assert hashes==cat['source_sha256']==rec['input_sha256']
        gt=read(rec['gt_path']);bound=gt.get('session_sha256')==hashes and gt.get('session_id')==sid and sha(rec['gt_path'])==rec['gt_sha256']
        gt_info={k:gt.get(k) for k in ['session_id','session_sha256','review_status','gt_level','uncertain_intervals']}
        issues=[]; counts={'reviewed_person_points':0,'fg_kept':0,'oracle_hits':0,'runtime_hits':0,'runtime_points':0,'furniture':0,'unknown':0,'frames':0}
        frame_manifest=[]
        for fi,f in enumerate(meta['frames']):
            row=read(PS/'output'/sid/f'{fi:04d}.json')
            assert row['frame_index']==fi and row['session_id']==sid and row['source_frame']['offset_points']==f['offset_points']
            for scope in ['full_3d','roi_3d','full_2d','reference']:
                for c in row[scope]:
                    ids=c['source_indices']
                    assert len(ids)==len(set(ids)) and all(type(i) is int and 0<=i<f['count_points'] for i in ids)
            frame_manifest.append({'frame':fi,'timestamp_sec':f['stamp_sec'],'timestamp_nanosec':f['stamp_nanosec'],
                                  'raw_offset_points':f['offset_points'],'raw_count_points':f['count_points'],
                                  'result_sha256':sha(PS/'output'/sid/f'{fi:04d}.json')})
            if not bound:continue
            people=row['metrics']['full_3d']['persons']
            groups=row['full_3d']
            chosen=max(groups,key=lambda c:c['pointnet_prob']*(c['independence']['score_0_100']/100)*np.log1p(c['point_count'])) if groups else None
            known={}
            for p in row['reference']:known[p['id']]=set(p['source_indices'])
            for p in people:
                count=p['reference_count'];hits=len(known.get(p['reference_id'],set()) & set(chosen['source_indices'])) if chosen else 0
                counts['reviewed_person_points']+=count;counts['fg_kept']+=p['fg_kept'];counts['oracle_hits']+=p['intersection'];counts['runtime_hits']+=hits;counts['frames']+=1
                scoring.append({'sid':sid,'frame':fi,'reference_id':p['reference_id'],'denominator':count,
                                'fg_kept':p['fg_kept'],'oracle_best_cluster_hits':p['intersection'],'runtime_selected_cluster':chosen['id'] if chosen else None,
                                'runtime_hits':hits,'fragments':p['fragments_with_reference_points'],'precision':None,'completeness':'PARTIAL',
                                'body_part':'UNKNOWN','multihuman_merge':'UNKNOWN_WITHOUT_EXHAUSTIVE_IDENTITIES'})
            if people and chosen:
                overlaps=chosen.get('reference_overlap',[])
                counts['runtime_points']+=chosen['point_count'];counts['furniture']+=sum(x['intersection'] for x in overlaps if x['class_name']=='FURNITURE')
                counts['unknown']+=chosen['point_count']-sum(x['intersection'] for x in overlaps)
        if bound:
            for key,o in gt.get('objects',{}).items():
                fi=o.get('frame_idx');ids=core.decode_indices(o.get('raw_point_indices',[]))
                if fi is None or not 0<=fi<len(meta['frames']) or (len(ids) and int(max(ids))>=meta['frames'][fi]['count_points']):issues.append(key)
        group=next((k for k,v in a['splits'].items() if sid in v),'UNKNOWN')
        s={'sid':sid,'sha256':hashes,'frames':frame_manifest,'label':{'path':rec['gt_path'],'sha256':sha(rec['gt_path']),
             'binding':'BOUND' if bound else 'INVALID_BINDING','eligible':bool(bound and rec['eligible'] and not issues),
             'metadata_claim':gt_info,'invalid_objects':issues,'completeness':'PARTIAL_NOT_EXHAUSTIVE','provenance_note':'human/propagated metadata; not new independent truth'},
             'coordinate':{'frame':'leveled-IFW192S','units':'m','R':catalog['R'],'t':catalog['T'],
                           'leveling_sha':sha(ROOT/'sidequests/human_fusion_lab/core/leveling.js'),
                           'registration':'COMMON_REF_RT_ASSUMPTION_NOT_PHYSICAL_VERIFICATION'},
             'roi':{'polygon':catalog['roi_xy'],'status':catalog['roi_status'],'config_sha':sha(PS/'config.yaml')},
             'background':{'path':str(PS/'output/background.json'),'sha256':sha(PS/'output/background.json'),'npz_sha256':sha(PS/'output/background.npz')},
             'split':group,'prospective_holdout':False,'metrics':counts}
        if sid.endswith('180557'):
            s['roi_issue']={'status':'PENDING_USER_COORDINATE_REVIEW','roi_candidate_frames':sum(x['roi_clusters']>0 for x in read(PS/'output'/sid/'summary.json')['frames']),
                            'reference_roi_fractions':[p['roi_point_fraction'] for fi in [0,10,100,300,522] for p in read(PS/'output'/sid/f'{fi:04d}.json')['reference']],
                            'roi_unchanged':True}
        if not bound:s['recovery']='No matching source binding; no rebinding or SHA rewriting performed'
        sessions.append(s)
        suggested=[0,min(10,len(meta['frames'])-1),len(meta['frames'])//2,len(meta['frames'])-1]
        if sid.endswith('180235'):suggested=[98,110,128,187,188]
        if sid.endswith('175943'):suggested=[0,52,117,162]
        review['windows'].append({'sid':sid,'frames':suggested,'activity':rec['activity'],'status':'PROPOSED',
                                  'url':f'http://127.0.0.1:8941/?sid={sid}&fi={suggested[0]}','body_parts':'UNKNOWN'})
        print('bound data',sid,bound,flush=True)
    # Bounded search: only capture and GT roots, no network/capture or new recording substitution.
    wanted=['cap_20261007_215623','cap_20261007_215643','cap_20261007_233658']
    roots=[ROOT/'captures',ROOT/'pc_apps/human_replay/gt_store',Path('D:/Code/radar/radar_capture_data')]
    matches={sid:[] for sid in wanted}
    for base in roots:
        if not base.exists():continue
        for folder,dirs,names in os.walk(base):
            for sid in wanted:
                if sid in folder and 'points.bin' in names:matches[sid].append(str(Path(folder)/'points.bin'))
    dump(out/'INPUT_MANIFEST.json',{'schema':'hf-real-input/1','sessions':sessions,'missing_search':{'roots':[str(p) for p in roots],
         'matches':matches,'status':{k:'FOUND' if v else 'DATA_BLOCKED' for k,v in matches.items()}},
         'source_index_semantics':'frame-local raw 28-byte record index; offset preserved','scoring_policy':'BOUND PARTIAL overlap only; no pure human precision PASS',
         'split_note':'historical train/validation/test/stress groups; not new holdout','S9':'INVALID_BINDING; original pair must be recovered or newly human reviewed'})
    dump(out/'REVIEW_QUEUE.json',review)
    with (out/'pointset_frame_results.jsonl').open('x',encoding='utf8') as f:
        for row in scoring:f.write(json.dumps(row)+'\n')
    dump(out/'POINTSET_METRICS.json',{'sessions':[{'sid':s['sid'],**s['metrics']} for s in sessions],
         'runtime_selector':'existing page PointNet probability * independence * log1p(count); no GT in selection',
         'oracle':'GT best cluster upper bound; distinct from runtime','precision':'BLOCKED_PARTIAL_LABELS'})


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['baseline','audit','data']);p.add_argument('--out',required=True);args=p.parse_args()
    out=Path(args.out).resolve();out.mkdir(parents=True,exist_ok=True)
    globals()[args.mode](out)
