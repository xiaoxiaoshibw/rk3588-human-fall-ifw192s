# HFUS-D05 Demo 一键启动

> 与 D04 Demo 并存，不覆盖任何 D04 资产。D05 侧改演示服务器与 HTML，原 D04 server/html 原样保留。

## 一键启动（AUTO 模式）

```
python sidequests/human_fusion_lab_next/d05/demo_server.py --port 8908
# 浏览器打开: http://127.0.0.1:8908/?AUTO=1
```

默认读取（除非用 `--root` 覆盖）：
- D05 evidence: `docs/human_capture/evidence/2026-10-11_hfus_d05_r1/`
- D04 evidence: `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/`
- D03 evidence: `docs/human_capture/evidence/2026-10-11_hfus_d03_r1/`
- captures: `captures/remote/`
- 3D 依赖: `pc_apps/human_replay/vendor/three.min.js`（本仓已有，无外部下载）

## 数据一致性

- `BASELINE_SHAS.json` 在 §1 阶段冻结了 `background/*`、`contracts/*`、`eval/instrument.js`、九会话 input、参考空场、模型、D04 base ledger 的 SHA。
- `MANIFEST_DEMO.json`/`REGRESSION_FINAL.json` 由 `make_regression.js` 在跑完 A/B/C/abc 后生成。
- demo 页首条信息行直接消费 manifest/regression，**SHA 漂移时 demo 仍能跑**，但顶层会显示对应文件版本；真实可复现性由 `BASELINE_SHAS.json` 保证。

## 视觉语义（必看）

- **左窗**: 原始帧 + GT 人(红) + GT 家具(粉) + 叠加 D05 变体候选(橙)。「原始点云」视角。
- **中窗**: D04 baseline（紫=候选） + D05 变体 accepted 覆盖（绿）。即「D05 相对 base 把人识别进了哪」的直观账。
- **右窗**: three.js 真实三维点云（鼠标拖动旋转/滚轮缩放）。颜色：背景灰、D05 变体候选紫、accepted 橙、A06/ABC 相对 base 新增候选 青、GT 人 红、GT 家具 粉。**青色就是 Demo 里「A06 真正恢复出的 UNKNOWN 人点」**。

## 一键场景

- **近距离丢失** → `cap_20261010_175429`，D05 a06。
- **远距离丢失** → `cap_20261010_180337` 或 `175553`，D05 a06。
- **静止人体** → `cap_20261010_180557` / `175943`，D05 a06/c。
- **家具误检** → `cap_20261010_175227`（FP 最高的家具空场）。
- **A06 相对 base 新增 accepted** → 自动找第一帧变体 accepted 数 > base 的帧。

## 停止

- 先找 8908 PID：`netstat -ano | grep ':8908.*LISTENING'`
- 精确结束：`taskkill //F //PID <pid>`（Git Bash 下用 // 转义；禁止宽 pkill）
