"""PC离线单worker运行时回放；可选127.0.0.1同款动态页面。"""
import argparse
from collections import Counter, deque
from contextlib import ExitStack
from functools import partial, lru_cache
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import threading
import time
import traceback
from release import VERSION
from analysis import export_run

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (HERE, ROOT/'tools', ROOT/'src/human_fall_detection', ROOT/'src/human_fall_detection/scripts'):
    sys.path.insert(0, str(path))
import replay_compare as view
from replay_range_frontend import session_meta, CALIBRATION
from core.capture_input import ROW_DTYPE, sha256_file
from core.range_contract import source_binding, load_ground
from core.range_image import ScanGrid
from core.range_runtime import RangeRuntime, serial
from core.node_runtime import LatestFrameQueue
from range_experiment import check_track_rows, RuleBaseline
from sync_audit import file_binding, digest

# perf_counter在两个支持的Windows解释器中均为单调高分辨率时钟。
clock = time.perf_counter


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False), encoding='utf-8')


def distribution(values):
    return dict(n=len(values), **{k:float(np.percentile(values, p)) if values else None
        for k,p in (('p50',50),('p95',95),('p99',99),('max',100))})


@lru_cache(maxsize=1)
def memory_reader():
    """只创建一次ctypes类型，避免每帧向POINTER类型缓存增加新类型。"""
    if os.name == 'nt':
        import ctypes
        from ctypes import wintypes
        class Counters(ctypes.Structure):
            _fields_ = [('cb',wintypes.DWORD),('PageFaultCount',wintypes.DWORD)] + [
                (n,ctypes.c_size_t) for n in ('PeakWorkingSetSize','WorkingSetSize','QuotaPeakPagedPoolUsage',
                'QuotaPagedPoolUsage','QuotaPeakNonPagedPoolUsage','QuotaNonPagedPoolUsage','PagefileUsage','PeakPagefileUsage')]
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        measure = ctypes.windll.psapi.GetProcessMemoryInfo
        measure.argtypes = [wintypes.HANDLE,ctypes.POINTER(Counters),wintypes.DWORD]
        measure.restype = wintypes.BOOL
        def read():
            c = Counters(); c.cb = ctypes.sizeof(c)
            if not measure(kernel.GetCurrentProcess(),ctypes.byref(c),c.cb):
                raise OSError('GetProcessMemoryInfo failed')
            return c.WorkingSetSize
        return read
    import resource
    return lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform == 'darwin' else 1024)


def memory_bytes():
    return memory_reader()()


class PacedQueue:
    """复用size-1 latest机制，外层锁保存每一次覆盖（不受128条诊断缓存限制）。"""
    def __init__(self):
        self.queue = LatestFrameQueue(1)
        self.lock = threading.Lock()
        self.pending = None

    def put(self, item):
        with self.lock:
            old = self.pending
            item['enqueued_mono_s'] = clock()
            self.queue.put(item)
            self.pending = item
            if old is not None:
                old.update(disposition='dropped', reason='latest_frame_overwritten',
                    dropped_mono_s=item['enqueued_mono_s'])
            return old

    def take(self):
        with self.lock:
            item = self.queue.take()
            self.pending = None
            return item


class Publications:
    def __init__(self, limit=240):
        self.lock = threading.Lock()
        self.rows = deque(maxlen=limit)
        self.seq = 0
        self.finished = False

    def publish(self, frame):
        with self.lock:
            self.seq += 1
            self.rows.append(dict(seq=self.seq, frame=frame))

    def since(self, after):
        with self.lock:
            return dict(rows=[r for r in self.rows if r['seq'] > after], finished=self.finished,
                oldest_seq=self.rows[0]['seq'] if self.rows else None, latest_seq=self.seq,
                cache_limit=self.rows.maxlen)


class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        request = urlparse(self.path)
        if request.path == '/api/frames':
            try: after = int(parse_qs(request.query).get('after',['0'])[0])
            except ValueError:
                self.send_error(400); return
            raw = serial(self.server.publications.since(after)).encode()
            self.send_response(200); self.send_header('Content-Type','application/json')
            self.send_header('Cache-Control','no-store'); self.send_header('Content-Length',str(len(raw)))
            self.end_headers(); self.wfile.write(raw)
        elif request.path == '/camera.jpg':
            try:
                i = int(parse_qs(request.query)['i'][0]); camera = self.server.camera
                if camera is None or not 0 <= i < len(camera[0]): raise ValueError()
                info = camera[0][i]; raw = camera[1][info['offset']:info['offset']+info['length']]
            except (ValueError,KeyError):
                self.send_error(404); return
            self.send_response(200); self.send_header('Content-Type','image/jpeg')
            self.send_header('Cache-Control','no-store')
            self.send_header('Content-Length',str(len(raw))); self.end_headers(); self.wfile.write(raw)
        elif request.path in ('/','/index.html','/data/frames.js'):
            super().do_GET()
        else: self.send_error(404)

    def log_message(self, *args):
        pass


