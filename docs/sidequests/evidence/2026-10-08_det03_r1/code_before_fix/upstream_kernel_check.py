"""Compile pinned upstream geometry on host; explicitly NOT a CUDA equivalence test."""
import ctypes
import json
from pathlib import Path
import subprocess

import numpy as np
import torch
from cpu_pointpillars import nms_cuda
from experiment import sha

ROOT = Path(__file__).resolve().parent
UP = ROOT / 'artifacts/det03_upstream_r1'


def build(out):
    source = UP / 'pointpillars/ops/iou3d/iou3d_kernel.cu'
    s = source.read_text(encoding='utf-8')
    # Original Point/overlap/IoU bodies unchanged; remove only device qualifier.
    body = s[s.index('__device__ const float EPS'):s.index('__global__')].replace('__device__', '')
    code = '#include <cmath>\n#include <algorithm>\nusing std::min;using std::max;\n' + body
    code += '\nextern "C" __declspec(dllexport) float ref_iou(float* a,float* b){return iou_bev(a,b);}\n'
    cpp = out / 'upstream_geometry_host.cpp'
    cpp.write_text(code, encoding='utf-8')
    dll = out / 'upstream_geometry_host.dll'
    cmd = ['g++', '-O2', '-shared', '-static-libgcc', '-static-libstdc++', str(cpp), '-o', str(dll)]
    run = subprocess.run(cmd, capture_output=True, text=True)
    (out / 'build.log').write_text(json.dumps(cmd) + '\n' + run.stdout + run.stderr, encoding='utf-8')
    run.check_returncode()
    lib = ctypes.CDLL(str(dll.resolve()))
    f = lib.ref_iou
    arr = np.ctypeslib.ndpointer(dtype=np.float32, ndim=1, flags='C_CONTIGUOUS')
    f.argtypes = [arr, arr]
    f.restype = ctypes.c_float
    return f, dict(source_sha256=sha(source),host_cpp_sha256=sha(cpp),dll_sha256=sha(dll),command=cmd,
                   boundary='Original float geometry compiled on host, not actual GPU/ATen execution')


def fixed_nms(boxes, scores, thresh, pre_maxsize=None, post_max_size=None):
    from cpu_pointpillars import nms_cuda as current
    b = boxes.clone()
    b[:, 4] *= -1
    return current(b, scores, thresh, pre_maxsize, post_max_size)


def main(out):
    out.mkdir(exist_ok=False)
    f, record = build(out)
    rng = np.random.default_rng(3108)
    boxes = np.column_stack([rng.uniform(-2, 2, (80, 2)), rng.uniform(.15, 3, (80, 2)), rng.uniform(-3, 3, 80)]).astype('f4')
    boxes[:, 2:4] += boxes[:, :2]
    # Include displaced parallel +45deg thin rectangles; catches handedness.
    boxes[:2] = [[-2,-.1,2,.1,np.pi/4],[-1.5,-.6,2.5,-.4,np.pi/4]]
    scores = torch.linspace(.99,.2,len(boxes))
    t = torch.from_numpy(boxes)
    old = nms_cuda(t,scores,.01).tolist()
    corrected = fixed_nms(t,scores,.01).tolist()
    keep = []
    for i in range(len(boxes)):
        if all(f(boxes[i], boxes[j]) <= .01 for j in keep):keep.append(i)
    assert corrected == keep, (corrected, keep)
    assert old != keep
    record.update(old_keep=old,corrected_keep=corrected,upstream_host_keep=keep,
                  diagonal_pair_iou=float(f(boxes[0],boxes[1])),old_pair_keep=nms_cuda(t[:2],scores[:2],.01).tolist(),
                  corrected_pair_keep=fixed_nms(t[:2],scores[:2],.01).tolist(),gpu_status='BLOCKED: torch CPU build, no CUDA runtime')
    (out/'result.json').write_text(json.dumps(record,indent=2),encoding='utf-8')
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    import sys
    main(Path(sys.argv[1]))
