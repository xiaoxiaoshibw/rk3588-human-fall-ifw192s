"""DET-06 evidence 01 data conditions + 02 protocol freeze record. Read-only inputs, no model."""
import json
from datetime import datetime, timezone
from pathlib import Path

from experiment import sha

ROOT = Path(__file__).resolve().parent
WORK = ROOT.parents[1]
PRE = ROOT / 'artifacts/det06_prepared_r1'
EV = WORK / 'docs/sidequests/evidence/2026-10-08_det06_r1'
DATA = Path('D:/Code/ldiar/captures/remote')

CONFIRM = ('用户 2026-10-08 会话确认：第二人 = C1（与之前四段为不同的人）；动作 = 站/举手；'
           '同一房间、雷达安装未移动；114819 空场模板确认全程无人；其余未录制采集暂不使用。')


def main():
    m = json.loads((PRE / 'manifest.json').read_text(encoding='utf-8'))
    sessions = []
    for s in m['sessions']:
        meta = json.loads((DATA / s['sid'] / 'meta.json').read_text(encoding='utf-8'))
        pts = sorted(f['points'] for f in s['frames'])
        sessions.append(dict(sid=s['sid'], name=s['name'], role=s['role'], frames=len(s['frames']),
                             duration_sec=meta['duration_sec'], source=s['source'],
                             transform_sha256=s['transform_sha256'],
                             leveling_recommended=s['leveling_recommended'],
                             rel_to_empty_deg=s.get('rel_to_empty_deg'), rel_to_empty_t_m=s.get('rel_to_empty_t_m'),
                             prepared_points=dict(min=pts[0], median=pts[len(pts) // 2], max=pts[-1])))
    value = dict(created_utc=datetime.now(timezone.utc).isoformat(), client_date='2026-10-08',
                 user_confirmation=CONFIRM, data_root=str(DATA),
                 prepared_manifest_sha256=sha(PRE / 'manifest.json'), sessions=sessions,
                 dev_sessions=['cap_20261007_215540', 'cap_20261007_215607', 'cap_20261007_215623',
                               'cap_20261007_215643'],
                 empty_old='cap_20261007_233658',
                 note='new sessions prepared from read-only captures; no uploads/deploy/model')
    with (EV / '01_data_conditions.json').open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
    protocol = dict(plan_sha256=sha(WORK / 'docs/sidequests/DET06_PLAN.md'),
                    acceptance_sha256=sha(WORK / 'docs/sidequests/DET06_ACCEPTANCE.md'),
                    input='per-session TLS leveling; z-1.73; intensity/1023; voxel 0.16x0.16x4; 32 pts/pillar',
                    arms=['first32 (main)', 'z_rank32 (aux, no selection)'],
                    eval_region='workspace crop consistent with B_workspace: z in [0.1,2.5]m, r in [0.35,25]m; out-of-region boxes listed separately',
                    matching=dict(primary_center_m=.55, aux_bev_iou=.5),
                    fp_budget_frames=[.1, .5, 1.0],
                    score=.1, nms=.01, top100=100, max50=50, model_z=-1.73, intensity_divisor=1023,
                    test_frames='24 C1 frames (6 evenly spread per session)',
                    empty_frames='114819 six spread + 233658 [17,35,53]',
                    dev_frames='four 2026-10-07 representative frames 32/33/33/28 for pipeline reproduction only',
                    note='frozen before any model forward this round; no calibration claims')
    with (EV / '02_protocol_freeze.json').open('x', encoding='utf-8') as f:
        json.dump(protocol, f, ensure_ascii=False, indent=2)
    print('01 written: %d sessions; 02 written' % len(sessions))


if __name__ == '__main__':
    main()
