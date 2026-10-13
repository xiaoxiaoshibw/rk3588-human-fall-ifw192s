"""DET-06: freeze gt_eval_v1 (boxes + frame lists) from confirmed annotation proposal. No model."""
import argparse
import json
from pathlib import Path

from experiment import sha

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--ann', type=Path, required=True)
    p.add_argument('--prepare', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--confirmation-file', type=Path, required=True)
    a = p.parse_args()
    confirmation = a.confirmation_file.read_text(encoding='utf-8').strip()
    ann = json.loads((a.ann / 'ann_manifest.json').read_text(encoding='utf-8'))
    assert not any(f['needs_manual'] for f in ann['frames']), 'annotation manifest has manual frames'
    test_frames = []
    for f in ann['frames']:
        payload = json.loads((a.ann / f['json']).read_text(encoding='utf-8'))
        assert not payload['needs_manual'] and payload['gt_proposal'] is not None
        assert payload['provenance']['pre_manifest_sha256'] == sha(a.prepare / 'manifest.json')
        test_frames.append(dict(sid=f['sid'], index=f['index'], name=payload['name'],
                                box=payload['gt_proposal'], rows=payload['person_rows'],
                                ann_json=f['json'], ann_json_sha256=f['json_sha256'],
                                ann_png=f['png'], ann_png_sha256=f['png_sha256']))
    empty = [dict(sid=e['sid'], index=e['index'])
             for e in ann['empty_frames']['new'] + ann['empty_frames']['old']]
    hard = json.loads((WORK / ann['hardneg']['json']).read_text(encoding='utf-8'))
    a.out.mkdir(parents=True, exist_ok=False)
    gt = dict(version='v1', created='2026-10-08', user_confirmation=confirmation,
              test_frames=test_frames, empty_frames=empty,
              hard_negative_structures=hard['structures'], hardneg_frame=dict(sid=hard['sid'], index=hard['index']),
              provenance=dict(annotation_manifest_sha256=sha(a.ann / 'ann_manifest.json'),
                              annotation_script_sha256=ann['script_sha256'],
                              prepare_manifest_sha256=sha(a.prepare / 'manifest.json')),
              note='box GT only; frozen after user confirmation; no later edits')
    with (a.out / 'gt_eval_v1.json').open('x', encoding='utf-8') as f:
        json.dump(gt, f, ensure_ascii=False, allow_nan=False, indent=2)
    frozen_files = [dict(path=str(p.relative_to(a.out)).replace('\\', '/'), sha256=sha(p))
                    for p in sorted(a.out.rglob('*')) if p.is_file()]
    manifest = dict(gt_sha256=sha(a.out / 'gt_eval_v1.json'), confirmation=confirmation,
                    frozen_files=frozen_files)
    with (a.out / 'freeze_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, allow_nan=False, indent=2)
    summary = dict(tag='03c_freeze', gt_sha256=manifest['gt_sha256'],
                   test_frames=len(test_frames), empty_frames=len(empty),
                   hard_negative_structures=len(gt['hard_negative_structures']), confirmation=confirmation)
    with (a.evidence / '03c_freeze.json').open('x', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, allow_nan=False, indent=2)
    print('FROZEN test=%d empty=%d hard=%d gt_sha=%s' %
          (len(test_frames), len(empty), len(gt['hard_negative_structures']), manifest['gt_sha256'][:12]))


if __name__ == '__main__':
    main()
