"""DET-06 fix round: freeze gt_eval_v2 (person z_min artifact fix) from the user-confirmed proposal.
Offline. v1 stays untouched; v2 supersedes it for 3D box reporting only (BEV metrics do not use z)."""
import argparse
import json
from pathlib import Path

from experiment import sha

ROOT = Path(__file__).resolve().parent
DET06 = ROOT / 'artifacts/det06_r1'
FIX = ROOT / 'artifacts/det06_fix_r1'

NEW_CONFIRMATION = (
    "\n\n(5) 修复轮确认（2026-10-08 会话，用户对修复轮收尾问题以多选项选择回复）：\n"
    "    冻结 gt_eval_v2（z_min 0.10）：用户选中\"冻结 gt_eval_v2（z_min 0.10）\"。\n"
    "    fixture #0 高度勘误：点云连通结构止于 1.41–1.45 m；1.9 m 高度的点属于距其质心 0.40 m 的相邻结构；"
    "用户选中\"按勘误记录（1.41 m）\"。\n"
    "    DET-07 预注册：用户选中\"起草（不执行）\"；预注册文件为草案，执行需另行授权。")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--evidence', type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=False)
    v1 = json.loads((DET06 / 'frozen/gt_eval_v1.json').read_text(encoding='utf-8'))
    prop = json.loads((FIX / 'gt_proposal/gt_v2_proposal.json').read_text(encoding='utf-8'))
    assert prop['status'].startswith('PROPOSAL')
    frames = []
    zs = []
    for f in v1['test_frames']:
        p = prop['person']['%s|%d' % (f['sid'], f['index'])]
        b = dict(f['box'])
        assert abs(b['aabb_min'][2] - p['old']) < 1e-9, 'proposal/v1 z_min mismatch'
        assert abs(p['z_top'] - b['z_top']) < 1e-9, 'z_top must not change'
        assert 0.09 <= p['v2'] <= 0.12 and p['n_below_old'] > 0
        b['aabb_min'] = [b['aabb_min'][0], b['aabb_min'][1], p['v2']]
        frames.append(dict(f, box=b))
        zs.append(p['v2'])
    assert len(frames) == 24
    v2 = dict(version='v2', created='2026-10-08', user_confirmation=v1['user_confirmation'] + NEW_CONFIRMATION,
              test_frames=frames, empty_frames=v1['empty_frames'],
              hard_negative_structures=v1['hard_negative_structures'], hardneg_frame=v1['hardneg_frame'],
              provenance=dict(v1_sha256=sha(DET06 / 'frozen/gt_eval_v1.json'),
                              proposal_sha256=sha(FIX / 'gt_proposal/gt_v2_proposal.json'),
                              freeze_script_sha256=sha(Path(__file__))),
              note='v2 supersedes v1 for 3D reporting only: person box z_min is the lowest B-workspace point '
                   '(z>=0.10) inside the v1 AABB footprint (empty-template-mask artifact removed). Centres, xy '
                   'extents, z_top, empty frames and hard-negative structures are unchanged; BEV metrics are '
                   'unaffected. v1 preserved.')
    p = a.out / 'gt_eval_v2.json'
    with p.open('x', encoding='utf-8') as fh:
        json.dump(v2, fh, ensure_ascii=False, allow_nan=False, indent=2)
    files = [dict(path=x.name, sha256=sha(x)) for x in sorted(a.out.rglob('*')) if x.is_file()]
    manifest = dict(gt_sha256=sha(p), files=files, test_frames=len(frames),
                    z_min=dict(min=min(zs), max=max(zs)), note='frozen from user-confirmed fix-round proposal')
    (a.out / 'freeze_manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    a.evidence.mkdir(parents=True, exist_ok=True)
    (a.evidence / 'frozen_v2_summary.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2),
                                                       encoding='utf-8')
    print('FROZEN v2 test=%d z_min %.4f..%.4f sha=%s' % (len(frames), min(zs), max(zs),
                                                         manifest['gt_sha256'][:16]))


if __name__ == '__main__':
    main()
