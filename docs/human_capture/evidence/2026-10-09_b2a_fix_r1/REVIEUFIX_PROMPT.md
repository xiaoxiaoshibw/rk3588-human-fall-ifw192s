# B2-A-FIX-R1 独立复审任务（只读，禁止改任何文件）

你是独立审计员。复审 B2-A-FIX-R1 的最小修复。不轻信 Codex 结论，逐行核对代码与测试。

## 背景
前一轮审计 (r1) 发现三项 FAIL：HUD 显示层 (is_stable 对 shown 恒真)、Reset 生命周期 (管不到 rAF/多路径绕过)、Track 关联正确性 (同帧多簇绑同一 track)。本轮 FIX-1/2/3 修复。证据在 `docs/human_capture/evidence/2026-10-09_b2a_review_r1/`（已 SHA 冻结）。

## 审计对象（只读）
源码：
- `D:/Code/ldiar/pc_apps/human_replay/detect_overlay.js`（FIX-1 关联唯一性 + FIX-2 HUD 删除死分支 + gen 守卫）
- `D:/Code/ldiar/pc_apps/human_replay/detect_overlay.test.js`（36 用例）
- `D:/Code/ldiar/pc_apps/human_replay/replay.js`（FIX-3：`S.session_gen`/`S.tracker_last_idx` 声明、`load()` 接管、`set_idx()` frame identity 守卫）
- `D:/Code/ldiar/pc_apps/human_replay/human_track.html`，`D:/Code/ldiar/pc_apps/human_replay/detect_ui.js`

对照证据：`docs/human_capture/evidence/2026-10-09_b2a_fix_r1/`（`before_r1/*.tracks.jsonl` 修复前 6 段快照；`after_fix/*` 修复后 Shadow/flicker）

## 逐条回答（CONFIRMED/REFUTED/PARTIAL + 行号 + 一句理由）

**A. FIX-1 关联唯一性**
1. `associate()` 是否建立了单帧 cluster↔track 一对一？(claimed 集)
2. 同一 track 单帧 age 是否至多单++？cx/cy 是否不再被第二簇覆写？
3. 匹配是否确定性可复现（基于 cluster 输入序 + find_clusters 按尺寸降序保证的稳定序）？输入簇顺序扰动是否在测试断言下保持 track 总数/集合语义一致？
4. 是否还有任何路径能让同帧两簇共享同一 track_id？

**B. FIX-2 HUD 语义**
5. `is_stable()` / `stat_count` / `stable` / `weak` 死分支是否已删除？
6. HUD "人 N 个 (track ...)" 现在的判据是什么？是否只依赖 RF(person_prob≥0.55) + track age≥MIN_AGE，不引入关联状态做分类？
7. `shown` 里保留的 `_shown_ids` dedup 是否只是防御、在 FIX-1 后已无真实触发场景？
8. `observing N (未确认)` 调试项与 "人" 文字是否明确区分？是否仍可能让用户误判 confirmed 集合？

**C. FIX-3 会话生命周期**
9. `load()` 是否所有载入入口（下拉/目录/?sid=/panel.load_by_sid）的唯一单点？它是否先 notify_session + reset 再正常推进？
10. `set_idx` 的 frame identity 守卫是否能防：(a) 同帧重复回调 set_idx(同 idx)；(b) 顺序 +1 播放；(c) 跳帧（|Δ|≠1: 滑块/循环/大步/逆序）→ reset 单帧重建？指出守卫的盲区。
11. `on_frame` 的 gen 守卫 (`S.session_gen !== session_gen → return`) 是否堵住旧会话异步/rAF 污染？rAF 持旧 S 引用的情形是否仍可能绕过？(注意: replay.js 的 load() 用 var S = {...} 同一引用, async 完成时 S.session_gen 已被 bump — 旧 gen 的 on_frame 是否还会通过?)

**D. 参数不变性**
12. RF_THRESHOLD(0.55)/TRACK_GATE_M(1.0)/TTL(15)/MIN_AGE(3)/z 带/bg_envelope/生产 human_pipe_lib.js 是否未改？

**E. 新发现缺陷（0–4 条）**
13. 你独立发现的、本轮修复引入的或仍残留的缺陷。

## 交付
对每项给裁定，最后给 4 个总分：FIX-1 PASS/FAIL、FIX-2 PASS/FAIL、FIX-3 PASS/FAIL/BLOCKED、整体能否进入 C 训练 YES/NO/BLOCKED。
不修改任何源码或测试。
