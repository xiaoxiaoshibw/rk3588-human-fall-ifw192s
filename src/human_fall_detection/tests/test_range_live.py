"""实时适配/队列/图像发布回归；纯NumPy及ROS消息替身，无设备访问。"""
import copy
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from core.capture_input import ROW_DTYPE
from core.range_live import LiveRange, image_buffers, pointcloud_rows
from core.range_image import ScanGrid
from range_image_node import heartbeat_status, main, publish_result, source_image_type


def cloud(rows, width=None, padding=0, endian='<', step=26, sec=10):
    """模拟驱动26字节、不对齐float64时间；也覆盖更长点/行填充。"""
    names = ('x', 'y', 'z', 'intensity', 'ring', 'timestamp')
    formats = [endian+x for x in ('f4', 'f4', 'f4', 'f4', 'u2', 'f8')]
    offsets = (0, 4, 8, 12, 16, 18)
    dtype = np.dtype(dict(names=names, formats=formats, offsets=offsets, itemsize=step))
    width = len(rows) if width is None else width
    height = len(rows)//width if width else 1
    stride = width*step+padding
    data = bytearray(height*stride)
    view = np.ndarray((height, width), dtype=dtype, buffer=data, strides=(stride, step))
    for name in names:
        view[name] = rows[name].reshape(height, width)
    return NS(width=width, height=height, point_step=step, row_step=stride,
              is_bigendian=endian == '>', data=bytes(data),
              fields=[NS(name=name, offset=offset, datatype=kind, count=1)
                      for name, offset, kind in zip(names, offsets, (7, 7, 7, 7, 4, 8))],
              header=NS(seq=1, stamp=NS(secs=sec, nsecs=123), frame_id='innolidar'))


def scene():
    az = np.array([[-20., 0., 20.], [-20., 0., 20.]])
    el = np.array([[-10.]*3, [10.]*3])
    grid = ScanGrid(az, el)
    rows = np.zeros(6, dtype=ROW_DTYPE)
    a, e = np.radians(az.ravel()), np.radians(el.ravel())
    rows['x'], rows['y'], rows['z'] = 2*np.cos(e)*np.cos(a), 2*np.cos(e)*np.sin(a), 2*np.sin(e)
    rows['ring'] = [0, 0, 0, 1, 1, 1]
    rows['intensity'] = np.arange(6)
    rows['timestamp'] = 100.25
    return grid, rows


