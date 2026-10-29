#!/usr/bin/env python3
"""独立ROS1距离图旁路。只订阅点云、发布图像/诊断，不写盘或调用设备控制。"""
import argparse
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from core.range_image import ScanGrid
from core.range_live import LiveRange


def source_image_type(image_type):
    """保留源header.seq；rospy默认会把_has_header消息的seq改成发布计数。

    仅改变本地序列化标志，继承原Image的线格式/type/md5，不修改ROS库或消息定义。
    """
    class SourceImage(image_type):
        _has_header = False
    return SourceImage


def publish_result(result, header, publishers, image_factory):
    """所有输出使用同一源header；测试通过注入普通消息替身运行。"""
    for name, values in result['images'].items():
        msg = image_factory()
        msg.header = header
        for key, value in values.items():
            setattr(msg, key, value)
        publishers[name].publish(msg)
    return {k:v for k,v in result.items() if k != 'images'}


def heartbeat_status(status, last_output, now, max_age_s):
    result = dict(status)
    result['last_result_age_ms'] = max(0., now-last_output)*1000
    if now-last_output > max_age_s:
        result.update(status='stale', last_result_status=status['status'])
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--azimuth-table', required=True)
    parser.add_argument('--elevation-table', required=True)
    parser.add_argument('--frame-id', required=True, help='expected raw sensor frame, e.g. innolidar')
    parser.add_argument('--topic', default='/innolidar_points')
    parser.add_argument('--output-prefix', default='/range_image_live')
    parser.add_argument('--max-age-s', type=float, default=.5)
    parser.add_argument('--preview', action='store_true', help='publish uncompressed RGB8, no PNG encoding')
    # ROS remapping/__name parameters are stripped only in the ROS entry point.
    if argv is None:
        argv = sys.argv[1:]
        if '--help' not in argv and '-h' not in argv:
            import rospy
            argv = rospy.myargv()[1:]
    args = parser.parse_args(argv)
    grid = ScanGrid.from_csv(args.azimuth_table, args.elevation_table)
    live = LiveRange(grid, args.frame_id, args.max_age_s, args.preview)
    import rospy
    from sensor_msgs.msg import Image, PointCloud2
    from std_msgs.msg import Header, String
    rospy.init_node('range_image_live', anonymous=False)
    source_image = source_image_type(Image)
    names = ['range', 'source_rows', 'valid'] + (['preview'] if args.preview else [])
    publishers = {name:rospy.Publisher(args.output_prefix+'/'+name, Image, queue_size=1, latch=False)
                  for name in names}
    state = rospy.Publisher(args.output_prefix+'/state', String, queue_size=1, latch=False)
    subscriber = rospy.Subscriber(args.topic, PointCloud2, live.submit, queue_size=1, buff_size=2**24)
    last_output = time.perf_counter()
    last_heartbeat = 0.
    status = dict(schema='lidar_range_live/1', status='waiting', source=None, grid_sha256=grid.sha256)
    try:
        while not rospy.is_shutdown():
            live.queue.wait(.1)
            result = live.process_latest()
            now = time.perf_counter()
            if result is not None:
                source = result['source']
                header = None
                if result['images']:
                    header = Header(seq=source['seq'], stamp=rospy.Time(source['stamp_sec'], source['stamp_nanosec']),
                                    frame_id=source['frame_id'])
                publish_start = time.perf_counter()
                status = publish_result(result, header, publishers, source_image)
                status['publish_enqueue_ms'] = (time.perf_counter()-publish_start)*1000
                status['latency_scope'] = 'local receive to conversion; publish is enqueue, not device/network/display latency'
                last_output = now
            elif now-last_heartbeat < .5:
                continue
            heartbeat = heartbeat_status(status, last_output, now, args.max_age_s)
            state.publish(String(data=json.dumps(heartbeat, allow_nan=False, separators=(',', ':'))))
            last_heartbeat = now
    finally:
        subscriber.unregister()
    return 0


if __name__ == '__main__':
    sys.exit(main())
