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

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.range_engine import RangeEngine
from core.range_image import ScanGrid
from core.range_service import RangeService, RawCloudWire, assert_single_publisher, acquire_service_lock
from core.range_fit_job import GroundFitJob
from core.range_site_ground import save_fit
from core.range_initialization import SiteInitialization
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
    parser.add_argument('--human-physical-v1', action='store_true',
                        help='enable pure-LiDAR human_physical_v1 telemetry (read-only sidecar, no writeback)')
    parser.add_argument('--single-person-lock', action='store_true',
                        help='enable fragment pre-filter and human-compatible single-target lock')
    parser.add_argument('--instant-start', action='store_true',
                        help='zero-init adaptive background + gravity leveling + silent background ground refinement')
    parser.add_argument('--mount-pitch-deg', type=float, default=26.0,
                        help='nominal sensor pitch downward in degrees for --instant-start (used before IMU/refinement)')
    parser.add_argument('--mount-roll-deg', type=float, default=0.0,
                        help='nominal sensor roll in degrees for --instant-start (used before IMU/refinement)')
    parser.add_argument('--imu-topic', default='/inno_imu',
                        help='optional ROS1 sensor_msgs/Imu topic for static gravity alignment in --instant-start')
    parser.add_argument('--disable-imu', action='store_true',
                        help='do not subscribe to --imu-topic even in --instant-start mode')
    if argv is None and '--help' not in sys.argv and '-h' not in sys.argv:
        import rospy
        argv = rospy.myargv()[1:]
    args = parser.parse_args(argv)
    if not math.isfinite(args.ground_fit_timeout_s) or args.ground_fit_timeout_s <= 0:
        parser.error('ground fit timeout must be positive and finite')
    if not (-85.0 <= args.mount_pitch_deg <= 85.0 and -85.0 <= args.mount_roll_deg <= 85.0):
        parser.error('mount pitch/roll must be finite within [-85, 85] degrees')
    if args.instant_start and (args.declare_empty_prefix or args.fit_ground_out):
        parser.error('--instant-start cannot be combined with --declare-empty-prefix or --fit-ground-out')
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
    effective['human_physical_v1'] = args.human_physical_v1
    effective['single_person_lock'] = args.single_person_lock
    effective['instant_start'] = args.instant_start
    if args.instant_start:
        effective['mount_pitch_deg'] = args.mount_pitch_deg
        effective['mount_roll_deg'] = args.mount_roll_deg
        effective['imu_topic'] = None if args.disable_imu else args.imu_topic
    grid = ScanGrid.from_csv(az, el)
    engine = RangeEngine(grid, config['frame_id'],
        empty_prefix_frames=50 if args.declare_empty_prefix else None,
        human_physical_v1=args.human_physical_v1,
        single_person_lock=args.single_person_lock,
        instant_start=args.instant_start,
        mount_pitch_deg=args.mount_pitch_deg,
        mount_roll_deg=args.mount_roll_deg)
    engine.diagnostics = args.diagnostics
    service = RangeService(
        engine, args.release_id, preview=config.get('preview', True),
        preview_compress_level=1 if args.instant_start else 6,
    )
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

    any_msg_cls = getattr(rospy, 'AnyMsg', None)

    def callback(msg):
        now = time.monotonic()
        if guard is not None:
            guard.note_message(now)
        raw_buf = getattr(msg, '_buff', None) if any_msg_cls is not None else None
        service.submit(RawCloudWire(raw_buf) if raw_buf is not None else msg)

    cloud_msg_type = any_msg_cls if any_msg_cls is not None else PointCloud2
    guard = SubscriptionGuard(lambda: rospy.Subscriber(topic, cloud_msg_type, callback,
        queue_size=1, buff_size=2**24), time.monotonic(), watch_messages=True)
    imu_sub = None
    if args.instant_start and not args.disable_imu and args.imu_topic:
        try:
            if any_msg_cls is not None:
                imu_state = [0, 0.0]

                def imu_callback(msg):
                    # 前 50 个样本全速收敛（约 0.2 s），收敛后按 20 Hz 采样，消除 230 Hz 冗余回调开销
                    if imu_state[0] >= 50:
                        now_imu = time.monotonic()
                        if now_imu - imu_state[1] < 0.05:
                            return
                        imu_state[1] = now_imu
                    if service.submit_imu(msg):
                        imu_state[0] += 1

                imu_sub = rospy.Subscriber(args.imu_topic, any_msg_cls, imu_callback,
                                           queue_size=8, buff_size=65536)
            else:
                from sensor_msgs.msg import Imu as _ImuMsg
                imu_sub = rospy.Subscriber(args.imu_topic, _ImuMsg, service.submit_imu, queue_size=50)
        except Exception:
            imu_sub = None
    failure = []
    if args.instant_start:
        initializer = None
        initialization = dict(
            background='instant_adaptive_far_bg',
            ground='gravity_only_with_silent_refinement',
            imu_topic=None if (args.disable_imu or imu_sub is None) else args.imu_topic,
            mount_pitch_deg=args.mount_pitch_deg,
            mount_roll_deg=args.mount_roll_deg,
        )
    else:
        initializer = SiteInitialization(service, declared_empty=args.declare_empty_prefix,
            output=args.fit_ground_out, site_id=args.site_id, upstream='ros:'+topic,
            timeout_s=args.ground_fit_timeout_s, stop=stop, job_factory=GroundFitJob, save=save_fit)
        initialization = initializer.status

    def recognition():
        try:
            while not stop.is_set():
                service.queue.wait(.05)
                result = service.process_latest()
                if initializer is not None:
                    initializer.observe(result)
                elif getattr(service.engine, 'ground_refiner', None) is not None:
                    initialization['ground'] = service.engine.ground_refiner.stage
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
    config_sha256 = hashlib.sha256(json.dumps(effective, sort_keys=True).encode()).hexdigest()
    config_file_sha256 = hashlib.sha256(config_bytes).hexdigest()
    try:
        while not rospy.is_shutdown() and not stop.is_set():
            now = time.monotonic()
            guard.poll(now)
            if now >= next_owner_check:
                assert_single_publisher(master.getSystemState()[0], state_topic, rospy.get_name())
                next_owner_check = now+2.
            # Clear before snapshot: an update landing during publish stays pending
            # and wakes the next iteration immediately. Heartbeat cap 150 ms (< 500 ms TTL)
            # avoids duplicate 65 KB PNG re-serialization between 10 Hz frames.
            if updated is not None: updated.clear()
            result = service.snapshot(guard.report())
            result['service'].update(configSha256=config_sha256,
                configFileSha256=config_file_sha256,
                effectiveConfig=effective, initialization=dict(initialization))
            start = time.monotonic()
            service.note_publish_started()
            publisher.publish(String(data=json.dumps(result, allow_nan=False, separators=(',', ':'))))
            service.note_published((time.monotonic()-start)*1000)
            if updated is not None: updated.wait(.15)
            else: stop.wait(.05)
    finally:
        stop.set()
        if initializer is not None:
            initializer.close()
        if imu_sub is not None:
            try:
                imu_sub.unregister()
            except Exception:
                pass
        guard.subscriber.unregister() if guard.subscriber else None
        for worker in workers:
            worker.join(2.)
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
