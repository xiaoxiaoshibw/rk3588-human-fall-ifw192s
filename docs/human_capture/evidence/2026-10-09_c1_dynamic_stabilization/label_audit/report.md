# C1.3 标签与训练数据审计

## A. probe↔生产锚点

全部一致: **是**

- ✓ `find_hot (z带/bg差分支干) — 数值指纹一致`
- ✓ `find_clusters (漫水/min30/top4) — 数值指纹一致`
- ✓ `associate (claimed/gate/TTL/MIN_AGE) — 数值指纹一致`
- ✓ `const TRACK_GATE_M`
- ✓ `const TRACK_TTL_FRAMES`
- ✓ `const TRACK_MIN_AGE`
- ✓ `const BG_CELL`
- ✓ `z_band 0.1-2.3 常量在两侧调用处一致`
- ✓ `bg envelope boost +0.25 m`
- ✓ `cluster min 30 pts`
- ✓ `top-4 clusters`
- ✓ `FIX-1 claimed 单帧一对一 (两侧)`
- ✓ `线上阈值 0.55 / 探针档 [0.55,0.65,0.80]`

## C. ai_labels 语义分级

| sid | labelled_by | posture | person帧 | xy跨度m | 语义 |
|---|---|---|---|---|---|
| cap_20261009_122637 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 116 | 0.037 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_122616 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 139 | 0.046 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_122700 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 111 | 0.03 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_121647 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 218 | 0.06 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_121622 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 107 | 0.035 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_121723 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 223 | 0.056 | STATIC_HUMAN_STAND_POSE (站立真人; 帧级 auto 标签, 无人工逐帧确认) |
| cap_20261009_114641 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 177 | 0.043 | UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认) |
| cap_20261009_114709 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 172 | 0.044 | UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认) |
| cap_20261009_114734 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 99 | 0.032 | UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认) |
| cap_20261009_114754 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 123 | 0.049 | UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认) |
| cap_20261009_114817 | auto_person_label.py+empty-template-bgdiff | ['stand'] | 131 | 0.031 | UNKNOWN_HAT_STAND (人戴帽站立; 无人工标注, 动态性未确认) |

结论: 六段主要会话的 person 帧标签全部是 AI 自动判读 (confidence=auto), 无人工逐帧确认; 仅能在「站立真人」粒度作真值, 「动态/静态」为 STATIC_HUMAN_STAND_POSE; 帽子 5 段语义 UNKNOWN。
