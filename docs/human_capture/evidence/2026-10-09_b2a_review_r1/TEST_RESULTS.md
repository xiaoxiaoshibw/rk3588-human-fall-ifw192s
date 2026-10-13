# B2-A-REVIEW 测试结果汇总

## 1. 反例套件（本轮新建）
`counterexamples.js`：7/7 组 PASS（exit 0）。详见 `COUNTEREXAMPLES.md`。

```
PASS: CE1.a 建 track / CE1.b 同帧两簇 age 两次++ / CE1.c cx 被后簇覆写 / CE1.d 同 track_id
PASS: CE2.a 两簇同 track_id / CE2.b dedup 掩盖底层共享
PASS: CE3.a 5帧误检 MIN_AGE ✓ / CE3.b miss=0 ✓ / CE3.c is_stable→人 组
PASS: CE4.a 真皮稳定 / CE4.b 漏1帧→低稳定 / CE4.c 回帧→回人(闪烁)
PASS: CE5.a reset 清 last / CE5.b reset 后 on_frame 复活 / CE5.c 新 id 从 1
PASS: CE6.a 切前 id 到 6 / CE6.b 切后 id=1
PASS: CE7.a 稳定 A=true / CE7.b 间歇 B=false / CE7.c 同屏拆开
```

## 2. 既有 detect_overlay.test.js（23 用例，本次HUD会话所写）
`node detect_overlay.test.js`：**23/23 PASS（ALL PASS）**。
- reset×4 + is_stable×6 + 原 associate/find_clusters/grid_key/level_frame×13。
- **审计警示**：其中 is_stable 用例只验证 `miss===0↔is_stable` 的布尔映射，**未断言 weak 分支可达**——这正是 Q3 死代码被测试掩盖的原因。测试通过 ≠ 语义正确。

## 3. Shadow 复跑（参数不变性回归）
`b2a_shadow_probe` 复跑 122637/121622 两段：
- 122637：top1 p50=0.98，rank1 prob=0.76 n=108，track ids=[1,2]，三档 confirmed=114/116 → 与 r1 **完全一致**。
- 121622：top1 0.95 恒定，rank1 prob=0.87 n=23，track ids=[1,2,3]，漂移 #2→#3(9f,0.14m)，柜位成簇 22% run中位1f → 与 r1 **完全一致**。
- 结论：本次 HUD 会话**未改变 RF/聚类/关联数值行为**，仅动了显示/reset 层。

## 4. grid_key 碰撞核实脚本（node，量程分析）
- 碰撞需 `gy≥4095` 即 `y≥204.75m`；IFW192S 量程 ≤30m → **物理不可达**。
- 负 y 侧量程内各 gx/gy 组合 key 互不碰撞（实测 gx=1,gy=-1→4094 等）。
- 唯一实伤：漫水邻域反解对负 key 错误（`floor(cur/4096),cur%4096` 负数），影响负 y 区聚类邻域完整性。**PARTIAL，非阻塞。**

## 5. 结论对照（测试 PASS 与语义正误分离）
| 项 | 测试 PASS | 语义正确 |
|---|---|---|
| reset 清 last/t_id/frame_no | ✓ | 部分（管不到 rAF） |
| is_stable 布尔映射 | ✓ | ✗（对 shown 恒 true，死代码） |
| 同帧多簇 dedup | ✓(shown=1) | ✗(底层 track 共享未修) |
| Shadow 数值不变 | ✓ | ✓ |

> 报告纪律：测试 PASS 仅证明"按断言运行无误"，不代表语义正确。Q3 死代码与 Q1 关联缺陷在测试全套 PASS 下依然成立——这正是本轮要求独立审计的原因。
