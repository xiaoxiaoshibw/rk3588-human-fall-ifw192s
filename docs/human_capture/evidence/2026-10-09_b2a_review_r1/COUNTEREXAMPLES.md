# B2-A-REVIEW 反例清单（7 组确定性反例）

运行：`cd pc_apps/human_replay && node ../../docs/human_capture/evidence/2026-10-09_b2a_review_r1/counterexamples.js`
结果：**7/7 组全部按审计预期确认**（exit 0）。

| # | 反例 | 证明的缺陷 | 关键断言 |
|---|---|---|---|
| CE1 | 同帧两簇(距同 track 各 <1.0m)输入 associate | **同帧多簇绑同一 track**：`age` 同帧两++（1→3 应为 2）、`cx/cy` 被后簇覆写（A 信息丢失） | `tr.age===3`、`tr.cx===2.30` |
| CE2 | 两簇都 age≥3 的 cluster 列表过 shown 判据 | **底层同 track_id 共享**；HUD `_shown_ids` dedup 只掩盖（shown=1 但共享不变） | `cl0.track_id===cl1.track_id`、`shown.length===1` |
| CE3 | 连续 5 帧误检簇（模拟柜子过 RF） | **`miss===0` 不证明真人**：MIN_AGE/miss=0/is_stable 全满足 → HUD 归「人」 | `is_stable(tr)===true` |
| CE4 | 真皮 10 帧连 → 漏 1 帧 → 回帧 | **真人短暂漏检**：漏帧→不进 shown（存在性闪烁）；is_stable 也 false→true 帧间跳 | `miss=1→is_stable=false`、回帧 `true` |
| CE5 | reset() 后立即再 associate | **reset 管不到 on_frame**：reset 后下一帧 on_frame 又把 track 建回（id=1 起） | `tracks=1, id=1` |
| CE6 | session A 累计 id→6，reset→session B 首簇 | **跨会话 reset 有效**（此项确认修复）：新 track id=1 | `id===1` |
| CE7 | 同屏稳定 track A + 间歇 track R(3/6 命中) | **分组拆分**：A is_stable=true、B=false | `is_stable(A)!==is_stable(B)` |

## 反例与用户三条评审问题的映射

| 用户问题 | 反例 | 结论 |
|---|---|---|
| P0 同帧多簇 → age 重复/位置覆写 | CE1/CE2 | **成立，真实跟踪缺陷，未修复**（dedup 仅显示层规避） |
| P1 `miss===0` 作人体稳定性判据 | CE3 | **不成立**：连续误检柜子也拿 miss=0；且对 shown 恒 true → weak 死代码（见 Q3） |
| P1 真人漏帧被误降 + 闪烁 | CE4 | **成立**：存在性闪烁（HUD 消失一帧），is_stable 在帧间跳 |
| reset / 跨会话隔离 | CE5/CE6 | **部分**：reset 自身清 last 有效(CE6)，但管不到 rAF 复活(CE5)，多路径绕过 |

## 关键反例 CE3 的逐帧语义（用户 P1 直译）

```
帧1: associate([柜簇]) → track born, age=1, miss=0
帧2: associate([柜簇]) → 命中同 track, age=2, miss=0
...
帧5: age=5 ≥ MIN_AGE=3 ✓; miss=0 ✓; is_stable()=true ✓
HUD: 归「人」组
```
结论：`is_stable(miss===0)` 在「连续误检」面前**无任何判别力**。它只能表"当前帧 associate 命中"，与"是真人"无关。且由于 shown 内 miss 恒为 0（Q3），`weak` 分支在任何输入下都是死代码——`is_stable` 作为 HUD 分组依据**应当删除或改为真正的判别器**。
