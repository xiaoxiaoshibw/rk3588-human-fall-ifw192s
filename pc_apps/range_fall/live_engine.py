"""PC live adapter for the same RangeRuntime; no ROS, device writes or recording."""
import base64
import hashlib
import io
import json
from pathlib import Path
import struct
import sys
import time
from types import SimpleNamespace as NS
from urllib.parse import urlparse
from urllib.request import build_opener,ProxyHandler,HTTPRedirectHandler
import uuid
import zipfile

import numpy as np

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'src/human_fall_detection'))
from core.range_background import RayBackground
from core.range_contract import binding_tuple
from core.range_ground_alert import GroundAlertObserver,GroundAlertGapCandidate
from core.range_live import pointcloud_rows, image_buffers
from core.range_posture import PostureObserver
from core.range_runtime import RangeRuntime
from core.range_skeleton import estimate, project_regions
from core.range_engine import RangeEngine
from core.range_wire import parse_cloud
from core.range_site_ground import site_ground


def memory_background(url, manifest_path, grid):
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or parsed.username or parsed.password:
        raise ValueError('background handoff must be loopback HTTP')
    expected=json.loads(Path(manifest_path).read_text('utf8'))
    if expected.get('status')!='ready' or expected.get('frames')!=50 or len(expected.get('headers',[]))!=50:
        raise ValueError('a complete declared 50-frame background is required')
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self,*args,**kwargs):return None
    with build_opener(ProxyHandler({}),NoRedirect()).open(url,timeout=5) as response:raw=response.read(4*1024*1024+1)
    if len(raw)>4*1024*1024:raise ValueError('oversized background')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        if sum(info.file_size for info in archive.infolist())>4*1024*1024:raise ValueError('oversized decoded background')
    with np.load(io.BytesIO(raw),allow_pickle=False) as data:
        metadata=json.loads(str(data['metadata']))
        if metadata!=expected or metadata.get('gridSha256')!=grid.sha256:
            raise ValueError('background manifest/calibration mismatch')
        bg=RayBackground.__new__(RayBackground)
        for name in ('mean_m','sigma_m','known','observations'):
            array=data[name].copy()
            if array.shape!=grid.shape:raise ValueError('background shape mismatch')
            setattr(bg,name,array)
    identity=metadata['identity']
    if (identity.get('epoch')!='live_source_header' or identity.get('grid_sha256')!=grid.sha256
            or bg.known.dtype!=np.bool_ or bg.observations.dtype.kind not in 'iu'
            or not bg.known.any() or not np.isfinite(bg.mean_m[bg.known]).all()
            or not np.isfinite(bg.sigma_m[bg.known]).all() or (bg.sigma_m[bg.known]<.005).any()
            or not np.array_equal(bg.known,bg.observations>=10)):
        raise ValueError('invalid declared background arrays')
    bg.binding=(binding_tuple(identity),grid.sha256)
    bg.min_valid_fraction=metadata['min_valid_fraction'];bg.scene_change_fraction=metadata['scene_change_fraction']
    if bg.min_valid_fraction!=.6 or bg.scene_change_fraction!=.35:raise ValueError('background settings changed')
    bg.invalidated=False
    headers=metadata['headers']
    for previous,current in zip(headers,headers[1:]):
        if current['seq']!=previous['seq']+1 or current['frame_id']!=identity['coordinate'][4:]:
            raise ValueError('declared background source discontinuity')
    last=headers[-1]
    bg.last_declared_header=(last['seq'],last['sec']+last['nsec']/1e9)
    return identity,bg


class LiveEngine(RangeEngine):
    """PC-only optional body analysis; recognition stays in RangeEngine."""
    @staticmethod
    def make_body(job):
        frame,rows=job
        body_path=str(ROOT/'pc_apps/annotator_v2')
        if body_path not in sys.path:sys.path.insert(0,body_path)
        from body_branches import propose,METHOD
        try:
            indices=frame.source_rows[::-1,::-1];parts=propose(indices,frame.xyz,rows)
            return dict(method=METHOD,semantic='UNKNOWN',parts=[dict(part=p['part'],
                sourceRows=indices.ravel()[p['pixels']].tolist() if p.get('pixels') else []) for p in parts])
        except (ValueError,TypeError,FloatingPointError):return None
