"""Read-only frozen replay + candidate coordinate conversion, never reruns inference."""
import copy
import hashlib
import importlib.util
import json
import sys
from pathlib import Path
import numpy as np
from bootstrap import ROOT, OUT, sha, write
from coordinates import Transform, RAW_VERSION, check_points, valid_xyz, plane_basis


def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()


def make_transform(protocol):
    h=protocol['historical']
    if sha(ROOT/h['path'])!=h['sha256'] or sha(ROOT/h['report'])!=h['report_sha256']:
        raise ValueError('Historical artifact drift')
    old=load(ROOT/h['path']);report=load(ROOT/h['report'])
    estimator=report['estimators']['tls']
    if (old['units']!='m' or old['from_frame']!='innolidar' or old['to_frame']!='ground_offline_display' or
            old['R']!=estimator['R'] or old['t']!=estimator['t'] or old['source']!=report['source']):
        raise ValueError('Historical direction/report/source mismatch')
    # The full R/t is used unchanged. PLAN basis is a crosscheck using its u axis.
    R,t,n,d=plane_basis(estimator['normal_source'],estimator['offset_source_m'],old['R'][0])
    if not np.allclose(R,old['R'],atol=1e-12,rtol=0) or not np.allclose(t,old['t'],atol=1e-12,rtol=0):
        raise ValueError('Historical basis incompatible with PLAN')
    a=dict(schema='hfus-candidate-transform/1',from_frame='innolidar',to_frame='candidate_local',units='m',
        R=old['R'],t=old['t'],direction='p_local=R@p_raw+t; row array p_raw@R.T+t',
        plane=dict(normal=n.tolist(),d_m=d),reference_axis=old['R'][0],
        historical=h,historical_internal_id=old['transform_id'],
        historical_source=old['source'],current_source=protocol['source'],
        reuse='COMPLETE_HISTORICAL_R_T_UNCHANGED; no refit or residual minimization',
        state='CANDIDATE_PLANE_PREVIEW',mode='OFFLINE_REVIEW',
        qualification=dict(geometry_validated=False,ground_identity=False,physical=False,runtime=False),
        warning='候选配平预览，地面身份与本段几何尚未验证')
    a['transform_id']=digest(a)
    a['coordinate_version']='CANDIDATE_LOCAL/'+a['transform_id']
    Transform(a)
    return a


class Frozen:
    def __init__(self, protocol):
        self.protocol=protocol
        self.path=ROOT/protocol['frozen_run']
        self.hashes=load(self.path/'OUTPUT_INDEX.json')
        self.index=self.read_json('INDEX.json')
        entry=copy.deepcopy(self.index['entries'][0]);s=protocol['source']
        if (entry['sid']!=s['sid'] or entry['source_sha256']!=dict(meta=s['meta'],points=s['points']) or
                entry['coordinate_version']!=RAW_VERSION or not entry['development_seen'] or not entry['dev_tainted']):
            raise ValueError('Frozen source binding mismatch')
        # Reuse strict existing parser without importing algorithm or write entry points.
        name='r02_readonly_source'
        spec=importlib.util.spec_from_file_location(name,ROOT/'sidequests/hfus_tcms_02/realdev/r01/contracts.py')
        contract=importlib.util.module_from_spec(spec);spec.loader.exec_module(contract)
        entry['path']=s['path']
        self.source=contract.Source(entry)
        if len(self.source.frames)!=s['frames'] or self.source.meta['total_points']!=s['rows']:
            raise ValueError('Source row/frame denominator mismatch')
        self.map_meta=self.read_json('map/MAP.json')
        p=self.checked('map/surfaces.npz')
        with np.load(p) as z:self.map={k:z[k] for k in z.files}
        self.map_build_end=max(f['fi'] for f in self.map_meta['build'])
        self.source_stats=self.stats()

    def stats(self):
        return [(p.stat().st_size,p.stat().st_mtime_ns) for p in (self.source.folder/'meta.json',self.source.folder/'points.bin')]

    def checked(self,name):
        p=(self.path/name).resolve()
        if not p.is_relative_to(self.path.resolve()) or sha(p)!=self.hashes[name]:
            raise ValueError('Frozen artifact drift: '+name)
        return p

    def read_json(self,name):
        return load(self.checked(name))

    def frame(self,fi):
        if type(fi) is not int or not 0<=fi<len(self.index['frames']):raise ValueError('Wrong fi')
        if self.stats()!=self.source_stats:raise ValueError('Source stat drift; restart for SHA')
        f=self.index['frames'][fi];m=f['variants']['main']
        r=self.read_json(m['record'])
        with np.load(self.checked(m['ledger'])) as z:rows=z['current'];hits=z['map_hits']
        src=self.source.frame(fi);p=src['xyz'];offset=src['offset']
        raw28=self.source.buffer[offset*28:(offset+len(p))*28]
        if (hashlib.sha256(raw28).hexdigest()!=f['raw28_sha256'] or len(rows)!=len(p) or
                offset!=f['offset_points'] or r['fi']!=fi or r['time_ns']!=src['time_ns'] or
                r['source_sha256']!=self.source.binding or r['coordinate_version']!=RAW_VERSION or
                not np.array_equal((rows['flags']&1)!=0,valid_xyz(p))):
            raise ValueError('Source/byte/row/validity drift')
        if r['candidate_map_exists'] and fi<=self.map_build_end:
            raise ValueError('Future map leak')
        return f,r,rows,hits,p


