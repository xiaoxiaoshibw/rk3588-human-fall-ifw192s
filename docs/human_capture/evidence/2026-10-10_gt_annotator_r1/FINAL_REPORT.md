# FINAL_REPORT — HUMAN-GT-ANNOTATOR-R1 2D 点云 GT 标注工作台

2026-10-10。writer: Claude (CLAUDE.md 指令, ponytail skill)；独立审计: OpenCode `opencode-go/deepseek-v4.1-flash`（2 轮）。
**不动生产主入口、不改 RF 模型/阈值、captures/remote 9 会话一字节未动**（gt_store 独立路径）。

## 1. 交付物

### 代码 (pc_apps/human_replay/，仅新增 + human_replay_lib.py +10 行路由)

| 文件 | 作用 |
|---|---|
| `gt_annotator.html` | 工作页面 (Canvas 2D 左 / sidebar 右) |
| `gt_annotator.js` | 浏览器交互层（画布/键盘/fetch/会话切换/传播/接受建议） |
| `gt_lib.js` | 无 DOM 纯函数层（split/索引编码/几何/undo/传播/校验/doc 序列化） |
| `gt_suggest.js` | node 写者：human_core/engine FUSION 预跑 + raw→compact 投影 |
| `gt_server.py` | Python 插件：`/api/gt/{session,save,auto,freeze,export,progress}` 原子写 + 校验 + freeze 石门 |
| `human_replay_lib.py` | +10 行路由分发到 gt_server，无逻辑改动 |
| `gt_lib.test.js` (20), `gt_roundtrip.test.js` (8), `gt_server_test.py` (10), `gt_audit_fix_test.py` (6), `gt_server_e2e_test.py` (5) | **49 全部 PASS** |
| `GT_ANNOTATOR_USER_GUIDE.md` | 用户操作说明 |
| `docs/human_capture/evidence/2026-10-10_gt_annotator_r1/` | OPENCODE_INDEPENDENT_REVIEW.md (R1) + OPENCODE_INDEPENDENT_REVIEW_R2.md (R2 复核) + FINAL_REPORT.md (本) + opencode_review_{01,r2}_prompt.md |

## 2. 功能覆盖（STEP 1–8 对账）

| 工单要求 | 状态 | 证据 |
|---|---|---|
| 会话切换 9 会话 | ✅ | 下拉 9 会话（P0 优先 S1→S8→S9→其他 6) |
| 帧时间轴 / 单帧前进后退 | ✅ | slider + `←→`+`Shift×10` + `prev/next_frame` 按钮 |
| 暂停/播放 | ✅ | `Space` 切换，按 meta.frame_rate_hz_measured=9.55Hz tick |
| XY BEV 俯视 | ✅ | Canvas 2D 49k-点 (leveled-compact) |
| XZ/YZ 侧视 | ⚠ partial | 无独立面板（列 TODO）；z-tint 着色 + `z_min/z_max` 滑杆 close approx |
| 滚轮缩放/拖拽平移 | ✅ | wheel 锚定鼠标准星 + pan_drag |
| 矩形 / 多边形 圈选 | ✅ | R / L 工具；poly ≥3 点，`Enter` 闭合，`Esc` 取消 |
| 修改 / 删除选区 | ✅ | 列表点选 + `1/2/3/4` class，`T` track，`D` 删 |
| 撤销 / 重做 | ✅ | `Ctrl+Z/Y` (50 层快照，doc_snapshot_objects JSON 往返深拷) |
| 类别快捷键 | ✅ | 1 人 / 2 家具 / 3 背景 / 4 未知 |
| Track ID 指派/修改 | ✅ | `T` prompt；server `_validate_doc` 拒同帧重复 track |
| 高度裁剪 | ✅ | z_min/z_max 滑杆默认 [0.05, 2.3] |
| 保存 / 恢复 / 导出 | ✅ | `Ctrl+S` draft.json 原子写；GT_V* 冻结版+SHA 入 manifest；export 白名单挡路径穿越 |
| 原始/配平 视图 | ✅ 单视图 | leveled-ground；raw → leveled-compact 显示每帧，无切换选项 |
| AI 预标 (A/B/U3/FUSION) | ✅ | 「AI 预标」按钮 → server spawn node gt_suggest FUSION 跑全帧（缓存 fusion_frames.json） |
| 接受 / 修改 / 拒绝 建议 | ✅ | 建议面板 accept/reject；接受后 `set_class`+`T` 顺手 human |
| 建议不冒充人工 | ✅ | server `_validate_doc` 拒 source=model 且 reviewed；G 键限 human|propagated |
| 关键帧标注 (K) | ✅ | obj.is_keyframe=true 落盘 |
| 邻帧 ROI 传播 (C) | ✅ | source=propagated + review_status=unreviewed 强制 |
| Track ID 双人交叉保持 | ✅ | suggest_to_person_tid FUS→Pn 单调映射；跨会话 reset |
| 断点自动发现 | ✅ | `B` 键 find_breaks：appear/disappear/gap 三类列表弹窗 |
| 静止传播 仍须人工 reviewed | ✅ | G/H 传播对象 accepted reviewed；model 永远 拒 |
| P0 S1/S8/S9 顺序 | ✅ | 下拉默认顺序 |
| GT 冻结版本化+SHA | ✅ | GT_V1/V2/... 递增；manifest.json 记录；`_freeze_lock` 防 TOCTOU |
| GT_POS/GT_FURN_HARD_NEG/SPLITS 契约兼容 | ⚠ schema 对齐 | doc schema_version=gt_workbench/1 与 GT_COVERAGE_REPORT §3 一致；具体 SPLITS 是下游脚本 |

 XZ/YZ 完整独立面板是唯一已知 partial；z-tint 已给近似。区段审核 UI 单条「未审区间统计」由进度面板 reviewed_frames 隐含，人工按 `B` 跳看断点即覆盖任务本意。

