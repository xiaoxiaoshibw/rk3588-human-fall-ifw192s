## DET-06 R1 — 2026-10-08 / OpenCode / SUBMITTED

- 唯一验收：docs/sidequests/DET06_ACCEPTANCE.md v1（R1 自验区已追加），SHA `bca1b1e0323a98f963d1d24dcc3885089d0a7ff01f2c4fb32ee33d6a68abbcad`；计划 docs/sidequests/DET06_PLAN.md v1。
- 唯一 writer OpenCode（opencode-go/deepseek-v4.1-flash）；ponytail full 经 opencode skill 工具实际加载（id=ponytail；base dir `C:/Users/30680/.config/opencode/skills/ponytail`）。
- 分支 codex/human-detector-models，起始/结束 HEAD cfbb80c57508be1a0435fdb92260f698dc763934；主树只读（未写入；18 复核中 3 个外部文档文件 `docs/human_capture/*` 有变化，非本轮写入，已记录未回滚）。
- 用户授权链：第二人 = C1（与现有四段不同的人）；动作=站/举手；同房间、雷达未动；空场 114819 全程无人；24 帧人框"人框 OK"；硬负例 #1 桌子 / #2、#0 像人的固定物（非真人）。

### 结果摘要（描述性，单人单场景 24 帧）

- first32：同误报预算 ≤0.5 框/帧 recall 4.2%，≤1.0 时 25%。
- z_rank32：≤0.5 框/帧 recall 58.3%，≤1.0 时 100%（τ=0.25，约 0.92 框/帧）。
- 空场与人形固定物：first32 最高 0.20–0.29，z_rank32 0.35–0.54；空场不响需 τ>0.55，此时 z_rank32 recall 约 21%。
- 实现可信度：对照帧与 DET-03 存档逐值一致（atol 1e-5）；旧四段前景重生成与 DET-02 原产物 253/253 逐字节一致。

### 逐 ID 作者自验

|ID|作者自验|证据|
|---|---|---|
|S01|PASS|00 baseline / 18 integrity（3211 资产 0 变化；忽略文件 5876 0 变化）|
|P01|PASS|01_data_conditions / 03b|
|P02|PASS|02_protocol_freeze|
|A01|PASS|03_annotation_author（annotate_r4）+ 渲染|
|A02|PASS|03b "人框 OK" / 03c_freeze（gt_eval_v1，24/9/3）|
|B01|PASS|04_eval_config / 04_eval_summary（74 前向）；首跑路径 bug 保留 04_eval_r1_fail.log|
|M01|PASS|05_metrics.json；reproduction 逐值一致|
|T01|PASS|sidequests/human_detectors/test_det06.py（3 项）；`python -B -W error -m unittest discover` 15/15 OK；首次红灯（无 GT 守卫）已修复并保留结论|
|R01|PASS|17 打包（见 17_run_manifest / 17_artifact_index）；18_integrity.json|
|R02|PASS|本回传；sidequests/human_detectors/README 顶部同步；完整报告 evidence/2026-10-08_det06_r1/README.md|
|E03|BLOCKED|DET-03 资源限制继承；native ATen 未运行|
|G01|BLOCKED|仅 CPU；无 GPU 轮授权|
|L01|NOT_RUN|物理/辐射标定与独立人/场景泛化未做|
|D01|NOT_RUN|无设备/网络/驱动/部署/采集/生产动作|

### 失败与中间版（保留）

- 03_annotation_r1_fail.log：渲染中文字形缺失（-W error）→ 设置中文字体后重跑；03_annotation_r2/r3：中间版（硬负例筛选、<50 点残差显示）；最终采用 r4（03_annotation_*）。
- 03c_freeze_r1_fail.log：硬负例路径双重拼接，修复后重跑；无部分输出。
- 04_eval_r1_fail.log：评测路径类型 bug，首个条目加载前停止，无前向；修复后重跑，04_eval_config_r1_fail.json 保留。

### 限制与下一步

- 结论仅为描述性基线：单人、单场景、24 帧测试集；无 p 值；不报泛化或可用性。
- 下一步需新授权：DET-07 同传感器适配对照（固定本协议、dev 训练、test 不参与选择；判据以本基线为参照）；或 ATen/GPU 等价轮。
- 复审入口：[完整报告](../evidence/2026-10-08_det06_r1/README.md)，[唯一验收v1](../DET06_ACCEPTANCE.md)，编号日志 / 17 清单 / 18 完整性 / 22 范围。当前状态 SUBMITTED，未自行 ACCEPTED。
