# R05 当前只读同帧 Demo

启动：仓库根目录 `python -B -W error sidequests/human_fusion_lab_next/d05/r05/demo/demo_server.py --port 8916`，访问 http://127.0.0.1:8916/ 。只读取完整保存的顺序推理，不在seek续票或重跑。

三个同步视图：原始点云与来源分离人工参照、D04 frozen候选/终端结果（同口径R02base提供诊断stages）、当前R05。版本可切换fresh control与anchor，control实际2605帧与R04精确等价，不冒充新收益。新收益索引来自R05完整对照；control导航由精确parity派生，明确标签。

九会话、播放暂停、步进、拖动、重置和场景/失败/收益快捷跳转；同帧时间、候选/分数/确认、实际删除/净BG恢复、H4相对control final集合新增与移除点、pre-fusion PA内部轨迹与成员来源、真实银行更新和锚点均可核查。FG证明只表示独立输入与原模型资格，不表示真人。coasting只保留最后观测位置，无运动外推；S9 INVALID_BINDING、未审核UNKNOWN。

输入/GT/冻结及当前ledger/实际加载源/tooling SHA与响应crypto SHA均核查。纯性能不含浏览器读取/SHA/渲染。原R04 Demo8915及失败历史保留。本文件不证明浏览器已通过，实际操作/截图另在R05 evidence。银行原raw重入标签存在秒TTL边界，派生BANK_EVENT_CASES_v2同时按帧/秒门补证。
