"""Streaming same-frame audit; GT is consumed only after saved inference."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R02 = ROOT / 'docs/human_capture/evidence/2026-10-11_hfus_d05_r2'
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r3'
FROZEN = ROOT / 'docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/base'
RUNS = R02 / 'runs/full'
ARTIFACT = OUT / 'analysis_v1'
ARTIFACT.mkdir(exist_ok=False)

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda: f.read(8*1024*1024), b''): h.update(b)
    return h.hexdigest()

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def rows(p):
    with p.open(encoding='utf-8') as f:
        for line in f: yield json.loads(line)

def accepted(r): return [c for c in r['candidates'] if c['decision'] in ('HUMAN_CANDIDATE','CONFIRMED_HUMAN')]
def union(cs): return set(i for c in cs for i in c['raw_indices'])
def overlap(ids, g):
    n = len(set(ids) & set(g['indices']))
    return {'intersection':n,'coverage':n/len(g['indices']) if g['indices'] else 0,'purity':n/len(ids) if ids else 0}
def best(cs,g):
    return max([dict(id=c['id'],**overlap(c['raw_indices'],g),rejected=c.get('hard_gate_pass') is False,reason=c.get('rejection_reasons',[]),prob=c.get('prob')) for c in cs],key=lambda x:x['intersection'],default=None)

def attribution(r,g):
    G=set(g['indices']); st=r['stages']
    counts={k:len(G&set(st[k])) for k in ('valid_ids','bg_kept_ids','cleanup_kept_ids','final_ids','cleanup_deleted_ids','retained_ids','readmitted_ids')}
    comps=best(r['raw_components'],g); cand=best(r['candidates'],g)
    sid=g['id']; strict=r['strict']
    if sid not in strict['observed_confirmed']['fn_ids']: reason='OBSERVED_STRICT_MATCH'
    elif sid not in strict['accepted']['fn_ids']: reason='7_ASSOCIATION_CONFIRMATION'
    elif sid not in strict['proposal']['fn_ids']: reason='6_CLASSIFIER_REJECTION'
    elif counts['valid_ids']<len(G)*.5: reason='1_RAW_INVALID_INSUFFICIENT'
    elif counts['final_ids']<len(G)*.5 and counts['bg_kept_ids']<len(G)*.5: reason='2_BG_UNKNOWN_LOSS'
    elif counts['final_ids']<len(G)*.5 and counts['cleanup_kept_ids']<len(G)*.5: reason='3_CLEANUP_LOSS'
    elif comps and comps['coverage']>=.5 and comps['purity']>=.8 and comps['rejected']: reason='5_PROPOSAL_QUALITY_GATE'
    else: reason='4_MIXED_COMPONENT' if comps and comps['coverage']>=.5 and comps['purity']<.8 else '4_COMPONENT_FRAGMENTATION_OR_GATE'
    return dict(reason=reason,gt_n=len(G),counts=counts,best_component=comps,best_candidate=cand,
                bg_reasons={k:len(G&set(v)) for k,v in st['reason_ids'].items() if G&set(v)})

def main():
    reports={v:load(RUNS/v/f'R02_{v}_SUMMARY.json') for v in ('base','a06','split')}
    reports['gate']=load(OUT/'runs/gate/R03_gate_SUMMARY.json')
    assert all(len(j['sessions'])==9 for j in reports.values())
    session_results=[]; cases=[]; manual=[]
    with (ARTIFACT/'FAILURE_LEDGER.jsonl').open('x',encoding='utf-8') as ff, (ARTIFACT/'FRAME_COMPARISON.jsonl').open('x',encoding='utf-8') as cf:
        for base_sum in reports['base']['sessions']:
            sid=base_sum['sid']; summaries={v:next(s for s in j['sessions'] if s['sid']==sid) for v,j in reports.items()}
            paths={v:Path(s['ledger']['path']) for v,s in summaries.items()}
            for v,p in paths.items(): assert sha(p)==summaries[v]['ledger']['sha256']
            frozen_path=FROZEN/f'D04_base_{sid}.jsonl'
            meta=load(ROOT/'captures/remote'/sid/'meta.json')
            counts={v:Counter() for v in reports}; sources=Counter(); reasons={v:Counter() for v in reports}; point_totals={v:Counter() for v in reports}; neg={v:Counter() for v in reports}
            timing={v:[] for v in reports}; track={v:{'first':None,'longest_qualified_fn':0,'current_fn':0,'id_changes_contiguous_gt':0,'reacquisition':0,'last_id':None,'last_gt_track':None,'last_gt_frame':-2,'duplicate_ids':0,'max_coast_lost':0,'confirmed_coast_frames':0} for v in reports}
            parity=True; n=0
            streams=[rows(paths[v]) for v in reports]+[rows(frozen_path)]
            for br,ar,sr,gr,fr in zip(*streams,strict=True):
                rr=dict(base=br,a06=ar,split=sr,gate=gr);fi=br['frame_index']; n+=1
                assert fi==n-1
                for r in rr.values(): assert r['sid']==sid and r['frame_index']==fi and r['timestamp_s']==meta['frames'][fi]['bag_time_sec'] and r['raw_n']==meta['frames'][fi]['count_points']
                parity &= all(br['strict'][k]==fr['strict'][k] for k in ('accepted','observed_confirmed')) and br['legacy']==fr['legacy'] and br['candidates']==fr['candidates']
                for g in br['gt']:sources[g['class_name']+'/'+g.get('source','UNKNOWN')]+=1
                frame={'sid':sid,'frame_index':fi,'timestamp':br['timestamp_s'],'qualification':br['qualification'],'variants':{}}
                base_fg=set(br['stages']['final_ids']); base_bg=set(br['stages']['bg_kept_ids']); base_acc=union(accepted(br))
                for v,r in rr.items():
                    if fi>=5:timing[v].append(r['diagnostic_total_ms'])
                    for key in ('proposal','accepted','observed_confirmed'):
                        if r['strict'][key]:
                            for k in ('tp','fp','fn','unmatched_unknown'):counts[v][key+'/'+k]+=r['strict'][key][k]
                    for key in ('accepted','confirmed'):
                        if r['legacy']:
                            for k in ('tp','fp','fn','unmatched_unknown'):counts[v]['legacy_'+key+'/'+k]+=r['legacy'][key].get(k,0)
                    if r['qualification'] in ('UNKNOWN','INVALID_BINDING'):counts[v]['unknown_frames']+=1
                    st=r['stages']; net=set(st['bg_kept_ids'])-base_bg; netfg=set(st['final_ids'])-base_fg; newacc=union(accepted(r))-base_acc
                    human=set(i for g in r['gt'] if g['class_name']=='PERSON' and g['source']=='human' for i in g['indices'])
                    detail={'net_bg_recovery':len(net),'net_final_recovery':len(netfg),'new_accepted_points':len(newacc),'human_supported_net_bg_points':len(net&human),'cleanup_deleted':len(st['cleanup_deleted_ids']),'strict':r['strict'],'split_parents':len(r['split_log'])}
                    point_totals[v].update({k:detail[k] for k in ('net_bg_recovery','net_final_recovery','new_accepted_points','human_supported_net_bg_points','cleanup_deleted','split_parents')});frame['variants'][v]=detail
                    tids=[c['track_id'] for c in r['candidates']];track[v]['duplicate_ids']+=len(tids)-len(set(tids))
                    coasts=[t for t in r['tracks'] if t['human_confirmed'] and t['lost']>0];track[v]['confirmed_coast_frames']+=bool(coasts);track[v]['max_coast_lost']=max([track[v]['max_coast_lost']]+[t['lost'] for t in coasts])
                    for g in r['gt']:
                        if g['class_name']=='FURNITURE':
                            errors=[c['id'] for c in accepted(r) if overlap(c['raw_indices'],g)['purity']>=.8]
                            neg[v][g['source']+'/objects']+=1;neg[v][g['source']+'/accepted_overlaps']+=len(errors)
                            if errors:manual.append({'sid':sid,'f':fi,'class':'FURNITURE','source':g['source'],'candidate_ids':errors,'variant':v,'status':'DRAFT_NO_INDEPENDENT_NEGATIVE_QUALIFICATION'})
                        if g['class_name']!='PERSON':continue
                        a=attribution(r,g);reasons[v][g['source']+'/'+a['reason']]+=1
                        ff.write(json.dumps({'sid':sid,'frame_index':fi,'timestamp':r['timestamp_s'],'variant':v,'gt_id':g['id'],'source':g['source'],**a})+'\n')
                        if g['source']=='human':
                            t=track[v]; ok=a['reason']=='OBSERVED_STRICT_MATCH'
                            contiguous=fi==t['last_gt_frame']+1 and g.get('track_id')==t['last_gt_track'];
                            if not contiguous:t['current_fn']=0;t['last_id']=None
                            if ok:
                                if t['first'] is None:t['first']=fi
                                matching=[c for c in accepted(r) if overlap(c['raw_indices'],g)['coverage']>=.5 and overlap(c['raw_indices'],g)['purity']>=.8 and c['track_confirmed']]
                                tid=matching[0]['track_id'] if matching else None
                                t['reacquisition']+=bool(t['current_fn']);t['id_changes_contiguous_gt']+=bool(tid and t['last_id'] and tid!=t['last_id']);t['last_id']=tid;t['current_fn']=0
                            else:t['current_fn']+=1;t['longest_qualified_fn']=max(t['longest_qualified_fn'],t['current_fn'])
                            t['last_gt_frame']=fi;t['last_gt_track']=g.get('track_id')
                cf.write(json.dumps(frame)+'\n')
                if br['qualification'] not in ('UNKNOWN','INVALID_BINDING'):
                    for v,r in [('a06',ar),('split',sr),('gate',gr)]:
                        before=br if v=='a06' else ar if v=='split' else sr
                        delta=r['strict']['observed_confirmed']['tp']-before['strict']['observed_confirmed']['tp']
                        if delta or (r['strict']['observed_confirmed']['fn'] and any(g['class_name']=='PERSON' and g['source']=='human' for g in r['gt'])):
                            cases.append({'sid':sid,'frame':fi,'timestamp':r['timestamp_s'],'variant':v,'delta_observed_tp':delta,'kind':'SUCCESS' if delta>0 else 'REGRESSION' if delta<0 else 'REMAINING_FAILURE','context':[max(0,fi-5),min(len(meta['frames'])-1,fi+5)]})
            assert n==len(meta['frames'])==base_sum['frames']
            for v in rr:
                for key in ('proposal','accepted','observed_confirmed','legacy_accepted','legacy_confirmed'):
                    for k in ('tp','fp','fn','unmatched_unknown'): assert counts[v][key+'/'+k]==summaries[v][key][k],(sid,v,key,k)
                assert counts[v]['unknown_frames']==summaries[v]['unknown_frames']
            session_results.append({'sid':sid,'frames':n,'frozen_base_exact_terminal_and_candidates':parity,'qualification':'INVALID_BINDING' if sid.endswith('180751') else 'PARTIAL_REVIEWED_BOUND','gt_sources':dict(sources),'variants':{v:{'counts':dict(counts[v]),'reasons':dict(reasons[v]),'point_totals':dict(point_totals[v]),'furniture_diagnostic':dict(neg[v]),'tracking':track[v],'performance':summaries[v]['performance']} for v in reports}})
            print(sid,'audited',n,'base parity',parity,flush=True)
    report={'version':'R03-comparison-v1','sessions':session_results,'limits':['partial GT, contiguous identity metrics only on contiguous same GT track','furniture human/propagated overlap diagnostic; no independent negative qualification','S9 INVALID_BINDING; no formal metrics','Windows instrumentation timings not board runtime','missing GT frames UNKNOWN; not zero FN success']}
    for name,value in [('COMPARISON.json',report),('CASE_INDEX.json',cases),('MANUAL_REVIEW_MINIMAL.json',{'status':'DRAFT','items':manual[:30],'total_engineering_items':len(manual),'binding_missing':'S9 needs real human binding/review; no automatic correction','selection':'first 30 furniture source-separated diagnostics, not independent training negatives'})]:
        with (ARTIFACT/name).open('x',encoding='utf-8') as f:json.dump(value,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