def display_pick(points, size_m, limit, seed_key):
    """与既有voxel_pick逐点相同；字节记录去重避免三字段结构化排序。"""
    points = np.asarray(points,dtype=np.float64)
    if not len(points): return np.empty((0,3),dtype=float)
    cells = np.ascontiguousarray(np.floor(points/float(size_m)).astype(np.int64))
    records = cells.view(np.dtype((np.void,cells.dtype.itemsize*3))).ravel()
    _,first = np.unique(records,return_index=True)
    keep = np.sort(first)
    if len(keep)>limit:
        seed = int.from_bytes(hashlib.sha256(seed_key.encode('utf8')).digest()[:8],'little')
        picked = np.random.default_rng(seed).choice(len(keep),int(limit),replace=False)
        keep = keep[np.sort(picked)]
    return points[keep]


def display_frame(frame, result, plane, camera, info, legacy=False):
    sc = view.sc
    t, rule = result['tracking'], result['rule']
    chosen = t['target_source_rows']
    basis = sc.display_basis(plane['normal']) if plane else np.eye(3)
    offset = plane['offset_m'] if plane else 0.
    points = frame.xyz[chosen].astype(float) if chosen else np.empty((0,3))
    shown = sc.to_display(points, basis, offset)
    features = rule['features']; heights = features.get('height_m') or {}
    cam = view.camera_link(camera, info.get('bag_time_sec'))
    pick = sc.voxel_pick if legacy else display_pick
    return dict(i=t['frame'], t=t['time_s'], st=rule['state']['state'], rs=rule['state'].get('reason_codes') or [],
        tid=t['target_track_id'], n=len(chosen), hm=features.get('height_median_m'), ht=heights.get('max'),
        sp=features.get('horizontal_extent_m'), rt=features.get('descent_rate_m_s'), vt=features.get('axis_verticality'),
        bb=sc.quantize(np.stack([shown.min(axis=0),shown.max(axis=0)])) if chosen else None,
        c=sc.quantize(np.median(shown,axis=0)[:2]) if chosen else None, cam=cam, bl=None,
        bg=sc.quantize(pick(sc.to_display(frame.xyz[frame.source_rows[frame.valid]],basis,offset),
            sc.SCENE_VOXEL_M,sc.SCENE_DISPLAY_POINTS,'scene:%d'%t['frame'])),
        tg=sc.quantize(pick(shown,sc.TARGET_VOXEL_M,sc.TARGET_DISPLAY_POINTS,'target:%d'%t['frame'])),
        generation=t['generation'], reset_reason=t['reset_reason'], target_reason=t['target_reason'],
        cam_status='missing' if cam is None else ('nearby' if abs(cam[1])<=.2 else 'stale'))


def make_page(out, session, count, plane, first, port, duration=0., camera_count=0, paced=True):
    (out/'data').mkdir()
    summary = dict(title='离线逐帧运行时 · '+session.name, session=session.name,
        source=dict(frames=count,camera_frames=camera_count,duration_sec=duration),
        presentation_mode='PC离线源节奏运行时' if paced else 'PC离线全帧运行时', honesty=dict(non_causal_background=False),
        display=dict(view=dict(yaw=-1.08,pitch=.42,dist=4.8,tx=2.,ty=0.,tz=.9),
            sensor_origin_cm=[0,0,int(round(100*plane['offset_m'])) if plane else 0]),
        verdict='当前到达帧 → W1/W2 → 特征 → 规则；confirmed关闭',
        presentation_notes=['离线模式；人体/身份/跌倒/浴室GT与物理同步UNKNOWN。',
            '绿框使用全部当前目标实测点；相机仅接收近邻预览。',
            '浏览器和服务缓存各240帧；暂停与跳帧只渲染，不重算算法。'], reproduce='见本目录CONFIG.json')
    page = view.render_html(summary).replace('<script src="data/frames.js"></script>',
        '<script>window.RANGE_RUNTIME=true;</script><script src="data/frames.js"></script>')
    page = page.replace('</body>', '''<script>
    (function poll(){fetch('/api/frames?after='+(window.rangeRuntimeSeq||0),{cache:'no-store'})
      .then(function(r){if(!r.ok)throw Error(r.status);return r.json();})
      .then(function(p){window.rangeRuntimeAppend(p);if(!p.finished)setTimeout(poll,50);})
      .catch(function(){setTimeout(poll,500);});})();
    </script></body>''')
    (out/'index.html').write_text(page,encoding='utf-8')
    (out/'data/frames.js').write_text('window.FRAMES='+serial([first])+';',encoding='utf-8')
    return summary


