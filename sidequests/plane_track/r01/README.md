# PLANE-01 小飞行目标支线（配平 → 去背景 → 跟踪）

隔离目录：本目录只读消费 `captures/remote`、`captures/leveled`、`src/human_fall_detection/core/`、
`pc_apps/human_replay/`，不写任何旧证据/生产/录制。证据在
`docs/sidequests/evidence/2026-10-14_plane_track_r1/`，回传在 `docs/sidequests/returns/PLANE-01.md`。

Windows 本机运行（Python 3.12 + NumPy 1.26；板端兼容代码保持 3.8/stdlib+NumPy，本目录脚本不部署板端）：

```bash
python -B -W error inventory.py   --out <evidence> [--name 01_INVENTORY_v2.json --markdown 01_INVENTORY.md]
python -B -W error level_sessions.py --out <evidence> <sid> [<sid> ...]        # 调 pc_apps/human_replay/leveling.run_job
python -B -W error inspect_target.py --out <evidence> --sid cap_XXX --job <job_id> --method tls
python -B -W error background.py  --out <evidence> --registration <dir>        # 空场配准 + 泄漏定量
python -B -W error background_probe.py --out <evidence> --registration <dir>   # 泄漏分布
python -B -W error plane_track.py --out <evidence> --job <job_id> --method tls # T4 实拍
python -B -W error plane_track.py --out <evidence> --synthetic [--name X.json] # T4 合成
python -B -W error replay_server.py --port 8941 --start-delay 5                # T5 10 Hz 回放
python -B -W error replay_client.py --url http://127.0.0.1:8941 --out <evidence> --name 08_REPLAY_10HZ.json
python -B -W error deletion_list.py --inventory <01_INVENTORY_v2.json> --out <evidence> [--write]
python -B -W error apply_deletion.py --out <evidence> --candidates <10_DELETION_CANDIDATES.json> <sid> ...
python -B -W error -m unittest test_plane_track -v
```

要点：

- `plane_track.py` 复用 `src/human_fall_detection/core/lidar_candidates.py` 的候选层，只改设置
  （`min_cluster_points=5`、`denoise_enabled=False`、`cluster_cell_m=0.3`、range 1–10 m、height −0.5–4.5 m）。
- 跟踪门限不用 `config/perception.yaml` 的 `max_speed_m_s=2.5`/`gate_m=0.8`：基础门 0.35 m（本工单实测
  目标 2.7 s 漂移 ±0.15 m），并按上一帧"划痕"长度自适应放大（`1.2×streak+0.15`）。
- `background.py` 的泄漏判据是距离判据（目标点在空场 `cell_m` 网格 ±1 格内无空场点 = 泄漏），
  避免体素网格相位假象（v1 网格精确判据已被 v2 取代，保留为 SUPERSEDED）。
- matplotlib 只用于证据 PNG（本机已装），跟踪/检测/回放链路只用 stdlib+NumPy。
