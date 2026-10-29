# REPO-CLEANUP-01 回传

## 2026-10-18 · r1 · Codex 单写入者

- 状态：SUBMITTED；用户指令“现在项目文件太多了没用的归档，重复的删除”。不接管 HF/GL、HC/HR 工单。
- 策略：ENGINEERING；保留运行版本与历史证据，标准库 ZIP 归档和 SHA256 精确去重，不改生产代码。
- 实际 Ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 基线：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；所有 Git 可见含未跟踪文件 SHA 见 BASELINE.json，旧工作树差异保留。
- 当前唯一验收：[v1](../evidence/2026-10-18_repository_cleanup_r1/ACCEPTANCE_V1.md)；详细清单：[MANIFEST](../evidence/2026-10-18_repository_cleanup_r1/MANIFEST.json)；[检查结果](../evidence/2026-10-18_repository_cleanup_r1/CHECK.json)。

## 集中诊断与实际变更

临时目录保留旧打包暂存和浏览器诊断，控制台 dist 累积多版备份，ml_step1 为无现行运行代码引用的旧实验目录。归档到 `_archive/2026-10-18_cleanup_r1/`，原路径映射、字节与 SHA256 全量记录；ZIP 逐成员核验通过后才移除原文件，重复项仅在保留原样文件或已核验归档成员时删除。

`Bird识别/` 虽被 .gitignore 标为旧副本，仍被 sidequests/plane_track/r02/make_session_video.py 调用，保留。`data/`、`captures/`、junction、历史 evidence/returns、sidequests 研究输出、源码、现行 Console.exe 与发布包保持。无 Git 写操作、采集、训练、部署。

## 逐条验收

- C01：PASS（本机离线文件完整性检查，详见 CHECK.json）。
- C02：PASS（本机离线文件完整性检查，详见 CHECK.json）。
- C03：PASS（本机离线文件完整性检查，详见 CHECK.json）。
- C04：PASS（本机离线文件完整性检查，详见 CHECK.json）。
- C05：PASS（本机离线文件完整性检查，详见 CHECK.json）。
- C06：NOT_RUN（设备/物理/部署，无本轮授权）。

归档原件 410 个；删除哈希相同副本 223 个；原路径移除总计 633 个。原总字节 4173800417；ZIP 总字节 3812389189。未运行算法回归（生产代码未变）；归档逐成员及既有 Git 可见文件 SHA 检查完成。

## 未闭合与限制

历史证据和研究逐帧输出占据主要文件量，本轮按只读约束保留；不能仅按数量/扩展名判断无效。归档 README 提供无覆盖恢复步骤。独立复审 NOT_RUN，不自行宣布工单 ACCEPTED。
