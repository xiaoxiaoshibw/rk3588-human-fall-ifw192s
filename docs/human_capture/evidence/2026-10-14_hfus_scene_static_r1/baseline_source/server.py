"""Local replay and append-only point-part annotations for this isolated experiment."""
import argparse
import hashlib
import json
import socket
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
PARTS = json.loads((HERE/'ANNOTATION_SCHEMA.json').read_text(encoding='utf8'))['point_parts']['classes']
OUT = HERE/'output'
ACTION_OUT = HERE/'action_output'
RESEARCH_OUT = HERE/'action_research_r2'
R3_OUT = HERE/'action_research_r3'
RETENTION_OUT = HERE/'action_research_retention'
SOURCE_QUERY_BINDINGS = {}


def retention_current():
    path=next((RETENTION_OUT/n for n in ['CURRENT_V2.json','CURRENT.json','PREVIEW.json'] if (RETENTION_OUT/n).exists()),RETENTION_OUT/'CURRENT.json')
    return json.loads(path.read_text(encoding='utf8'))


def retention_binding(current,variant):
    if variant not in current['variants']:raise ValueError('Unknown retention variant')
    row=current.get('variant_sources',{}).get(variant,{})
    return row.get('run_id',current['run_id']),row.get('variant',variant),row.get('status',current.get('status','ALL_FRAMES_GENERATED; verification/delivery status in report; NOT_DEFAULT'))
SCENE_CHANGE_OUT = HERE/'action_research_scenechange_guarded'
REVIEW_QUEUE = HERE.parents[3]/'docs/human_fall/evidence/2026-10-14_hf_real_close_data_bg_r1/REVIEW_QUEUE.json'


def validate_review(row, catalog, frame):
    if not isinstance(row, dict) or type(row.get('frame_index')) is not int or row.get('schema_version') != 'pointset-annotation/1' or row.get('session_id') != frame['session_id'] or row.get('frame_index') != frame['frame_index']:
        raise ValueError('Annotation binding mismatch')
    rec = next((s for s in catalog['sessions'] if s['session_id'] == row['session_id']), None)
    if rec is None or row.get('source_sha256') != rec['source_sha256']:
        raise ValueError('Source hash mismatch')
    if not isinstance(row.get('reviewer'), str) or not row['reviewer'].strip():
        raise ValueError('Reviewer name required')
    if row.get('provenance') != 'HUMAN_REVIEW' or row.get('part_class') not in PARTS:
        raise ValueError('Human provenance and known part class required')
    ids = row.get('source_indices')
    if not isinstance(ids, list) or not ids or len(set(ids)) != len(ids) or any(type(i) is not int or not 0 <= i < frame['source_frame']['count_points'] for i in ids):
        raise ValueError('Invalid frame-local source indices')
    scope = row.get('object_scope')
    if scope not in ['reference', 'full_3d', 'roi_3d', 'full_2d']:
        raise ValueError('Explicit object scope required')
    objects = frame[scope]
    obj = next((o for o in objects if o['id'] == row.get('object_id') and o['kind'] == row.get('object_kind')), None)
    if obj is None or not set(ids).issubset(obj['source_indices']):
        raise ValueError('Points do not belong to selected object')
    return row


def validate_source_binding(directory, expected):
    # Save boundary rehashes actual sources; cached catalog cannot authorize drifted input.
    for name, key in [('meta.json', 'meta'), ('points.bin', 'points')]:
        h = hashlib.sha256()
        with (directory/name).open('rb') as f:
            for block in iter(lambda: f.read(1024*1024), b''):
                h.update(block)
        if h.hexdigest() != expected.get(key):
            raise ValueError('Actual source hash drift; annotation refused')


def bound_reviews(records, catalog, frame):
    valid, rejected = [], []
    for record in records:
        if not isinstance(record, dict):
            rejected.append('Malformed annotation record')
            continue
        if record.get('session_id') != frame['session_id'] or record.get('frame_index') != frame['frame_index']:
            continue
        try:
            valid.append(validate_review(record, catalog, frame))
        except (ValueError, KeyError, TypeError) as exc:
            rejected.append(str(exc))
    return {'records': valid, 'rejected': rejected}


