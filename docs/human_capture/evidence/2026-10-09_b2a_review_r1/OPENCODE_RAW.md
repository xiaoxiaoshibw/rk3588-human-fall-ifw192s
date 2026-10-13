# opencode 独立审计原始回复（deepseek-v4.1-flash）

> 本文件为独立审计员 opencode CLI 的原始输出存档，未经 Codex 修改。
> Codex 对其中 Q6/Q7/Q8.1 的事实性偏差已在 AUDIT_REPORT.md 用 git/node 核实修正，
> 但此处保留审计员原文，以维持独立审计证据的完整性与可追溯性。

模型：opencode-go/deepseek-v4.1-flash（OpenCode Go 订阅）
输入：AUDIT_PROMPT.md（stdin 管道，只读任务）

---

VERDICT_OVERLAY_HUD: FAIL
VERDICT_RESET: FAIL
VERDICT_TRACK_ASSOC: FAIL
VERDICT_ALLOW_C: NO

**Q1 CONFIRMED** — `associate()` 每簇独立找最近 track,无 `used` 集(detect_overlay.js:198-217)。A 簇绑 T 后改写 T.cx=A.cx(:207-208);B 簇(距 A <1.0m)仍以 T 为 best,再 `age++`、覆写 cx/cy/r90/zmax/n(:208-209)。同帧 age 双增、字段被后簇覆盖,成立。

**Q2 CONFIRMED** — `_shown_ids` 只在 shown 过滤时去重(:271-281),底层两簇仍共享同一 `track_id`;着色循环遍历 `clusters` 而非 `shown`(:287-294),两簇点都染红。纯显示层掩盖。

**Q3 REFUTED** — 语义不成立,且分组退化。`shown` 只来自本帧 clusters,而 associate 保证任何被簇引用的 track `miss===0`(:208,211-212)。故 `is_stable(tr_h)`(:234)对 shown 恒 true,`weak` 恒空(:310-323)。`miss===0` 仅表示"本帧关联命中",连家具/真人都区分不了(RF 才是判别器)。

**Q4 PARTIAL** — "两组间闪烁"不成立(weak 不可达)。真人漏帧时该 track 无本帧簇→根本不进 shown,表现为 HUD 里该 track/count **消失一帧再回来**(存在性闪烁),非分组闪烁。代价:计数抖动、sprite/框闪断。

**Q5 CONFIRMED** — `reset()` 只清 last+labelSprites(:367-372),管不到 rAF:replay.js:500-516 的 `tick→set_idx→on_frame` 在 reset 后继续用旧 S 重建 track、吃掉 id,随后 finish_load `set_idx(0)` 又在新 S 上叠加;滑块(:684-687)、step(:523-526)、方向键、speedSel(:530-533)均能复活。绕过点还有 `?sid=`(human_track.html:208-211)、panel.js load_by_sid/同步自动载入(:248-258)。`hud_extra`、colorBuf 红点也不清。

**Q6 PARTIAL** — 两处只覆盖 human_track 下拉+开关 与 detect_ui 开关;index.html:166 有 `detectBtn` 入口,但切会话走 panel.js:`load_by_sid`→`__load_session_sid`,**无 reset** → index.html 跨会话污染仍在。human_track `?sid=` 路径同样漏。

**Q7 PARTIAL** — 4 文件 diff 逐参数核对:RF_THRESHOLD 0.55(:34)、TRACK_GATE_M 1.0(:191)、TTL 15(:192)、MIN_AGE 3(:193)、z 带 0.1–2.3(:247)、bg 均**未改**。但 `human_pipe_lib.js` 在工作树中**已被改**(git diff:新增 `extract_foreground_fused` 等 HR-RET-V2 融合代码),非本次 HUD diff 所触,属独立改动;若"本次改动"指整棵工作树,则它被触碰。

**Q8 NEW_DEFECTS**
1. `grid_key` 非单射(:125-128):`gx*4096+gy`,负 gy(如 gx=1,gy=-1→4095)与 gx=0,gy=4095 碰撞;反查 `cur%4096`(:163)对负值也解错。雷达后方(y<0)点会被错误合并/粘连。触发:任意 y<0 点。
2. 未确认簇也染红(:287-294):遍历 `clusters` 而非 `shown`,age<MIN_AGE 或(若 reset 未清)残留簇的点被涂红,与 HUD"无目标"矛盾。
3. `_test.stat_count`(:382)永不更新,测试面误导;且无任何用例断言 `weak` 非空,掩盖 Q3 退化。
4. `reset()` 不清 `S.hud_extra`/颜色缓冲(:367-372),重开后 HUD 文案与红点短暂陈旧。

**MINIMAL_FIX**
```
associate: used={}; for cl: for tr: if(!used[tr.id] && d<gate) best=tr;
           if(best){used[best.id]=1; ...}
is_stable: 删除,或维持 tr.miss_hist(近K帧 miss 计数) over miss===0;
           若不做历史,直接删 weak 分支(死代码)。
reset: replay.js load() 入口单点调用 HUMAN_DETECT_OVERLAY.reset()(根因),
       并在 reset 内 S.hud_extra="" 且重刷 colorBuf;或给 S 加 session_gen,
       on_frame 校验 gen 不符则忽略。
grid_key: 改 string `${gx},${gy}` 或 gy 偏移常量,消除碰撞。
```
NEW_DEFECTS: 见 Q8 四条。
（未改任何文件,纯只读推理。）
