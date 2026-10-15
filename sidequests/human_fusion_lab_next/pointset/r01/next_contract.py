"""Strict new-run boundary shared by local HTTP and verification; no cached fallback."""
import copy
import hashlib
import json
from pathlib import Path
import numpy as np
ROOT=Path(__file__).resolve().parents[4]
REASONS=['INVALID_RAW','OUTSIDE_DOMAIN','BACKGROUND_MATCH','CLUSTER_REJECTED','UNSELECTED_CLUSTER','SELECTED_UNKNOWN']


def read(path):return json.loads(Path(path).read_text(encoding='utf8'))


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1<<20),b''):digest.update(block)
    return digest.hexdigest()


def validate_frozen_inputs(evidence):
    e=Path(evidence);manifest=read(e/'RUN_MANIFEST.json')
    if manifest.get('schema')!='hfus-next/1' or manifest['run_id']!=e.name:raise ValueError('Unsupported frozen run binding')
    for name,h in manifest['code_sha256'].items():
        if sha(e/'EXECUTED_SOURCE'/name)!=h:raise ValueError('Executed source drift')
    for path,h in manifest['transforms'].items():
        if sha(path)!=h:raise ValueError('Transform drift')
    for asset in manifest['background_assets']:
        if sha(asset['path'])!=asset['sha256']:raise ValueError('Frozen background drift')
    return manifest


def validate_meta(meta, size):
    if not isinstance(meta,dict) or meta.get('format') != 'human_capture_session' or type(meta.get('format_version')) is not int or meta.get('format_version') != 1:
        raise ValueError('Unsupported source schema')
    if type(meta.get('point_stride_bytes')) is not int or meta['point_stride_bytes'] != 28:
        raise ValueError('Invalid source stride')
    if type(meta.get('total_points')) is not int or meta['total_points'] < 0 or size != meta['total_points']*28:
        raise ValueError('Truncated/invalid source')
    if not isinstance(meta.get('frames'),list):raise ValueError('Invalid frame list')
    end, last = 0, None
    for frame in meta['frames']:
        if not isinstance(frame,dict):raise ValueError('Invalid frame record')
        for key in ['offset_points','count_points','stamp_sec','stamp_nanosec']:
            if type(frame.get(key)) is not int:
                raise ValueError('Non-integer frame field')
        if frame['offset_points'] != end or frame['count_points'] < 0 or not 0 <= frame['stamp_nanosec'] < 1000000000:
            raise ValueError('Invalid frame offset/count/time')
        end += frame['count_points']
        stamp = frame['stamp_sec']*1000000000+frame['stamp_nanosec']
        if last is not None and stamp <= last:
            raise ValueError('Nonmonotonic device time')
        last = stamp
    if end != meta['total_points']:
        raise ValueError('Source total mismatch')


