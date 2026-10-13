# B2-A-REVIEW 独立审计报告

日期：2026-10-09（Asia/Shanghai）。范围：仅审计 `detect_overlay.js` / `detect_overlay.test.js` / `human_track.html` / `detect_ui.js` 的显示层小修（reset、HUD 分组、dedup）。**本轮不改生产、不启 C 训练。**

方法：Codex 基线检查 + 7 组确定性反例（`counterexamples.js`，7/7 运行确认）+ opencode CLI `deepseek-v4.1-flash` 独立只读审计（prompt 见 `AUDIT_PROMPT.md`）。Codex 未以自身测试替代独立审计；对 opencode 结论中两处事实性偏差另行用 git/node 核实并在文中标注。

## 一、最终裁定

| 维度 | 裁定 | 依据 |
|---|---|---|
| HUD 显示层 | **FAIL** | Q3 证伪：`is_stable(miss===0)` 对 `shown` 恒 true→「低稳定候选」分支为死代码，零区分力（详见 Q3） |
| Reset 生命周期 | **FAIL** | Q5：reset 管不到 rAF；多路径绕过（滑块/step/循环/`?sid=`/panel.js `load_by_sid`），index.html 切会话未接 reset |
| Track 关联正确性 | **FAIL** | Q1 确认：同帧多簇绑同一 track，`age` 重复 ++、`cx/cy` 覆写；`shown` dedup 仅显示层规避 |
| 是否允许进入 C 训练 | **NO** | 关联缺陷未隔离；HUD 分组语义失效；需先最小修复 + 回归 |

opencode 独立审计三项裁定一致 FAIL。Codex 在核实后对 Q6/Q7/新缺陷#1 做了修正（见下"核实修正"），**不改三项 FAIL 主结论**。

## 二、逐项审计结论

### Q1 同帧多簇绑同一 track — **CONFIRMED（缺陷）**
`associate()`（`detect_overlay.js:195-226`）对每簇独立找最近 track，无「本帧已认领」集。簇 A 绑 track T 并覆写 `T.cx/cy/r90/zmax/n`（`:207-208`）后，簇 B（距 T<1.0m）仍以 T 为 best，再次 `age++` 并覆写字段（`:208-209`）。
实测（CE1）：单帧两簇 → `age` 由 1 直接变 3（应为 2），`cx` 记录后簇 B 位置（前簇 A 信息丢失）。**物理对应**：柜位 5cm 漫水把一个高目标裂成两簇。这是 Shadow r1 中 `age=148>frame_no=107` 的根因。

### Q2 `shown` dedup 是根治还是规避 — **CONFIRMED（显示层规避）**
`_shown_ids`（`:271-281`）只在 display 过滤时去重；底层两簇仍共享同一 `track_id`，且 `on_frame` 着色循环遍历 `clusters`（非 `shown`，`:287-294`）两簇点都染红。CE2 实测：dedup 后 shown=1，但底层 track 被两簇共享不变。

### Q3 `is_stable(miss===0)` 分组语义 — **REFUTED（语义失效，死代码）**
`shown` 仅来自当前帧 `clusters`；被 cluster 引用的 track 在 `associate` 中必 `miss=0`（`:208`）。故 `is_stable(tr_h)` 对 `shown` 恒 true → `weak` 数组恒空（`:310-323`）。
- **后果**：「低稳定候选」分组**结构性不可达**。Codex 此前冒烟测 `weak=0` 误判为"间歇 filtered 正确"，实为死代码。
- **用户 P1 担心成立且更重**：`miss===0` 仅表"当前帧 associate 命中"，连"连续误检的家具 vs 真人"都无法区分（CE3：柜子 5 帧→is_stable=true）。判别器只能是 RF，不是关联状态。

### Q4 真人短暂漏检 → HUD 闪烁 — **PARTIAL**
"人/候选两组间闪烁"不成立（weak 不可达）。真人漏帧 → 该 track 本帧无簇 → 不进 `shown` → HUD 里**消失一帧再回来**（存在性闪烁，sprite/框闪断）。CE4 确认；代价为计数抖动。

