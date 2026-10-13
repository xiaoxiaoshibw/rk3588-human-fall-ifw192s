# B2-A-FIX-R1 修复后反例对照（与 r1 审计证据锚定）

r1 的 7 组反例在修复后的行为变化。**r1 原始证据不动**（`2026-10-09_b2a_review_r1/` SHA 已冻结），
本表仅描述 FIX-R1 后 `detect_overlay.test.js` 的对应回归断言与运行结果。

| r1 反例 | r1 结论 | FIX-R1 后行为 | 对应测试 | 结果 |
|---|---|---|---|---|
| CE1 同帧两簇 → age 双++/cx 覆写 | 缺陷确认 | **claimed 集**：第二簇若唯一候选被认领→新建 track；age 单帧单++；cx 不被覆写 | `CE1.b/c/d/e` | **PASS**（36/36 全过） |
| CE2 底层同 track_id 共享 | dedup 掩盖 | 关联层唯一，`track_id` 天然无重复；dedup 仅防御性保留 | `CE2` | **PASS**（`cl0.track_id !== cl1.track_id`） |
| CE3 连续误检柜子 is_stable=true → HUD 人 | 死代码/分类错误 | **删除 is_stable/stat_count/stable/weak**；"人 vs 非人" 只归 RF 分类 + track age 时序；track 层只维护时序不扮演分类器 | `CE3` | **PASS**（is_stable/stat_count 已从导出删除） |
| CE4 真人漏帧 → HUD 组间闪烁 | 存在性闪烁 | 漏帧 → track miss++（TTL 内留住）；无"人/候选"分组往返；age 不因 miss 增长 | `CE4` | **PASS**（miss=1 但 age 单帧至多单++；接回同 track） |
| CE5 reset 管不到 rAF | 多路径绕过 | `notify_session` + `S.session_gen` 守卫 + `set_idx` frame identity；旧 gen 的 on_frame 直接 return | `CE5.c/d` | **PASS**（旧 gen 被忽略 / 新 gen 正常） |
| CE6 跨会话 id 累计 | 部分确认（r1 已修复表象） | load() 入口单点 notify_session+reset（不再漏 `?sid=`、panel.js 路径） | `CE6.b` | **PASS**（id=1，不再累计） |
| CE7 稳定/间歇并筛 | is_stable 二分不合理 | 移除 is_stable；track 层语义清晰（稳定 age 全命中；间歇 age=命中帧数，miss=间隔数） | `CE7.a/b/c` | **PASS** |

## Shadow 复跑：修复前 vs 修复后（claimed 版重生成，审计员 E#1 解除后）

**重要**：本表数据由**修复后**的 `b2a_shadow_probe.js`（claimed associate）重新生成。
此前用旧版 probe 跑的"6 段逐项一致"结论**作废**——那是同一旧算法跑两次，对 FIX-1 零信息量（审计员 E#1 证伪）。

### 6 段差异帧（claimed vs before_r1）

| sid | 差异帧数 | 首次差异 | after_fix 内 age 单帧>+1 帧数 |
|---|---|---|---|
| cap_20261009_121622 | 20 | @87 | **0** |
| cap_20261009_121647 | 0 | — | 0 |
| cap_20261009_121723 | 0 | — | 0 |
| cap_20261009_122616 | 59 | @80 | 0 |
| cap_20261009_122637 | 92 | @24 | 0 |
| cap_20261009_122700 | 0 | — | 0 |

差异帧与 opencode 复算**逐帧一致**；122637/122616/121622 是柜位裂簇高发段，claimed 在此生效；其余 3 段无裂簇触发，no-op（正确）。

### 离散现场：122637 frame24（FIX-1 的真实收益）

```
f22  before_r1: #1(age23, miss0) #2(age15, miss0)
     after_fix:  #1(age23, miss0) #2(age15, miss0)

f23  before_r1: #1(age24, miss0) #2(age16, miss0)
     after_fix:  #1(age24, miss0) #2(age16, miss0)

f24  before_r1: #1(age26, miss0) #2(age17, miss0)          ← 裂簇并入 #1: age 24→26 (+2 通胀)
     after_fix:  #1(age25, miss0) #2(age17, miss0) #3(age1) ← claimed: #1 单++; 裂簇独立成 #3

f25  before_r1: #1(age27, miss0) #2(age18, miss0)
     after_fix:  #1(age26, miss0) #2(age18, miss0) #3(age1, miss1)
```

`真人 #1` 的 age 在 r1 下被裂簇虚增（生命周期污染）；FIX-1 后裂簇独立成 temporarily track，真人 age 单调 +1。这是关联唯一性的可观察收益。

## 新增反例（修复引入/路径覆盖测试）

| 用例 | 覆盖场景 | 结果 |
|---|---|---|
| `顺序扰动` | 输入簇 [A,B] vs [B,A] → track 总数均=2（确定性） | PASS |
| `CE5.c/d` | 旧 gen on_frame 忽略 / 新 gen 正常 | PASS |
| `CE6.b` | notify_session + reset 后 id=1（不再累计 #8/#11） | PASS |
| `CE4` | miss 不增 age | PASS |
| `保留: 1.5m 外簇新建` / `保留: 距离门限` | 原有用例在 claimed 集下语义不变 | PASS |

## FIX-3 验收的诚实分级（重要）

| 用户验收原文 | 本轮实现 | 诚实评级 |
|---|---|---|
| 任意跳转至第 N 帧的 track 状态 = 从起点顺序处理到 N 的结果 | **未实现**（需要每帧全量点云缓存或 1.42M 点快速重放） | **BLOCKED / 设计外** |
| 顺序 +1 播放的 track 演化 | 通过 `tracker_last_idx` frame identity 守卫，+1 才走 incremental associate，连续历史 | **PASS** |
| 同帧重复回调 | `S.tracker_last_idx === S.idx` → 跳过 on_frame 不重复 associate | **PASS** |
| 跳帧（滑块/循环/方向键大步/step 越界/逆序） | reset + 单帧重建；HUD 明示"单帧分类"（不伪装历史） | **PASS（语义诚实）** |
| 异步/rAF 旧回调污染新会话 | `S.session_gen !== session_gen` → return | **PASS** |
| 不得以"reset 后直接处理 N 帧"冒充历史重建 | 我在跳帧走 reset 单帧，但**不自称等于历史**，文档+HUD 明示语义 | **PASS（冒充未发生）** |

> 任意跳帧 = 顺序重建是设计外目标，需独立的 "history cache" 工单。本轮明确限制在 "顺序播放历史正确 + 跳帧语义诚实"。
