# HFUS-D02 离线待审包与复核辅助工具 — 证据索引（2026-10-11 r1）

工单 HFUS-D02（HUMAN-FUSION 并行开发），回传 `docs/human_capture/returns/HFUS-D02-REVIEW.md`。
工具（本任务独占）`sidequests/human_fusion_lab_next/next/review/`，产物 `…/review_out/`。

| 文件 | 内容 |
|---|---|
| `01_REVIEW_TARGET_FRAMES.md` | S1–S9 会话↔cap 映射、S6 重点帧逐点归因（依据，非新跑算法） |
| `02_BUILD_SUMMARY.json` | CLI 真实跑出的构建摘要（n_records/资格/割裂/SHA 索引） |
| `03_QUALIFICATION_AND_SPLIT.md` | **资格报告 + split 草案 + 人工审核清单 + D01 待接入声明（核心）** |
| `04_ARTIFACT_SHA256.json` | 本任务 25 个产物文件 SHA256 快照 |
| `05_ACCEPTANCE_DRAFT.md` | 建议验收表 18 条（D02-01..18，唯一表待主控登记） |
| `README.md` | 本索引 |

## 工具产物（`sidequests/human_fusion_lab_next/next/review/review_out/`）

| 文件 | 内容 |
|---|---|
| `review_package.jsonl` | 待审包 2309 条（机器建议 only，无 reviewed/BOUND） |
| `review_package.manifest.json` | 资格/原因/会话分布 + 9 会话 {meta,points} 双 SHA + jsonl sha 对账 |
| `split_draft.json` | split 草案（同会话单 fold，S9 blocked） |
| `dedup_report.json` | exact_duplicate=0 / cross_fold_hashes=0 |
| `negative_evidence_report.json` | 负例三级分级（reviewed=0/model_suspect=0/unknown=1824/folded=0） |
| `qualify_items.json` | 每条记录的机器资格 + reason |

## 状态

SUBMITTED（工程 18/18 PASS，经独立对抗复审返工：HIGH S6 漏检资格标定 + LOW 编码/兼容性已修）；D02-12/13/14/16 BLOCKED（语义/双人/负例/静止窗/模型晋级待人工审核）；D02-11 D01 契约待接入 BLOCKED；D02-15 存量 NOT_RUN；D02-17 设备 NOT_RUN。

复跑：`python -B sidequests/human_fusion_lab_next/next/review/build_review_package.py`
测试：`python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/next/review -p "test_*.py"`（**18/18 PASS**；对抗性独立复审返工后，含 HIGH/LOW 回归用例）
