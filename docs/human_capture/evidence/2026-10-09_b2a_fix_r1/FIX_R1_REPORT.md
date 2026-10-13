# B2-A-FIX-R1 最小修复交付报告

日期：2026-10-09（Asia/Shanghai）。范围：B2-A-REVIEW r1 三项 FAIL 的最小修复。
授权：用户 2026-10-09 B2-A-FIX-R1 授权（FIX-1/FIX-2/FIX-3 + 回归；FIX-4 仅反例，不修）。
边界：未改 RF/阈值/MIN_AGE/TTL/门/z 带/bg_envelope/生产 human_pipe_lib.js/融合层 v2/背景去除/聚类核心。未部署、未启动 C。

## 0. 关键证据锚点
- r1 证据（已冻结，SHA 见 `../2026-10-09_b2a_review_r1.sha256`）：4 份报告 + 7 组反例。
- r1 before Shadow：`before_r1/*.tracks.jsonl`（旧 associate 6 段快照）。
- r1 修复后 Shadow：`after_fix/`（含 6 段 clusters/tracks + flicker.json）。
- HR-RET-V2 保护：`protected_snapshot/` 的 SHA 与当前工作树一致（`human_pipe_lib.js/.test.js` 未受本轮影响）。
- opencode 复审：`REVIEUFIX_RESPONSE.md`（独立审计员原文）。

## 1. 三项修复总览

| ID | 目标 | 实现 | 文件 | diff 行 |
|---|---|---|---|---|
| FIX-1 | 单帧 cluster↔track 一对一 | `claimed` 集：同帧 track 至多单++、不被覆写 | `detect_overlay.js` | +13/−5 |
| FIX-2 | 删除 is_stable 死分支 | 移除 is_stable/stat_count/stable/weak；HUD 只显示"人 N(confirmed) + 观察中 N(未确认)" | `detect_overlay.js` | +22/−24 |
| FIX-3 | 会话生命周期统一接管 | `session_gen` + `tracker_last_idx`；`load()` 单点 notify_session+reset；`set_idx` frame identity；`on_frame` gen 守卫 | `replay.js` + `detect_overlay.js` + 两个 UI | +40/−6 |

净 core diff（不含测试）：约 +75/−35 行；测试用例重写 +156/−39 行。

## 2. 修复细节

### FIX-1 — Track 关联唯一性
**根因**（r1 CE1）：`associate()` 无「本帧已认领」集，两簇 <1.0m 于同一 track → 同帧 age 双++、`cx/cy` 被后簇覆写。
**修复**：
```
claimed = {}
for cl in clusters:
    for tr in tracks:
        if claimed[tr.id]: continue          # FIX-1 新增
        if d(cl, tr) < gate: best = tr
    if best: update(best); claimed[best.id]=1; cl.track_id=best.id
    else: create track; claimed[new.id]=1
```
- **确定性**：贪心按 cluster 输入序；`find_clusters` 已按尺寸降序 → 整个管线序稳定。
- **顺序鲁棒性**：测试断言 `[A,B]` 与 `[B,A]` 两种序下 track 总数一致（`顺序扰动` 用例）；具体哪簇绑哪 track 按序先到先得，不属"不合理变化"。
- **HUD 保障**：track_id 在 clusters 内天然唯一，HUD 不再可能 `(track #3 #3)`；dedup 防御性保留。
- **风险披露**：柜位裂簇从"共享 1 track"变"裂成 2 track"，**track 总数短期上升**——这如实反映簇结构，在 release note 标注。

### FIX-2 — HUD 语义（删除死分支）
**根因**（r1 Q3）：`is_stable(miss===0)` 对 `shown` 恒 true，weak 恒空（死代码）；且 `miss===0` 不能区分连续误检。
**修复**：删除 `is_stable`/`stable`/`weak`/`stat_count`。HUD 只显示：
- `人 N 个 (track #a #b)` — confirmed = RF(person_prob≥0.55) + track age≥MIN_AGE。
- `观察中 N (未确认)` — 调试观察项（过 RF 但 age<MIN_AGE 的 track 数）。**明确"未确认"字样**，不与 confirmed 混淆。
- **判据归属**：分类（人 vs 家具）只在 RF；时序确认（闪帧过滤）只在 `age≥MIN_AGE`；关联状态（miss）**不再介入分类**。
- **Q8.2 顺带修复**：染色只遍历 `shown`（confirmed），不再染 age<MIN_AGE 的簇。

### FIX-3 — Replay 会话生命周期
**根因**（r1 Q5/Q6）：reset 管不到 rAF；滑块/step/循环/`?sid=`/panel.js 多路径绕过；index.html 未接。

**三层防御**：
1. **代际守卫**（detect_overlay）：`session_gen` 模块级自增；`replay.js load()` 唯一入口 `notify_session()` + `reset()` + `S.session_gen = gen`。`on_frame` 检查 `S.session_gen !== session_gen → return` → 旧会话异步/rAF 带旧 gen 直接被忽略。
2. **frame identity 守卫**（replay.js `set_idx`）：`S.tracker_last_idx` 记录最近一帧。同 idx 重入 → 跳过 `on_frame`（不重复 associate）。`|Δ|≠1` → `reset()` + 单帧重建。
3. **UI 调用点瘦身**：`human_track.html` sessSel.change 不再手动 reset（load() 入口单点接管）；btn 重开张保留 reset + `tracker_last_idx = -1`（同会话内状态清理）。

