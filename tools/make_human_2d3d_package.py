"""把一个独立的 2D→3D 人体算法包生成到指定目录（默认用法：桌面），可选同时出 ZIP。

约束：
- 算法文件从 ``src/human_fall_detection/core``（及其 ``scripts/sensor_health.py``）和
  ``pc_apps/annotator_v2/body_branches.py`` **逐字节复制**，不手改、不拼接；
- 包内只放算法、角表、自检与文档：不含会话/采集数据、UI、ROS、模型或板端脚本；
- 输出目录必须不存在（只创建不覆盖）；ZIP 使用固定元数据，相同输入字节相同；
- 生成后立即按 MANIFEST 重新校验全部 SHA。
"""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import shutil
import zipfile

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
CORE = ROOT / 'src' / 'human_fall_detection' / 'core'
SCRIPTS = ROOT / 'src' / 'human_fall_detection' / 'scripts'
TABLES = ROOT / 'src' / 'inno_lidar_ros' / 'config' / 'ifw192s'
TEMPLATE = ROOT / 'tools' / 'human_2d3d_package'

NAME = 'Human2D3D'
VERSION = '1.0.0'
KIND = 'human_2d3d_algorithm_source'
FIXED_ZIP_DATE = (2026, 10, 27, 0, 0, 0)
CALIBRATION = ('ifw192s_azimuth_192x256.csv', 'ifw192s_elevation_192x256.csv')
ROOTS = ('range_runtime', 'range_image', 'range_skeleton', 'range_posture', 'range_contract',
         'range_wire', 'range_background', 'range_components', 'range_denoise',
         'range_features', 'range_tracker')
EXTRA_SOURCES = {'body_branches.py': ROOT / 'pc_apps' / 'annotator_v2' / 'body_branches.py'}
TEMPLATE_FILES = ('human_2d3d.py', 'cli.py', 'run.py', 'synthetic.py',
                  'README.md', 'ALGORITHM.md', 'tests/test_algorithm.py')


def module_file(dotted):
    base = CORE / dotted.replace('.', '/')
    if base.with_suffix('.py').is_file():
        return base.with_suffix('.py')
    if (base / '__init__.py').is_file():
        return base / '__init__.py'
    return None


def module_name(dotted):
    return 'scripts/sensor_health.py' if dotted == 'sensor_health' else \
        'core/' + dotted.replace('.', '/') + '.py'


def imported_modules(path):
    """返回文件中所有可能指向 core/scripts 的模块名（含函数内 import）。"""
    tree = ast.parse(path.read_text(encoding='utf-8'))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            base = node.module or ''
            if node.level:
                if base:
                    found.append(base)
                else:
                    found.extend(alias.name.split('.')[0] for alias in node.names)
            elif base == 'core':
                found.extend(alias.name.split('.')[0] for alias in node.names)
            elif base.startswith('core.'):
                found.append(base[5:])
            elif base:
                found.append(base)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                found.append(alias.name)
    return found


def closure():
    files, pending = {}, list(ROOTS)
    while pending:
        dotted = pending.pop()
        if dotted in files:
            continue
        if dotted == 'sensor_health':
            path = SCRIPTS / 'sensor_health.py'
        else:
            path = module_file(dotted)
        if path is None or not path.is_file():
            if dotted in ROOTS:
                raise SystemExit('missing algorithm module: ' + dotted)
            continue
        files[dotted] = path
        for candidate in imported_modules(path):
            resolved = candidate if candidate == 'sensor_health' else candidate
            if resolved in files:
                continue
            if resolved == 'sensor_health':
                pending.append(resolved)
            elif module_file(resolved) is not None:
                pending.append(resolved)
    return files


def grid_sha256():
    azimuth = np.loadtxt(TABLES / CALIBRATION[0], delimiter=',')
    elevation = np.loadtxt(TABLES / CALIBRATION[1], delimiter=',')
    digest = hashlib.sha256()
    for values in (azimuth, elevation):
        digest.update(values.astype('<f8').tobytes())
    digest.update(json.dumps(dict(shape=azimuth.shape, tolerance_deg=0.02), sort_keys=True).encode())
    return digest.hexdigest()


def build(out, make_zip=True):
    out = Path(out).resolve()
    for name in ('data', 'captures'):
        protected = (ROOT / name).resolve()
        if out == protected or protected in out.parents:
            raise ValueError('protected output directory')
    if out.exists():
        raise ValueError('output already exists: %s' % out)
    modules = closure()
    content, sources = {}, {}
    content['core/__init__.py'] = (CORE / '__init__.py').read_bytes()
    sources['core/__init__.py'] = (CORE / '__init__.py').relative_to(ROOT).as_posix()
    for dotted, path in sorted(modules.items()):
        target = module_name(dotted)
        content[target] = path.read_bytes()
        sources[target] = path.relative_to(ROOT).as_posix()
    for target, path in EXTRA_SOURCES.items():
        content[target] = path.read_bytes()
        sources[target] = path.relative_to(ROOT).as_posix()
    for name in CALIBRATION:
        content['calibration/' + name] = (TABLES / name).read_bytes()
    for name in TEMPLATE_FILES:
        content[name] = (TEMPLATE / name).read_bytes()
    content['VERSION'] = (VERSION + '\n').encode()
    content['start.cmd'] = (b'@echo off\r\n'
                            b'python -B -W error "%~dp0run.py" %*\r\n'
                            b'exit /b %errorlevel%\r\n')
    manifest = dict(name=NAME, version=VERSION, kind=KIND, semantic='UNKNOWN',
                    confirmedEnabled=False, gridSha256=grid_sha256(),
                    modules=sorted(modules),
                    sources=sources,
                    files={name: hashlib.sha256(raw).hexdigest()
                           for name, raw in sorted(content.items())})
    content['MANIFEST.json'] = json.dumps(manifest, ensure_ascii=True, indent=2,
                                          sort_keys=True).encode('utf-8')
    out.mkdir(parents=True)
    for name, raw in sorted(content.items()):
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    verify(out)
    report = dict(path=str(out), version=VERSION, files=len(content),
                  bytes=sum(len(raw) for raw in content.values()),
                  gridSha256=manifest['gridSha256'],
                  algorithmModules=len(modules), sources=len(sources))
    if make_zip:
        archive = out.with_name(out.name + '.zip')
        if archive.exists():
            raise ValueError('archive already exists: %s' % archive)
        with archive.open('xb') as stream, zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as bundle:
            for name, raw in sorted(content.items()):
                info = zipfile.ZipInfo(NAME + '-' + VERSION + '/' + name, FIXED_ZIP_DATE)
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o100644 << 16
                bundle.writestr(info, raw)
        report.update(zip=str(archive), zipBytes=archive.stat().st_size,
                      zipSha256=hashlib.sha256(archive.read_bytes()).hexdigest())
    return report


def verify(out):
    out = Path(out).resolve()
    manifest = json.loads((out / 'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('kind') != KIND or manifest.get('version') != VERSION:
        raise ValueError('manifest header mismatch')
    for name, expected in manifest['files'].items():
        path = (out / name).resolve()
        if out not in path.parents or not path.is_file():
            raise ValueError('missing/unsafe package file: ' + name)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('SHA mismatch: ' + name)
    listed = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
    if listed != set(manifest['files']) | {'MANIFEST.json'}:
        raise ValueError('package file set differs from MANIFEST')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True, help='新包目录，必须不存在')
    parser.add_argument('--no-zip', action='store_true')
    arguments = parser.parse_args()
    print(json.dumps(build(arguments.out, not arguments.no_zip), ensure_ascii=False,
                     sort_keys=True))