class Handler(BaseHTTPRequestHandler):
    def send(self, code, data, kind='application/json; charset=utf-8'):
        if not isinstance(data, bytes):
            data = json.dumps(data, ensure_ascii=False, allow_nan=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', kind)
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
        self.wfile.write(data)

    def get_frame(self, sid, fi, dataset='legacy'):
        folder = ACTION_OUT if dataset == 'actions' else OUT
        cat = json.loads((folder/'catalog.json').read_text(encoding='utf-8'))
        rec = next((s for s in cat['sessions'] if s['session_id'] == sid), None)
        if rec is None or not 0 <= fi < rec['frame_count']:
            raise ValueError('Unknown session/frame')
        if fi not in rec.get('available_frames', range(rec['frame_count'])):
            raise ValueError('Frame excluded from independent HOLDOUT evaluation')
        return cat, json.loads((folder/sid/f'{fi:04d}.json').read_text(encoding='utf-8'))

    def do_GET(self):
        req = urlparse(self.path)
        dataset = parse_qs(req.query).get('dataset', ['actions'])[0]
        if dataset not in ['actions', 'legacy']:
            self.send(400, {'error':'Unknown dataset'})
            return
        folder = ACTION_OUT if dataset == 'actions' else OUT
        try:
            if req.path == '/api/version':
                self.send(200, {'page_version':'HF-MAINLINE-POINTS-01/R3-COMPARE', 'default':'R1_BASELINE',
                    'source_sha256':{n:hashlib.sha256((HERE/n).read_bytes()).hexdigest() for n in ['app.js','index.html','server.py']},
                    'experiments':'NOT_DEFAULT_IDENTITY_UNKNOWN'})
            elif req.path == '/api/scene-source':
                if dataset != 'actions': raise ValueError('Scene change applies only to action sources')
                import numpy as np
                from core import R, T
                q = parse_qs(req.query); sid, fi, index = q['sid'][0], int(q['fi'][0]), int(q['index'][0])
                _, base = self.get_frame(sid, fi, dataset)
                row = json.loads((SCENE_CHANGE_OUT/sid/f'{fi:04d}.json').read_text(encoding='utf8'))
                if not 0 <= index < base['source_frame']['count_points']: raise ValueError('Invalid source row')
                directory = HERE.parents[3]/'captures/remote'/sid
                validate_source_binding(directory, row['source_sha256'])
                offset = base['source_frame']['offset_points']+index
                with (directory/'points.bin').open('rb') as f:
                    f.seek(offset*28); raw_bytes = f.read(28)
                raw = np.frombuffer(raw_bytes[:12], dtype='<f4').astype(float); xyz = raw @ R.T + T
                cal = json.loads((ACTION_OUT/'RUN_MANIFEST.json').read_text(encoding='utf8'))['config']
                prior = Path(cal['background_experiment']); bg = json.loads((ACTION_OUT/'catalog.json').read_text(encoding='utf8'))['background']['session']
                if sid != bg:
                    reg = json.loads((prior/(sid+'_registration.json')).read_text(encoding='utf8'))
                    xyz = xyz @ np.array(reg['R']).reshape(3, 3).T + reg['t']
                vibration = row['vibration']; xyz = xyz @ np.array(vibration['R']).T + vibration['t']
                finite = lambda x: [float(v) if np.isfinite(v) else None for v in x]
                self.send(200, {'sid':sid, 'fi':fi, 'local_index':index, 'global_row':offset,
                    'raw_xyz':finite(raw), 'xyz':finite(xyz), 'opaque_hex_12_27':raw_bytes[12:].hex(),
                    'vibration':vibration, 'source_sha256':row['source_sha256'], 'identity':'UNKNOWN',
                    'background_match':index in row['scene_change']['matched_source_indices'],
                    'pose_ambiguous':index in row['scene_change'].get('pose_ambiguous_indices', []),
                    'new_point':index in row['scene_change']['new_source_indices'],
                    'target':index in row['selection']['selected_source_indices']})
            elif req.path in ['/api/retention-diagnostic','/api/retention-source','/api/retention-members']:
                if dataset != 'actions': raise ValueError('Retention applies only to action sources')
                import numpy as np
                from research_retention import CODE
                from research_actions import display
                q=parse_qs(req.query);sid=q['sid'][0];fi=int(q['fi'][0]);cat,base=self.get_frame(sid,fi,dataset)
                current=retention_current()
                requested=q.get('variant',['ret_combined'])[0].removeprefix('ret_')
                run,variant,delivery_status=retention_binding(current,requested)
                with np.load(RETENTION_OUT/current['baseline_id']/sid/f'{fi:04d}.npz') as data:a={k:data[k] for k in data.files}
                qualification=RETENTION_OUT/current['baseline_id']/sid/f'{fi:04d}_qualification.npz'
                if qualification.exists():
                    with np.load(qualification) as d:a.update({k:d[k] for k in d.files})
                members_path=RETENTION_OUT/run/variant/sid/f'{fi:04d}_members.npz'
                with np.load(members_path) as data:m={k:data[k] for k in data.files}
                final_path=RETENTION_OUT/run/variant/sid/f'{fi:04d}_final_terminal.npz'
                if final_path.exists():
                    with np.load(final_path) as d:m['final_terminal_reason']=d['final_terminal_reason']
                guard_path=RETENTION_OUT/run/variant/sid/f'{fi:04d}_guard.json'
                guard=json.loads(guard_path.read_text(encoding='utf8')) if guard_path.exists() else None
                if req.path == '/api/retention-members':
                    # Full source identities + complete stage arrays; sampled UI never used for metrics.
                    import io
                    metadata={'schema':'hf-complete-source-export/1','sid':sid,'fi':fi,'run_id':run,'variant':requested,
                        'source_sha256':base['source_sha256'],'source_frame':base['source_frame'],'units':'XYZ/distance m; frame stamp sec+nanosec',
                        'coordinate_frame':base['coordinate_frame'],'background_sha256':cat['background']['background_file_sha256'],
                        'opaque_reference':'original source points.bin[global_row*28+12:global_row*28+28], preserved SHA',
                        'identity':'UNKNOWN','first_reason_and_candidate_final_state_separate':True}
                    b=io.BytesIO();np.savez_compressed(b,metadata_json=np.array(json.dumps(metadata,ensure_ascii=False)),**a,**{'recovery_'+k:v for k,v in m.items()})
                    self.send(200,b.getvalue(),'application/octet-stream')
                elif req.path == '/api/retention-source':
                    i=int(q['index'][0])
                    if not 0 <= i < len(a['xyz']):raise ValueError('Invalid source index')
                    global_row=int(a['global_row'][i]);source=HERE.parents[3]/'captures/remote'/sid/'points.bin'
                    opaque=None;source_binding_status='MISSING_ORIGINAL_SOURCE'
                    if source.exists() and (source.parent/'meta.json').exists():
                        signature=tuple((source.parent/n).stat().st_mtime_ns for n in ['meta.json','points.bin'])+tuple((source.parent/n).stat().st_size for n in ['meta.json','points.bin'])
                        if SOURCE_QUERY_BINDINGS.get(sid)!=signature:
                            validate_source_binding(source.parent,base['source_sha256'])
                            SOURCE_QUERY_BINDINGS[sid]=signature
                        with source.open('rb') as f:f.seek(global_row*28+12);opaque=f.read(16).hex()
                        source_binding_status='SHA_VERIFIED_CURRENT_SOURCE'
                    finite=lambda x:[float(v) if np.isfinite(v) else None for v in x]
                    positions=np.flatnonzero(m['pool']==i)
                    recovery_predicates={key:(bool(m[key+'_pass'][positions[0]]) if len(positions) else 'NOT_REACHED') for key in ['local','reference','temporal']}
                    self.send(200,{'sid':sid,'fi':fi,'local_index':i,'global_row':global_row,'offset_bytes':global_row*28,
                        'raw_xyz':finite(a['raw_xyz'][i]),'xyz':finite(a['xyz'][i]),'opaque_hex_12_27':opaque,
                        'source_binding_status':source_binding_status,'ledger_basis':'FROZEN_VERIFIED_OUTPUT; original source required for rerun and opaque bytes',
                        'source_frame':base['source_frame'],'first_terminal_reason':next(k for k,v in CODE.items() if v==a['first_terminal_reason'][i]),
                        'source_sha256':base['source_sha256'],'background_sha256':cat['background']['background_file_sha256'],
                        'coordinate_frame':base['coordinate_frame'],'reference_nearest_index':int(a['reference_nearest_index'][i]),
                        'actual_background_distance_m':float(a['actual_background_distance_m'][i]) if np.isfinite(a['actual_background_distance_m'][i]) else None,
                        'counterfactual_background_distance_m':float(a['counterfactual_background_distance_m'][i]) if np.isfinite(a['counterfactual_background_distance_m'][i]) else None,
                        'cluster_id':int(a['cluster_id'][i]),
                        'overlapping_predicate_bits':int(a['overlapping_predicates'][i]),'reached_stage_bits':int(a['reached_stage_bits'][i]),
                        'candidate_qualification_bits':int(a.get('candidate_qualification_bits',np.zeros(len(a['xyz']),dtype='u1'))[i]),
                        'recovery_state':int(m['recovery_state'][i]),
                        'candidate_final_terminal_reason':int(m['final_terminal_reason'][i]) if 'final_terminal_reason' in m else None,
                        'geometric_guard_reasons':guard['reasons'] if guard and i in guard['guard_rejected_source_indices'] else [],
                        'recovery_predicates':recovery_predicates,
                        'identity':'UNKNOWN','run_id':run,'variant':requested})
                else:
                    row=json.loads((RESEARCH_OUT/sid/f'{fi:04d}.json').read_text(encoding='utf8'))
                    for name,codes in [('domain_rejected',[1,2,3,4,5]),('cluster_rejected',[7,8,9])]:
                        ids=np.flatnonzero(np.isin(a['first_terminal_reason'],codes))
                        ids=ids[np.isfinite(a['xyz'][ids]).all(axis=1)]
                        row['layers'][name]=display(a['xyz'],ids,2000)
                    row['layers']['candidate_pool']=display(a['xyz'],m['pool'].astype(int),2000)
                    row['layers']['recovered']=display(a['xyz'],m['added'].astype(int),2000)
                    row['terminal_counts']={k:int(np.count_nonzero(a['first_terminal_reason']==v)) for k,v in CODE.items()}
                    self.send(200,row)
            elif req.path == '/api/research':
                row=json.loads((RESEARCH_OUT/'experiments.json').read_text(encoding='utf8'))
                if (R3_OUT/'experiments.json').exists():
                    r3=json.loads((R3_OUT/'experiments.json').read_text(encoding='utf8'))
                    row['r3']=r3;row['cases']=r3['cases']+row['cases']
                self.send(200, row)
            elif req.path in ['/api/diagnostic', '/api/experiment', '/api/source-members']:
                if dataset != 'actions':
                    raise ValueError('R2 research applies only to action sources')
                q = parse_qs(req.query); sid, fi = q['sid'][0], int(q['fi'][0])
                self.get_frame(sid, fi, dataset)
                if req.path == '/api/experiment':
                    variant = q['variant'][0]
                    if variant == 'scene_change':
                        self.send(200, (SCENE_CHANGE_OUT/sid/f'{fi:04d}.json').read_bytes())
                        return
                    if variant.startswith('ret_'):
                        c=retention_current()
                        v=variant.removeprefix('ret_');run,actual,status=retention_binding(c,v)
                        row=json.loads((RETENTION_OUT/run/actual/sid/f'{fi:04d}.json').read_text(encoding='utf8'))
                        row['variant']=variant;row['delivery_status']=status
                        guard_path=RETENTION_OUT/run/actual/sid/f'{fi:04d}_guard.json'
                        if guard_path.exists():row['geometric_guard']=json.loads(guard_path.read_text(encoding='utf8'))
                        self.send(200,row)
                        return
                    if variant not in ['point12','point20','component20','low20','axis','r3_graph','r3_background','r3_temporal','r3_combined','r3','r3_feedback','r3_signed','r3_signed_feedback']:
                        raise ValueError('Unknown experimental variant')
                    root=R3_OUT if variant.startswith('r3') else RESEARCH_OUT
                    self.send(200, (root/variant/sid/f'{fi:04d}.json').read_bytes())
                elif req.path == '/api/source-members':
                    self.send(200, (RESEARCH_OUT/sid/f'{fi:04d}_sources.npz').read_bytes(), 'application/octet-stream')
                else:
                    self.send(200, (RESEARCH_OUT/sid/f'{fi:04d}.json').read_bytes())
            elif req.path == '/api/catalog':
                self.send(200, (folder/'catalog.json').read_bytes())
            elif req.path == '/api/info':
                self.send(200, {'sessions':json.loads((folder/'catalog.json').read_text(encoding='utf8'))['sessions'], 'dataset':dataset})
            elif req.path == '/api/review-queue':
                self.send(200, REVIEW_QUEUE.read_bytes())
            elif req.path == '/api/frame':
                q = parse_qs(req.query)
                _, row = self.get_frame(q['sid'][0], int(q['fi'][0]), dataset)
                self.send(200, row)
            elif req.path == '/api/models':
                self.send(200, {'status':'NOT_USED_GEOMETRIC_ASSOCIATION'} if dataset == 'actions' else (OUT/'model_comparison.json').read_bytes())
            elif req.path == '/api/actions':
                self.send(200, (folder/'action_catalog.json').read_bytes())
            elif req.path == '/api/parts':
                q = parse_qs(req.query)
                sid, fi = q['sid'][0], int(q['fi'][0])
                cat, frame = self.get_frame(sid, fi, dataset)
                if dataset == 'actions':
                    self.send(200, {'records':[], 'rejected':[], 'status':'AI_INFERRED_NOT_HUMAN_LABELS'})
                    return
                rec = next(s for s in cat['sessions'] if s['session_id'] == sid)
                validate_source_binding(HERE.parents[3]/'captures/remote'/sid, rec['source_sha256'])
                path = HERE/'labels/human_parts.jsonl'
                records = []
                if path.exists():
                    records = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line]
                self.send(200, bound_reviews(records, cat, frame))
            elif req.path.startswith('/data/'):
                path = (folder/req.path.removeprefix('/data/')).resolve()
                if not path.is_relative_to(folder.resolve()) or path.name not in ['human_reference.npz', 'summary.json', 'action_report.json', 'candidate_source_indices.npz']:
                    raise ValueError('Unknown artifact')
                self.send(200, path.read_bytes(), 'application/octet-stream')
            elif req.path in ['/', '/app.js']:
                name = 'index.html' if req.path == '/' else 'app.js'
                self.send(200, (HERE/name).read_bytes(), 'text/html; charset=utf-8' if name.endswith('html') else 'text/javascript; charset=utf-8')
            else:
                self.send(404, {'error': 'Not found'})
        except (OSError, KeyError, ValueError, TypeError) as exc:
            self.send(400, {'error': str(exc)})

    def do_POST(self):
        try:
            if parse_qs(urlparse(self.path).query).get('dataset', ['legacy'])[0] == 'actions':
                self.send(400, {'error':'Action predictions are not manual labels; use legacy annotation scope'})
                return
            if self.path != '/api/parts':
                self.send(404, {'error': 'Not found'})
                return
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                raise ValueError('Cross-origin mutation refused')
            size = int(self.headers.get('Content-Length', 0))
            if not 0 < size <= 2*1024*1024 or 'application/json' not in self.headers.get('Content-Type', ''):
                raise ValueError('Invalid annotation request')
            row = json.loads(self.rfile.read(size))
            cat, frame = self.get_frame(row['session_id'], int(row['frame_index']))
            validate_review(row, cat, frame)
            validate_source_binding(HERE.parents[3]/'captures/remote'/row['session_id'], row['source_sha256'])
            path = HERE/'labels'
            path.mkdir(exist_ok=True)
            # Append only. No edits to old GT, point recordings, or models.
            with (path/'human_parts.jsonl').open('a', encoding='utf-8') as f:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False)+'\n')
            self.send(200, {'saved': True, 'points': len(row['source_indices'])})
        except (OSError, KeyError, ValueError, TypeError) as exc:
            self.send(400, {'error': str(exc)})


class LocalReplayServer(ThreadingHTTPServer):
    # Windows SO_REUSEADDR can silently route two localhost services on one port.
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket,'SO_EXCLUSIVEADDRUSE'):
            self.socket.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        if self.address_family == socket.AF_INET6:
            self.socket.setsockopt(socket.IPPROTO_IPV6,socket.IPV6_V6ONLY,1)
        super().server_bind()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8941)
    parser.add_argument('--ipv6', action='store_true', help='Use IPv6 localhost ::1, same port, exclusive bind')
    args = parser.parse_args()
    server_class=LocalReplayServer
    if args.ipv6:
        class IPv6ReplayServer(LocalReplayServer):
            address_family=socket.AF_INET6
        server_class=IPv6ReplayServer
    host='::1' if args.ipv6 else '127.0.0.1'
    server = server_class((host, args.port), Handler)
    display_host='[::1]' if args.ipv6 else host
    print(f'Pointset replay http://{display_host}:{args.port}/', flush=True)
    server.serve_forever()