**诚实分级**（用户验收"任意跳 N 帧 = 顺序重放到 N"）：
- **未实现**：需要每帧全量点云缓存或快速重放；**不在本轮范围**。
- **已实现且语义无谎**：顺序 +1 → 增量历史；跳帧 → reset 单帧重建，HUD 显示的只是"本帧分类"，不冒充历史。
- **不冒充**：代码注释、`set_idx` 注释、`COUNTEREXAMPLES_AFTER.md` 明确写出该分级。

## 3. 回归证据

### 3.1 单元测试 `detect_overlay.test.js`
**36/36 PASS**（含 r1 7 组反例转化 + 顺序扰动/重复帧/逆序/跨 gen/异步旧回调 12 组）。
opencode 复跑 37/37（含其自加一组），方向一致。

### 3.2 Shadow 复跑（claimed 版重生成，E#1 解除后）
6 段 after_fix 由修复后的 `b2a_shadow_probe.js`（claimed associate）产出：
- `age` 单帧 >+1 帧数 = **0**（审计员解除条件 ① 满足）。
- 与 before_r1 差异帧：121622=20(@87) / 122616=59(@80) / 122637=92(@24) / 其余 3 段=0——**与 opencode 复算逐帧一致**。
- 离散现场 122637 frame24（COUNTEREXAMPLES_AFTER.md）：`before_r1: #1(age26)` vs `after_fix: #1(age25) #3(age1)`。

### 3.3 gen 守卫 + frame identity 自验
- 旧 gen `on_frame` → `frame_no=0`（被忽略）；新 gen → 正常 +1。
- 同帧重入（直接调 overlay 2 次）：底层 `frame_no=2`；replay `tracker_last_idx` 在上层挡第二次——双层防御。

### 3.4 r1 证据 + HR-RET-V2 完整性
- r1 证据 SHA 复核：7/7 文件一致（未动）。
- HR-RET-V2 `human_pipe_lib.js/.test.js` SHA 复核：与 `protected_snapshot/HRV2.sha256` 一致（未受本轮影响）。

## 4. 独立审计（opencode, REVIEUFIX_RESPONSE.md 原文存档）

**审计员裁定**：FIX-1 代码 PASS、FIX-2 PASS、FIX-3 代码 PASS（附注）、进 C 训练 **NO**（当时因 E#1 证据无效阻断）。

**审计员 4 条新发现缺陷与 Codex 处置**（详见 `REVIEUFIX_RESPONSE_CODEX_RESOLUTION.md`）：

| # | 缺陷 | Codex 处置 | 状态 |
|---|---|---|---|
| E#1 | after_fix 由旧 probe 生成（零信息量） | probe 同步 claimed 版重生成；与审计员复算逐帧一致 | ✅ 解除 |
| E#2 | 跨会话红点失效 | `finish_load` 重挂 `attach_color(S.colour)` | ✅ 修复 |
| E#3 | reset() 注释事实错误（set_idx 不重刷） | reset 实清 colorBuf 红点 | ✅ 修复 |
| E#4 | `?sid=` 前置守卫不可达 | 移出守卫，独立 `handle_query_sid` 轮询 | ✅ 修复 |
| E#11 | gen 守卫"装饰性死代码" | 代码保留+注释诚实（replay 兜底=load()/set_idx 双重，gen 守卫是冗余） | ✅ 处置 |

## 5. 最终裁定（Codex 主，与审计员复审后对齐）

| 维度 | 裁定 | 依据 |
|---|---|---|
| FIX-1 关联唯一性 | **PASS（代码+证据双层）** | 36/36 + claimed 重生成后无 age+2、差异帧与审计员复算一致 |
| FIX-2 HUD 语义 | **PASS** | 死分支删净，RF+age 判据 |
| FIX-3 会话生命周期 | **PASS（代码，E#11 处置后）** | load() 单点 + set_idx 守卫 + E#2/E#3/E#4 修复；gen 守卫生效路径诚实标注 |
| HR-RET-V2 保护 | **PASS** | SHA 一致 |
| r1 证据完整 | **PASS** | SHA 复核无变 |
| **进入 C 训练** | **YES**（E#1 阻断已解除 + E#2/E#3/E#4 全修复 + 审计员所有 PASS 保留） | 关联缺陷隔离完成；证据链双层闭环 |

## 6. 交付物清单
- 代码 diff：`{detect_overlay.js, detect_overlay.test.js, replay.js, human_track.html, detect_ui.js, b2a_shadow_probe.js}`（b2a_shadow_probe 是 claimed 同步）
- 证据：`before_r1/`（旧快照）, `after_fix/`（claimed 重生成）, `protected_snapshot/`（HRV2 SHA）
- 文档：`FIX_R1_REPORT.md`(本), `COUNTEREXAMPLES_AFTER.md`, `REVIEUFIX_PROMPT.md`, `REVIEUFIX_RESPONSE.md`, `REVIEUFIX_RESPONSE_CODEX_RESOLUTION.md`
- SHA manifest：`SHA_MANIFEST.sha256`
- 单元测试：36/36 PASS（opencode 复跑 37/37）
- opencode 独立审计：原文存档，不篡改；4 条新发现全部处置
