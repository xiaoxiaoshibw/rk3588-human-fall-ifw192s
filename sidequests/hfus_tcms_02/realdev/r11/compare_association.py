import json
from collections import Counter
from common import ROOT, EV, SK, read, save, jsonlines
from replay import BASE

old=jsonlines(BASE/'frames.jsonl');new=jsonlines(EV/'ASSOCIATION_FRAMES.jsonl')
oldtracks=read(BASE/'TRACKS.json')['tracks'];newtracks=read(EV/'ASSOCIATION_TRACKS.json')

def stats(frames,tracks):
    output={}
    for window in ('ALL','ACTION'):
        rs=frames if window=='ALL' else [r for r in frames if r['phase']=='ACTION']
        candidates=sum(bool(r['candidate_summaries']) for r in rs)
        edges={}
        for a,b in SK.EDGES:
            key=a+'|'+b
            records=[e for r in rs for tr in r['track_results'] for e in tr['edges'] if e['edge']==[a,b]]
            drifts=[d for tr in tracks.values() for d in tr['calibration']['drift_events'] if d['edge']==[a,b] and (window=='ALL' or frames[d['fi']]['phase']=='ACTION')]
            edges[key]=dict(measurements=sum(e['measurement'] is not None for e in records),states=dict(Counter(e['state'] for e in records)),current_measured_calibrated=sum(e['measurement'] is not None and e['state']=='CALIBRATED' for e in records),drift_events=len(drifts))
        output[window]=dict(frames=len(rs),candidate_frames=candidates,six_frames=sum(r['best_valid_nodes']>=6 for r in rs),six_per_all=sum(r['best_valid_nodes']>=6 for r in rs)/len(rs),six_per_candidate=None if not candidates else sum(r['best_valid_nodes']>=6 for r in rs)/candidates,measurement_frames=sum(bool(r['track_results']) for r in rs),track_measurements=sum(len(r['track_results']) for r in rs),ambiguity_frames=sum(bool(r['association']['ambiguous_candidate_ids']) for r in rs),ambiguous_candidate_occurrences=sum(len(r['association']['ambiguous_candidate_ids']) for r in rs),ambiguous_track_occurrences=sum(len(r['association']['ambiguous_track_ids']) for r in rs),unmatched_track_occurrences=sum(len(r['association']['unmatched_track_ids']) for r in rs),edges=edges)
    output['tracks']=dict(total=len(tracks),ever_calibrated_edges=sorted({k for tr in tracks.values() for k,e in tr['calibration']['edges'].items() if e['ever_calibrated']}),drifts=sum(len(tr['calibration']['drift_events']) for tr in tracks.values()))
    return output

save('ASSOCIATION_COMPARISON.json',dict(old=stats(old,oldtracks),new=stats(new,newtracks),delta_frame_file='ASSOCIATION_DIFF.jsonl',comparison='All tracks, all frames; no chosen primary; current measurement vs persisted calibration separate.'))
