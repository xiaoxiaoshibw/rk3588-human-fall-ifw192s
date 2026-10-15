# 09 演示页（效果展示）与 14 附注

本文件是本轮的追加附注（不改回传正文，故回传 `PLANE-01.md` 自身 SHA 仍为 `c77543267941e3d9…`）。

## 内容

- `09_DEMO_10HZ.html`：自包含 10 Hz 演示页（27 帧循环、可暂停/拖动/逐帧看），数据=captures/leveled/363473a9…/tls（只读）。
  每帧统计与 `06_TRACK_REAL.json` 一致（27/27 命中、丢 0、每帧 8–23 点、R 6.38–6.62 m）。生成器 `sidequests/plane_track/r01/make_demo.py`。
- `09_DEMO_SUMMARY.png`：由 `05_TARGET_IDENTITY.png`、`06_TRACK_REAL.png`、`04_BACKGROUND.png`、`08_REPLAY_PAGE.png`
  拼的 2×2 总览（matplotlib 一次拼图，不是新分析）。
- `09_DEMO_10HZ_v1_broken.html`：v1 渲染失败版本（`const top` 与 `window.top` 重名导致 SyntaxError），改名留档不删；
  另有第二次 `BOUNDS[i]` 数值索引错误（也已复现）；最终版已在真实 Chromium 里确认 HUD/画布正常、无 console error。

## 查看方式（本机）

```bash
cd docs/sidequests/evidence/2026-10-14_plane_track_r1
python -B -m http.server 8961 --bind 127.0.0.1
# 浏览器打开 http://127.0.0.1:8961/09_DEMO_10HZ.html
```

本文件写入时该静态服务仍运行在 8961（我起的、只读证据目录、静态文件服务）；不需要时关掉该进程即可。

## SHA256

- `sidequests/plane_track/r01/make_demo.py`: `cdd77b43b45d96d32d80a6d30933b8fbc50e164a5d3023ef688725580b78b04f`
- `docs/sidequests/evidence/2026-10-14_plane_track_r1/09_DEMO_10HZ.html`: `dc91eed68c8e8377d31549f5a5fa7765ff52087341e8cb275671d55d7621b4d8`
- `docs/sidequests/evidence/2026-10-14_plane_track_r1/09_DEMO_SUMMARY.png`: `84cceab378d580c1586a514dff8f2b32f4eac14ffe8aa338ca0c3b25e699074c`
- `docs/sidequests/evidence/2026-10-14_plane_track_r1/09_DEMO_10HZ_v1_broken.html`: `3ecf642820236f36d3c0b91e113de34e35c24754d9fb6a0c403e40654af2db55`

## 说明

- 演示页是**展示用**，不是新实验；所有数值仍以 `06_TRACK_REAL.json` / `08_REPLAY_10HZ.json` 为准。
- 页面里的目标几何为"细长静止吊装物"，语义 UNKNOWN（未做飞行验证），演示标题不宣称"确认的小飞机"。
