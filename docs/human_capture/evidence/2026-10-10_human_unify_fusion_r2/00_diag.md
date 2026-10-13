# R2 执行前集中诊断

Codex唯一writer；ponytail读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。另使用 scikit-learn skill；只用已有NumPy/sklearn与标准库。

原工单从未落盘，用户已确认以R1 FINAL_REPORT §3 + 交接 §4 + 母验收表等效；本轮唯一表在 `../../HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md`，不重写历史。

| 组合/ID | 实查问题与处理 |
|---|---|
| manifest V1/e2e→V2正常 | 按最后非e2e版本读取；验证字节SHA，不写GT |
| 冻结文件SHA正确/会话绑定错误 | S9 V2 points=64个a且缺meta；拒绝可信指标及训练，只跑诊断 |
| reviewed/gt_level旧UNKNOWN | 8会话实际所有对象reviewed；按结构及人工确认资格校验，记录陈旧字段，不改文件 |
| dense/sparse标帧 | 实际832已标帧/2605总帧；未标帧UNKNOWN，不插值，不计无人 |
| PERSON同帧重复/非法索引 | 校验同帧track唯一、压缩解码数量与原帧compact范围 |
| S1重复静态对象 | 真实GT有原框+static_fill重复；训练按同帧同点集去重，报告原数及去重数 |
| S1家具训练/空场评估 | 用户新授权覆盖旧“S1只能val/test”规则；S1评估属于训练集拟合，缺独立家具泛化证据阻断推广 |
| 会话划分/同演员未知 | 会话级划分在训练前落盘；无演员/新场景信息，不宣称跨人跨景 |
| 全帧运行/抽帧指标 | engine.tick顺序跑全部帧维持真实跟踪；只在可信已标帧匹配；S9 f1缺P2不当负例 |
| A/B/U3/FUSION | 新离线脚本直接消费diag._candidates/_tracks，不改engine/生产；相同帧同模型同R/T；记录差异，不要求异算法逐候选相等 |
| RF v2加载 | 离线engine实例rf.init加载独立候选；原v1与生产51维契约保持SHA |
| track/episode/断点 | 一对一匹配；confirmed且lost=0才计当前track；未标帧不连接身份，不用ever当人数；GT.find_breaks分别标注采样gap与已知f1缺标 |

默认划分：train S1/S3-near/S4/S5；val S3-far；test S7/S8；stress S6；S9 BLOCKED。阈值固定0.55，无test调参。候选负例不足，不能出MODEL_PROMOTION_READY=PASS。

F3导出优先消费冻结对象compact点集（原有硬负导出只支持旧sessions/frames/rois格式并采用圆裁剪，直接套新GT会KeyError且圆可能包含别类）；F3新入口保留精确点集及来源。F4匹配默认XY中心距≤0.75m，全局最大匹配数后最小距离，边界一对一；额外输出0.5/1.0m敏感性，尺度不是新性能门槛。
