# HUMAN-UNIFY-R1 返工唯一验收表 v1

生效：2026-10-10，用户明确指令“帮我返工”。本表只覆盖Codex审核R01–R07及其直接相关的索引/保留/跳帧缺陷；不反向追认历史交付。Codex唯一writer，范围为`pc_apps/human_core/`和本工单新文档/证据；既有human_replay实现、数据、旧证据只读。禁止自动提交、push、部署、采集、驱动/网络改动、模型切换或ML激活。

| ID | 软件验收要求 |
|---|---|
| R01 | BASE_B复用原B聚类/关联，逐帧候选索引、坐标、RF概率、track ID/寿命/确认与原B全链对拍；.9m关联及同帧近邻两簇有反例回归；实例隔离 |
| R02 | 每个候选携带正确原帧索引，强度与XYZ同点；过滤前置无效点回归 |
| R03 | 建背景与tick共用raw/leveled及R/T契约，显式参数有效，冲突拒绝；CLI identity/ref有效；BASE_A与生产pipeline同输入对拍 |
| R04 | 换会话/同sid循环清输出及状态，过时session/代际拒绝，重复帧和跳帧策略有实际断言 |
| R05 | 实例跟踪参数实际生效且不污染其他实例/生产模块；未实现/非法配置拒绝 |
| R06 | eager/lazy统一元数据、文件尺寸、帧连续范围验证；short read拒绝并关闭句柄；合法数据解码一致 |
| R07 | accepted/rejected候选统计不称家具GT；输出当前确认与曾确认分开；报告不从无GT推断家具免疫/真人漏检精度 |
| R08 | U2/U3保留点不重复、FG/retained/merged来源和raw索引可追溯；过期退出，不用仅保留点自刷新寿命；合成机制验证不等于算法提升 |
| S01 | 既有core及相关生产JS回归通过；新9会话×5模式结果manifest与输入/实现/模型SHA完整，新路径不覆盖 |
| S02 | 全tracked/untracked起始清单及SHA冻结，结束核对变化范围，旧证据/原输入/生产核心不改 |
| Q01 | 指定OpenCode CLI opencode-go/deepseek-v4.1-flash只读独审，实际结果保存；如服务不可用如实BLOCKED，不冒称独审 |
| D01 | 设备/物理/部署/采集NOT_RUN，不以本机软件结果替代 |

逐ID报告PASS/FAIL/NOT_RUN/BLOCKED；作者自验仅SUBMITTED，不自行宣称总体ACCEPTED。性能保留真实机器/命令/日志及内存口径，负载失败保留，不删断言迎合结果。
