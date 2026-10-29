"""Continue an immutable candidate package after an actual user confirmation.

This is never invoked by the AI to manufacture HUMAN_CONFIRMATION. Request must
come from actual user review of the package URL/version; synthetic tests use Engine.
"""
import argparse
import json
from pathlib import Path
import shutil
import numpy as np
from scipy.spatial import cKDTree
from contracts import ROOT, Source, new_output, write_new, save_array, sha, digest,verify_ai_review
from pipeline import FrozenMap, Engine
from server import Replay


def load_map(path):
    meta=json.loads((path/'map/MAP.json').read_text(encoding='utf8'))
    m=FrozenMap.__new__(FrozenMap)
    m.binding=meta['source_sha256'];m.coordinate=meta['coordinate'];m.protocol=meta['protocol'];m.build=meta['build'];m.map_id=meta['map_id']
    with np.load(path/'map/surfaces.npz') as z:m.arrays={k:z[k] for k in z.files}
    for name,key in [('centers','centers'),('noise','noise'),('minimum','minimum'),('maximum','maximum'),('count','count'),('frames','frame_count'),('first','first_fi'),('last','last_fi'),('eligible','eligible'),('tree_ids','tree_ids'),('support_global','support_global'),('indptr','indptr')]:setattr(m,name,m.arrays[key])
    m.n=len(m.centers);m.tree=cKDTree(m.arrays['matching_tree_xyz']) if len(m.tree_ids) else None
    if m.tree is not None:m.arrays['matching_tree_xyz']=m.tree.data
    for a in m.arrays.values():a.setflags(write=False)
    if m.fingerprint()!=m.map_id:raise ValueError('Frozen map fingerprint mismatch')
    return m


def execute(run,request_path,output,allow_ai=False):
    replay=Replay(run);env=json.loads((run/'ENVIRONMENT.json').read_text(encoding='utf8'))
    for name,h in env['source_sha256'].items():
        if sha(ROOT/name)!=h:raise ValueError('Candidate code/dependency changed; user confirmation invalid')
    request=json.loads(request_path.read_text(encoding='utf8'))
    human=request.get('provenance')=='HUMAN_CONFIRMATION' and request.get('actual_user_review_evidence')
    ai=allow_ai and request.get('provenance')=='AI_VISUAL_REVIEW' and request.get('human_confirmation') is False and request.get('user_delegation_evidence') and request.get('visual_review_evidence')
    if not (human or ai) or not request.get('candidate_url'):
        raise ValueError('Actual user package review evidence required; no automatic confirmation')
    if type(request.get('fi')) is not int or request['fi'] not in replay.frames or replay.frames[request['fi']]['relative_s']<30:raise ValueError('Confirmation outside frozen-map action review')
    frozen=load_map(run);origin,_,_=replay.record(request['fi'],'main')
    if ai:request=verify_ai_review(request,run,origin)
    qualification=json.loads((run/'QUALIFICATION.json').read_text(encoding='utf8'))
    e=Engine(None,'main',digest(env['source_sha256']),run_version=origin['run_version'],protocol_sha=origin['protocol_sha'])
    out=new_output(output);(out/'main').mkdir();(out/'map').mkdir()
    for p in (run/'map').iterdir():
        if p.is_file():
            with p.open('rb') as a,(out/'map'/p.name).open('xb') as b:shutil.copyfileobj(a,b)
    review_name='HUMAN_CONFIRMATION.json' if human else 'AI_VISUAL_REVIEW.json'
    write_new(out/review_name,dict(request=request,request_sha256=sha(request_path),candidate_package=str(run),human_confirmation=bool(human),
                 candidate_package_index_sha256=sha(run/'OUTPUT_INDEX.json'),scope='Same immutable run, added human evidence; invalid if source/code/config/candidate changes'))
    index=[]
    try:
        for fi in range(len(replay.source.frames)):
            f=replay.source.frame(fi);t=f['relative_s'];phase='MAP_BUILDING' if t<20 else 'TEMPORAL_VALIDATION' if t<28 else 'EMPTY_AUDIT' if t<30 else 'ACTION'
            if t>=20:e.map=frozen
            qualified=bool(qualification['qualified_M0'] and fi>qualification['available_after_fi'])
            r,rows,hits=e.step(f,phase,qualified)
            if fi==request['fi']:e.confirm(f,r,request,rows)
            save_array(out/'main'/('%04d.npz'%fi),current=rows,map_hits=hits);write_new(out/'main'/('%04d.json'%fi),r)
            index.append(dict(fi=fi,time_ns=f['time_ns'],relative_s=t,offset_points=f['offset'],count_points=len(rows),raw28_sha256=replay.frames[fi]['raw28_sha256'],variants={'main':dict(record='main/%04d.json'%fi,ledger='main/%04d.npz'%fi)}))
        write_new(out/'INDEX.json',dict(schema='hfus-realdev-index/1',entries=[replay.source.entry],frames=index,variants=['main'],map_id=frozen.map_id,
                     development_seen=True,dev_tainted=True,cases=[],confirmed_continuation_of=str(run),confirmation_sha256=sha(out/review_name),human_confirmation=bool(human)))
        write_new(out/'ENVIRONMENT.json',env)
        if frozen.fingerprint()!=frozen.map_id:raise ValueError('Map changed during continuation')
        for key,name in [('meta','meta.json'),('points','points.bin')]:
            if sha(replay.source.folder/name)!=replay.source.binding[key]:raise ValueError('Source drift during continuation')
        write_new(out/'OUTPUT_INDEX.json',{str(p.relative_to(out)).replace('\\','/'):sha(p) for p in out.rglob('*') if p.is_file()})
    finally:replay.source.close()


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--request',required=True);p.add_argument('--out',required=True);p.add_argument('--allow-ai-visual-review',action='store_true');a=p.parse_args()
    execute(Path(a.run),Path(a.request),a.out,a.allow_ai_visual_review)
