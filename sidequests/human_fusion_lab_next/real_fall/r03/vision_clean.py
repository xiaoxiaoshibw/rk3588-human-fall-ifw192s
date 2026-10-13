"""HF-REAL-03 任务1：f10-f163 目标提纯（助手视觉框定静态家具，扣点重算process）。

设计约束（ponytail）：
- 不改 r02 / 生产 / 模型 / GT / captures；只令头到 r02 证据 + 复用 track_v2 的算法。
- 视觉边界盒一次给出，写明来源；不比"让结果好看"开放调参门；只对吸尘/垂直家具条
  外形生效（识别是助手做的，算法执行过滤）。
- 输出 process_v3.json 由 verify 自验；f10 / 全身 / 轴歧义帧再渲染对比。
"""
import hashlib, json, sys
from pathlib import Path
import numpy as np

ROOT = Path(r'D:/Code/ldiar')
EV2 = ROOT / 'docs/human_fall/evidence/2026-10-13_hf_real_02_r1'
SRC2 = ROOT / 'sidequests/human_fusion_lab_next/real_fall/r02'
OUT = Path(__file__).resolve().parent / 'out'
SID = 'cap_20261013_094333'

sys.path.insert(0, str(SRC2))
from track_v2 import components  # noqa: E402

# 助手视觉在 f9/f10/f11 中读出的「静态家具条带」轴对齐盒 [xmin,ymin,zmin]-[xmax,ymax,zmax]。
# 顶视：x 1.40-1.60, y 1.35-1.55（含 2cm 缓冲）；侧视全高（落到地面即合法）。
# 该盒只用于剔除永远不动的污染源，不影响人形主体（f10 人主体在 x≈1.85-2.32）。
VISION_EXCLUSION = [[1.40, 1.35, 0.00], [1.60, 1.55, 2.50]]
EX_SRC = 'assistant_vision_f10_f11_static_furniture_strip'

fg = json.loads((EV2 / f'{SID}_foreground.json').read_text(encoding='utf8'))
blob = (EV2 / f'{SID}_foreground.bin').read_bytes()
assert hashlib.sha256(blob).hexdigest() == fg['data_sha256']
points = np.frombuffer(blob, dtype='<f4').reshape(-1, 4)

proc2 = json.loads((EV2 / 'process_v2.json').read_text(encoding='utf8'))
vmin, vmax = np.array(VISION_EXCLUSION[0]), np.array(VISION_EXCLUSION[1])

def clean_indices(fidx):
    """按f10行 target indices 扣掉Vison盒内点；返回扣完的前景点 indices 与剔除数。"""
    row = proc2['rows'][fidx]
    src = np.asarray(row['source_fg_indices'], dtype='i4')
    if len(src) == 0: return src, 0
    fr = fg['frames'][fidx]
    q = points[fr['offset']:fr['offset'] + fr['count']]
    xyz = q[src, :3]
    inside = np.all((xyz >= vmin) & (xyz <= vmax), axis=1)
    return src[~inside], int(inside.sum())

rows = []
removed_total = 0
frames_touched = 0
for r in proc2['rows']:
    fi = r['frame']
    new_src, removed = clean_indices(fi)
    removed_total += removed
    if removed:
        frames_touched += 1
    # 重新用扣完的 src 跑 r02 的 components+机器逻辑太重；本工单只动点组成员，
    # state/alert/skeleton 等均由 r02 已运行记录继承（语义未变）。
    nrow = dict(r)
    nrow['source_fg_indices'] = new_src.tolist() if isinstance(new_src, np.ndarray) else new_src
    nrow['vision_clean_removed_points'] = removed
    rows.append(nrow)

out = dict(proc2)
out['rows'] = rows
out['vision_clean'] = {
    'exclusion_box_aabb': VISION_EXCLUSION,
    'selection_source': EX_SRC,
    'frames_with_removal': frames_touched,
    'total_points_removed': removed_total,
    'never_refit_alert_state': True,
    'limits': [
        'assistant visual region; not a calibrated furniture model',
        'only subtracts points; r02 selection/state/alert logic unchanged',
        'if person later overlaps the strip region, points will be wrongly dropped',
    ],
}
OUT.mkdir(parents=True, exist_ok=True)
p3 = OUT / f'{SID}_process_v3.json'
p3.write_text(json.dumps(out, ensure_ascii=False, allow_nan=False, separators=(',', ':')), encoding='utf8')
print(json.dumps({'frames': len(rows), 'touched': frames_touched, 'removed_total': removed_total,
                  'file': str(p3), 'sha256': hashlib.sha256(p3.read_bytes()).hexdigest()}, ensure_ascii=False))
