"""DET-05 freeze: no overrides, write labels_v1/gt_v1/freeze manifest + 03b confirmation record. No network."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
ANN = ROOT / 'artifacts/det05_r1/annotate'
PRE = ROOT / 'artifacts/det02_prepared_r1'
LABEL_FRAMES = [('cap_20261007_215540', 32), ('cap_20261007_215607', 33), ('cap_20261007_215623', 33),
                ('cap_20261007_215643', 3), ('cap_20261007_215643', 7), ('cap_20261007_215643', 11),
                ('cap_20261007_215643', 12), ('cap_20261007_215643', 17), ('cap_20261007_215643', 28),
                ('cap_20261007_215643', 37)]


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--confirm-file', type=Path, required=True)
    args = parser.parse_args()
    args.confirm_text = args.confirm_file.read_text(encoding='utf-8').strip().splitlines()[0]
    out = args.out.resolve()
    evidence = args.evidence.resolve()
    out.mkdir(parents=True, exist_ok=False)
    author = json.loads((evidence / '03_annotation_author.json').read_text(encoding='utf-8'))
    author_by = {(f['sid'], f['index']): f for f in author['frames']}
    pre_manifest = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    transforms = {s['sid']: s['transform_sha256'] for s in pre_manifest['sessions']}
    labels, gts, proposal_files = {}, {}, []
    for sid, index in LABEL_FRAMES:
        proposal = json.loads((ANN / ('ann_%s_%d.json' % (sid, index))).read_text(encoding='utf-8'))
        assert sha(ANN / ('ann_%s_%d.json' % (sid, index))) == author_by[(sid, index)]['json_sha256']
        assert proposal['needs_manual'] is False and proposal['human_component_id'] is not None
        prepared, raw, cls = proposal['points']['prepared_rows'], proposal['points']['raw_rows'], proposal['points']['cls']
        assert len(prepared) == len(raw) == len(cls) == proposal['scope_n']
        counts = {name: cls.count(name) for name in ('human', 'furniture', 'mixed_uncertain')}
        assert counts == author_by[(sid, index)]['counts'], (counts, author_by[(sid, index)]['counts'])
        human = [i for i, c in enumerate(cls) if c == 'human']
        hp = [prepared[i] for i in human]
        hr = [raw[i] for i in human]
        gt = proposal['gt_proposal']
        assert gt['n_human'] == len(hp)
        labels['%s|%d' % (sid, index)] = dict(sid=sid, index=index, prepared_rows=prepared, raw_rows=raw, cls=cls,
                                              proposal_sha256=sha(ANN / ('ann_%s_%d.json' % (sid, index))))
        gts['%s|%d' % (sid, index)] = dict(sid=sid, index=index, human_prepared_rows=hp, human_raw_rows=hr,
                                           n_human=len(hp), centroid_xy=gt['centroid_xy'], z_top=gt['z_top'],
                                           aabb_min=gt['aabb_min'], aabb_max=gt['aabb_max'],
                                           proposal_sha256=labels['%s|%d' % (sid, index)]['proposal_sha256'])
        proposal_files.append(dict(path=str((ANN / ('ann_%s_%d.json' % (sid, index))).relative_to(WORK)).replace('\\', '/'),
                                   sha256=labels['%s|%d' % (sid, index)]['proposal_sha256']))
    assert len(labels) == 10
    frozen = dict(version='v1', frozen_utc=datetime.now(timezone.utc).isoformat(), overrides=[],
                  confirm_text=args.confirm_text, channel='opencode session question tool, 2026-10-08',
                  frame_set=[[sid, index] for sid, index in LABEL_FRAMES], labels=labels)
    with (out / 'labels_v1.json').open('x', encoding='utf-8') as f:
        json.dump(frozen, f, ensure_ascii=False, allow_nan=False)
    gt = dict(version='v1', frozen_utc=frozen['frozen_utc'], confirm_text=args.confirm_text,
              gt_rule='centroid=mean xy of human points; z_top=max z; aabb=min/max xyz of human points; rows bound to prepared frame and raw capture',
              frames=gts)
    with (out / 'gt_v1.json').open('x', encoding='utf-8') as f:
        json.dump(gt, f, ensure_ascii=False, allow_nan=False)
    manifest = dict(version='v1', frozen_utc=frozen['frozen_utc'], confirm_text=args.confirm_text,
                    overrides=[], frames=len(gts), human_total=sum(g['n_human'] for g in gts.values()),
                    proposal_files=proposal_files, transform_sha256_by_session=transforms,
                    seed_sha256=author['seed_sha256'], pre_manifest_sha256=author['pre_manifest_sha256'],
                    fg_manifest_sha256=author['fg_manifest_sha256'],
                    files=[dict(path=str(p.relative_to(WORK)).replace('\\', '/'), sha256=sha(p))
                           for p in [out / 'labels_v1.json', out / 'gt_v1.json']])
    with (out / 'freeze_manifest.json').open('x', encoding='utf-8') as f:
        json.dump(manifest, f, ensure_ascii=False, allow_nan=False, indent=2)
    with (evidence / '03b_confirmation.log').open('x', encoding='utf-8') as f:
        f.write('DET-05 user confirmation, %s\n' % frozen['frozen_utc'])
        f.write('Channel: opencode session question tool, 2026-10-08\n')
        f.write('Question: 10 帧人体点初标是否确认？\n')
        f.write('Answer: %s\n' % args.confirm_text)
        f.write('Overrides applied: none (proposal v1 = frozen labels v1)\n')
    with (evidence / '03c_freeze.json').open('x', encoding='utf-8') as f:
        json.dump(dict(manifest=manifest, labels_sha256=sha(out / 'labels_v1.json'),
                       gt_sha256=sha(out / 'gt_v1.json'), freeze_manifest_sha256=sha(out / 'freeze_manifest.json')),
                  f, ensure_ascii=False, allow_nan=False, indent=2)
    print('FREEZE PASS: 10 frames, %d human points, no overrides, confirm=%r' %
          (manifest['human_total'], args.confirm_text))


if __name__ == '__main__':
    main()
