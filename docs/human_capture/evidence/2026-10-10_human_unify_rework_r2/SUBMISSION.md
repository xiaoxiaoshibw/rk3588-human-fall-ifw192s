# HUMAN-UNIFY-R1 R2 软件返工提交

日期2026-10-10；Codex唯一writer；用户“帮我返工”及新录制计划。作者状态SUBMITTED，待指定只读独审；不自行宣布ACCEPTED。

当前验收：[唯一表v1](../../HUMAN_UNIFY_R1_ACCEPTANCE.md)。实际ponytail路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。

## 作者自验

| ID | 结果 | 证据/说明 |
|---|---|---|
| R01 | PASS | parity_02.json：9会话1196帧原A pipeline与原B完整on_frame对拍；近邻两簇/.9m/实例隔离test_rework |
| R02 | PASS | 强度与raw索引回归；对拍XYZ/intensity/RF；A保留raw索引 |
| R03 | PASS | 背景/tick相同坐标契约；leveled/raw/显式变换/冲突/CLI测试 |
| R04 | PASS | replay_contract现11实际行为检查，清报告、过时代际、跳帧重置 |
| R05 | PASS | 实例PIPE参数实际生效，U6寿命30；未知/未实现/非法配置拒绝 |
| R06 | PASS | eager/lazy尺寸/元数据/范围一致；截断、partial read、异常close回归 |
| R07 | PASS | 输出v2使用accepted/rejected及current/ever；AB_RESULTS仅软件统计，不报家具免疫或真人精度 |
| R08 | PASS | 合成FG/retained/merged来源与去重、过期、独立FG确认建bank；真实算法收益BLOCKED |
| S01 | PASS | tests_01七suite/94断言exit0；production_js_01六suite全部exit0；新runs_01共45JSON+45CSV，5980帧次，全SHA匹配matrix_summary |
| S02 | 待结束复核 | 全8281文件约22GiB起始SHA已保存，symlink不跟随；结束检查另生成 |
| Q01 | 待独审 | 指定模型plan模式probe_01真实PROBE_OK/exit0；独审另存日志 |
| D01 | NOT_RUN | 没有设备/物理/采集/部署操作 |

## 修复与语义边界

B直接复用生产已公开聚类和关联函数，而不是手写一个不同的跟踪器；闭包工厂将PIPE、RF trees、B tracks按实例隔离。A背景先denoise再build与原消费者一致。配置统一验证，坐标契约贯穿背景和帧；接口v2要求session_generation，旧消费者需同步更新。本轮未接浏览器/EXE/板端。

候选按raw索引映射，保留来源可追溯，不再用“拒绝=家具”；统计当前确认和曾确认分别报告。U2在当前帧前景不足时补bank周边当前有效点，不能凭空推断人还存在；不靠retained确认无限续命。U3空场误报风险仍属于算法待验证边界，未借软件修复宣称解决。

旧unify evidence/原审计保留。parity_01失败为审核测试错误要求HUD文本按track创建顺序，而原HUD按当帧簇顺序；parity_02改为比较确认ID集合，并额外核对候选ID、中心、点数绑定，没有删除算法对拍门。首轮测试修复过程中出现Float32坐标网格键与JS double造样的差异，已按实际Float32样本建测试背景。

历史所谓家具203帧、家具免疫、动态真人死于分类器及性能固定值等不作为当前结论。当前报告以AB_RESULTS和本轮日志为准；新录制安排见NEW_CAPTURE_NOTES，仍需独立人工GT/审核/场景留出，算法资格和生产资格BLOCKED。
