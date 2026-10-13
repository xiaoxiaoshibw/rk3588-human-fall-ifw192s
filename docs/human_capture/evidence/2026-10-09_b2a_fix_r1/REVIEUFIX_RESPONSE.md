# B2-A-FIX-R1 独立复审原文（opencode, deepseek-v4.1-flash）

> 本文件存档独立审计员回包，未经 Codex 修改。Codex 已在 REVIEUFIX_RESPONSE_CODEX_RESOLUTION.md
> 对其 4 条新发现缺陷逐条处置（E#1 解除 / E#2 修复 / E#3 修复 / E#4 修复）。

模型：opencode-go/deepseek-v4.1-flash。审计方法：ponytail full（通读 + 复跑 37/37 测试 + 20000 组模糊 + 逐帧复算 after_fix）。

---

已按 `ponytail`(full) 执行：审查前先通读全部被审代码、调用链与证据，未改任何文件。测试现场复跑：`detect_overlay.test.js` 37/37 PASS；r1 冻结反例套件已按预期方向翻转（在 `T.is_stable` 处崩溃，证明死分支已删）。对 FIX-1 另做 20000 组随机模糊与逐帧管线复算。

## A. FIX-1 关联唯一性
1. CONFIRMED — `detect_overlay.js:202` 建 `claimed`，`:208` 跳过已认领。单帧一对一成立。
2. CONFIRMED — age++ 只在匹配成功执行一次；cx/cy/r90/zmax/n 不被第二簇覆写。20000 组模糊：同帧重复 track_id=0、age 异常=0。
3. CONFIRMED（附条件）— 输入序稳定 → 可复现；但 associate 贪心**非排列不变**：测试只断言"总数=2"，逐簇归属依赖上游稳定序（真实管线无影响）。
4. CONFIRMED — cl.track_id 只在 associate 赋值；新建 id 唯一；无其他共享路径。

## B. FIX-2 HUD 语义
5. CONFIRMED — is_stable/stable/weak/stat_count 已删净；测试反向断言。
6. CONFIRMED — 确认=RF(person_prob≥0.55) ∩ age≥MIN_AGE；HUD 不引用关联状态做分类。
7. CONFIRMED — `_shown_ids` 在 FIX-1 后无真实触发，纯防御。
8. CONFIRMED — confirmed "人 N 个" 与 "观察中 N (未确认)" 文字明确区分。

## C. FIX-3 会话生命周期
9. CONFIRMED — `load()` 是所有入口唯一单点（目录/?sid/下拉/panel.load_by_sid→`__load_session_sid`→load），首步 notify_session+reset+复位 tracker_last_idx。
10. CONFIRMED（列盲区）— set_idx 守卫覆盖 (a) 同 idx 重入 (b) +1 增量 (c) 跳帧 reset；盲区：同 idx 早退不重刷颜色（残红不清）；循环 wrap 被当跳帧（有意）；守卫仅在 HDO 存在时生效。
11. REFUTED — `on_frame` 的 gen 守卫对 replay.js 真架构**基本无效**：全程一个 S 对象，load() 就地改写 `S.session_gen`；旧 rAF 回调传的同一 S 读到新 gen → 守卫通过。测试的 `S_old` 是人工第二对象，生产中不存在。真正兜底是 load() 的 reset + set_idx 跳帧 reset；gen 守卫是装饰性死代码。

## D. 参数不变性
12. CONFIRMED — RF 0.55/TRACK_GATE_M 1.0/TTL 15/MIN_AGE 3/z 带/bg_envelope 未动；`human_pipe_lib.js`/`.test.js` sha256 与 protected_snapshot **逐字节一致**。

## E. 新发现缺陷
- **#1 [高] after_fix 证据无效**：`b2a_shadow_probe.js:106-136` 的 associate 是旧版拷贝（无 claimed）。after_fix 六段与 before_r1 逐帧完全相同 = 同算法两次跑，A/B 对 FIX-1 零信息量。真实修复版复算 3/6 段分歧：121622 20 帧(@87)、122616 59(@80)、122637 92(@24)。
- **#2 [中] 跨会话红点失效**：build_geometry 每次新建 S.colour，attach_color 只在页面初始化调一次 → 切会话后 colorBuf 指向废弃数组。
- **#3 [中] reset() 注释事实错误**：set_idx 只改 drawRange，不重刷 colorBuf；reset 实际不清残红。
- **#4 [低] `?sid=` 路径不可达**：try_init 要求 S.geo 前置，冷启到不了；index.html 不传 RF，HUD 退化为仅 age>=3（弱页面，低危）。

## 四项总分
| 项 | 裁定 |
|---|---|
| FIX-1 | PASS（代码）— 但 after_fix 证据无效（#1），回归结论不成立 |
| FIX-2 | PASS |
| FIX-3 | PASS（代码，附注）— gen 守卫无效(#11)、跨会话红点失效(#2) 残留 |
| 进 C 训练 | **NO** — after_fix 是旧算法产物、仍含被修缺陷，无法支撑放行 |

**解除阻断最小条件**：①shadow_probe 的 associate 同步为 claimed 版，重出 after_fix 且无 age 单帧+2；②切会话重挂 attach_color（或复用旧数组）；③（可选）?sid= 移出 S.geo 前置守卫。
