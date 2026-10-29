"""Exact calibrated RangeFrame -> lossless radial PNG16 + display PNG + target mask.

No interpolation. PNG quantization is export only, never an inference input.
"""
import hashlib
import json
from pathlib import Path
import struct
import zlib

import numpy as np


import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/human_fall_detection'))
from core.range_png import png


def export_depth(frame, source_rows, root, frame_index, stamp_sec, raw_sha, identity):
    root = Path(root)
    valid = frame.valid
    chosen = np.asarray(source_rows, dtype=np.int64)
    if (chosen.ndim != 1 or len(np.unique(chosen)) != len(chosen)
            or not np.isin(chosen, frame.source_rows[valid]).all()):
        raise ValueError('depth mask requires current decoded source rows')
    target = valid & np.isin(frame.source_rows, chosen)
    metric = np.zeros(valid.shape,dtype=np.uint16)
    rounded = np.rint(frame.range_m[valid]*1000)
    overflow = valid & (frame.range_m > 65.534)
    metric[valid] = np.clip(rounded,1,65534).astype(np.uint16)
    metric[overflow] = 65535
    # Fixed red-near / blue-far ramp, black missing. Display clamps only.
    t = np.clip((frame.range_m[valid]-.1)/7.9,0,1)
    rgb = np.zeros(valid.shape+(3,),dtype=np.uint8)
    rgb[valid] = np.column_stack((255*(1-t),255*(1-np.abs(2*t-1)),255*t)).astype(np.uint8)
    folder = root/'depth'
    folder.mkdir(exist_ok=True)
    descriptor = dict(format='lidar_range_image',version=2,width=valid.shape[1],height=valid.shape[0],
        orientation='native_grid_rotated_180_for_view',nativeTransform='rotate180',
        nativeRowFormula='height-1-image_row',nativeColumnFormula='width-1-image_column',quantity='radial_range',units='m',
        sessionId=identity['session'],frameIndex=frame_index,stampSec=stamp_sec,rawSha256=raw_sha,
        gridSha256=frame.grid.sha256,sourceBinding=identity,scaleM=.001,invalidValue=0,overflowValue=65535,
        previewMinM=.1,previewMaxM=8.,validPixels=int(valid.sum()),overflowPixels=int(overflow.sum()),
        targetPixels=int(target.sum()),interpolation=False)
    for kind, pixels in [('metric',metric),('preview',rgb),('mask',target.astype(np.uint8)*255)]:
        name = 'depth/%06d_%s.png'%(frame_index,kind)
        # All exports share the same view. Native source ownership stays in ScanGrid.
        raw = png(pixels[::-1,::-1])
        with (root/name).open('xb') as output:
            output.write(raw)
        descriptor[kind] = dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    raw = json.dumps(descriptor,ensure_ascii=False,sort_keys=True,allow_nan=False).encode('utf-8')
    name = 'depth/%06d.json'%frame_index
    with (root/name).open('xb') as output:
        output.write(raw)
    descriptor['metadata'] = dict(path=name,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    return descriptor
