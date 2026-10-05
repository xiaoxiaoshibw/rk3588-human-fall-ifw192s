# 外部GL-I06 skeleton复核 / 2026-10-04

输入：evidence/2026-10-04_gl_i06_r1_skeleton/。完整读取七份Markdown；00_diag/00_SCOPE/README与planning三文件的六个登记SHA全部吻合99_STOP_WRITE。没有.py、实验台账、GT结果、成本数据或本轮独审记录。它自述只规划、NOT_RUN，与实际目录一致；不将文档中的下一步建议当本轮执行授权。

## 对主线的裁定

- 保留为规划参考，不替代2026-10-04_gl_i06_r1实际提交、全W/GT实验和指定独审，也不把已有PASS回退成PLANNED。
- R0拒绝账本、K1/K2/K3、三域oracle、seed/置换/成本等已完成，不为骨架重做。
- irls_huber/full_fit_refine仅为预留名字，不是收益或条件门已触发的证据。本阶段仍优先GL-E02有效source/up/原点/独立地面源行；不自动转算法R2。
- 能借鉴的是按事件记录、reason汇总只派生、variant参数/精炼域版本化、预算与不收敛分开。与既有契约不一致的部分需先纠正，不能原样实施。

## 具体设计问题

1. **BEST_ONLY语义偏差。** oracle_design把它写成最高支持见证集合。现行GL-I05/GL-I06诊断比较的是NEAR池中至少一端为最高支持见证的所有对，最高ties全保留。最小反例：A角0°/support500，B角13°/support450；NEAR含A/B，top仅A。草案只看top-top没有可比较对，会给出holds=true；现行BEST_ONLY须比较A/B并给holds=false。它仍不能用于放行。
2. **只看标量不能独立重算数据指标。** 从n/d/support可以独立核关系；重算真实支持、RMS/P95/覆盖，还需带SHA的源点与源行。实现给出的RMS等标量只能做一致性检查，不是独立数据验证。应把关系oracle与数据/GT审计分开。
3. **把不收敛当普通reject有吞W风险。** 正常K完成但仍变化、后轮越界/振荡，必须保留最后有效见证和质量未决；不能仅在refine_reject记一条后从W删seed，再让剩余W闭合。资格拒绝、质量未决、资源未处理是不同事件。
4. **六个reject桶不是完整生命周期。** 合格→精炼→保留/精确合并/存储不足、trace不足以及最后决策均需关联。实际见证竞争是多个见证的关系，不能硬塞成单个假设的“首次拒绝”；已经精炼但没存下也不同于根本未执行TLS。
5. **frozen_baseline与complete K1不能承诺同整体行为。** 冻结生产fitter先保留有限代表再TLS；完整W路线对全部合格假设TLS。单次TLS公式相同，不意味着完整搜索W/行为相同。K1也不应无依据加入K2/K3的收敛放行要求而仍称冻结基线。
6. **精确去重后比较域必须明示。** full W多重集与unique存储的pair计数/索引本来会不同。可检查关系性质不变，或恢复多重性后按full W对拍，不能要求unique域直接与full W逐项全等。
7. **schema是样例，不是可执行draft-07约束。** rejection_ledger_schema的JSON是实例草图，没有type/properties/required等完整校验语义。不能直接当作已可验证的JSON Schema；“有界猴子精炼”“IRES”等不准确文字也应在未来新编号版本清理。

这些是外部未实施草案的设计缺口，不是已获审GL-I06实现新FAIL。当前不修改外部目录，不启动实验/CLI/生产阶段。

## 纳入下一阶段提示的方式

GL-E02只借鉴元数据身份、事件与证据来源清晰分层；执行现有GLE02_ACCEPTANCE v1。场景照片真实、视向已确认的证据予以保留；点云源轴、原点高度和照片/录制/源行绑定各自补齐。用户新照片不能直接填旧录制up，外部骨架也不能成为继续RANSAC/IRLS扫参的理由。

EXECUTION_PROMPT_02.md是新增补充版本，保留01原样；没有启动GL-E02代码。
