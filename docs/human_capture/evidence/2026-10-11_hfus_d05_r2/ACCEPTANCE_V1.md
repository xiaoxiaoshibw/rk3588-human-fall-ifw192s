# HFUS-D05-R02 唯一验收 v1（实验前冻结，2026-10-11 Asia/Shanghai）

用户当前直接授权 D05 收口与离线返工。Codex 唯一 writer；两代理及指定 OpenCode 只读。不是 D05a/D05b，不启动 D06/D07。ponytail 实际读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。

代码只新增 `sidequests/human_fusion_lab_next/d05/r02/`；新证据只写本目录；README 当前入口和 D05 return 追加登记。历史代码、模型、GT、captures、证据不修改。禁止部署、采集、生产修改、ML 激活与 Git 写操作。

| ID | 冻结验收要求 |
|---|---|
| R02-01 | 起始 branch/HEAD/status，tracked/untracked/ignored SHA；结束变化与读取错误单列，不称原子冻结 |
| R02-02 | D05 六套九会话 ledger/SUMMARY/REGRESSION 与当前输入/源码 SHA 核对；缺件和旧语义缺陷保留 |
| R02-03 | 九会话完整顺序诊断 base 与 A06；每帧 raw/valid/BG/cleanup/retention/组件/候选/分类/跟踪账；已标失败对象逐点归因；未标 UNKNOWN |
| R02-04 | A06 参数不变；分别报告净恢复、新增 accepted 点、人工支持的正确检出；BG净恢复不称真人 |
| R02-05 | GT-free 单因素提案分离；成员 key 互斥、守恒；不放宽原质量/分类门、不读 GT 或未来帧；有可运行反例检查 |
| R02-06 | frozen D04、同新口径 base/A06/返工九会话完整实跑；strict/legacy逐场景与来源分账；far 与走停走 strict TP有收益且其它正式会话无 TP下降；家具 human负例与propagated诊断不得净新增错误接受，资格不足则 BLOCKED |
| R02-07 | 跟踪 observed/coast、首次确认、最长合格FN、重新捕获、ID变化/重复/退出残留；seek/倒放/重复/gap/reset/跨会话契约实查；预测不计实际检出 |
| R02-08 | 三同步视图 raw+参照/D04 frozen/current；九会话/播放暂停/步进/拖动/重置/快捷片段；真实删除、净恢复、成员、最终输出与原因；SHA校验及真浏览器截图 |
| R02-09 | 无评测竞争时统一预热5帧、相同计时范围串行对拍；纯算法与instrumentation/读/render分开；p95 <50ms沿用原门，不宣称板端实时 |
| R02-10 | 指定 OpenCode CLI opencode-go/deepseek-v4.1-flash 独立只读审查，进程/exit/实际模型/完整指令与缺陷处理留证 |
| R02-11 | 新源码SHA、逐帧与逐场景账、成功/失败索引、最小人工复核包、追加return；工程/算法/GT/生产独立裁定；不自行ACCEPTED |

## 本轮单因素假设 H1（跑前登记）

A06 保持 r=.6、link=.3、min_ref=1、min_local=1。主要因素仅改变 PA 提案划分：当前前景 XY voxel 中 z>=1.3m 且该高度点数>=10 的密集核心；原0.15m四邻连通；核心>=3 cell、>=60高层点，至少两核且中心间距>=.45m才触发。每个完整 XY cell 归最近核心（最小格距离），最大扩展 .30m；剩余 cell 按原四邻组件保留。全点守恒、互斥，继续原聚类/分类/跟踪门；不通过 z 删除人体下半身。超过 .30m 的外围不混入核心。若无收益/回退则停止扩大此方向，不事后改阈值。

证据依据：far剩余76个混簇/碎裂失败；f12有密集人体与家具通过薄桥连接；f80高层确有两核；walkstop f75高层两个主体。f5/f40普通高层连通方案不能分离，因此不承诺全片段修复。对照以同口径实跑为准，旧评分账保留。

GT frozen严格门仍coverage>=.5/purity>=.8，legacy距离.75；S9始终INVALID_BINDING；human、propagated、auto、PERSON/FURNITURE/UNKNOWN分列；当前strict FP零不构成家具安全证据（negative_reviewed缺失/导出遗漏）。性能与晋级标准不降低。新诊断账采用相同 strict_v2，并另列精确来源审计，不修旧账。
