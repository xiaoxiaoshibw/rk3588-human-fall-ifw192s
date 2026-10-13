# HFUS-D02 建议验收表（草案 v1 · 交主控登记为唯一当前验收表）

依据 HFUS-D02 任务书 + Unified Plan §5 表格行 + Taskbook E1 验收条款逐项映射。
每条为自验结果；`PASS` 是可复跑的工程自验，不等于主控/用户 ACCEPTED。
最终唯一验收表 ID 命名由主控统一登记，此处给出建议 ID `D02-xx`。

| 建议ID | 验收条款（出处 Taskbook E1 / Plan §5-D02 行 / 用户授权） | 自验命令/位置 | 结果 |
|---|---|---|---|
| **D02-01 工具可复跑** | 可复跑的工具入口（端到端一键构建待审包+split+报告） | `python -B sidequests/human_fusion_lab_next/next/review/build_review_package.py` 全量 exit 0，n_records=2309，产物落 review_out + evidence | **PASS** |
| **D02-02 索引绑定（工程）** | 28B raw / GT compact / leveled 三域显式区分；读错索引域即 FAIL；compact→raw 无误、越界计数 | `test_review_package.TestIndexBinding`（s/r/m decode + 越界）+ S6 obj_f0_n1 polygon 比对命中小簇（实证域=leveled-compact）| **PASS** |
| **D02-03 机器不升级人工** | 机器建议只标 DRAFT_UNREVIEWED/UNKNOWN；绝不自动写 HUMAN_REVIEWED/BOUND_HUMAN_REVIEWED | `TestMachineNeverUpgradesHuman` 各分支 + `TestPackageRealReadback.test_no_auto_reviewed_in_real_package` 真实包回读；`validate_no_human_auto` 硬门 | **PASS** |
| **D02-04 导出回读 + SHA 对账** | 待审包/资格 manifest 落盘；jsonl.sha256 == manifest 声明；9 会话 {meta,points} 双 SHA 入 manifest | `TestExportRoundtrip` + `test_manifest_consistent_with_jsonl`；`review_out/review_package.manifest.json.input_sha256_map`（9 会话） | **PASS** |
| **D02-05 不覆盖原始 GT** | 原始 GT / captures / 旧证据只读；本任务只新增文件 | 本任务仅写 `sidequests/human_fusion_lab_next/next/review/` 与 `docs/human_capture/evidence/2026-10-11_human_fusion_d02_r1/` 与 returns；git status 无 GT/captures 修改 | **PASS** |
| **D02-06 待审清单覆盖授权点名** | S6 f128/129/130/171/187/188+邻帧（bg_loss/no_candidate 落盘生效）；S4/S8 连续窗；S5/S7 低覆盖；S1 首中末+变化点；S9 双人 | S6：f187/188→`UNKNOWN bg_loss`、f91/128/129/130/171→`UNKNOWN no_candidate`、邻帧 f127/172/173→`PARTIAL coverage_gap`（真实落盘，对抗性复审修复后）；S8 53 静止候选；S1 1824 家具；S9 36 全 INVALID_BINDING | **PASS**（工程层齐备，经复审修复） |
| **D02-07 split 草案同会话单 fold** | 同会话不得跨 fold；不复制负例凑数；exact_duplicate=0 | `TestSplitLeakage.test_session_stays_in_one_fold` + `test_cross_fold_duplicate_detected`；dedup_report exact_duplicate=0/cross_fold_hashes=0 | **PASS**（草案工程） |
| **D02-08 负例来源坦诚** | 明确哪些负例有人工证据、哪些只是模型误检疑似；不复制负例 | `review_out/negative_evidence_report.json`：reviewed=0 / model_suspect=0 / unknown=1824 / folded_to_val_or_test=0 | **PASS**（记录坦诚） |
| **D02-09 测试 -B -W error** | 测试验证索引绑定、无效数据、导出回读、标签状态；Python 用 -B -W error | `python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/next/review -p "test_*.py"` = **18/18 PASS, exit 0**（含复审 HIGH/LOW 回归用例） | **PASS** |
| **D02-10 记录 branch/HEAD/输入SHA** | 先记录 branch、HEAD 和相关文件 SHA（含 untracked） | 本回传「本轮信息」+ `04_ARTIFACT_SHA256.json` + manifest input_sha256_map | **PASS** |
| **D02-11 与 D01 契约待接入声明** | 最终索引映射/导出须用 Codex D01 冻结 schema/version/SHA；未发布则记录待接入，不自猜 | `03_QUALIFICATION_AND_SPLIT.md` §五：D01 未发布 → 最终映射**待接入 BLOCKED**，采用双域如实记录+双 SHA 待重导出 | **BLOCKED（按授权如实登记）** |
| **D02-12 S9 双人身份真值** | S9 双人成员/身份/SHA 绑定问题（真值） | GT_V2 `aaaa…` 占位 → 36 全 INVALID_BINDING 登记；无人工复核 | **BLOCKED**（E1：语义/双人 BLOCKED） |
| **D02-13 有效独立 val/test 负例** | val/test 有独立于 train 的已审核负例 | reviewed_negatives=0；S1 propagated 负例未经人工确认独立性 | **BLOCKED**（E1：无人工审核则资格 BLOCKED） |
| **D02-14 静止 ≥20s 窗资格** | S4/S8 ≥20s 连续静止人工窗 | S8 最长静止段 1.76s，无 ≥20s GT；机器登记 UNKNOWN | **BLOCKED**（需人工补标） |
| **D02-15 跨 fold 重复为 0（语义）** | cross-fold exactduplicate=0 | 新包 exact_duplicate=0 已 PASS；但存量 XGB 训练折历史复制风险（train_person_rf.py:56/85）未由本任务证伪 | **NOT_RUN（存量）/ 交 D05a owner** |
| **D02-16 模型晋级** | 模型晋级需 D02 有效负例后 | 依赖 D02-13 人工负例，未达成 | **BLOCKED** |
| **D02-17 设备/板端/物理/部署** | 任何设备/物理/部署/采集 | 全程离线 PC，未触板 | **NOT_RUN** |
| **D02-18 提交/推送/部署/采集/ML** | 不 commit/push/deploy/采集/激活 ML | 未执行任何上述动作 | **PASS**（负向约束遵守） |

## 汇总

- 工程工具项 **D02-01~10、D02-18：PASS**（自验 18/18 + 真实包回读；含对抗性复审修复后回归）。
- **D02-11 D01 契约待接入：BLOCKED**（外部依赖，已如实登记，不自猜）。
- **D02-12/13/14/16：BLOCKED**（E1 明文：语义/双人/新家具泛化/模型晋级在无人工审核时 BLOCKED）。
- **D02-15 存量：NOT_RUN**（新包已 PASS；存量训练折历史风险交 D05a owner）。
- **D02-17：NOT_RUN**（设备未触）。

**状态：SUBMITTED（工程可交付）/ 语义与模型晋级保持 BLOCKED，等待人工审核。**
