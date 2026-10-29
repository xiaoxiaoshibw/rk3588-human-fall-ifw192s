"""原生标注台：真实 Qt 鼠标拖框 → 保存 → 重载 → 旧版本/非法文档被拒；源会话不变。"""
import hashlib
import json
import math
import os
from pathlib import Path
import struct
import subprocess
import sys
import unittest

import test_integration as fixtures
from test_integration import ROOT, SDK, DLL, HOST


def _point(x, y, z, intensity=100.0):
    return struct.pack('<ffff', x, y, z, intensity) + bytes(12)


def make_session(directory, frames_points):
    """合法最小会话：stride 28、帧界连续、源时间单调；点用真实米制坐标便于框选。"""
    directory.mkdir(parents=True)
    raw = b''.join(_point(*p) for frame in frames_points for p in frame)
    (directory / 'points.bin').write_bytes(raw)
    frames = []
    offset = 0
    stamp = 1.0
    for frame in frames_points:
        frames.append(dict(offset_points=offset, count_points=len(frame), stamp_sec=stamp, stamp_nanosec=0))
        offset += len(frame)
        stamp += 0.1
    meta = dict(point_file='points.bin',
                point_layout=dict(stride_bytes=28, dtypes=[], fields=[], pad_offsets_bytes=[], endian='little'),
                frames=frames, total_points=offset)
    (directory / 'meta.json').write_text(json.dumps(meta), 'utf-8')


def person_cloud(cx, cy):
    """12 点的小环形“人体”范围，中心与半径固定，便于核对拖框读回米制尺寸。"""
    return [(cx + 0.30 * math.cos(a / 12 * 2 * math.pi),
             cy + 0.30 * math.sin(a / 12 * 2 * math.pi),
             0.4 + 0.12 * (a % 5)) for a in range(12)]


