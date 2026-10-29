# qual_r01 — HFUS-INDOOR-DATA-QUAL-01 数据资格线（2026-10-16）

独立侧链：公开 OD1 数据集（O-LiPeDeT，ML/data 三 ZIP）的**数据契约与人工审核资格**核验。
不训练、不解锁 HFUS E1/HR09。唯一验收：`docs/human_capture/evidence/2026-10-16_hfus_indoor_data_qual_r1/`
下按 ACCEPTANCE_V2（ND01–ND08）逐条记账；证据目录含 ND02 结论、解释注册表、队列与几何实测。

- `box_rotation_test.py`：末列= yaw(度,绕+Z) 的物理判定（526 框 PCA+值域+相邻帧持久性）。
- `make_queue.py`：冻结 24 帧人工审核队列（规则预注册）+ 采集组账本。
- `qual_server.py` + `index.html/app.js`：本地审核台（127.0.0.1 随机端口，追加式哈希链账本
  `reviews/ledger.jsonl`，只存真实人工判断；自检走 `--ledger` 临时路径）。
- 双击 `start_qual.bat` 或 `python -B -W error sidequests/hfus_indoor_ai_test/qual_r01/qual_server.py`。

已知边界：可信独立采集组 0（作者无录制元数据，ND04 BLOCKED）；GT 完备性/单框语义须人工判定（ND03）；
候选负类需完备 CONFIRMED 或逐候选人审；本目录读取 r7/r4 只读，不覆盖旧 run。
