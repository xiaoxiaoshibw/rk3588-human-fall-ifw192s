#!/usr/bin/env python3
"""Resident ROS1 adapter for the shared RangeEngine. No Qt/process control API."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import threading
import time
import queue

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService, assert_single_publisher, acquire_service_lock
from core.range_fit_job import GroundFitJob
from core.range_site_ground import FIT_FRAMES, HELD_FRAMES, fit_site, save_fit
from core.subscription_health import SubscriptionGuard


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--release-id', default='development')
    parser.add_argument('--azimuth-table', type=Path)
    parser.add_argument('--elevation-table', type=Path)
    parser.add_argument('--declare-empty-prefix', action='store_true',
                        help='explicitly authorize the next 50 consecutive input frames as empty')
    parser.add_argument('--fit-ground-out', type=Path, help='one asynchronous 25+3 frame site fit; derived evidence only')
    parser.add_argument('--site-id')
    parser.add_argument('--ground-fit-timeout-s', type=float, default=60.)
    parser.add_argument('--diagnostics', action='store_true', help='bounded derived candidate/history summaries; no raw clouds')
    if argv is None and '--help' not in sys.argv and '-h' not in sys.argv:
        import rospy
        argv = rospy.myargv()[1:]
    args = parser.parse_args(argv)
    if not math.isfinite(args.ground_fit_timeout_s) or args.ground_fit_timeout_s <= 0:
        parser.error('ground fit timeout must be positive and finite')
    config_bytes = args.config.read_bytes()
    config = json.loads(config_bytes)
    if config.get('protocol') != 'range_recognition/1':
        parser.error('unsupported service config')
    if args.fit_ground_out and (not args.site_id or not args.declare_empty_prefix):
        parser.error('site fit requires --site-id and an explicitly declared empty background prefix')
    bundle = Path(__file__).resolve().parents[3]
    az, el = [args.azimuth_table or bundle/config['azimuth_table'],
              args.elevation_table or bundle/config['elevation_table']]
    effective = dict(config, azimuth_table=str(az), elevation_table=str(el),
        declare_empty_prefix=args.declare_empty_prefix, site_id=args.site_id,
        fit_ground_out=str(args.fit_ground_out) if args.fit_ground_out else None,
        ground_fit_timeout_s=args.ground_fit_timeout_s)
    effective['diagnostics'] = args.diagnostics
    grid = ScanGrid.from_csv(az, el)
    engine = RangeEngine(grid, config['frame_id'], empty_prefix_frames=50 if args.declare_empty_prefix else None)
    engine.diagnostics = args.diagnostics
    service = RangeService(engine, args.release_id, preview=config.get('preview', True))
    with acquire_service_lock(config['state_topic']):
        return serve(args, config, effective, config_bytes, grid, engine, service)


def serve(args, config, effective, config_bytes, grid, engine, service):
    import rospy
    import rosgraph
    from sensor_msgs.msg import PointCloud2
    from std_msgs.msg import String
    topic, state_topic = config['input_topic'], config['state_topic']
    # Check before init_node: fixed ROS names can shut down an existing instance.
    probe = rosgraph.Master('/range_recognition_preflight')
    assert_single_publisher(probe.getSystemState()[0], state_topic, '')
    rospy.init_node('range_recognition_service', anonymous=True)
    master = rosgraph.Master(rospy.get_name())
    assert_single_publisher(master.getSystemState()[0], state_topic, rospy.get_name())
    publisher = rospy.Publisher(state_topic, String, queue_size=1, latch=False)
    stop = threading.Event()
    guard = None

    def callback(msg):
        now = time.monotonic()
        if guard is not None:
            guard.note_message(now)
        service.submit(msg)

    guard = SubscriptionGuard(lambda: rospy.Subscriber(topic, PointCloud2, callback,
        queue_size=1, buff_size=2**24), time.monotonic(), watch_messages=True)
    failure = []
    initialization = dict(background='explicit_empty_prefix_50' if args.declare_empty_prefix else 'not_declared',
        ground='pending_single_fit' if args.fit_ground_out else 'not_loaded')

    fit_job = [None]
    fit_lock = threading.Lock()
    fit_results = queue.Queue(maxsize=1)
    fit_thread = [None]

    def current_fit(detach=False):
        with fit_lock:
            job = fit_job[0]
            if detach:fit_job[0] = None
            return job

    def fit_failed(reason):
        initialization['ground'] = 'fit_failed: '+str(reason)
        if engine.runtime:
            engine.runtime.ground = None
            engine.runtime.ground_sha = None
            engine.runtime.config['ground_sha256'] = None
            engine.runtime.config_sha = hashlib.sha256(json.dumps(engine.runtime.config,sort_keys=True).encode()).hexdigest()
        engine.ground_status = dict(available=False, reason=initialization['ground'])
        engine.clear_history()

    def finish_fit(samples, headers, unavailable=None):
        """Spawn, reap, save and validate files away from recognition/heartbeat."""
        job = None
        try:
            report = unavailable
            if report is None:
                job = GroundFitJob((samples, headers,
                    dict(siteId=args.site_id, frameId=engine.frame_id, gridSha256=grid.sha256),
                    dict(upstream='ros:'+topic, identity=dict(engine.identity))),
                    timeout_s=args.ground_fit_timeout_s)
                with fit_lock:
                    if not stop.is_set():fit_job[0] = job
                if stop.is_set():return
                while not stop.is_set():
                    report = job.poll()
                    if report is not None:break
                    stop.wait(.02)
            if stop.is_set():return
            path = save_fit(report, args.fit_ground_out)
            if not path:
                outcome = (None, None, report.get('reason', 'fit_unavailable'))
            else:
                ground, sha = engine.prepare_ground(path, args.site_id)
                outcome = (ground, sha, None)
            if not stop.is_set():fit_results.put_nowait(outcome)
        except Exception as exc:
            if not stop.is_set():fit_results.put_nowait((None, None, repr(exc)))
        finally:
            if job is not None:job.close()
            with fit_lock:
                if fit_job[0] is job:fit_job[0] = None

    def start_fit(samples, headers, unavailable=None):
        initialization['ground'] = 'fitting' if unavailable is None else unavailable['reason']
        fit_thread[0] = threading.Thread(target=finish_fit, args=(samples,headers,unavailable),
            name='ground-fit-completion', daemon=True)
        fit_thread[0].start()

    def recognition():
        samples, headers = [], []
        try:
            while not stop.is_set():
                service.queue.wait(.05)
                result = service.process_latest()
                try:outcome = fit_results.get_nowait()
                except queue.Empty:outcome = None
                if outcome is not None:
                    service.clear_ground_binding()
                    try:
                        ground, sha, reason = outcome
                        if reason:fit_failed(reason)
                        elif not stop.is_set():
                            engine.install_prepared_ground(ground,sha,'ros:'+topic)
                            initialization['ground'] = 'bound'
                    except Exception as exc:
                        fit_failed(repr(exc))
                if (not stop.is_set() and args.fit_ground_out and initialization['ground'] == 'pending_single_fit'
                        and current_fit() is None and result and result.get('source')):
                    h = result['source']
                    header = dict(seq=h['seq'], sec=h['stamp_secs'], nsec=h['stamp_nsecs'],
                                  frame_id=h['frame_id'], wire_sha256=result['local_range']['wireSha256'])
                    if headers and header['seq'] != headers[-1]['seq']+1:
                        start_fit([], [], dict(status='unavailable', reason='fit_source_discontinuous', headers=headers))
                        samples, headers = [], []
                        continue
                    frame = engine.ground_frame
                    samples.append(frame.xyz[frame.source_rows[frame.valid]].copy())
                    headers.append(header)
                    if len(samples) == FIT_FRAMES+HELD_FRAMES:
                        start_fit(samples,headers)
                        samples, headers = [], []
        except Exception as exc:
            failure.append('recognition_worker_failed: '+repr(exc))
            stop.set()

    def preview():
        try:
            while not stop.is_set():
                service.previews.wait(.05)
                service.process_preview()
        except Exception as exc:
            # Preview failure is explicit and cannot stop target/alarm processing.
            initialization['preview'] = 'unavailable: '+repr(exc)

    workers = [threading.Thread(target=recognition, name='recognition', daemon=True)]
    if service.preview:
        workers.append(threading.Thread(target=preview, name='preview', daemon=True))
    for worker in workers:
        worker.start()
    next_owner_check = 0.
    updated = getattr(service, 'updated', None)
    try:
        while not rospy.is_shutdown() and not stop.is_set():
            now = time.monotonic()
            guard.poll(now)
            if now >= next_owner_check:
                assert_single_publisher(master.getSystemState()[0], state_topic, rospy.get_name())
                next_owner_check = now+2.
            # Clear before snapshot: an update landing during publish stays pending
            # and wakes the next iteration immediately. Test substitutes without the
            # event keep the fixed 50 ms cadence.
            if updated is not None: updated.clear()
            result = service.snapshot(guard.report())
            result['service'].update(configSha256=hashlib.sha256(json.dumps(effective,sort_keys=True).encode()).hexdigest(),
                configFileSha256=hashlib.sha256(config_bytes).hexdigest(),
                effectiveConfig=effective, initialization=dict(initialization))
            start = time.monotonic()
            service.note_publish_started()
            publisher.publish(String(data=json.dumps(result, allow_nan=False, separators=(',', ':'))))
            service.note_published((time.monotonic()-start)*1000)
            if updated is not None: updated.wait(.05)
            else: stop.wait(.05)
    finally:
        stop.set()
        job = current_fit(detach=True)
        if job is not None:job.close()
        guard.subscriber.unregister() if guard.subscriber else None
        for worker in workers:
            worker.join(2.)
        if fit_thread[0] is not None:fit_thread[0].join(2.)
        final = service.snapshot(guard.report())
        final.update(source=None, local_range=None, groundBinding=None, target_source_rows=[], track_id=None,
                     bbox_observed=False, fall_status='unknown', observability='invalid',
                     acquisition=dict(reason=failure[0] if failure else 'service_stopped'))
        publisher.publish(String(data=json.dumps(final, allow_nan=False)))
    if failure:
        raise RuntimeError(failure[0])
    return 0


if __name__ == '__main__':
    sys.exit(main())