def converted_record(T,r,raw,local,rows):
    fi=r['fi'];base=T.tag(fi,False)
    out=dict(fi=fi,time_ns=r['time_ns'],relative_s=r['relative_s'],sid=r['sid'],
        source_sha256=r['source_sha256'],state='CANDIDATE_PLANE_PREVIEW',mode='OFFLINE_REVIEW',
        warning=T.artifact['warning'],tag=T.tag(fi),raw_tag=base,
        candidate_map_exists=r['candidate_map_exists'],historical_map_id=r['map_id'],
        map_id=digest([r['map_id'],T.id]),historical_phase=r['phase'],
        original_denominator=len(raw),accounting=r['accounting'],historical_run=r['run_version'],
        historical_record_sha=None,identity_valid_for_coordinate_version=False,
        geometry_validated=False,ground_identity_confirmed=False,physical_verified=False,runtime_eligible=False,
        physical_height_m=None,near_ground_hard_delete=False,development_seen=True,dev_tainted=True,
        algorithm='FROZEN_NUMERIC_TRANSFORM_ONLY; no local voxel rebuild, clustering, association or threshold changes',
        candidates=[],raw_candidates=[],track=None,raw_track=None)
    for c in r['candidates']:
        ids=np.asarray(c['rows'],dtype=int)
        if (len(ids)!=c['count'] or len(np.unique(ids))!=len(ids) or np.any(ids<0) or np.any(ids>=len(raw)) or
                not valid_xyz(raw[ids]).all() or not np.all(rows['candidate'][ids]==c['id'])):
            raise ValueError('Frozen candidate membership mismatch')
        # All members remain in the stored full cloud and the original rows list.
        before=dict(c,**base)
        after=T.object(before,fi)
        if before['rows']!=after['rows'] or not np.allclose(after['center'],local[ids].mean(axis=0),atol=1e-10,rtol=0):
            raise ValueError('Candidate member/center drift')
        after['member_coordinates']='full local frame array indexed by rows; no display subsampling in computation'
        out['candidates'].append(after);out['raw_candidates'].append(before)
    before=dict(r['track'],**base)
    after=T.object(before,fi)
    if before['rows']!=after['rows']:raise ValueError('Track association drift')
    after['historical_only']=True
    out['track']=after;out['raw_track']=before
    # Remaining frozen objects are counts/row ledgers, not geometric detections.
    out['frozen_row_evidence']={k:r[k] for k in ['rejected_unknown_objects','local_map_conflicts','local_map_conflict_rows']}
    return out


def sampled_ids(rows,limit=9000):
    cand=np.flatnonzero(rows['candidate']>=0)
    cand=cand[np.linspace(0,len(cand)-1,min(len(cand),3000),dtype=int)] if len(cand) else cand
    uniform=np.linspace(0,len(rows)-1,min(len(rows),limit-len(cand)),dtype=int)
    return np.unique(np.r_[uniform,cand])


def validate_output_binding(T,index,transform_sha,source_sha):
    if (index['tag']!=T.tag(-1) or index['transform_sha256']!=transform_sha or
            index['source_sha256']!=source_sha):
        raise ValueError('Stale/mixed output transform/source version; new output run required')


def validate_record_binding(T,r,fi,source_sha):
    if (r['fi']!=fi or r['tag']!=T.tag(fi) or r['raw_tag']!=T.tag(fi,False) or
            r['source_sha256']!=source_sha or r['state']!='CANDIDATE_PLANE_PREVIEW' or
            r['mode']!='OFFLINE_REVIEW' or r['identity_valid_for_coordinate_version'] is not False or
            any(r[k] for k in ['geometry_validated','ground_identity_confirmed','physical_verified','runtime_eligible','near_ground_hard_delete'])):
        raise ValueError('Frame/source/version/qualification mismatch')


def source_payload(T,raw,local):
    out=copy.deepcopy(raw);fi=out['fi']
    if out.pop('coordinate_version')!=RAW_VERSION:raise ValueError('Unexpected source coordinate version')
    xyz=out.pop('xyz')
    out.update(raw_xyz=xyz,local_xyz=[float(v) if np.isfinite(v) else None for v in local],
        source_coordinate_version=RAW_VERSION,coordinate_version=T.version,
        frame='candidate_local',transform_id=T.id,tag=T.tag(fi),raw_tag=T.tag(fi,False))
    return out