class FrozenRun:
    def __init__(self, evidence, expected_manifest_sha=None, expected_index_sha=None):
        self.e = Path(evidence).resolve()
        self.manifest_sha = sha(self.e/'RUN_MANIFEST.json')
        if expected_manifest_sha is not None and self.manifest_sha != expected_manifest_sha:
            raise ValueError('Same run ID changed manifest')
        self.manifest = copy.deepcopy(read(self.e/'RUN_MANIFEST.json'))
        if self.manifest.get('schema') != 'hfus-next/1' or self.manifest['run_id'] != self.e.name:
            raise ValueError('Unsupported run schema/ID')
        self.catalog = read(self.e/'catalog.json')
        pointer=self.e/'CURRENT_DELIVERY.json'
        delivery_name=read(pointer)['binding'] if pointer.exists() else 'DELIVERY_BINDING.json'
        if delivery_name not in ['DELIVERY_BINDING.json','DELIVERY_BINDING_R3.json','DELIVERY_BINDING_R4.json','DELIVERY_BINDING_R5.json']:raise ValueError('Unsupported explicit delivery binding')
        self.pointer_sha=sha(pointer) if pointer.exists() else None
        delivery_path=self.e/delivery_name;self.delivery_path=delivery_path
        delivery=read(delivery_path) if delivery_path.exists() else None
        if delivery is not None and delivery.get('schema') not in ['hfus-next-delivery/2','hfus-next-delivery/3','hfus-next-delivery/4','hfus-next-delivery/5']:
            raise ValueError('Unsupported delivery schema')
        index_name=delivery['artifact_index_path'] if delivery is not None else 'ARTIFACT_INDEX.json'
        if index_name not in ['ARTIFACT_INDEX.json','ARTIFACT_INDEX_V2.json']:raise ValueError('Unsupported explicit index path')
        self.index_path=self.e/index_name
        if expected_index_sha is not None and sha(self.index_path)!=expected_index_sha:
            raise ValueError('Same run ID changed artifact index')
        self.index = read(self.index_path)
        self.index_sha=sha(self.index_path)
        if self.index.get('schema') != 'hfus-next-index/1':
            raise ValueError('Unsupported index schema')
        if self.index['manifest_sha256'] != self.manifest_sha:
            raise ValueError('Index manifest drift')
        self.verified(self.e/'catalog.json')
        # Executed source is part of the frozen numeric result, current source is
        # separately bound by the delivery record; never pretend they are equal.
        if (self.e/'EXECUTED_SOURCE').exists():validate_frozen_inputs(self.e)
        if delivery_path.exists():
            if delivery['manifest_sha256']!=self.manifest_sha or delivery['artifact_index_sha256']!=sha(self.index_path):
                raise ValueError('Delivery index/run drift')
            for path,h in delivery['executed_sources'].items():
                if sha(self.e/path)!=h:raise ValueError('Executed source binding drift')
            self.delivery=copy.deepcopy(delivery)
        else:self.delivery=None
        self.delivery_sha=sha(delivery_path) if delivery is not None else None

    def verified(self, path):
        relative = str(path.relative_to(self.e)).replace('\\','/')
        if relative not in self.index['files'] or sha(path) != self.index['files'][relative]:
            raise ValueError('Same run ID changed artifact')
        return path

    def frame(self, sid, fi, group):
        if sha(self.e/'RUN_MANIFEST.json')!=self.manifest_sha or sha(self.index_path)!=self.index_sha:
            raise ValueError('Live run/index content drift')
        if self.pointer_sha is not None and sha(self.e/'CURRENT_DELIVERY.json')!=self.pointer_sha:
            raise ValueError('Live delivery pointer drift')
        if self.delivery_sha is not None and sha(self.delivery_path)!=self.delivery_sha:
            raise ValueError('Live delivery content drift')
        if group not in self.index['groups'] or sid not in self.manifest['source_sha256'] or type(fi) is not int:
            raise ValueError('Unknown group/source')
        rec = next(r for r in self.catalog['sessions'] if r['session_id'] == sid)
        if fi not in rec['available_frames']:
            raise ValueError('Excluded FIT/CAL or invalid frame')
        path = self.verified(self.e/'runs'/group/sid/('{:04d}.json'.format(fi)))
        row = read(path)
        if row.get('schema') != 'hfus-next-frame/1' or row.get('run_id') != self.manifest['run_id'] or row.get('variant') != group:
            raise ValueError('Unsupported frame schema/binding')
        if row['session_id'] != sid or row['frame_index'] != fi or row['source_sha256'] != self.manifest['source_sha256'][sid] or row['manifest_sha256'] != self.manifest_sha:
            raise ValueError('Frame source/run drift')
        if row['code_sha256']!=self.manifest['code_sha256']:
            raise ValueError('Code version drift')
        for path,key in [(self.e/'common'/sid/('{:04d}.npz'.format(fi)),'common_sha256'),
                         (self.e/'runs'/group/sid/('{:04d}_members.npz'.format(fi)),'member_sha256')]:
            if sha(self.verified(path)) != row[key]: raise ValueError('Member/common binding drift')
        # Compatibility display metadata, no numerical/member changes.
        for body in row['body_3d']:body['model_status']='NOT_USED'
        row['viewer_adapter']='FROZEN_NUMERICS_MODELS_UNUSED_IDENTITY_UNKNOWN'
        row['coordinate_frame']='HISTORICAL_RT_REGISTRATION_STATIC_COMPENSATION; NOMINAL_NOT_PHYSICAL_CALIBRATION'
        row['semantic']['zero_denominator']='NA_WHEN_K_EMPTY; IDENTITY_METRICS_BLOCKED'
        return row

    def source(self, sid, fi, group, index, directory=None):
        row = self.frame(sid,fi,group)
        if type(index) is not int or not 0 <= index < row['source_frame']['count_points']:
            raise ValueError('Invalid source row')
        directory = Path(directory) if directory is not None else ROOT/'captures/remote'/sid
        meta,points = directory/'meta.json',directory/'points.bin'
        result = {'sid':sid,'fi':fi,'local_index':index,'identity':'UNKNOWN','run_id':row['run_id'],'variant':group,
                  'source_sha256':row['source_sha256'],'device_time':row['device_time'], 'source_binding_status':'BLOCKED_MISSING_ORIGINAL',
                  'raw_bytes_hex':None,'opaque_hex_12_27':None}
        if not meta.is_file() or not points.is_file():
            result['reason']='ORIGINAL_META_OR_POINTS_MISSING; NO_FALLBACK'
            return result
        from server import validate_source_binding
        validate_source_binding(directory,row['source_sha256'])
        m=read(meta);validate_meta(m,points.stat().st_size)
        if m['frames'][fi] != row['source_frame']: raise ValueError('Source frame drift')
        offset=(row['source_frame']['offset_points']+index)*28
        with points.open('rb') as f:f.seek(offset);data=f.read(28)
        if len(data)!=28:raise ValueError('Truncated query')
        with np.load(self.e/'common'/sid/('{:04d}.npz'.format(fi))) as d:
            finite=lambda x:[float(v) if np.isfinite(v) else None for v in x]
            result.update(raw_xyz=finite(d['raw_xyz'][index]),nominal_xyz=finite(d['nominal_xyz'][index]),xyz=finite(d['xyz'][index]))
        with np.load(self.e/'runs'/group/sid/('{:04d}_members.npz'.format(fi))) as d:
            result.update(terminal_reason=int(d['terminal_reason'][index]),cluster_id=int(d['cluster_id'][index]),
                          terminal_reason_name=REASONS[int(d['terminal_reason'][index])],
                          pose_ambiguous=bool(d['pose_ambiguous'][index]),background_match=bool(d['background_match'][index]),
                          background_distance_m=float(d['background_distance'][index]) if np.isfinite(d['background_distance'][index]) else None)
        result.update(source_binding_status='ORIGINAL_BYTES_SHA_VERIFIED',offset_bytes=offset,raw_bytes_hex=data.hex(),opaque_hex_12_27=data[12:].hex())
        return result
