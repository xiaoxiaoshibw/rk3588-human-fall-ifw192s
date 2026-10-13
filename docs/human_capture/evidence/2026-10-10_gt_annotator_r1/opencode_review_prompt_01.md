# HUMAN-GT-ANNOTATOR-R1 OpenCode 独立审计 prompt

2026-10-10。

## 任务范围

审计本目录 (/pc_apps/human_replay/ 及本文档父目录) 内 HUMAN-GT-ANNOTATOR-R1 工单的产出：

- `gt_annotator.html` / `gt_annotator.js`（浏览器 2D canvas 标注工作台）
- `gt_lib.js`（无 DOM 纯函数）
- `gt_server.py`（/api/gt/* 服务端插件）
- `gt_lib.test.js` / `gt_roundtrip.test.js` / `gt_server_test.py` / `gt_server_e2e_test.py`（43 全部 PASS claim）
- `human_replay_lib.py`（新加 2 行路由 /api/gt/*）
- `gt_suggest.js`（human_core FUSION 预跑节点）

工单目标：
- 用户可真实打开 S1/S8/S9 9 个会话
- 鼠标圈选人体/家具、跨帧 track_id、接受/拒绝 AI 建议
- 模型建议永远 unreviewed, 人工确认才 reviewed
- GT 准备/冻结/导出原子写 + SHA 守卫

## 审计问题

1. STEP 1 页面清单覆盖度：会话切换/时间轴/暂停播放单帧前进后退/BEV/XZ/YZ/缩放平移/矩形/多边形/修改删除/撤销重做/快捷键/track_id/高度裁剪/保存恢复导出 — 哪些真的做了？哪些未完成？（允许 partial，说清现状）
2. 模型建议冒充人工 GT 的强约束是否真实生效？(看 `make_object`/`propagate_object`/`validate_doc`/`server _freeze`/`test_validate_doc_rejects_model_marked_reviewed`)
3. 双人交叉是否被空间最近原则强制合并？(看 `propagate_object` 与 `find_breaks` 的 track_id 处理)
4. GT 保存/冻结/导出原子写 + SHA 守卫是否真实？（看 `_atomic_write`, `_freeze` 版本递增, manifest）
5. raw/leveled/compact 坐标契约是否混用？（重点：`gt_lib.split_frame_indices` 的 stride=4 vs stride=7 语义, `gt_suggest.js` 全局 compact 与 frame-level compact 是否正确同步）
6. 未修改的文件是否实际未修？（应只修 `human_replay_lib.py` 2 行 + 新增 gt_* 文件；不允许动 `human_core`/`human_replay_lib.js`/`rf_person*.json`）
7. 报告任何潜在 bug/崩溃/数据不一致的具体证明（复现路径）

## 期望产出

markdown 审查报告, 每项 FAIL 给出代码位置 + 失败案例 + 建议修复；PASS 给简要判据。存入 `OPENCODE_INDEPENDENT_REVIEW.md`。