class TestAnnotationBench(unittest.TestCase):
    setUp = fixtures.TestApp.setUp

    def test_native_annotation_roundtrip_and_rejections(self):
        work = self.out / 'sessions'
        work.mkdir()
        make_session(work / 'annot_001', [person_cloud(2.0, 0.2) + person_cloud(2.4, 0.6),
                                          person_cloud(2.05, 0.25) + person_cloud(2.45, 0.65)])
        before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                  for p in work.rglob('*') if p.is_file()}
        gt = self.out / 'gt'
        args = [str(SDK), str(DLL), '--session', str(work / 'annot_001'),
                '--host', str(HOST), '--report', str(self.out / 'run.json'),
                '--python', sys.executable, '--gt-root', str(gt),
                '--annotation-report', str(self.out / 'annotation.json'), '--no-external-open']
        done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=90)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))

        report = json.loads((self.out / 'annotation.json').read_text('utf-8'))
        self.assertEqual(report['status'], 'PASS', report)
        checks = {row['case']: row['passed'] for row in report['checks']}
        for name in ('annotation_view_visible', 'drag_creates_one_box', 'drag_marks_dirty',
                     'box_has_metric_extent', 'save_bumps_version', 'save_clears_dirty',
                     'reload_keeps_box', 'reload_reports_saved_version', 'interval_added',
                     'interval_saved', 'interval_kept_in_model', 'stale_save_rejected',
                     'invalid_box_rejected'):
            self.assertTrue(checks.get(name), (name, report['checks']))
        self.assertIn('版本冲突', report['message'] + json.dumps(report['checks'], ensure_ascii=False))

        draft_path = gt / 'annot_001' / 'draft.json'
        self.assertTrue(draft_path.is_file())
        envelope = json.loads(draft_path.read_text('utf-8'))
        self.assertEqual(envelope['version'], 2)          # 保存两次；冲突/非法两次都被拒
        doc = envelope['doc']
        self.assertEqual(doc['format'], 'gt_annotate')
        self.assertEqual(doc['formatVersion'], 2)
        self.assertEqual(doc['sessionId'], 'annot_001')
        self.assertEqual(doc['coordinateFrame'], 'sensor-IFW192S-raw')
        self.assertEqual(doc['units'], 'm')
        self.assertEqual(doc['frameCount'], 2)
        self.assertEqual(len(doc['persons']), 1)
        self.assertEqual(doc['persons'][0]['personId'], 'P1')
        self.assertEqual(len(doc['boxes']), 1)
        box = doc['boxes'][0]
        self.assertEqual(box['frameIndex'], 0)
        self.assertEqual(box['personId'], 'P1')
        self.assertEqual(box['visibility'], 'visible')
        self.assertEqual(box['origin'], {'kind': 'human'})
        self.assertGreater(box['w'], 0.05)
        self.assertGreater(box['h'], 0.05)
        self.assertGreater(box['zMax'], box['zMin'])
        self.assertEqual(len(doc['intervals']), 1)
        interval = doc['intervals'][0]
        self.assertEqual(interval['label'], 'fall')
        self.assertEqual(interval['kind'], 'event')
        self.assertEqual((interval['startFrame'], interval['endFrame']), (0, 1))
        self.assertEqual(doc['suggestions'], [])
        self.assertEqual(doc['sampleFrames'], [])
        self.assertTrue(doc['savedAtMs'])
        # 标注 store 只写这一份草稿，不写会话目录
        self.assertEqual([p.name for p in (gt / 'annot_001').iterdir()], ['draft.json'])

        for path, sha in before.items():
            self.assertEqual(hashlib.sha256(Path(path).read_bytes()).hexdigest(), sha)
        service = json.loads((self.out / 'run.json').read_text('utf-8'))
        self.assertEqual(service['status'], 'PASS')
        self.assertEqual(service['sessionDeletes'], 0)
        self.assertEqual(service['jointMutationRequests'], 0)
        self.assertEqual(service['directBoardCalls'], 0)
        saved = [row for row in service['log'] if row['eventType'] == 'gtSaved']
        self.assertEqual([row['version'] for row in saved], [1, 2])
        self.assertEqual(saved[-1]['boxes'], 1)
        self.assertEqual(saved[-1]['intervals'], 1)
        errors = [row['message'] for row in service['log'] if row['eventType'] == 'commandError']
        self.assertTrue(any('版本冲突' in message for message in errors))
        self.assertTrue(any('zMax' in message for message in errors))
        self.assertEqual([row for row in service['log'] if row['eventType'] == 'annotatorOpened'], [])

    def test_gt_store_rejects_paths_and_bad_suggestions(self):
        """store 级回归：尾分隔符根目录能存、'..' 读不到 store 外、suggestions 按 validation.ts 拒。"""
        gt = self.out / 'gt'
        gt.mkdir()
        args = [str(SDK), str(DLL), '--session', str(ROOT / 'data/sessions/cap_20261018_110029'),
                '--host', str(HOST), '--report', str(self.out / 'run.json'),
                '--gt-root', str(gt) + os.sep, '--self-check-gt']
        done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=90)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
        report = json.loads((self.out / 'run.json').read_text('utf-8'))
        self.assertEqual(report['status'], 'PASS', report)
        row = next(r for r in report['log'] if r['eventType'] == 'gtStoreChecks')
        self.assertTrue(row['checks']['passed'], row['checks'])
        self.assertTrue(row['rawRoot'].endswith(os.sep), row['rawRoot'])
        checks = {c['name']: c for c in row['checks']['checks']}
        for name in ('gt_root_has_no_trailing_separator', 'save_with_raw_gt_root_works',
                     'save_with_trailing_separator_root_works', 'version_conflict_still_rejected',
                     'load_rejects_dotdot', 'load_rejects_dot', 'save_rejects_dotdot',
                     'save_rejects_path_separator', 'suggestion_duplicate_id_rejected',
                     'suggestion_empty_rejected', 'suggestion_valid_accepted',
                     'suggestion_survives_roundtrip', 'adopted_origin_warning_not_rejected',
                     'valid_web_draft_roundtrip', 'draft_written_inside_store_root'):
            self.assertIn(name, checks, row['checks'])
            self.assertTrue(checks[name]['passed'], (name, checks[name]))
        self.assertIn('建议 id 重复', checks['suggestion_duplicate_id_rejected']['detail'])
        self.assertIn('必须携带框或区间', checks['suggestion_empty_rejected']['detail'])
        self.assertIn('版本冲突', checks['version_conflict_still_rejected']['detail'])
        # --gt-root 的尾分隔符真的传到了 GtStore（GetFullPath 保留），store 再去掉它：
        # 修复前 Root+"\" 让前缀检查恒假，保存必失败。
        self.assertTrue(row['checks']['root'].endswith(os.sep), row['checks']['root'])
        self.assertFalse(checks['gt_root_has_no_trailing_separator']['detail'].endswith(os.sep),
                         checks['gt_root_has_no_trailing_separator']['detail'])
        # 尾分隔符的根目录真的写进去了；store 外的诱饵 draft.json 已清理、没有被读走或创建。
        self.assertTrue((gt / 'probe_trailing' / 'draft.json').is_file())
        self.assertTrue((gt / 'probe_web_draft' / 'draft.json').is_file())
        self.assertFalse((self.out / 'draft.json').exists())
        self.assertFalse((self.out / 'escape').exists())

    def test_existing_web_draft_loads_and_keeps_untouched_fields(self):
        """Web 标注台写过的真实草稿：原生界面载入后追加一框/一区间，建议与取样清单原样保留。"""
        session = ROOT / 'data/sessions/cap_20261023_221125'
        source = ROOT / 'pc_apps/annotator_v2/gt_store_v2/cap_20261023_221125/draft.json'
        if not session.is_dir() or not source.is_file():
            self.skipTest('real web draft or its session is not present')
        gt = self.out / 'gt'
        target = gt / 'cap_20261023_221125'
        target.mkdir(parents=True)
        original = source.read_bytes()
        (target / 'draft.json').write_bytes(original)
        before_doc = json.loads(original)
        before = before_doc['doc']
        before_version = before_doc['version']
        session_sha = {name: hashlib.sha256((session / name).read_bytes()).hexdigest()
                       for name in ('meta.json', 'points.bin')}
        args = [str(SDK), str(DLL), '--session', str(session), '--host', str(HOST),
                '--report', str(self.out / 'run.json'), '--python', sys.executable,
                '--gt-root', str(gt), '--annotation-report', str(self.out / 'annotation.json'),
                '--no-external-open']
        done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=90)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))
        report = json.loads((self.out / 'annotation.json').read_text('utf-8'))
        self.assertEqual(report['status'], 'PASS', report)

        envelope = json.loads((target / 'draft.json').read_text('utf-8'))
        doc = envelope['doc']
        self.assertEqual(envelope['version'], before_version + 2)   # 框、区间各保存一次
        self.assertEqual(len(doc['boxes']), len(before['boxes']) + 1)
        self.assertEqual(len(doc['intervals']), 1)
        self.assertEqual(doc['sampleFrames'], before['sampleFrames'])
        self.assertEqual(doc['suggestions'], before['suggestions'])
        self.assertEqual(doc['persons'], before['persons'])
        self.assertEqual(doc['annotator'], before['annotator'])
        kept = {box['boxId'] for box in before['boxes']}
        self.assertTrue(kept.issubset({box['boxId'] for box in doc['boxes']}))
        self.assertEqual(doc['sessionId'], 'cap_20261023_221125')
        # 真实会话文件不被修改
        for name, sha in session_sha.items():
            self.assertEqual(hashlib.sha256((session / name).read_bytes()).hexdigest(), sha)
        self.assertNotEqual(original, (target / 'draft.json').read_bytes())


if __name__ == '__main__':
    unittest.main()