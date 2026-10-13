"""Streaming same-frame audit; GT is consumed only after saved inference."""
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
R02 = ROOT / 'docs/human_capture/evidence/2026-10-11_hfus_d05_r2'
OUT = ROOT / 'docs/human_capture/evidence/2026-10-12_hfus_d05_r5'
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
    reports={'base':load(R02/'runs/full/base/R02_base_SUMMARY.json')}
    reports.update({v:load(OUT/'runs'/v/f'R05_{v}_SUMMARY.json') for v in ['control','anchor']})
    assert all(len(r['sessions'])==9 for r in reports.values())
    results=[]; cases=[]; gates=[]
    with (ARTIFACT/'FAILURE_LEDGER.jsonl').open('x',encoding='utf-8') as ff, (ARTIFACT/'FRAME_COMPARISON.jsonl').open('x',encoding='utf-8') as cf:
        for base_sum in reports['base']['sessions']:
            sid=base_sum['sid']; summaries={v:next(s for s in j['sessions'] if s['sid']==sid) for v,j in reports.items()}
            paths={v:Path(s['ledger']['path']) for v,s in summaries.items()}
            for v,p in paths.items(): assert sha(p)==summaries[v]['ledger']['sha256']
            meta=load(ROOT/'captures/remote'/sid/'meta.json'); counts={v:Counter() for v in reports}; reasons={v:Counter() for v in reports}; neg={v:Counter() for v in reports}; points={v:Counter() for v in reports}; sources=Counter(); tracking={v:{'first_confirmed_output':None,'first_qualified_person_match':None,'confirmed_coast_frames':0,'max_coast_lost':0,'duplicate_ids':0,'identity':'BLOCKED_continuous_qualification_missing','exit':'BLOCKED_missing_exhaustive_exit_GT'} for v in reports}; parity=True; n=0; near=[]
            streams=[rows(paths[v]) for v in reports]+[rows(FROZEN/f'D04_base_{sid}.jsonl')]
            for br,cr,ar,fr in zip(*streams,strict=True):
                rr={'base':br,'control':cr,'anchor':ar}; fi=br['frame_index']; n+=1; assert fi==n-1
                for r in rr.values(): assert r['sid']==sid and r['frame_index']==fi and r['timestamp_s']==meta['frames'][fi]['bag_time_sec'] and r['raw_n']==meta['frames'][fi]['count_points'] and r['gt']==br['gt']
                parity &= br['candidates']==fr['candidates'] and br['legacy']==fr['legacy'] and all(br['strict'][k]==fr['strict'][k] for k in ['accepted','observed_confirmed'])
                for g in br['gt']: sources[g['class_name']+'/'+g.get('source','UNKNOWN')]+=1
                frame={'sid':sid,'frame_index':fi,'timestamp':br['timestamp_s'],'qualification':br['qualification'],'variants':{}}
                for v,r in rr.items():
                    for key in ['proposal','accepted','observed_confirmed']:
                        if r['strict'][key]:
                            for k in ['tp','fp','fn','unmatched_unknown']: counts[v][key+'/'+k]+=r['strict'][key][k]
                    for key in ['accepted','confirmed']:
                        if r['legacy']:
                            for k in ['tp','fp','fn','unmatched_unknown']: counts[v]['legacy_'+key+'/'+k]+=r['legacy'][key].get(k,0)
                    counts[v]['unknown_frames']+=r['qualification'] in ['UNKNOWN','INVALID_BINDING']
                    net=set(r['stages']['final_ids'])-set(cr['stages']['final_ids']); removed=set(cr['stages']['final_ids'])-set(r['stages']['final_ids']); accepted_new=union(accepted(r))-union(accepted(cr)); human=set(i for g in r['gt'] if g['class_name']=='PERSON' and g['source']=='human' for i in g['indices'])
                    detail={'strict':r['strict'],'legacy':r['legacy'],'net_retention_final_points_vs_control':len(net),'removed_final_points_vs_control':len(removed),'new_accepted_points_vs_control':len(accepted_new),'human_supported_net_points':len(net&human),'human_supported_removed_points':len(removed&human),'bank_updates':len(r.get('bank_events',{}).get('updates',[]))}; frame['variants'][v]=detail; points[v].update({k:x for k,x in detail.items() if isinstance(x,int)})
                    tr=tracking[v]; ids=[c['track_id'] for c in r['candidates']]; tr['duplicate_ids']+=len(ids)-len(set(ids)); coasts=[t for t in r['tracks'] if t['human_confirmed'] and t['lost']>0]; tr['confirmed_coast_frames']+=bool(coasts); tr['max_coast_lost']=max([tr['max_coast_lost']]+[t['lost'] for t in coasts])
                    if tr['first_confirmed_output'] is None and any(t['human_confirmed'] and t['lost']==0 for t in r['tracks']): tr['first_confirmed_output']=fi
                    if tr['first_qualified_person_match'] is None and r['strict']['observed_confirmed']['tp']: tr['first_qualified_person_match']=fi
                    for g in r['gt']:
                        if g['class_name']=='FURNITURE':
                            neg[v][g['source']+'/objects']+=1; neg[v][g['source']+'/accepted_overlaps']+=sum(overlap(c['raw_indices'],g)['purity']>=.8 for c in accepted(r))
                        if g['class_name']=='PERSON':
                            a=attribution(r,g); reasons[v][g['source']+'/'+a['reason']]+=1; ff.write(json.dumps({'sid':sid,'frame_index':fi,'timestamp':r['timestamp_s'],'variant':v,'gt_id':g['id'],'source':g['source'],**a})+'\n')
                cf.write(json.dumps(frame)+'\n')
                if sid.endswith('175429') and fi in range(220,225): near.append({'frame':fi,'control':cr['strict']['observed_confirmed'],'anchor':ar['strict']['observed_confirmed']})
                if cr['qualification'] not in ['UNKNOWN','INVALID_BINDING']:
                    delta=ar['strict']['observed_confirmed']['tp']-cr['strict']['observed_confirmed']['tp']
                    if delta or cr['strict']['observed_confirmed']['fn'] or ar['strict']['observed_confirmed']['fn']:
                        cases.append({'sid':sid,'frame':fi,'timestamp':cr['timestamp_s'],'variant':'anchor','delta_observed_tp':delta,'kind':'SUCCESS' if delta>0 else 'REGRESSION' if delta<0 else 'REMAINING_FAILURE','context':[max(0,fi-5),min(len(meta['frames'])-1,fi+5)]})
            assert n==len(meta['frames'])==base_sum['frames'] and parity
            for v in reports:
                for key in ['proposal','accepted','observed_confirmed','legacy_accepted','legacy_confirmed']:
                    for k in ['tp','fp','fn','unmatched_unknown']: assert counts[v][key+'/'+k]==summaries[v][key][k],(sid,v,key,k)
                assert counts[v]['unknown_frames']==summaries[v]['unknown_frames']
            strict_ok=counts['anchor']['observed_confirmed/tp']>=counts['control']['observed_confirmed/tp']
            furniture_ok=all(neg['anchor'][k]<=neg['control'][k] for k in ['human/accepted_overlaps','propagated/accepted_overlaps','auto/accepted_overlaps'])
            near_ok=all(x['control']['tp']==x['anchor']['tp']==1 for x in near) if near else True
            benefit=counts['anchor']['observed_confirmed/tp']>counts['control']['observed_confirmed/tp'] or any(neg['anchor'][k]<neg['control'][k] for k in ['human/accepted_overlaps','propagated/accepted_overlaps'])
            gates.append({'sid':sid,'strict_no_regression':strict_ok,'furniture_diagnostic_no_increase':furniture_ok,'near_protected_window':near_ok,'benefit_observed':benefit})
            results.append({'sid':sid,'frames':n,'frozen_base_exact_candidates_terminal':parity,'gt_sources':dict(sources),'near_protected_frames':near,'qualification':'INVALID_BINDING' if sid.endswith('180751') else 'PARTIAL_REVIEWED_BOUND','variants':{v:{'counts':dict(counts[v]),'reasons':dict(reasons[v]),'point_totals':dict(points[v]),'furniture_diagnostic':dict(neg[v]),'tracking':tracking[v]} for v in reports}})
            print(sid,n,'AUDITED',flush=True)
    algorithm_pass=all(g['strict_no_regression'] and g['furniture_diagnostic_no_increase'] and g['near_protected_window'] for g in gates) and any(g['benefit_observed'] for g in gates)
    payload={'version':'R05-comparison-v1','sessions':results,'algorithm_registered_gate':'PASS' if algorithm_pass else 'FAIL','gates':gates,'limits':['GT used only after saved inference','base diagnostic stages from new R02 base proven exact D04 terminal/candidate parity','S9 INVALID_BINDING and missing GT UNKNOWN','furniture human/propagated overlap engineering only, independent negatives BLOCKED','identity/exit BLOCKED, output first confirmation is not human first confirmation','instrument timings excluded from pure performance claims']}
    for name,value in [('COMPARISON.json',payload),('CASE_INDEX.json',cases)]:
        with (ARTIFACT/name).open('x',encoding='utf-8') as f: json.dump(value,f,ensure_ascii=False,indent=2)

if __name__=='__main__':main()
