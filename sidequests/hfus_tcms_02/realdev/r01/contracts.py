"""REALDEV strict sources and exclusive item-local outputs; opaque tail stays opaque."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
EVIDENCE_ROOT = ROOT / 'docs/human_fall/evidence'
ITEM = EVIDENCE_ROOT / '2026-10-17_hfus_tcms_02_realdev_r1'
PREDEV = ROOT / 'sidequests/hfus_tcms_02/predev/r01'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


pre = module('realdev_pre_contract', PREDEV / 'contracts.py')
sha, digest, production_geometry, validate_members = pre.sha, pre.digest, pre.production_geometry, pre.validate_members


def guarded(path):
    p = Path(path).absolute()
    if not p.resolve().is_relative_to(ITEM.resolve()) or p.resolve() == ITEM.resolve():
        raise ValueError('Output must be under this new REALDEV evidence root')
    if any(q.is_junction() or q.is_symlink() for q in [p, *p.parents] if q.exists()):
        raise ValueError('Output reparse/link path forbidden')
    return p


def new_output(path):
    p = guarded(path)
    p.mkdir(parents=True, exist_ok=False)
    return p


def write_new(path, value):
    with guarded(path).open('x', encoding='utf8') as f:
        json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)


def save_array(path, **arrays):
    with guarded(path).open('xb') as f:
        np.savez_compressed(f, **arrays)


class Source(pre.Source):
    def __init__(self, entry):
        # Positive whitelist runs BEFORE any path access. No new source-kind alias.
        if entry.get('kind') == 'SYNTHETIC':
            if entry.get('role') not in ('SYNTHETIC_CONTRACT', 'MAP_ONLY'):
                raise ValueError('Unknown synthetic role')
            if not Path(entry['path']).resolve().is_relative_to(ITEM):
                raise ValueError('Synthetic fixture must be item-local')
            # Parent Source is reused only for strict REAL_DEVELOPMENT parsing;
            # restore actual fixture kind after construction. Never used for real.
            translated = dict(entry, kind='REAL_DEVELOPMENT', role='B')
        else:
            translated = entry
            if entry.get('kind') != 'REAL_DEVELOPMENT' or entry.get('role') != 'B':
                raise ValueError('Only explicit REAL_DEVELOPMENT/B supported')
        if type(entry.get('independent_test', False)) is not bool or entry.get('independent_test', False):
            raise ValueError('D/HOLDOUT/independent input forbidden')
        super().__init__(translated)
        self.entry = copy.deepcopy(entry)
        self.stamps = [int(f['stamp_sec'])*10**9+int(f['stamp_nanosec']) for f in self.frames]
        self.times = [(n-self.stamps[0])/1e9 for n in self.stamps] if self.stamps else []

    def frame(self, fi):
        f = super().frame(fi)
        f['source_sha256'] = copy.deepcopy(self.binding)
        f['relative_s'] = self.times[fi]
        return f

    def raw_row(self, fi, row):
        b = self.mapping(fi, source_row=row)
        with (self.folder/'points.bin').open('rb') as f:
            f.seek(b['byte_offset']); raw = f.read(28)
        xyz = np.frombuffer(raw[:12], dtype='<f4')
        return dict(b, time_ns=self.stamps[fi], source_sha256=self.binding,
                    coordinate_version=self.entry['coordinate_version'],
                    xyz=[float(x) if np.isfinite(x) else None for x in xyz],
                    raw_bytes_hex=raw.hex(), opaque_bytes_12_27='NOT_INTERPRETED')


def protocol_gate(manifest):
    mode = manifest.get('mode')
    p = manifest.get('real_protocol', {})
    if set(p) != {'pass_lines','matching_rules','annotation_coverage','development_split'}:
        raise ValueError('Four real_protocol keys required')
    if not isinstance(p['development_split'], dict) or not p['development_split']:
        raise ValueError('Explicit development split required')
    if mode == 'DIAGNOSTIC':
        if p['pass_lines'] is not None or p['matching_rules'] is not None or p['annotation_coverage'] != dict(status='DECLARED_ZERO',label_count=0,audited_rows=0) or manifest.get('labels'):
            raise ValueError('Diagnostic must declare zero labels, null lines/rules')
        return
    if mode != 'LABELLED':
        raise ValueError('Unknown processing mode')
    lines, matching, coverage = p['pass_lines'], p['matching_rules'], p['annotation_coverage']
    if (not isinstance(lines,dict) or not lines or
        any(type(v) not in (float,int) or not np.isfinite(v) for v in lines.values()) or
        not isinstance(matching,dict) or not matching or
        not isinstance(coverage,dict) or type(coverage.get('audited_rows')) is not int or coverage['audited_rows'] <= 0 or
        not manifest.get('labels')):
        raise ValueError('LABELLED requires numeric lines, rules, actual coverage and labels')
    raise ValueError('LABELLED scoring remains disabled until audited label schema/protocol is registered')


def diagnostic_evaluation():
    return dict(stage='REAL_DIAGNOSTIC',effectiveness_pass=None,effectiveness_status='BLOCKED',
                reason='NO_LABELS_IS_NOT_ZERO_CONTAMINATION',point_retention=None,point_purity=None,
                known_background_mixing=None,id_switches=None,first_discovery_delay_s=None,
                maximum_measured_gap_s=None,false_track_duration_s=None,annotation_coverage=0,
                independent_result=None,development_seen=True,dev_tainted=True)


def bound_json(evidence):
    if not isinstance(evidence,dict) or set(evidence)!={'path','sha256'}:raise ValueError('Evidence file/SHA required')
    p=Path(evidence['path']).resolve()
    if not p.is_relative_to(ITEM) or not p.is_file() or sha(p)!=evidence['sha256']:raise ValueError('Evidence missing/outside item/SHA drift')
    return json.loads(p.read_text(encoding='utf8'))


def layout_evidence(protocol):
    q=protocol['qualification']
    if q.get('layout_consistent') is not True:return False
    e=q.get('layout_evidence',{})
    if not isinstance(e,dict) or not e.get('file'):raise ValueError('Layout evidence required')
    doc=bound_json(dict(path=str(ITEM/e['file']),sha256=e.get('sha256')))
    if not isinstance(doc.get('layout_fact'),str) or not doc['layout_fact'] or doc['layout_fact']!=e.get('fact'):raise ValueError('Layout fact binding mismatch')
    return True


def verify_ai_review(request,run,origin):
    """External evidence gate; pure Engine receives only this verified envelope."""
    from urllib.parse import urlparse,parse_qs
    protocol=json.loads((run/'INPUT_MANIFEST.json').read_text(encoding='utf8'))['protocol']
    update=bound_json(request.get('user_delegation_evidence'))
    expected=protocol['qualification']['layout_evidence']
    if request['user_delegation_evidence']['sha256']!=expected['sha256'] or update.get('visual_delegation')!='借助视觉帮我判断就行':raise ValueError('Actual user delegation binding mismatch')
    visual=bound_json(request.get('visual_review_evidence'))
    for key in ['sid','fi','time_ns','source_sha256','coordinate_version','run_version','protocol_sha']:
        if visual.get(key)!=origin.get(key) or request.get(key)!=origin.get(key):raise ValueError('Visual frame/source/run binding mismatch')
    if (visual.get('candidate_version')!=request.get('candidate_version') or
        not any(c['version']==visual['candidate_version'] for c in origin['candidates']) or
        visual.get('candidate_package_index_sha256')!=sha(run/'OUTPUT_INDEX.json') or
        visual.get('human_confirmation') is not False):raise ValueError('Visual candidate/package binding mismatch')
    service=bound_json(visual.get('service_record'))
    if Path(service['run']).resolve()!=run.resolve():raise ValueError('Visual service points to different run')
    url=request.get('candidate_url');u=urlparse(url or '');q=parse_qs(u.query)
    if (url!=visual.get('candidate_url') or u.hostname!='127.0.0.1' or u.port!=service['address'][1] or
        q.get('fi')!=[str(origin['fi'])]):raise ValueError('Visual URL binding mismatch')
    shots=visual.get('screenshots')
    if not isinstance(shots,list) or not shots:raise ValueError('Actual screenshots required')
    for shot in shots:
        if not isinstance(shot,dict):raise ValueError('Screenshot path/SHA required')
        p=Path(shot.get('path','')).resolve()
        if not p.is_relative_to(ITEM) or not p.is_file() or sha(p)!=shot.get('sha256') or not p.read_bytes().startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('Screenshot evidence missing/SHA drift')
    request['evidence_verified']=True
    return request
