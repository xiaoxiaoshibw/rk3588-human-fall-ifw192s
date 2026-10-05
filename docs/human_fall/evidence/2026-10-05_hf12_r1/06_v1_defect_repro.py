"""HF-12 v1 defect repro (pre-fix packing): kept as a failure record.

The first implementation packed cell keys as
    key = ((cx) * span_y + cy) * span_z + cz
(per-axis extents) and applied the 27 (dx,dy,dz) offsets directly in key
space. When an axis span equals 1, one position in key space carries two
different "digit" meanings, so several offsets collapse onto the same key and
the same cell is counted repeatedly (and digits can borrow across axes).
On the archived failing case the v1 code produced totals [6, 6, 3] and a keep
mask [True, True, True] at min_neighbors=2 instead of [2, 2, 1] / 
[True, True, False]; the test suite failed 3/14. The fix uses a uniform digit
base = max(span) + 1 (see _packed_neighbour_counts) and the dense box-sum path.
"""

import numpy as np

cells = np.array([[29, 0, 0], [30, 0, 0], [50, 50, 0]], dtype=np.int64)
low = cells.min(axis=0)
extent = cells.max(axis=0) - low + 1
key = ((cells[:, 0] - low[0]) * extent[1] + (cells[:, 1] - low[1])) * extent[2] \
    + (cells[:, 2] - low[2])
unique, counts = np.unique(key, return_counts=True)
stride_x = int(extent[1] * extent[2])
stride_y = int(extent[2])
total = np.zeros(len(key), dtype=np.int64)
for dx in (-1, 0, 1):
    for dy in (-1, 0, 1):
        for dz in (-1, 0, 1):
            shifted = key + (dx * stride_x + dy * stride_y + dz)
            index = np.minimum(np.searchsorted(unique, shifted), len(unique) - 1)
            hit = unique[index] == shifted
            total += np.where(hit, counts[index], 0)
print("v1 keys:", key.tolist(), "v1 totals:", total.tolist())
print("v1 mask (min_neighbors=2):", (total >= 2).tolist())
print("expected total/mask      :", [2, 2, 1], [True, True, False])
