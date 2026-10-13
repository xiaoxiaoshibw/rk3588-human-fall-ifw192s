# HUMAN-UNIFY-R1 回传

## 2026-10-10 Codex 独立审核 R1

- 用户当前指令：审核粘贴的HUMAN-UNIFY-R1交付记录。
- 状态：SUBMITTED / REWORK_REQUIRED；软件FAIL、算法资格BLOCKED、生产资格BLOCKED；设备/物理/部署/采集NOT_RUN。
- 唯一验收表：当前入口未链接此单验收表，原任务书未提供；正式逐原ID验收BLOCKED，本轮R01–R07仅为审查缺陷ID。
- 起始基线：master / 777296d；完整工作树清单及范围SHA见新证据，不修改已有脏树。
- ponytail实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- 复核结果：原73断言/6套测试exit0；单独性能9/9阈值PASS、exit0；19/19生产SHA和45/45结果manifest SHA匹配。
- R01 FAIL：BASE_B与生产B跟踪门限、平滑、寿命及一对一语义不同，直接对拍有反例。
- R02 FAIL：BASE_B去噪后强度/原始索引错位。
- R03 FAIL：已配平输入背景与帧坐标不一致。
- R04 FAIL：会话切换后报告混入旧会话行。
- R05 FAIL：配置寿命30但实际8，U6配置不生效。
- R06 FAIL：懒读取截断点云静默补零。
- R07 FAIL：拒绝候选误命名为家具，家具免疫/漏检归因证据不成立。
- 新证据：[审核报告](../evidence/2026-10-10_human_unify_review_r1/CODEX_REVIEW.md)，含probe脚本、JSON结果、测试与性能日志。
- 当前停止点：审核完成；没有源码修复、CLI派工、commit/push或设备操作。修复及重新生成证据待用户后续明确指令。

## 2026-10-10 Codex返工 R2

- 用户授权：“帮我返工”；后续用户表示将自行重录九类会话，未替代当前软件返工，不记为已采集/已标注。
- 状态：SUBMITTED / 停写；R01–R08功能修复PASS（含两次独审），整体未ACCEPTED。算法/生产资格BLOCKED；性能检查FAIL；设备/物理/部署/采集NOT_RUN。
- 唯一验收表：[HUMAN_UNIFY_R1_ACCEPTANCE.md v1](../HUMAN_UNIFY_R1_ACCEPTANCE.md)；当前SHA另保存在证据acceptance_sha.txt。
- 起始master/777296d，全tracked/untracked清单及8281现存文件约22GiB起始SHA冻结，符号链接不跟随；大量既有脏树保留。无commit/push/reset/checkout/clean。
- ponytail实际路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。
- R01 PASS：生产B聚类/关联直接复用，原A/B1196帧同输入对拍；近邻双簇/.9m回归。
- R02 PASS：XYZ/intensity/raw索引同点，A过滤及保留来源可追溯。
- R03 PASS：统一背景/帧坐标，显式变换及identity/ref有效，冲突拒绝。
- R04 PASS：会话报告与状态清空、代际拒绝、重复/回退/跳帧实际断言。
- R05 PASS：实例PIPE/RF/globalThis隔离，配置实际生效，未知/未实现配置拒绝。
- R06 PASS：合法eager/lazy一致，元数据/尺寸/连续边界/short-read/partial-read/close回归；SHA来自实际读取字节。
- R07 PASS：accepted/rejected不是家具GT，current/ever不是人数，不报无GT的识别精度。
- R08 PASS（软件机制）：retained去重、来源、过期、不自续命；真实收益BLOCKED。
- S01 PASS：96项/7suite exit0；最终runs_03 45JSON+45CSV、5980帧次，当前输入/实现/输出完整SHA核对，A=U1；parity_04 9会话1196帧PASS。
- S02 BLOCKED：范围外rf_person.js多次变化，未由本轮写入，不回退、不洗成全树无改动PASS；当前core提交SHA保持。
- Q01 PASS：OpenCode CLI `opencode-go/deepseek-v4.1-flash`/plan/default DB，两次probe及两次实际审计exit0；R01–R08与后加四处来源守卫独审无软件FAIL。
- 性能附加检查FAIL：当前依赖perf_02 dynamic U3 P95=71.49ms，perf_03 dynamic BASE_B P95=53.33ms，均8/9、exit1；保留原失败，不调阈值刷通过。
- 最终代码及证据：core16文件SHA见submitted_source_sha_02；具体修复、范围外变化、旧/新证据分界、机器/命令/限制见[收口](../evidence/2026-10-10_human_unify_rework_r2/CLOSEOUT.md)。
- 当前停止点：功能返工完成并停写；待稳定RF工单归属/性能定位/用户新数据与独立GT，未自动接浏览器/EXE/板端或下一阶段。
