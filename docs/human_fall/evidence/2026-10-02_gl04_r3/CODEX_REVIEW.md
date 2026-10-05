# Codex GL04 R3 独立复审 / 2026-10-02

GL04 v1不变，结论REWORK。指定Go Flash/default DB session ses_f02dccc50ffetKiDi7ATzgxOLv，23:15真实exit0并停止写入；提交四preview SHA见12_scope_sha，独立检查使用这些当前源。90_codex_runtime：旧29反例独立全部通过，补C01/C05/C07两mode后30 PASS/4 FAIL；91_codex_lib 42 passed exit0。数量仅检查记录。

| ID | 结果 | 依据 |
|---|---|---|
| V01 | PASS | 保留R2合法source/ground、原样本原RT、不在browser生成几何、缺输入回退；29旧反例通过 |
| V02 | PASS | explicit3D nullZ拒绝，已知Z保留；预算/源indices/LineLoop与两mode支持原义保留 |
| V03 | PASS | units非m拒绝、动态hfPosLabel及候选当前mode读数、schema分列源码＋独立29；实际browser新截图留下一轮完整验证 |
| V04 | NOT_RUN | 原runtime DPR/resize与R2实际rotate/zoom/resize仍适用；实际DPR未改变，不冒称已跑 |
| V05 | PASS | 原token/oldID/mutation/foreign-frame拒绝、fresh合法/unselected首次选择通过；V09另记legacy退化 |
| V06 | FAIL | R2 cal交错/schema2/GPU expiry已闭合；单侧snapshot GDID=null/state=g1仍upright，nullable binding只比both非空 |
| V07 | FAIL | no/empty/ground字段缺失已闭合；source/ground旧字段仍存在而snapshot只剩other时仍upright/旧位置；hfTargetGeometryPresent是presence、未验证对应目标 |
| V08 | PASS | 独立真实publisher state.performance.queue_dropped=3显示；renderer计数/未知值保持；新六图与同屏指标仍需最终browser复核 |
| V09 | FAIL | 原42断言保留，core/正式无本轮写入；但合法无cal/ground的source-only unselected首次选择被observationQualified拒绝，违反C01原模式保留 |
| V10 | BLOCKED | 生产R/t/support缺口保持，不改core |
| D01 | NOT_RUN | 未设备/物理操作 |

C01 FAIL（legacy原始首选）；C02/C03/C04 PASS（到齐/相同/配对标定）；C05 FAIL（nullable GDID）；C06 PASS（显式错误schema/frame）；C07 FAIL（other＋旧source/ground目标字段）；C08仅unselected正常带cal首次选择PASS，legacy/对应详情未闭合；C09/C10/C11 PASS原已列runtime，最终browser复核未跑；C12 NOT_RUN真实DPR；C13/C14/C15 PASS单位/3D支持/性能；R3未把纯检查冒充新browser结果。

责任与连续族见R4 PLAN_REVIEW：R3工单明确要当前对应详情，实现只测非空；CodexR2原反例只清ground字段，source及旧字段仍存在的组合漏测，现已补同要求。R4必须唯一匹配已发布标识/几何字段，不nearest/first/浏览器跟踪；选择context与已有目标观测分别守门，both-null合法legacy不应死锁首选。无新需求，不改v1、不换模型。

未跑326/7/12+2，未部署/采集/板端访问/commit；已有外部formal Q/E/帮助与目录重组保留，未纳入本轮成果。R3上下文约154k仍超120k执行门槛，记录，不当作模型能力对照证据。R4同model defaultDB紧凑新会话，R3原会话保留。