class LiveRangeTests(unittest.TestCase):
    def test_binary_layout_endian_padding_and_extra_fields(self):
        _, rows = scene()
        for endian in ('<', '>'):
            for step in (26, 48):
                msg = cloud(rows, width=3, padding=7, endian=endian, step=step)
                if step == 48:
                    msg.fields.append(NS(name='distance', offset=26, datatype=6, count=1))
                np.testing.assert_array_equal(pointcloud_rows(msg), rows)

    def test_float32_time_and_empty_message(self):
        _, rows = scene()
        # Canonical capture layout is also legal, but not assumed for live data.
        msg = cloud(rows, step=28)
        msg.data = rows.tobytes()
        msg.row_step = len(rows)*28
        msg.fields[-1].offset, msg.fields[-1].datatype = 20, 7
        np.testing.assert_array_equal(pointcloud_rows(msg), rows)
        empty = cloud(rows[:0])
        self.assertEqual(len(pointcloud_rows(empty)), 0)

    def test_invalid_layouts_rejected(self):
        _, rows = scene()
        cases = []
        base = cloud(rows)
        for attr, value in [('data', base.data[:-1]), ('data', base.data+b'x'),
                            ('row_step', 1), ('height', 0), ('width', -1), ('width', 999999)]:
            msg = copy.deepcopy(base)
            setattr(msg, attr, value)
            cases.append(msg)
        for attr, value in [('datatype', 6), ('count', 2), ('offset', -1), ('offset', 23), ('offset', 4)]:
            msg = copy.deepcopy(base)
            setattr(msg.fields[0], attr, value)
            cases.append(msg)
        msg = copy.deepcopy(base); msg.fields.pop(); cases.append(msg)
        msg = copy.deepcopy(base); msg.fields.append(msg.fields[0]); cases.append(msg)
        for msg in cases:
            with self.subTest(msg=repr(msg)[:80]), self.assertRaises(ValueError):
                pointcloud_rows(msg)

    def test_source_rows_survive_invalid_and_duplicate_returns(self):
        grid, rows = scene()
        rows['x'][0] = np.nan
        rows['x'][2] = rows['y'][2] = rows['z'][2] = 0
        rows['ring'][3] = 999
        rows = np.r_[rows, rows[[1]]]
        rows['x'][-1] *= .5; rows['y'][-1] *= .5; rows['z'][-1] *= .5
        actual = grid.decode(pointcloud_rows(cloud(rows)), ('live',))
        self.assertEqual(actual.source_rows[0, 1], 6)
        self.assertEqual(actual.source_rows[1, 2], 5)
        self.assertEqual(actual.rejected['nonfinite_rows'].tolist(), [0])
        self.assertEqual(actual.rejected['duplicate_rows'].tolist(), [1])

    def test_images_orientation_and_source_lookup(self):
        grid, rows = scene()
        frame = grid.decode(rows, ('live',))
        images = image_buffers(frame, preview=True)
        self.assertEqual(images['preview']['step'], 9)
        for name, dtype, expected in [('range', '<f4', frame.range_m.astype('<f4')),
                                      ('source_rows', '<i4', frame.source_rows),
                                      ('valid', 'u1', frame.valid*255)]:
            actual = np.frombuffer(images[name]['data'], dtype=dtype).reshape(2, 3)
            np.testing.assert_array_equal(actual, expected[::-1, ::-1])
        rgb = np.frombuffer(images['preview']['data'], 'u1').reshape(2, 3, 3)
        self.assertTrue((rgb.sum(axis=2) > 0).all())

    def test_latest_only_and_original_header(self):
        grid, rows = scene()
        live = LiveRange(grid, 'innolidar', preview=True)
        for sec in (10, 11, 12):
            live.submit(cloud(rows, sec=sec))
        result = live.process_latest()
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(result['source']['stamp_sec'], 12)
        self.assertEqual(result['queue_overwritten'], 2)
        self.assertEqual(result['received'], 3)
        self.assertIsNone(live.process_latest())

    def test_bad_header_or_message_clears_images_then_recovers(self):
        grid, rows = scene()
        live = LiveRange(grid, 'innolidar')
        for change in ('frame', 'stamp', 'data'):
            msg = cloud(rows)
            if change == 'frame': msg.header.frame_id = 'rotated_cloud'
            if change == 'stamp': msg.header.stamp.nsecs = 1000000000
            if change == 'data': msg.data = b'x'
            live.submit(msg)
            result = live.process_latest()
            self.assertEqual(result['status'], 'invalid')
            self.assertFalse(result['images'])
        live.submit(cloud(rows))
        self.assertEqual(live.process_latest()['status'], 'ready')

    def test_expiration_before_and_after_conversion(self):
        grid, rows = scene()
        clock = [0.]
        live = LiveRange(grid, 'innolidar', max_age_s=.5, clock=lambda:clock[0])
        live.submit(cloud(rows))
        clock[0] = 1.
        self.assertEqual(live.process_latest()['status'], 'expired')
        class SlowGrid:
            sha256 = grid.sha256
            def decode(self, *args):
                frame = grid.decode(*args)
                clock[0] += 1.
                return frame
        live = LiveRange(SlowGrid(), 'innolidar', max_age_s=.5, clock=lambda:clock[0])
        live.submit(cloud(rows))
        result = live.process_latest()
        self.assertEqual(result['status'], 'expired')
        self.assertFalse(result['images'])

    def test_empty_frame_publishes_explicit_invalid_pixels(self):
        grid, rows = scene()
        live = LiveRange(grid, 'innolidar', preview=True)
        live.submit(cloud(rows[:0]))
        result = live.process_latest()
        self.assertEqual(result['status'], 'no_valid_pixels')
        self.assertTrue(np.isnan(np.frombuffer(result['images']['range']['data'], '<f4')).all())
        self.assertTrue((np.frombuffer(result['images']['source_rows']['data'], '<i4') == -1).all())
        self.assertFalse(any(result['images']['preview']['data']))

    def test_publisher_same_header_encoding_and_metadata_no_binary(self):
        grid, rows = scene()
        live = LiveRange(grid, 'innolidar', preview=True)
        msg = cloud(rows)
        live.submit(msg)
        result = live.process_latest()
        output = {}
        class Pub:
            def __init__(self, name): self.name = name
            def publish(self, msg): output[self.name] = msg
        publishers = {name:Pub(name) for name in result['images']}
        status = publish_result(result, msg.header, publishers, NS)
        self.assertNotIn('images', status)
        self.assertEqual(len(output), 4)
        for image in output.values():
            self.assertIs(image.header, msg.header)
            self.assertEqual(len(image.data), image.step*image.height)

    def test_calibration_identity_changes_and_directions_remain_checked(self):
        grid, rows = scene()
        other = ScanGrid(grid.azimuth_deg+.1, grid.elevation_deg)
        live = LiveRange(other, 'innolidar')
        live.submit(cloud(rows))
        result = live.process_latest()
        self.assertEqual(result['grid_sha256'], other.sha256)
        self.assertNotEqual(grid.sha256, other.sha256)
        self.assertEqual(result['valid_pixels'], 0)
        self.assertEqual(result['rejected']['unknown_direction_rows'], len(rows))

    def test_stale_heartbeat_preserves_source_without_claiming_new_image(self):
        previous = dict(status='ready', source={'seq':9})
        self.assertEqual(heartbeat_status(previous, 1., 1.2, .5)['status'], 'ready')
        current = heartbeat_status(previous, 1., 2., .5)
        self.assertEqual(current['status'], 'stale')
        self.assertEqual(current['last_result_status'], 'ready')
        self.assertEqual(current['source'], previous['source'])
        self.assertEqual(previous['status'], 'ready')

    def test_ros_entrypoint_with_fake_transport(self):
        grid, rows = scene()
        publications, subscriptions, loops = {}, [], [0]
        class Pub:
            def __init__(self, topic, factory, **options):
                self.topic = topic
                self.options = options
                publications[topic] = []
                self.assert_options = (options['queue_size'] == 1 and not options['latch'])
                if not self.assert_options: raise AssertionError(options)
            def publish(self, msg): publications[self.topic].append(msg)
        def subscribe(topic, factory, callback, **options):
            subscriptions.append((topic, options))
            callback(cloud(rows))
            return NS(unregister=lambda:subscriptions.append('unregistered'))
        def stopped():
            loops[0] += 1
            return loops[0] > 2
        rospy = NS(init_node=lambda *a,**k:None, Publisher=Pub, Subscriber=subscribe,
                   is_shutdown=stopped, Time=lambda sec,ns:NS(secs=sec,nsecs=ns))
        modules = {'rospy':rospy, 'sensor_msgs':NS(), 'sensor_msgs.msg':NS(Image=NS,PointCloud2=NS),
                   'std_msgs':NS(), 'std_msgs.msg':NS(Header=NS,String=NS)}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, modules):
            az, el = Path(tmp)/'az.csv', Path(tmp)/'el.csv'
            np.savetxt(az, grid.azimuth_deg, delimiter=',')
            np.savetxt(el, grid.elevation_deg, delimiter=',')
            self.assertEqual(main(['--azimuth-table',str(az),'--elevation-table',str(el),
                                   '--frame-id','innolidar','--preview']), 0)
        self.assertEqual(subscriptions[0][0], '/innolidar_points')
        self.assertEqual(subscriptions[-1], 'unregistered')
        self.assertEqual(len(publications['/range_image_live/range']), 1)
        self.assertEqual(publications['/range_image_live/range'][0].header.stamp.nsecs, 123)
        self.assertIn('"status":"ready"', publications['/range_image_live/state'][0].data)

    def test_source_header_survives_rospy_sequence_rewrite(self):
        class Image(NS):
            _has_header = True
        class RosPublisher:
            def publish(self, msg):
                # rospy.msg.serialize_message applies precisely this branch.
                if getattr(msg.__class__, '_has_header', False):
                    msg.header.seq = 999
        grid, rows = scene()
        live = LiveRange(grid, 'innolidar')
        msg = cloud(rows)
        live.submit(msg)
        result = live.process_latest()
        publishers = {name:RosPublisher() for name in result['images']}
        publish_result(result, msg.header, publishers, source_image_type(Image))
        self.assertEqual(msg.header.seq, 1)

    def test_installed_ros_serializer_preserves_source_header_and_wire_type(self):
        try:
            import io
            from rospy.msg import serialize_message
            from sensor_msgs.msg import Image
            from std_msgs.msg import Header
        except ImportError:
            self.skipTest('ROS serialization only available in board ROS environment')
        source_type = source_image_type(Image)
        msg = source_type()
        msg.header = Header(seq=17232782,frame_id='innolidar')
        msg.header.stamp.secs, msg.header.stamp.nsecs = 123, 456
        msg.height, msg.width, msg.encoding, msg.step = 1, 1, 'mono8', 1
        msg.data = b'\xff'
        buf = io.BytesIO()
        serialize_message(buf, 999, msg)
        decoded = Image().deserialize(buf.getvalue()[4:])
        self.assertEqual(decoded.header.seq, 17232782)
        self.assertEqual((decoded.header.stamp.secs,decoded.header.stamp.nsecs), (123,456))
        self.assertEqual(decoded.data, b'\xff')
        self.assertEqual(source_type._md5sum, Image._md5sum)
        self.assertEqual(source_type._type, Image._type)


if __name__ == '__main__':
    unittest.main()