### Q5 reset 完整性 — **CONFIRMED（不完整，多路径绕过）**
`reset()` 只清 `last`+`labelSprites`（`:367-372`），管不到 rAF：`replay.js:500-516` 的 `tick→set_idx→on_frame` 在 reset 后继续用旧 `S` 重建 track、消耗 id；滑块（`:684-687`）、`step`（`:523-526`）、方向键、`speedSel`（`:530-533`）、`?sid=`（`human_track.html:208-211`）、`panel.js load_by_sid`（`:248-258`）均能复活。`S.hud_extra`、colorBuf 红点在 reset 也不清。

### Q6 两处 UI 调用点覆盖 — **PARTIAL（核实修正 opencode）**
- opencode 称 index.html `detectBtn` 切会话无 reset。核实：index.html 的切会话走 `panel.js load_by_sid → __load_session_sid`，该路径**无 `HUMAN_DETECT_OVERLAY.reset()`**；`detect_ui.js` 只在 btn 重开接 reset。→ **index.html 跨会话污染仍在，确认缺陷。**
- `human_track.html` 的 `?sid=` 首次载入（`:208-211`）在 `sessSel.change` 之外，同样未触发 reset。

### Q7 参数核对 — **PASS（核实修正 opencode 的 PARTIAL）**
本次 4 文件 diff：RF_THRESHOLD 0.55(:34)、TRACK_GATE_M 1.0(:191)、TTL 15(:192)、MIN_AGE 3(:193)、z 带 0.1–2.3(:247)、bg_envelope 生成链均**未改**。
- opencode 标 `human_pipe_lib.js` PARTIAL，因 `git diff` 见其有 `extract_foreground_fused`。核实：**该改动是 HR-RET-V2 融合 increment 1 的既有未提交改动**（`git log 8637f01 HR-W03`，非本次 HUD 会话触碰）。本次会话 `git diff --name-only` 中该文件与会话 4 文件并列，属同 working tree 既有脏态，非本次写入。**判定：本次会话未触碰生产 human_pipe_lib.js。**

### Q8 审计员新发现（核实）
1. **grid_key 非单射**（`:125-128` `gx*4096+gy`）：碰撞需 `gy≥4095` 即 `y≥204.75m` —— IFW192S 量程 ≤30m，**物理不可达**。但漫水邻域反解 `Math.floor(cur/4096), cur%4096` 对负 key 错误（负 y 侧），影响负 y 区聚类邻域。**PARTIAL：理论缺陷，量程内不触发；负 y 反解值得最小修复，非阻塞。**
2. **未确认簇也染红**（`:287-294` 遍历 `clusters` 非 `shown`）：age<MIN_AGE 或残留簇的点被涂红，与 HUD"无目标"矛盾。确认。
3. **`_test.stat_count` 永不更新且无 weak 断言**：测试面误导，掩盖 Q3 死代码。确认。
4. **reset 不清 hud_extra/colorBuf**：重开后文案/红点短暂陈旧。确认。

## 三、生产值不变性确认
本次会话 4 文件 diff 未触碰：RF 阈值、TRACK_MIN_AGE、TTL、关联距离、z 带、bg_envelope、生产 `human_pipe_lib.js`、`human_track.html` 之外的管线页。`b2a_shadow_probe` 复跑两段（122637/121622）clusters/tracks 数字与 r1 完全吻合。

## 四、证据文件
- `counterexamples.js` + 运行输出（7/7 PASS）→ `TEST_RESULTS.md`
- `AUDIT_PROMPT.md`（opencode 输入）、opencode 原始回复（本报告 §二 各条）
- 核实脚本输出（grid_key 碰撞物理量程分析，§Q8.1）

> Codex 与独立审计员（opencode）结论：三项 FAIL、C 训练暂停。待最小修复 + 回归后复审。
