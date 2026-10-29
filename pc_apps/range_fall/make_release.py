"""生成无原始数据、无模型、可搬迁的确定性PC离线源码ZIP。"""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile

from release import VERSION, ROOT


def build(out):
    out = Path(out).resolve()
    for name in ('data','captures'):
        protected = (ROOT/name).resolve()
        if out == protected or protected in out.parents: raise ValueError('protected output')
    names = ['pc_apps/range_fall/'+n for n in ('release.py','make_release.py','runtime_replay.py','replay_compare.py',
        'replay_template.html','session_compare.py','analysis.py','depth.py')]
    names += ['tools/range_experiment.py','tools/sync_audit.py']
    names += ['pc_apps/annotator_v2/body_branches.py']
    names += ['src/human_fall_detection/scripts/'+n for n in ('replay_range_frontend.py','sensor_health.py')]
    names += [p.relative_to(ROOT).as_posix() for p in sorted((ROOT/'src/human_fall_detection/core').glob('*.py'))]
    names += ['src/inno_lidar_ros/config/ifw192s/'+n for n in ('ifw192s_azimuth_192x256.csv','ifw192s_elevation_192x256.csv')]
    names += ['docs/RANGE_RELEASE_0_1.md']
    content = {n:(ROOT/n).read_bytes() for n in names}
    content['README.md'] = (ROOT/'docs/RANGE_RELEASE_0_1.md').read_bytes()
    content['docs/RANGE_RUNTIME.md'] = (ROOT/'docs/RANGE_RUNTIME.md').read_bytes()
    content['run.py'] = b"import sys\nfrom pathlib import Path\nsys.path.insert(0,str(Path(__file__).resolve().parent/'pc_apps/range_fall'))\nfrom release import main\nmain()\n"
    content['start.cmd'] = b'@echo off\r\npython -B -W error "%~dp0run.py" %*\r\nexit /b %errorlevel%\r\n'
    manifest = dict(version=VERSION,kind='pc_offline_source_release',confirmed_enabled=False,
        files={n:hashlib.sha256(b).hexdigest() for n,b in sorted(content.items())})
    content['MANIFEST.json'] = json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True).encode('utf-8')
    # 固定ZIP元数据；相同文件产生相同发行字节。输出只创建，不覆盖。
    with out.open('xb') as stream, zipfile.ZipFile(stream,'w',zipfile.ZIP_DEFLATED) as archive:
        for name,raw in sorted(content.items()):
            info=zipfile.ZipInfo('RangeReplay-'+VERSION+'/'+name,(2026,10,24,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED;info.external_attr=0o100644<<16
            archive.writestr(info,raw)
    return dict(path=str(out),bytes=out.stat().st_size,sha256=hashlib.sha256(out.read_bytes()).hexdigest(),
        files=len(content),version=VERSION)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(build(parser.parse_args().out),sort_keys=True))
