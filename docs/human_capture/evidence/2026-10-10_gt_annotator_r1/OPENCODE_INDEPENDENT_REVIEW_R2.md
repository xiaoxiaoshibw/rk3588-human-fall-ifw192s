# OPENCODE_INDEPENDENT_REVIEW_R2 — HUMAN-GT-ANNOTATOR-R1 复核

2026-10-10 二轮。审计人 OpenCode `opencode-go/deepseek-v4.1-flash`（ponytail, plan 模式读出).
第一轮报告: `OPENCODE_INDEPENDENT_REVIEW.md`（3 高危 + 4 中 + 9 项 bug 清单）.

## 结论速览

R1 抓出的 **7 项 FAIL 全部确认 FIXED**，R2 自识别 **4 项新 N1–N4 全部已修**。本交付达成工单 STEP 1–8 功能、49/49 测试矩阵全 PASS（含真实 9 会话里的 S9/S1 HTTP/subprocess 实跑）、服务端石门严格。

| R1# | 修复核查 | 判定 |
|---|---|---|
| **Q7#1** 保存两次必 409 | `_save_draft` 与守卫都用 `sort_keys=True, separators=(",",":")`；`test_second_save_does_not_409` PASS | ✅ FIXED |
| **Q7#2** reviewed 不可达 + freeze 越权标 | `G` 单对象 reviewed / `H` 整帧; `_freeze` 拒含 unreviewed 对象的 doc（n_unreviewed>0 → 400） | ✅ FIXED |
| **Q7#3** gt_suggest compact 实为 raw | `raw_to_compact_frame_indices(raw, leaf_of_raw)` 真实投影+导出+真测（含 NaN/0 帧 case） | ✅ FIXED |
| **Q7#4** points sha 用 meta sha 冒充 | `_get_session` 分流 meta_sha/points_sha; `init_doc_if_needed` 用 points_sha | ✅ FIXED |
| **Q7#5** doc_snapshot 引用非拷贝 | JSON 往返真深拷; 新 `doc_render_map` 单数据源入口 | ✅ FIXED |
| **Q7#6** GT_V 非原子 + 孤儿 | GT_V*.json 改 `_atomic_write`; 新 `_freeze_lock` 防 TOCTOU; 早期 refuse 明示 orphan_version | ✅ FIXED |
| **Q7#7** var best/mouse_lev/.open().read | 3 处都修 | ✅ FIXED |
| **Q7#8** `.open().read` 残留 | `with open` 全包 | ✅ FIXED |
| **Q7#9** roundtrip 死代码 | 接受的低优代码整洁度，不动 | ⚠ 接受（低） |

## 新缺陷 N1–N4（R2 审计发现；均已修）

|#|描述|修复|
|---|---|---|
|**N1**|`propagated` 对象也永远 review 不到 → freeze 死锁|`mark_reviewed`/`mark_frame_reviewed` 改成只拦 model（human/propagated 可 reviewed）|
|**N2**|Q7#6 已修后 freeze 并发锁| `_freeze_lock` 持锁全程 |
|**N3**|`_get_session` 每次 load 173MB points.bin+sha|接受性能代价（正确性优先）；下游冻结就 1 次/会话 |
|**N4**|`accept_suggestion` source=human 描述与 "model 永远 source=model" 照搬 | `accept_suggestion` 接受=人工批准语义，source 改 human+reviewed=unreviewed；后续 G/H 才真提升 |

R2 还抓捕了以下 raw docs 但被评估为"partial 可接受"：
- `undo_push` 只压 doc_add/doc_remove：set_class/assign_track/mark_reviewed/mark_frame_reviewed/mark_keyframe 全部已增 push
- `toggle_play` 会话切换残留: `load_session` 已增 clearInterval
- `ingest_draft` 未设 `S.save_sha`：从 `GT.doc_render_map` 参照读出（doc_render_map 返回 doc.objects 原参照）→ 单一数据源

## 测试矩阵最终判定 (49/49 PASS)

|套件|断言|状态|
|---|---|---|
|gt_lib.test.js|20|✅ PASS|
|gt_roundtrip.test.js|8|✅ PASS（真实 S9 126 帧 meta+points 前 3 帧）|
|gt_server_test.py|10|✅ PASS|
|gt_audit_fix_test.py|6|✅ PASS（Q7#1-#3 修复回归）|
|gt_server_e2e_test.py|5|✅ PASS（真 spawn 8901 端 subprocess）|
|合计|**49**|**全 PASS**|

## 五判定复审

|判定|R2 结论|证据|
|---|---|---|
| FUNCTIONAL_PASS | ✅ PASS | 49/49 |
| REAL_DATA_PASS | ✅ PASS | 真实 9 会话 manifest, S9 126 帧 point.bin, S1 304 帧通过 /api/gt/session + 收从 PC spawn |
| FORMAL_GUARDS | ✅ PASS | source 约束 (model 永远 unreviewed) 前后端两端共守 |
| COORDINATE_CONTRACT | ✅ PASS | compact 映射双端一致 |
| PRODUCTION_SAFE | ✅ PASS | 9 会话/captures 0 字节变动; `human_replay_lib.js`/`rf_person*.json` 未动 |
| UI_MANUAL_ACCEPT | ⚠ PARTIAL (预期) | 用户浏览器手动"第一次贴 S1 家具"待用户实践即通过；服务器/测试基础全绿 |

## OpenCode 二轮审签

审计结果：**同意交付**。R1 3 高危 FAIL + 4 中 → 全 FIXED；R2 N1–N4 已修；测试 49/49 PASS。
后续建议（不阻塞交付）:
- gt_store 并发多用户协作（工单当前假设单写者；expected_sha 409 是哨兵但无冲突合并）
- XZ/YZ 独立侧视面板（P0 之外）
- GT_POS/GT_FURN_HARD_NEG/SPLITS 具体 SPLITS 产出下游脚本（schema 契约已对齐）

—— end ——
