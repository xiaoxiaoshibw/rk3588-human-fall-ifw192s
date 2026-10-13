# CASEBOOK — 典型成功/失败案例（HFUS-RD-01 交付 7）

回放入口：`python sidequests/HFUS-RD-01/demo/demo_server.py`，然后打开
`http://127.0.0.1:8930/`。左右面板可分别挂 mainline 与 D2 任意变体；
跳转某案例 = 选择对应会话然后把帧 slider 拖到 `frame` 值。

## 成功案例（变体真实改善）

### SC-1  C4_DUAL_SRC 对 S5-turn 的救回
- **会话/帧**：S5-turn (`cap_20261010_175943`)，全部 202 帧
- **现象**：mainline BG 把人点大幅删（BG 只剩 31.1%，UNKNOWN-reason 占
  65.9%）→ 人在提案层几乎消失，全会话只有 6 个 reviewed GT 对象（每帧
  ~1/33 帧有 GT）；C4（valid 全点上欧氏 r=0.35 min=15）可恢复 GT 触及
  到 cov_mean≈0.99（D2 实测）。
- **回放**：会话 S5-turn，左 mainline（橙） vs 右 C4（青）。
  可看到 mainline 下人点残缺、CONFIRMED 缺席；C4 下人形完整。
- **证据**：`D2_CLUSTER_ABLATION.json → cap_20261010_175943`；
  `D1_LAYER_SUMMARY.json` S5 行。

### SC-2  C4 对 S7-far5m 的补点
- **会话/帧**：S7-far5m (`cap_20261010_180337`)，251 帧；GT 12 对象。
- **现象**：远处点稀，mainline BG 保 83.7%；C4 在 valid 上保持 100%，
  GT-hit50 与 hit10 满。
- **回放**：S7-far5m，左 mainline vs 右 C4。
- **证据**：`D2_CLUSTER_ABLATION.json → cap_20261010_180337`。

### SC-3  RF 在已命候选上无独立误拒（Oracle 证实）
- **会话/帧**：全部 reviewed 帧
- **现象**：507/510 在提案上活，其中 0 个因 RF prob<0.55 被独拒 →
  **主链接受的候选对已存活的人**没有进一步损失。
- **证据**：`D1_LAYER_SUMMARY.json` 每会话 `oracle_reject_rf_low=0`。

## 失败案例（如实保留）

### FC-1  S1 家具场景全候选 58% 被接受（高分家具混诈）
- **会话/帧**：S1-empty-with-furniture (`cap_20261010_175227`)，304 帧
- **现象**：644 个 mainline 候选，375 个（58.2%）RF prob≥0.55 被接受；
  这一会话内 GT=0（家具），全部是误报。prob 分布 p50=0.87/p90=0.89/
  p99=0.90 → RF51 对家具完全没分。
- **回放**：S1，左 mainline（橙+绿）——可看到房间内茶几/椅子/衣柜轮
  流变绿；右边同时挂 C1（青）可对照它们的几何结构并不比人"不像"。
- **证据**：`D1_LAYER_SUMMARY.json` S1 行 + `candidates_stage2.jsonl`
  prob。
- **深层原因**：RF51 是"像人"评分（特征以直立度、高度带、宽度等为主），
  家具在这套特征族里常常同样"像人"；不解决负例判别，任何下游调度
  都没救。

### FC-2  S6-occlusion 遮挡下 track 延迟 19 帧才 confirm
- **会话/帧**：S6-occlusion (`cap_20261010_180235`)，238 帧
- **现象**：GT track 首个 confirmed 帧从 GT 标签帧起延迟 19 帧；
  flicker 156 次/238 帧。遮挡让人候选断续，3 票窗在多数帧无法完成。
- **证据**：`D1_TRACK_EVENTS.json → cap_20261010_180235`。

### FC-3  S4-walkstop 停顿间提案丢失 229 帧
- **会话/帧**：S4-walk-stop (`cap_20261010_175804`)，239 帧
- **现象**：GT 只在 11/239 帧登记；其余 229 帧人"停顿"时无 GT 但有
  mainline 高 prob 候选——无法判定是提案在，还是 GT 疏。本轮把此
  会话作为 **UNKNOWN 优先核查对象**，不进 GT 对齐分类。
- **证据**：`D1_LAYER_SUMMARY.json` 175804 行（gt_obj_total=11）。

### FC-4  C5_CONS_BG 更保守背景造成 GT 覆盖腰斩
- **会话/帧**：全部 reviewed 会话
- **现象**：把 readmitted_ids 保留点扣掉（更保守 BG）后，GT 覆盖从
  C0 的 0.776 下降到 0.434（175429）/ ~0.41（多会话平均）——XG 支撑
  点实质是人体的合法点，把它们当噪声砍掉会显著伤人。
- **证据**：`D2_CLUSTER_ABLATION.json` 各会话 `C5_CONS_BG` 列。
- **结论**：**不能把 UNKNOWN 支撑论据当噪声**；D05 R04 fast 把这
  些点 readmit 是正确的。

### FC-5  高 prob 高分无 GT 的 UNK 候选（175429 F0/F10/F11/F14）
- **会话/帧**：S3-near f0/f10/f11/f14 等
- **现象**：mainline 高 prob (>0.90) 但账本 ledger 里无 GT 交集；这些
  帧 GT 人已在另一候选里，高 prob 候选是"人影/家具"重叠。本轮不修
  复，仅作为人工标注清单（D_AUDIT §5）来源。
- **回放**：175429 f10，左边看 a_10_3 (n=60, prob=0.910) 与 GT 红
  点分离。

## 案例跳转清单（复制到演示器）

| 名称 | sid | 建议帧 |
|---|---|---:|
| C4 救转身 | S5-turn | 50, 100, 150 |
| C4 救 5m 远 | S7-far5m | 80, 150, 200 |
| 家具误检 | S1-furniture | 0, 30, 100, 200 |
| 跟踪延迟 | S6-occlusion | 0..19, 100 |
| 停顿丢失 | S4-walkstop | 50..150（225 帧 GT 空窗中） |