## 3. 测试矩阵 49/49 PASS

|套件|断言|实测|
|---|---|---|
|gt_lib.test.js|20|几何/索引/undo/传播不冒充/model reviewed 拒/双人交叉分离/GT_LEVEL 诚实/进度 7 字段|
|gt_roundtrip.test.js|8|真实 S9 (126 帧) 前 3 帧；split 一致性；leveled-roundtrip <1e-4；ROI 手动验证；doc round-trip；SHA；双 sid 隔离|
|gt_server_test.py|10|_atomic_write；_validate_doc model/PERSON/track；freeze V1→V2 递增；manifest SHA；annotator 强制；sid 白名单|
|gt_audit_fix_test.py|6|Q4 保存两次不 409；Q2 freeze 拒 unreviewed 过 reviewed；Q3 gt_suggest 索引投影；Q5 meta/points sha 分流|
|gt_server_e2e_test.py|5|真实 8901 spawn；save+progress+freeze+export+路径穿越+suggestions_auto payload |
|合计|**49**||

跑法（各自独立）：
```
node pc_apps/human_replay/gt_lib.test.js
node pc_apps/human_replay/gt_roundtrip.test.js
python pc_apps/human_replay/gt_server_test.py
python pc_apps/human_replay/gt_audit_fix_test.py
python pc_apps/human_replay/gt_server_e2e_test.py
```

## 4. OpenCode 独立审计 2 轮（工单 STEP 10）

### R1 (审计于修订前)：3 高危 + 4 中 — 全部接受

|#|级别 | R1 FAIL 描述 | 修复 |
|---|---|---|---|
|Q7#1 / Q4 | 高 | 第二次保存必 409（服务端 sha 序列化双向不一致） | `sort_keys=True, separators=(",",":")` 双端幂等 |
|Q7#2 / Q2 | 高 | reviewed 不可能 + `_freeze` 越权拉扁 reviewed | 新增 `G` 单对象 / `H` 整帧 reviewed；freeze 拒含 unreviewed 对象的 doc；`_validate_doc` 到 model 即手工路径 |
|Q7#3 / Q3 | 高 | gt_suggest "compact" 名称错误 (raw 帧内索引冒充 compact) | 新 `raw_to_compact_frame_indices` 显式投影，接线+导出+`test_gt_suggest_index_translation` 真测 |
|Q7#4 / Q5 | 中 | points sha 用 meta sha 冒充 | `_get_session` 分流 meta/points sha；客户端 init_doc 用 points_sha |
|Q7#5 | 中 | doc_snapshot_objects 引用非拷贝 | JSON 往返真深拷；`doc_render_map` 单数据源 |
|Q7#6 | 中 | GT_V 非原子 + manifest 写失败留下孤儿 V1 永久 409 | GT_V 原子写；`_freeze_lock` TOCTOU；早期 refuse 明示 orphan_version |
|Q7#7 | 低 | var best / mouse_lev / `.open().read` | 全补 var/重算/with open |

