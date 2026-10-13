# Codex 对 opencode 复审的逐条处置（B2-A-FIX-R1）

> 独立审计员三项代码层 PASS、整体 NO（E#1 阻断）。Codex 接受 NO、转条件修复，逐条处置如下。

## 接受审计员 ALL PASS 裁定中我无异议的部分

- A. FIX-1 claimed 集正确、20000 组模糊 0 缺陷、非排列不变但上游序稳定 → 无异议。
- B. FIX-2 死分支删净 → 无异议。
- C.9/C.10 load() 单点 + set_idx 守卫 → 无异议。
- D. 参数不变性、HRV2 保护 SHA → 无异议。

## 处置 E#11（gen 守卫"装饰性死代码"）—— 接受 REFUTED，但**保留代码+补注释**

审计员证伪我设计的第二条防线：replay.js 全程一个 `S` 对象引用，`load()` 就地改 `S.session_gen`；旧 rAF 回调拿到同一 S 读到新 gen → 守卫通过。gen 守卫对"同 S 复用"无效。

**核实：审计员正确**。真正兜底是 (1) load() 的 reset()，(2) set_idx 的跳帧 reset——这二者已覆盖全部 replay 生命周期。

**处置**：不删代码（叠加防御成本 1 行、零坏处；人造第二个 S 句柄的第三方嵌入/未来 worker 化会受益），但把注释从"gen 守卫防旧会话污染"改为**诚实**——它是"装饰性冗余防御，replay.js 兜底靠 load()/set_idx"。测试 `CE5.c/d` 保留（验证 gen 机制本身可工作，但不声称它是 replay 的防线）。

## 处置 E#1（高：after_fix 证据无效）—— **已修复并重生成**

- **审计员正确**：`b2a_shadow_probe.js:106-136` 是旧 R1 拷贝（无 claimed），六段与 before_r1 逐帧相同 = 零信息量；我此前"Shadow 复跑不变=参数保守"的解读**错误**。
- **已修**：`b2a_shadow_probe.js` 的 associate 同步为 claimed 版（与 detect_overlay.js FIX-1 同版），重跑 6 段。
- **重生成验证**（`after_fix/`）：
  - 六段 `age` 单帧 >+1 帧数 = **0**（审计员解除条件 ① 满足）。
  - 与 before_r1 差异帧：121622=20(@87)、122616=59(@80)、122637=92(@24)、其余 3 段=0——**与审计员复算逐帧一致**。
  - 122637 frame24 离散现场（写入 `COUNTEREXAMPLES_AFTER.md`）：
    ```
    f24 before_r1: #1(age26) #2         ← 裂簇并入 #1, age 24→26 (+2 通胀)
       after_fix:  #1(age25) #2 #3(age1) ← claimed: #1 单++; 裂簇独立成 #3
    ```
- **A/B 信息恢复**：after_fix 现在真实反映 FIX-1 生效（92/116 帧分歧于 122637 裂簇高发段），回归结论成立。

## 处置 E#2（中：跨会话红点失效）—— **已修复**

`replay.js finish_load` 在 `build_geometry()` 后、`paint_colours()` 后调用 `HUMAN_DETECT_OVERLAY.attach_color(S.colour)` 重挂（diff +6 行）。跨会话重挂成立。

## 处置 E#3（中：reset 注释事实错误）—— **已修复**

`detect_overlay.reset()` 注释从"set_idx 会重刷"改为**实清**：reset 遍历 colorBuf，把亮红（1.0,0.12,0.12）的点压回中性灰，replay 下次分位窗重画时被正确值覆盖。

## 处置 E#4（低：?sid= 不可达）—— **已修复**

`human_track.html` 把 `?sid=` 处理从 `try_init` 的 `S.geo && S.colour` 前置守卫中**提到独立的 `handle_query_sid` IIFE**：冷启时轮询 `__load_session_sid` 可用即触发载入，try_init 的几何等几何就绪另行等待。

## 处置 index.html 不传 RF（低，弱页面）—— **本轮不修**

如审计员注：index.html（detect_ui.js）不传 `rf` → HUD 退化为仅 `age>=3`，分类缺失。这是**页面本身的弱定位**，与 FIX-2"分类只归 RF"不矛盾（没说不接 RF 不算缺陷；是说"接了 RF 的页面里,关联状态不再当分类器"）。**低危**，属另一个工单（要么给 index.html 传 RF，要么明示它是弱复检页）。

## 复审后状态

| 项 | 审计员裁定 | Codex 处置 | 关闭 |
|---|---|---|---|
| FIX-1 代码 | PASS | 无异议 | ✅ |
| FIX-1 证据(E#1) | 高缺陷 | 已修 + 重生成 + 与审计员复算逐位一致 | ✅ |
| FIX-2 | PASS | — | ✅ |
| FIX-3 | PASS 附注 | E#11 保留+注释诚实；E#2/E#3/E#4 修复 | ✅ |
| 进 C 训练 | NO → 条件 | 3 项阻断全解除 | **条件 YES**（详见 FIX_R1_REPORT 终裁） |
