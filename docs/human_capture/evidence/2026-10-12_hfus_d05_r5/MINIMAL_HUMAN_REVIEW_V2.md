# HFUS-D05-R05 最小人工资格复核包

所有原GT只读。此包是需要复核的具体位置，不创建资格，不要求重新排查全链。Demo http://127.0.0.1:8917/ 支持会话/帧/投影、control与anchor；原始人工来源和未标区域UNKNOWN单列。

| 片段 | 已有工程证据与最小复核需求 | 阻止的结论 |
|---|---|---|
| 175553 f0–10 / f65–75 | CAUSAL_WINDOWS双方完整连续窗口；f4 FG proof中心与EMA差.505m，f5混入家具点减少。复核未审核区域家具、连续人物ID与出入 | 不能把legacy未知未匹配数当正式家具FP，不能认定无ID switch |
| 175429 f210–227 | 原人工PERSON严格比较已证明220–224全部回退；f217–219独立FG覆盖仅.143/.126/.098。无需新增GT即可裁定H4失败 | 人工新输入不阻止当前失败裁定；需要连续ID才可作身份结论 |
| 175227 f0–50及完整304帧 | f40纯FG候选176点，p=.9602，propagated家具纯度1；human家具仅5对象、propagated1515对象，缺独立审核负例分组。核查此对象、背景家具与有限延续/退出 | 模型泛化/晋级BLOCKED，工程错误接受诊断继续成立 |
| 175943 f157–167 / 175804 f233–238 | 转身与走停走现有失败/恢复阶段已在全FAILURE_LEDGER；f238已有高分候选，旧base混簇严格失败，当前control改善。复核连续人ID与同人转身标识 | 不以检测或输出track_id稳定推定真人身份无切换 |
| 180235 f105–115及全部已标帧 | 遮挡剩余严格失败，保留BG/cleanup人体点、分量及候选诊断 | 未标遮挡区域与完整出入仍UNKNOWN |
| 180557 全静止片段 | 53已有PERSON参照中51严格成功双方一致；核查未标连续时段与真实退出 | 全时段无漏检/ghost不可宣称 |
| 180751 S9 | 现有绑定INVALID_BINDING，原草稿不能代替人工审核；需人工确认帧索引、时间、raw成员及双人绑定后再独立生成新资格 | 正式S9精度/ID switch一直BLOCKED |

机器完整索引：analysis_v2/CASE_INDEX.json、FRAME_COMPARISON.jsonl、FAILURE_LEDGER.jsonl；成功与回退WIN_LOSS_INDEX.json。formal HUMAN PERSON与FURNITURE human/propagated/auto分开，无GT帧UNKNOWN，不累计FN不代表检测成功。未知区域不可因高分/绿色直接改成人体。

修正原包175804窗口越界：该会话239帧最大238，当前f233–238；原包保留，不修改GT、结果或机器CASE_INDEX。