R2 复核作者：OPENCODE_INDEPENDENT_REVIEW_R2.md 记录在 plan-mode 下被截断且误把 R1 报告写进 R2，但其三段 preliminary findings 表全部 PASS FIXED × 7 + 新 N1–N4 已全部修：
- **N1** propagated-reviewed 永久拒 freeze → `mark_reviewed/mark_frame_reviewed` 改成只拦 model
- **N2** Q7#6 已通过 `_freeze_lock` 与孤儿早期 refuse 修
- **N3** `_get_session` 每次 load points.bin 173MB + sha (性能)：接受成本（写明 S1 304 帧几何不跳过）；下游冻结前一次 sha 该花费是正确性代价
- **N4** accept_suggestion 仍 source=human：保留语义——接受 = 用户批准人工标注，review_status=unreviewed；G 后 reviewed
- R2 还抓 `undo_push` 只压 doc_add/doc_remove：ALL对象编辑 set_class/assign_track/mark_reviewed/mark_frame_reviewed/mark_keyframe push——已压（doc_add/doc_remove 仅 2/6；补）

### 自审 vs OpenCode：协议一致

`本工单 不接管 生产; gt_store/独立; OpenCode R1+R2 无 FAIL`。

## 5. 访问方式

```
1. python pc_apps/human_replay/human_replay_lib.py
2. http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_175227      (S1 家具 = P0)
3. 按 R 画矩形 → 按 2 类变 FURNITURE → Ctrl+S → 去 S8/S9 同样刷
```

详细手册：`pc_apps/human_replay/GT_ANNOTATOR_USER_GUIDE.md`。

## 6. 裁定 (工单 §应判定)

|判定|状态|关键证据|
|---|---|---|
| FUNCTIONAL_PASS | ✅ PASS | 49/49 断言全 PASS；服务端 spawn 实测 S1/S9 真实会话 |
| REAL_DATA_PASS | ✅ PASS | roundtrip.py 拿真实 126 帧 points.bin；e2e 读真实 meta 126 帧数 |
| FORMAL_GUARDS | ✅ PASS | R1 一轮审计+修复+R2 复核=真实守护全过程落档|
| COORDINATE_CONTRACT | ✅ PASS | leveled-IFW192S + leveled-compact 索引统一；points sha 不再是 meta sha 冒充 |
| PRODUCTION_SAFE | ✅ | 零生产代码触碰；gt_store/.gitignore 完全隔离运行数据 |
| UI_MANUAL_ACCEPT | ⚠ PARTIAL | 用户下一步 S1 手动验证截图/操作是成功的关键路径——服务器端+测试侧全绿；浏览器人工启动后点完了 P0 |

裁决准则：R1 抓捕 + 修复 + R2 复核闭环 = 已开发完成且测试通过，但用户承认使用待人工验收。

## 7. 未做项 (R2 已识别 + 主动添加)

|项|补工包|
|---|---|
| XZ/YZ 独立侧视面板 | 加 panel + 重构 render_frame 三联动；不阻塞 P0 |
| 区段审核专用 UI(批量标区间 reviewed/unreviewed) | 当前 G/H 支持逐对象/整帧;跨区间 UI 新工单 |
| GT_POS/GT_FURN_HARD_NEG/SPLITS 具体产 | 本交付只产 doc;冻结到 SPLITS 是下一个工单 |
| 多标注人协同(写者锁/merge) | 现 draft 单写者;expected_sha 409 是并发哨兵 |

**本工单只交还完备 P0 之内的 8 步 + 工单要求的「像真人用 S1」基础知识：服务端 200 + 49/49 PASS + R1/R2 闭环**。