def run(*args, **kwargs):
    with ExitStack() as resources:
        try:
            return _run(*args, _resources=resources, **kwargs)
        except BaseException as exc:
            out = getattr(resources, 'output', None)
            if out is not None:
                write_json(out/'FAILURE.json', dict(status='cancelled' if isinstance(exc, KeyboardInterrupt) else 'failed',
                    error=traceback.format_exc(), complete=False))
            raise


def _run(session, out, *, empty_prefix_frames, ground_path=None, limit=None,
        paced=False, speed=1., serve=None, processing_delay_s=0., compare_run=None, compare_rules=None,
        exit_after_replay=False, detailed=True, legacy_display=False, open_browser=False,
        alert_variant=None, body_candidates=False, _resources):
    session, out = Path(session).resolve(), Path(out).resolve()
    for protected in (session,ROOT/'data',ROOT/'captures'):
        p = protected.resolve()
        if out == p or p in out.parents or out in session.parents:
            raise ValueError('output must be outside source data')
    if not np.isfinite(speed) or speed <= 0 or not np.isfinite(processing_delay_s) or processing_delay_s < 0:
        raise ValueError('invalid playback speed/delay')
    if serve is not None and (type(serve) is not int or not 0 <= serve <= 65535):
        raise ValueError('invalid local port')
    if open_browser and serve is None: raise ValueError('open-browser requires --serve')
    if alert_variant not in (None, 'ground_alert_v1'): raise ValueError('unsupported alert variant')
    if serve is not None and not paced: raise ValueError('dynamic page requires paced offline mode')
    if paced and (compare_run or compare_rules):
        raise ValueError('compare full-frame history only in all-frames mode; paced verifies its consumed sequence')
    meta, msha = session_meta(session)
    count = len(meta['frames']) if limit is None else limit
    if not 1 <= empty_prefix_frames < count <= len(meta['frames']): raise ValueError('invalid prefix/count')
    grid = ScanGrid.from_csv(CALIBRATION/'ifw192s_azimuth_192x256.csv',CALIBRATION/'ifw192s_elevation_192x256.csv')
    identity = source_binding(session,meta,msha,sha256_file(session/'points.bin'),grid)
    identity.update(azimuth_sha256=sha256_file(CALIBRATION/'ifw192s_azimuth_192x256.csv'),
        elevation_sha256=sha256_file(CALIBRATION/'ifw192s_elevation_192x256.csv'))
    plane = load_ground(ground_path,identity) if ground_path else None
    ground_sha = sha256_file(ground_path) if ground_path else None
    runtime = RangeRuntime(grid,identity,empty_prefix_frames=empty_prefix_frames,ground=plane,ground_sha=ground_sha,detailed=detailed)
    sources = view.current_sources()+[Path(__file__).resolve(),HERE/'analysis.py',HERE/'depth.py',HERE/'release.py',ROOT/'src/human_fall_detection/scripts/replay_range_frontend.py',
        ROOT/'src/human_fall_detection/scripts/sensor_health.py']
    if body_candidates:
        sources.append(ROOT/'pc_apps/annotator_v2/body_branches.py')
    bindings = view.pin(sources+[session/n for n in ('meta.json','points.bin','camera_frames.jsonl','camera.mjpeg')])
    if ground_path:
        bindings.update(view.pin([Path(ground_path),Path(plane['provenance']['source'])]))
    old, old_rules, old_source, comparison_binding = None, None, None, {}
    if compare_run:
        folder = Path(compare_run); summary = json.loads((folder/'SUMMARY.json').read_text(encoding='utf-8'))
        legacy_config = {k:v for k,v in runtime.config.items() if k not in ('fall','posture','human_prior','baseline',
                                                                     'feature_defaults','fall_defaults','ground_alert','demo_alert')}
        legacy_sha = hashlib.sha256(serial(legacy_config).encode()).hexdigest()
        if summary['source_binding'] != identity or summary['config_sha256'] not in (runtime.config_sha, legacy_sha):
            raise ValueError('historical input/config mismatch')
        if sha256_file(folder/'frames.jsonl') != summary['frames_sha256']: raise ValueError('historical ledger SHA mismatch')
        old = view.records(folder/'frames.jsonl')
        comparison_binding.update(view.pin([folder/n for n in ('CONFIG.json','SUMMARY.json','frames.jsonl')]))
        comparison_binding['historical_source_status'] = {n:sha256_file(ROOT/n)==sha for n,sha in summary['source_sha256'].items()}
        if not all(comparison_binding['historical_source_status'].values()): raise ValueError('historical W2 source changed')
        comparison_binding['historical_manifest_scope'] = 'frozen listed sources matched; historical run is not re-certified as current complete manifest'
        old_inference = hashlib.sha256()
        for r in old:
            pure = view.experiment.inference_serial(r)
            old_inference.update(pure.encode())
        if old_inference.hexdigest() != summary['inference_output_sha256']:
            raise ValueError('historical inference aggregate mismatch')
    if compare_rules:
        folder = Path(compare_rules); summary = json.loads((folder/'SUMMARY.json').read_text(encoding='utf-8'))
        check = dict(summary); claimed = check.pop('content_sha256')
        if digest(check) != claimed or summary['source_binding'] != identity: raise ValueError('historical audit mismatch')
        if sha256_file(folder/'RULE_BASELINE.jsonl') != summary['rule_baseline_sha256']: raise ValueError('historical rules SHA mismatch')
        if sha256_file(folder/'SOURCE_ROWS.jsonl') != summary['source_rows_sha256']: raise ValueError('historical source rows SHA mismatch')
        for name,expected in summary['binding']['audit_sources'].items():
            if file_binding(ROOT/name) != expected: raise ValueError('historical audit source changed: '+name)
        old_rules = view.records(folder/'RULE_BASELINE.jsonl')
        old_source = view.records(folder/'SOURCE_ROWS.jsonl')
        if old is not None and (len(old_rules) != len(old) or any(
                rule.get('input_inference_sha256') != track.get('inference_sha256')
                or rule.get('source_rows') != track.get('target_source_rows')
                for track, rule in zip(old, old_rules))):
            raise ValueError('historical rule/inference binding mismatch')
        comparison_binding.update(view.pin([folder/n for n in ('SUMMARY.json','RULE_BASELINE.jsonl','SOURCE_ROWS.jsonl')]))
    out.mkdir(parents=True,exist_ok=False)
    _resources.output = out
    config = dict(release_version=VERSION,settings=runtime.config, config_sha256=runtime.config_sha, source_binding=identity,
        mode='source_paced' if paced else 'all_frames',speed=speed,processing_delay_s=processing_delay_s,
        queue_capacity=1, server_cache=240, browser_cache=240, clock='source header vs local replay perf_counter monotonic; NOT device end-to-end',
        clock_info=vars(time.get_clock_info('perf_counter')),detailed=detailed,legacy_display=legacy_display,
        input_and_source_bindings=bindings, historical_comparison=comparison_binding,
        environment=dict(python=sys.version,executable=sys.executable,numpy=np.__version__,platform=platform.platform(),
            threads={k:os.getenv(k) for k in ('OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS')}))
    if alert_variant is not None: config['alert_variant'] = alert_variant
    if body_candidates: config['body_candidates'] = True
    write_json(out/'CONFIG.json',config)
    if (session/'camera.mjpeg').exists() != (session/'camera_frames.jsonl').exists():
        raise ValueError('incomplete camera input pair')
    camera = view.sc.read_camera(session)
    q, publications = PacedQueue(), Publications()
    stop = threading.Event(); errors = []; costs = []; arrivals = []; consumed = []
    differences = []; states = Counter(); server = None; page_summary = None
    t0 = meta['frames'][0]['stamp_sec']*10**9+meta['frames'][0]['stamp_nanosec']
    def stamp(info):return (info['stamp_sec']*10**9+info['stamp_nanosec']-t0)/1e9
    with (out/'frames.jsonl').open('x',encoding='utf-8') as ledger, \
         (out/'RULE_BASELINE.jsonl').open('x',encoding='utf-8') as rules_file, \
         (out/'timings.jsonl').open('x',encoding='utf-8') as times, \
         (out/'SOURCE_ROWS.jsonl').open('x',encoding='utf-8') as audit, \
         (out/'display.jsonl').open('x',encoding='utf-8') as display_file:
        def consume(item):
            nonlocal server, page_summary
            i = item['frame']; info = meta['frames'][i]; start = clock()
            item['started_mono_s'] = start
            # 唯一worker读取当前字节；不预解码未来帧。
            io_start = time.perf_counter()
            with (session/'points.bin').open('rb') as stream:
                stream.seek(info['offset_points']*ROW_DTYPE.itemsize)
                raw = stream.read(info['count_points']*ROW_DTYPE.itemsize)
            if len(raw) != info['count_points']*ROW_DTYPE.itemsize: raise ValueError('truncated frame')
            io_done = time.perf_counter()
            result, frame, components = runtime.update(raw,stamp(info),i)
            item['completed_mono_s'] = clock()
            record = result['tracking']; rule = result['rule']; cost = result['timings']
            item['skipped_input_frames_before_current'] = result['skipped_input_frames']
            diag_start = time.perf_counter()
            source = check_track_rows(frame,record,components,plane)
            partition = np.concatenate([frame.source_rows[frame.valid]]+list(frame.rejected.values()))
            if not np.array_equal(np.sort(partition),np.arange(info['count_points'])):
                raise ValueError('decode partition mismatch')
            record.update(status=result['status'],source_binding=identity,config_sha256=runtime.config_sha,
                raw_sha256=hashlib.sha256(raw).hexdigest(),offset_points=info['offset_points'])
            source_encode_start = time.perf_counter()
            encoded_source = serial(dict(frame=i,raw_sha256=record['raw_sha256'],replay=source))
            cost['source_ledger_json_ms'] = (time.perf_counter()-source_encode_start)*1000
            source_io_start = time.perf_counter()
            audit.write(encoded_source+'\n')
            cost['source_ledger_io_ms'] = (time.perf_counter()-source_io_start)*1000
            if old_source is not None and source != old_source[i]['replay']:
                differences.append(dict(frame=i,kind='source_ownership',keys=['replay']))
            for kind, expected, actual in [('W2',old[i] if old else None,record),('rules',old_rules[i] if old_rules else None,rule)]:
                if expected is not None:
                    keys = list(actual) if kind == 'rules' else [k for k in result['tracking'] if k not in ('status','source_binding','config_sha256','raw_sha256','offset_points')]
                    changed = [k for k in keys if k not in ('inference_sha256','input_inference_sha256')
                               and expected.get(k) != actual[k]]
                    if changed: differences.append(dict(frame=i,kind=kind,keys=changed))
            cost['diagnostics_binding_ms'] = (time.perf_counter()-diag_start)*1000
            display_start = time.perf_counter()
            displayed = display_frame(frame,result,plane,camera,info,legacy=legacy_display)
            cost['display_ms'] = (time.perf_counter()-display_start)*1000
            if page_summary is None:
                page_summary = make_page(out,session,count,plane,displayed,serve,
                    duration=stamp(meta['frames'][count-1]),camera_count=len(camera[0]) if camera else 0,paced=paced)
            if server is None and serve is not None:
                server = ThreadingHTTPServer(('127.0.0.1',serve),partial(Handler,directory=str(out)))
                server.publications, server.camera = publications, camera
                threading.Thread(target=server.serve_forever,daemon=True).start()
                _resources.callback(server.server_close)
                _resources.callback(server.shutdown)
                print('PAGE http://127.0.0.1:%d/'%server.server_port,flush=True)
                if open_browser:
                    import webbrowser
                    webbrowser.open('http://127.0.0.1:%d/'%server.server_port)
            encode_start = time.perf_counter()
            encoded = serial(record); encoded_rule = serial(rule); encoded_display = serial(displayed)
            cost['json_ms'] = (time.perf_counter()-encode_start)*1000
            write_start = time.perf_counter()
            ledger.write(encoded+'\n'); rules_file.write(encoded_rule+'\n'); display_file.write(encoded_display+'\n')
            cost['output_io_ms'] = (time.perf_counter()-write_start)*1000
            publish_start = time.perf_counter()
            publications.publish(displayed)
            item['published_mono_s'] = clock()
            cost['publish_ms'] = (time.perf_counter()-publish_start)*1000
            cost.update(frame=i,status=result['status'], input_io_ms=(io_done-io_start)*1000,
                loop_ms=(clock()-start)*1000, queue_age_ms=(start-item['arrival_mono_s'])*1000,
                replay_frame_age_ms=(item['published_mono_s']-item['arrival_mono_s'])*1000,
                replay_backlog_ms=max(0.,(start-item['scheduled_mono_s'])*1000),memory_bytes=memory_bytes())
            times.write(serial(cost)+'\n'); costs.append(cost); consumed.append(i)
            states[rule['state']['state']] += 1
            item.update(disposition='processed',reason=None)
            if processing_delay_s and i >= empty_prefix_frames: time.sleep(processing_delay_s)
        def worker():
            try:
                while True:
                    q.queue.wait(.1)
                    item = q.take()
                    if item is not None: consume(item)
                    elif stop.is_set(): break
            except BaseException:
                errors.append(traceback.format_exc()); stop.set()
        worker_thread = threading.Thread(target=worker) if paced else None
        if worker_thread: worker_thread.start()
        epoch = clock()
        try:
            for i,info in enumerate(meta['frames'][:count]):
                scheduled = epoch+stamp(info)/speed if paced else clock()
                if paced:
                    while not errors:
                        remaining = scheduled-clock()
                        if remaining <= 0: break
                        stop.wait(min(.05,remaining))
                if errors: break
                item = dict(frame=i,source_time_s=stamp(info),scheduled_mono_s=scheduled,
                    arrival_mono_s=clock(),enqueued_mono_s=None,started_mono_s=None,
                    completed_mono_s=None,published_mono_s=None,queue_depth=1 if paced else 0)
                arrivals.append(item)
                if paced: q.put(item)
                else:
                    item['enqueued_mono_s'] = clock(); consume(item)
        except BaseException:
            errors.append(traceback.format_exc())
            raise
        finally:
            stop.set(); q.queue.wake()
            if worker_thread: worker_thread.join()
            publications.finished = True
            for item in arrivals:
                if 'disposition' not in item:
                    item.update(disposition='failed' if item['started_mono_s'] is not None else 'cancelled',
                        reason='replay_interrupted')
            with (out/'ARRIVALS.jsonl').open('x',encoding='utf-8') as f:
                for row in arrivals: f.write(serial(row)+'\n')
            write_json(out/'CONSUMED.json',consumed)
            if errors: (out/'ERROR.log').write_text('\n'.join(errors),encoding='utf-8')
        if errors:
            (out/'ERROR.log').write_text('\n'.join(errors),encoding='utf-8')
            raise RuntimeError('worker failed; see ERROR.log')
    # 同一实际消费序列重跑（不读跳过帧，也不要求与全帧一致）。
    recheck = RangeRuntime(grid,identity,empty_prefix_frames=empty_prefix_frames,ground=plane,ground_sha=ground_sha)
    sequence_diff = []
    with (session/'points.bin').open('rb') as stream, (out/'frames.jsonl').open(encoding='utf-8') as saved, \
         (out/'RULE_BASELINE.jsonl').open(encoding='utf-8') as saved_rules:
        for i in consumed:
            info = meta['frames'][i]; stream.seek(info['offset_points']*ROW_DTYPE.itemsize)
            actual,_,_ = recheck.update(stream.read(info['count_points']*ROW_DTYPE.itemsize),stamp(info),i)
            old_record = json.loads(next(saved)); old_rule = json.loads(next(saved_rules))
            if actual['tracking']['inference_sha256'] != old_record['inference_sha256'] or actual['rule'] != old_rule:
                sequence_diff.append(i)
    view.verify(bindings)
    view.verify({p:v for p,v in comparison_binding.items() if Path(p).is_absolute()})
    ready = [c for c in costs if c['status'] != 'prefix_warmup']
    result = dict(schema='range_runtime_replay_v1',release_version=VERSION,
        software_status='PASS' if not differences and not sequence_diff else 'FAIL',
        input_frames=len(arrivals),processed_frames=len(consumed),
        dropped_frames=sum(r['disposition']=='dropped' for r in arrivals),states=dict(states),
        differences=differences,consumed_sequence_differences=sequence_diff,
        performance={k:distribution([c[k] for c in ready]) for k in ready[0] if k not in ('frame','status')},
        warmup_performance={k:distribution([c[k] for c in costs if c['status']=='prefix_warmup']) for k in ('event_chain_ms','loop_ms','background_init_ms')},
        source_binding=identity,config_sha256=runtime.config_sha,
        gates=dict(G1a='prior PASS',G1b='FAIL 5.448%; f360 UNRESOLVED',
            G1c='PASS' if np.percentile([c['frontend_ms'] for c in ready],95)<10 else 'FAIL',
            G2='PASS' if np.percentile([c['algorithm_ms'] for c in ready],95)<15 else 'FAIL'),
        human_identity_fall_bathroom='UNKNOWN',physical_sync='UNKNOWN',board_performance='UNKNOWN',
        confirmed_enabled=False,device_end_to_end_latency='UNKNOWN',
        timing_scope='nested stage timers; algorithm_ms W1+W2; event_chain adds rule geometry/features/state; loop adds diagnostics/display/JSON/IO/publication; simulated delay outside loop; sequence recheck excluded',
        queue_capacity=1,queue_max_depth=max(r['queue_depth'] for r in arrivals),
        source_sha256={str(p.relative_to(ROOT)):sha256_file(p) for p in sources})
    (out/'replay.html').write_text(view.render_html(page_summary),encoding='utf-8')
    tail = [r['frame'] for r in publications.since(0)['rows']]
    (out/'data/frames.js').write_text('window.FRAMES='+serial(tail)+';',encoding='utf-8')
    if camera:
        (out/'camera').mkdir()
        for i in sorted({r['cam'][0] for r in tail if r['cam'] is not None and r['cam_status']=='nearby'}):
            info = camera[0][i]
            (out/'camera'/('c%03d.jpg'%i)).write_bytes(camera[1][info['offset']:info['offset']+info['length']])
    if serve is None:
        (out/'index.html').write_text(view.render_html(page_summary),encoding='utf-8')
    view.verify(bindings)
    result['ledger_sha256'] = {name:sha256_file(out/name) for name in ('frames.jsonl','RULE_BASELINE.jsonl','SOURCE_ROWS.jsonl')}
    write_json(out/'SUMMARY.json',result)
    if result['software_status'] == 'PASS':
        export_run(out, session, out/'analysis.json')
    if server:
        print('Replay complete; page remains available until Ctrl+C' if not exit_after_replay else 'Replay complete',flush=True)
        try:
            while not exit_after_replay: time.sleep(.2)
        except KeyboardInterrupt: pass
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--session',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    p.add_argument('--empty-prefix-frames',type=int,required=True);p.add_argument('--ground',type=Path)
    p.add_argument('--limit',type=int);p.add_argument('--paced',action='store_true');p.add_argument('--speed',type=float,default=1.)
    p.add_argument('--serve',type=int);p.add_argument('--processing-delay-s',type=float,default=0.)
    p.add_argument('--compare-run',type=Path);p.add_argument('--compare-rules',type=Path)
    p.add_argument('--exit-after-replay',action='store_true')
    p.add_argument('--open-browser',action='store_true')
    p.add_argument('--no-detail',action='store_true');p.add_argument('--legacy-display',action='store_true')
    p.add_argument('--alert-variant', choices=['ground_alert_v1'],
                   help='opt-in sustained low posture hint; squatting/sitting also triggers, not a fall event')
    p.add_argument('--body-candidates', action='store_true', help='precompute same-target body regions for playback')
    a=p.parse_args(argv);result=run(a.session,a.out,empty_prefix_frames=a.empty_prefix_frames,ground_path=a.ground,
        limit=a.limit,paced=a.paced,speed=a.speed,serve=a.serve,processing_delay_s=a.processing_delay_s,
        compare_run=a.compare_run,compare_rules=a.compare_rules,exit_after_replay=a.exit_after_replay,
        detailed=not a.no_detail,legacy_display=a.legacy_display,open_browser=a.open_browser,
        alert_variant=a.alert_variant,body_candidates=a.body_candidates)
    print(serial({k:result[k] for k in ('input_frames','processed_frames','dropped_frames','differences','consumed_sequence_differences','gates')}))
    if result['software_status'] != 'PASS': raise SystemExit(2)


if __name__=='__main__':main()
