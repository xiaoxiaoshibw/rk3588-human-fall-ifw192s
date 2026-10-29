"""Independent Python/NumPy oracle for the C# R2 decoder and stress construction."""
import hashlib
import json
from pathlib import Path
import subprocess
import uuid
import sys
import numpy as np
from run_spike_command import ROOT, OUT, environment

SERVICE = ROOT / 'console_v2/spike/service/bin/Release/net8.0-windows/win-x64/SpikeService.dll'
DOTNET = ROOT / 'console_v2/.tools/dotnet/dotnet.exe'
SESSION = ROOT / 'data/sessions/cap_20261018_110029'
PREFIX = next((a for a in sys.argv[1:] if not a.startswith('--')), '')
SINGLE = '--single' in sys.argv


def call(label, arguments, expected=0):
    label = PREFIX + label
    report = OUT / (label + '.json')
    if any((OUT / (label + suffix)).exists() for suffix in ['.json', '.stdout', '.stderr']):
        raise FileExistsError('Choose a fresh output directory or prefix: ' + label)
    command = [str(ROOT / 'console_v2/spike/package-single/SpikeService.exe')] if SINGLE else [str(DOTNET), str(SERVICE)]
    argv = command + ['--report', str(report)] + arguments
    result = subprocess.run(argv, cwd=ROOT, env=environment(), capture_output=True,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT / (label + '.stdout')).write_bytes(result.stdout)
    (OUT / (label + '.stderr')).write_bytes(result.stderr)
    assert result.returncode == expected, (label, result.returncode, result.stderr[-1000:])
    return json.loads(report.read_text(encoding='utf-8'))


def sha(data):
    return hashlib.sha256(data).hexdigest()


def main():
    assert call('codec_selftest', ['--self-test', '1'])['passed']
    meta = json.loads((SESSION / 'meta.json').read_text(encoding='utf-8'))
    reference = []
    dtype = np.dtype([('x', '<f4'), ('y', '<f4'), ('z', '<f4'), ('intensity', '<f4'), ('ring', '<u2'), ('timestamp', '<f4')])
    assert dtype.itemsize == 22
    with (SESSION / 'points.bin').open('rb') as stream:
        for index, f in enumerate(meta['frames'][:3]):
            stream.seek(f['offset_points'] * 28)
            raw = stream.read(f['count_points'] * 28)
            n = f['count_points']
            canonical = np.empty(n, dtype=dtype)
            for name, offset, field_type in [('x', 0, '<f4'), ('y', 4, '<f4'), ('z', 8, '<f4'),
                                             ('intensity', 12, '<f4'), ('ring', 16, '<u2'), ('timestamp', 20, '<f4')]:
                canonical[name] = np.ndarray((n,), dtype=field_type, buffer=raw, offset=offset, strides=(28,))
            xyz = np.ndarray((n, 3), dtype='<f4', buffer=raw, strides=(28, 4)).copy()
            finite = np.isfinite(xyz).all(axis=1)
            reference.append(dict(raw=raw, canonical=canonical.tobytes(), xyz=xyz[finite].copy(),
                                  nonfinite=int((~finite).sum()), offset=f['offset_points'], count=n))
    compared = []
    for target in [0, 50_000, 500_000]:
        result = call('decode_' + str(target), ['--session', str(SESSION), '--count', str(target), '--decode-only', '1'])
        for index, r in enumerate(reference):
            actual = result['frames'][index]
            xyz = r['xyz']
            if target:
                rows = np.arange(target, dtype=np.int64)
                projected = xyz[rows % len(xyz)].copy()
                tile = rows // len(xyz)
                selected = tile != 0
                projected[selected, 0] += ((tile[selected] % 4) * 2).astype(np.float32)
                projected[selected, 1] += ((tile[selected] // 4) * 2).astype(np.float32)
            else:
                projected = xyz
            expected = dict(raw_sha256=sha(r['raw']), canonical_fields_sha256=sha(r['canonical']),
                            xyz_sha256=sha(xyz.tobytes()), projected_sha256=sha(projected.tobytes()),
                            nonfinite_xyz=r['nonfinite'], count=r['count'], offset_points=r['offset'],
                            projected_count=len(projected))
            assert all(actual[k] == value for k, value in expected.items()), (target, index, actual, expected)
            compared.append(dict(target=target, frame=index, **expected))
    fixture_root = ROOT / 'console_v2/.tools/fixtures' / uuid.uuid4().hex
    fixture_root.mkdir(parents=True)
    negatives = []
    for case in ['stride16', 'truncated', 'point_file_traversal', 'negative_offset']:
        folder = fixture_root / case
        folder.mkdir()
        doc = {'point_file': 'points.bin', 'point_layout': {'stride_bytes': 28},
               'frames': [{'offset_points': i, 'count_points': 1} for i in range(3)]}
        points = bytes(84)
        if case == 'stride16': doc['point_layout']['stride_bytes'] = 16
        if case == 'truncated': points = points[:-1]
        if case == 'point_file_traversal': doc['point_file'] = '../points.bin'
        if case == 'negative_offset': doc['frames'][0]['offset_points'] = -1
        (folder / 'meta.json').write_text(json.dumps(doc), encoding='utf-8')
        (folder / 'points.bin').write_bytes(points)
        result = call('reject_' + case, ['--session', str(folder), '--decode-only', '1'], expected=2)
        assert result['stage'] == 'failed'
        negatives.append(case)
    argument_rejections = []
    for case, arguments in [('count_not_supported', ['--count', '49999']),
                            ('count_outside_limit', ['--count', '500001']),
                            ('updates_typo', ['--updates', 'dynamci'])]:
        result = call('reject_' + case, ['--session', str(fixture_root / 'does_not_exist')] + arguments, expected=2)
        assert result['stage'] == 'failed' and 'ArgumentException' in result['detail']
        assert ('--updates' if case == 'updates_typo' else '--count') in result['detail']
        argument_rejections.append(case)
    (OUT / (PREFIX + 'ARGUMENT_REJECTIONS.json')).write_text(json.dumps(dict(status='PASS', cases=argument_rejections,
        scope='Bad count/updates rejected before attempting to read a nonexistent session'), indent=2), encoding='utf-8')
    summary = dict(status='PASS', source=str(SESSION.relative_to(ROOT)), source_stride=28,
                   frames=compared, negative_cases=negatives, selftest_cases=4,
                   tolerance='zero; all decoded fields and projected XYZ compared by full-frame SHA256',
                   argument_rejections=argument_rejections,
                   scope='R2 fixed stride28 decoder, not R3 general data layer; stress data is synthetic tiled repetition')
    (OUT / (PREFIX + 'CODEC_DIFFERENTIAL.json')).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print('R2 decoder: three real frames × three modes exact; four negative fixtures and four self-checks PASS', flush=True)


if __name__ == '__main__':
    main()
