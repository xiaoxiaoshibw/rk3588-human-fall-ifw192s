# GT 标注工作台 USER_GUIDE — HUMAN-GT-ANNOTATOR-R1

2026-10-10。

## 0. 一键开门

```powershell
cd D:\Code\ldiar
python pc_apps\human_replay\human_replay_lib.py
# 浏览器自动弹 8901 → 自己改 URL：
#   http://127.0.0.1:8901/gt_annotator.html?sid=cap_20261010_175227
```

也可以：
- 下拉框选其它会话（默认显示 9 个新会话，S1 家具 = `cap_20261010_175227`）。
- 标注人名字段填你的 ID（例 `zhangsan`），否则默认 `annotator-1`（冻结时强制必填）。

## 1. 三步开始 S1 家具标注

1. 下拉选 `cap_20261010_175227` → 右侧进度面板出 `S1-empty-with-furniture` 标题。
2. 左手慢慢拖鼠标平移 / 滚轮缩放。看到家具黄色簇（桌子、柜子、沙发等 ~4-5 件在 10×10m 区）。
3. 标注第一件家具：
   - 按 `R` → 在家具圆团周围拖一个矩形，松手.
   - 按 `2` → 这件家具 class 变 FURNITURE（黄）.
   - (可选) 按 `T` 输入 track id (家具一般是 `F1/F2/...`，非 PERSON 不强制)。
   - 按 `K` 标关键帧（没用，家具 1 帧就够；S8/S9 人才跨帧需要）。

重复 ~5 件就 OK。

## 2. S8 坐 60 秒静立人 annotation (still recall 分母)

S8 = `cap_20261010_180557`（523 帧，单人 60 秒静立）。

1. 抽帧 - 每 25 帧标一帧（前文工单要求 static 抽稀 ≥ 25 帧 1 帧）。
2. 拖到人出现帧（从第 0 帧附近）。按 `L` 圈人形 (3-6 点多边形)。
3. 按 `1` 类变 PERSON。按 `T` 给 `P1`（单人 P1 就行）。
4. 按 `C` 复制到下一帧（源对象 source=propagated, review_status=unreviewed）。
5. 按 `→` 一帧一帧跳，对照实际形状修，按 `1` 重新 set human/reviewed。
6. 帧间批量：每 25 帧到一个采样帧，重复上一步，或在跳帧时按 `B` 看轨迹断点提示。

- 关键帧标记 K：标帧代表入/离场的标志点。工单需要 `入场帧、静止区段起止、离场帧` —— 分别在前中后找顯著变化的帧按 K。

## 3. S9 双人交叉（最难，先 S1+S8 defensively 通）

S9 = `cap_20261010_180751`（126 帧，双人交叉）。

1. **重点**：双人各自独立 `P1`、`P2`；不要因为空间"近"就把 P1 的 ROI 改成 P2。
2. 开帧快进到明显双人都可见的帧（一般 f10-f50）
3. 两人分别圈两个 ROI，一个 `P1` 一个 `P2`.
4. 轨迹交叉期：一帧一帧用 `→` 跟，交叉前后单独检查 `P1`、`P2` 身份。
   - 怀疑交叉期 ROI 混了 → 按 `B` 看断点。
   - cross 出现在两人的关键点（坐标差 <0.4m）时把 visibility 打 `partial` 或 `occluded`（右侧 obj 列表 → 点击 → 未编辑，这是 TODO）。
5. AI 预标：点上方「AI 预标」按钮（慢，3-5 分钟） → fusion_frames.json 会拉下来，帧帧渲染提建议。
   - 每个建议圆圈旁「接受/拒」按钮 → 接受会自动建对象（source=human）。
   - 接受后建议对象是 unreviewed，再按 `1`/`2`/`3`/`4` 类 + `K` 关键帧 → 与人确认一样。

> 警告：建议 source=model，永远不会自动 reviewed；GT 冻结时会被 `validate_doc` 拒绝（test_validate_doc_rejects_model_marked_reviewed 强制）。

## 4. 撤销 / 重做 / 保存 / 冻结

|用途|操作|
|---|---|
|撤销|`Ctrl+Z`（步进 50 层）|
|重做|`Ctrl+Y`|
|保存草稿|`Ctrl+S` 或左下「保存」→ 写入 `gt_store/<sid>/draft.json` + history.jsonl|
|冻结版本|左下「冻结版本」→ 服务器生成 `GT_V<n>.json` + SHA256 入 manifest|
|导出|左下「导出」→ 浏览器下载 manifest.json（GT_V<n> 在服务端）|

- 崩溃恢复：系统崩了刷新后，草稿从 `draft.json` 回读；SHA 冲突时服务器返回 409，不覆盖。
- 轨迹跨 gap 停止：同 track_id 的事件帧帧内有跳帧，GT 会自动 audit 提示（可解释）。

## 5. 标注合法性自查（军工要求）

- 冻结时候服务器执行 `gt_server._validate_doc`：错哪怕一项都 400。
- 主要规则：
  - `source` 必须是 human/model/propagated 之一。
  - `reviewed` 必须 `source=human`（不能 model 冒充）。
  - PERSON 必须 track_id；同帧内 track_id 唯一。
  - session_sha256.points 必须填（从 SESSION_DATASET_MANIFEST 拷贝）。
- 看全部 9 会话覆盖：`/api/gt/progress?sid=<sid>` 的服务器 response 给出工单要求的 track_ids 数 / person / 家具 / 冲突 / reviewed 覆盖率。

## 6. HOW TO 标注一段长时间人仍静止（S8 60 秒）

- 抽帧：每 25 帧 1 帧 → 把每个抽到的帧标 PERSON(visible)。
- 静止区段仍缺 visibility 单独标注：用 obj 右键看属性（TODO；当前 UI 未暴露），或在 doc 写 `note: "still"`。
- 离场帧 K 标关键帧。exit_frame 写进 episodes 字段（服务器端产物）——目前 UI 不直接编辑 episodes，用手动 JSON 补丁非常罕见。

## 7. 常见错误 / 修复

|症状|原因|修复|
|---|---|---|
|AI 预标慢|fusion 预跑 9 关联 + 49k 点|等待（S1 最长 ~5min）|
|建议点 0|fusion 在背景差分下没吃到人|按 `→` 换帧找下一个建议|
|接受后 track_id 出现 `P10+`|suggest_to_person_tid 全局累加|手动按 `T` 改名 → history 记 modified|
|保存返回 409|另一写者动 draft|刷新页面后重干；draft.json.sha256 冲突提示|
|冻结 400|同帧 track_id 重复|右侧 panel 点击对象改 track_id（按 `T`）|
|画面只看到建议看不到野点|z 带太窄|改 Z min/max 滑杆（默认 [0.05, 2.3]）|

## 8. 数据不污染承诺

- 不会改 `captures/remote/<sid>` 任何位置 (audit: gt_server 只写 `gt_store`)。
- 不会改生产 RF (`rf_person_v1.json`) — pre-annotation 只是计算；接受建议 = 建 GT 对象不是改模型。
- 不会改 leveling R/T (默认 `render_person_label.R/T` 是 REF_RT 同一)。
