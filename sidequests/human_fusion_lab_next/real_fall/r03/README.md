# HF-REAL-03 r03 — 助手视觉排查三单（f10 家具 / 093958 / P 臂吞人画像）

授权：用户 h2 明确"三项一起做"+"开发啊"。本目录为隔离产物； r01/r02 源未变。

## 文件清单

| 文件 | 用途 |
|---|---|
| `render_f10.py` | 渲染 r02 process_v2 的 f9/f10/f11 前景点 + target bbox 对比 图(助手视觉索引) |
| `vision_clean.py` | 应用视觉盒 （被证伪的盒子）到 process_v2，产生 process_v3.json. |
| `render_v3_compare.py` | 渲染 v2 vs v3 对比 + f47/109/118 骨架 AMBIG 检查图 |
| `examine_overlap_093958.py` | 视觉盒剔除点与 HF-REAL-01 人区 overlap 定量； 093958 leveling estimators keys dump （代理读） |
| `examine_093958_v2.py` | 093958 leveling.json 主要键 dump + 0.3% 快照 （中间版） |
| `examine_093958_v3.py` | 093958 按 28B 格式读， 渲 f5/f60/f115 （最终版） |
| `probe_215540.js` | P 臂 （仅在线静态背景）量化人物区点被吞 (按身高带 legs/torso/shoulders/head 分带），产出 mask JSON + frame stats |
| `render_215540_mask.py` | 读 mask.json，渲染 top/side/合成 PNG |
| `gen_boundary.py` | 产生 SOURCE_AND_END_BOUNDARY.json / ARTIFACTS_FINAL_SHA.json |
| `README.md` | 本清单 |

## 输出

- `out/` — 所有 png/json/svg； 复制到 `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/out/`
- 证据目录： `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/`

## 结论摘要

1. **任务 1**：r02 v2 target 在 f10 未被本单检出含家具残留； RS04 FAIL 的关闭需独审。视觉盒被证伪 （404 点均落人区内）。
2. **任务 2**：093958 DATA_BAD — side view 无地斜带； 不投入追踪。
3. **任务 3**：215540 站立人 P 臂吞人率 97.6% （112,903/115,677 点删），按部位列表。fusion v2 需要 233658 参照的记录 (STALE REGISTRATION）管理供同调度即可文档生产。

## 边界

- 独审 / 设备 / 部署 / 生产 / GT NOT_RUN。
- 无 commit/push/reset/clean； 仅起 ssh ls 一个只读板上调用。
- 不修改 r01/r02 源码、不修改生产 / 模型 / GT / captures。
