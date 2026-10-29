"""Raw depth corpus runner with a strictly separate author-label proxy report.

Can consume completed per-file download manifests while the known downloader
is running. An explicit bounded wait is required; partial/failed inputs stay in
the report and are never silently removed from the 30/40 denominators.
"""
import argparse
import csv
import json
import math
from pathlib import Path
import time

from fall_candidate_runtime import file_sha256
from urfall_raw_depth import run, SETTINGS, load_pinhole


def evaluate(root, extra_depth, calibration, out, wait_seconds=0., ground_start_fraction=.6,scene_references=None):
    if (not math.isfinite(wait_seconds) or wait_seconds < 0 or
            not math.isfinite(ground_start_fraction) or not .5 <= ground_start_fraction < 1.):
        raise ValueError('Invalid bounded wait or ground input fraction')
    out.mkdir(parents=True, exist_ok=False)
    expected = ['%s-%02d' % (kind, i) for kind, count in (('fall', 30), ('adl', 40)) for i in range(1, count+1)]
    protocol = dict(expected=expected, camera=load_pinhole(calibration),
                    settings=dict(SETTINGS,ground_start_fraction=ground_start_fraction),
                    primary_scope='raw PNG depth -> extracted target -> geometry; no labels at inference',
                    evaluation_scope='post-hoc posture transition proxy; not physical event recall',
                    wait_seconds=wait_seconds, camera_sha256=file_sha256(calibration))
    if scene_references is not None:
        protocol['scene_references']=dict(path=str(scene_references),required_for_each_sequence=True,
                                         missing='explicit failure; no fallback')
    (out/'PROTOCOL.json').write_text(json.dumps(protocol, indent=2), encoding='utf-8')
    with (root/'DOWNLOAD.json').open(encoding='utf-8') as stream:
        initial_downloads = {r['name']:r for r in json.load(stream)}
    completed, deadline = {}, time.monotonic()+wait_seconds
    while True:
        for seq in expected:
            if seq in completed:
                continue
            name = seq+'-cam0-d.zip'
            if name in initial_downloads:
                meta, archive = initial_downloads[name], root/name
            else:
                meta_path = extra_depth/(name+'.json')
                if not meta_path.exists():
                    continue
                try:
                    meta = json.loads(meta_path.read_text(encoding='utf-8'))
                except json.JSONDecodeError:
                    continue  # Writer is still finishing this small manifest.
                archive = extra_depth/name
            if meta.get('status') != 'OK':
                completed[seq] = dict(sequence=seq, status='DOWNLOAD_FAILED', details=meta)
                continue
            if file_sha256(archive) != meta['sha256']:
                completed[seq] = dict(sequence=seq, status='INPUT_SHA_MISMATCH')
                continue
            try:
                reference=None if scene_references is None else scene_references/seq/'REFERENCE.json'
                if reference is not None and not reference.is_file():
                    completed[seq]=dict(sequence=seq,status='SCENE_REFERENCE_NOT_PROVIDED')
                    continue
                summary = run(archive, root/(seq+'-data.csv'), calibration, out/seq,
                              ground_start_fraction=ground_start_fraction,scene_reference_path=reference)
                completed[seq] = dict(sequence=seq, status='OK', summary=summary)
            except Exception as error:
                completed[seq] = dict(sequence=seq, status='RUN_FAILED', error=repr(error))
            (out/'STATUS.json').write_text(json.dumps(dict(completed=len(completed), expected=70,
                sequences={s:r['status'] for s,r in completed.items()}), indent=2), encoding='utf-8')
        if len(completed) == len(expected) or time.monotonic() >= deadline:
            break
        time.sleep(1.)
    for seq in expected:
        if seq not in completed:
            completed[seq] = dict(sequence=seq, status='INPUT_NOT_READY_WITHIN_WAIT')
    # Author feature/pose tables are opened only after raw inference has finished.
    references = {}
    for name in ('urfall-cam0-falls.csv', 'urfall-cam0-adls.csv'):
        with (root/name).open(encoding='utf-8', newline='') as stream:
            for row in csv.reader(stream):
                references.setdefault(row[0], []).append((int(row[1]), int(row[2])))
    from urfall_geometry_proxy import read_sync
    results = []
    for seq in expected:
        record = completed[seq]
        if record['status'] != 'OK':
            results.append(dict(sequence=seq, status=record['status'], proxy_matched=False,
                                details={k:v for k,v in record.items() if k not in ('sequence','status')}))
            continue
        summary = record['summary']
        sync = read_sync(root/(seq+'-data.csv'))
        labels = references[seq]
        low = [sync[f] for f,label in labels if label == 1 and f in sync]
        first_low = min(low) if low else None
        transition = [sync[f] for f,label in labels if label == 0 and f in sync and
                      first_low is not None and sync[f] < first_low]
        onset = min(transition) if transition else None
        matched = [e for e in summary['events'] if onset is not None and onset <= e['alarm_s'] <= first_low+1.5]
        results.append(dict(sequence=seq, status='OK', frames=summary['frames'], target_frames=summary['target_frames'],
                            extraction_states=summary['extraction_states'], geometry_states=summary['geometry_states'],
                            events=summary['events'], posture_onset_proxy_s=onset, first_lying_label_s=first_low,
                            proxy_matched=bool(matched), proxy_latency_s=matched[0]['alarm_s']-onset if matched else None))
    result = dict(expected_fall_sequences=30, expected_adl_sequences=40,
                  completed_sequences=sum(r['status']=='OK' for r in results),
                  raw_fall_proxy_hits=sum(r['sequence'].startswith('fall') and r['proxy_matched'] for r in results),
                  raw_adl_sequences_with_candidate=sum(r['sequence'].startswith('adl') and bool(r.get('events')) for r in results),
                  failure_counts={s:sum(r['status']==s for r in results) for s in sorted(set(r['status'] for r in results))},
                  results=results, physical_event_recall='UNKNOWN', subject_split='UNKNOWN',
                  raw_person_precision_recall='UNKNOWN', IFW192S_effectiveness='UNKNOWN',
                  input_labels_sha256={name:file_sha256(root/name) for name in ('urfall-cam0-falls.csv','urfall-cam0-adls.csv')},
                  code_sha256=file_sha256(Path(__file__)))
    (out/'SUMMARY.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k not in ('results','input_labels_sha256')}, allow_nan=False), flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--extra-depth', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--wait-seconds', type=float, default=0.)
    parser.add_argument('--ground-start-fraction', type=float, default=.6)
    parser.add_argument('--scene-references',type=Path)
    args = parser.parse_args()
    evaluate(args.root,args.extra_depth,args.calibration,args.output,args.wait_seconds,
             args.ground_start_fraction,args.scene_references)
