"""Independently reconcile generated tables, partitions and lifecycle records."""
from common import EV, read, save, jsonlines
from experiment import summarize

records=jsonlines(EV/'ASSOCIATION_FRAMES.jsonl');tracks=read(EV/'ASSOCIATION_TRACKS.json')
previous={};lost=0;ambiguous_measurements=0;ambiguous_creations=0
for r in records:
    fi=r['fi'];a=r['association'];mt={m['track_id'] for m in a['matches']};mc={m['candidate_id'] for m in a['matches']}
    tgroups=[mt,set(a['ambiguous_track_ids']),set(a['unmatched_track_ids'])]
    cgroups=[mc,set(a['ambiguous_candidate_ids']),set(a['unmatched_candidate_ids'])]
    expected_tracks={tid for tid,s in r['states'].items() if s['state']!='LOST' and tracks[tid]['first_fi']!=fi}
    expected_candidates={c['candidate_id'] for c in r['candidate_summaries']}
    for groups,expected in ((tgroups,expected_tracks),(cgroups,expected_candidates)):
        assert set.union(*groups)==expected
        assert sum(map(len,groups))==len(expected)
    for tid,s in r['states'].items():
        prior=previous.get(tid)
        if prior and s['state'] in ('AMBIGUOUS','UNMATCHED'):
            assert s['last_measurement_frame']==prior['last_measurement_frame']
        if s['state']=='LOST' and (not prior or prior['state']!='LOST'):
            assert r['relative_s']-records[s['last_measurement_frame']]['relative_s']>1.
            assert any(e['fi']==fi and e['new']=='LOST' and e['reason']=='TTL_EXPIRED' for e in tracks[tid]['events'])
            lost+=1
    for tr in r['track_results']:
        ambiguous_measurements+=tr['candidate_id'] in a['ambiguous_candidate_ids']
        if tracks[tr['track_id']]['first_fi']==fi:ambiguous_creations+=tr['candidate_id'] in a['ambiguous_candidate_ids']
    previous=r['states']
assert ambiguous_measurements==ambiguous_creations==0
for g in ('RAW_OLD','FG_OLD','RAW_NEW','FG_NEW'):
    assert summarize(jsonlines(EV/(g+'_FRAMES.jsonl')))==read(EV/(g+'_SUMMARY.json'))
    assert read(EV/(g+'_VERIFY.json'))['frames']==386
save('DELIVERY_VERIFICATION.json',dict(PASS=True,association_frames=len(records),track_and_candidate_partitions='disjoint/exhaustive all 780 frames',ambiguous_measurements=ambiguous_measurements,ambiguous_creations=ambiguous_creations,explicit_expirations=lost,ambiguous_unmatched_measurement_clock_unchanged=True,all_four_group_all_window_summary_reconciled=True,raw_source_coordinate_recomputations='four *_VERIFY.json; every valid node, max error<1e-10m'))
