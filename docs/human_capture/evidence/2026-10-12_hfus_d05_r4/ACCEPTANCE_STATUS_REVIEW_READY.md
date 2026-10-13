# 审核前逐ID状态（不ACCEPTED）

| ID | 状态 | 证据/限制 |
|---|---|---|
| R02-01 | PASS | before/FINAL_TREE_SHA/BOUNDARY，外部lock消失单列，非原子冻结 |
| R02-02 | PASS | D05_CORRECTION_AUDIT与54历史ledger核查 |
| R02-03 | PASS | 完整27新ledger/逐层失败账 |
| R02-04 | PASS | point_totals逐点净恢复/new accepted/human-supported分列 |
| R02-05 | PASS | 冻结H1真实GT-free互斥守恒/实跑 |
| R02-06 | BLOCKED | strict收益子条件PASS，家具独立负例不足，旧legacy回退披露 |
| R02-07 | BLOCKED | 软件契约PASS；连续未标/退出参照不足，first不是全序首次确认 |
| R02-08 | FAIL | 原R02 viewer异步问题保留；最终R04 Demo v2修复并另验 |
| R02-09 | FAIL | far55.693/5m170.302ms，原门不改 |
| R02-10 | NOT_RUN | 原mid-review不够；最终指定独审完成后另裁定 |
| R02-11 | NOT_RUN | 待最终追加return，其它实物完整 |
| R03-01 | PASS | before/after范围核查 |
| R03-02 | PASS | 147固定真实候选/69D/raw/effective/43 veto |
| R03-03 | PASS | full9 actual exit0/原模型和参数不变 |
| R03-04 | FAIL | 家具diagnostic减少但near184→179，不晋级 |
| R03-05 | BLOCKED | 回退因果真实bank闭合，连续ID/退出/负例资格不足 |
| R03-06 | NOT_RUN | 当前v2完整浏览器待最终记录；旧v1 race保留 |
| R03-07 | FAIL | far51.598、5m与S9仍超50ms |
| R03-08 | NOT_RUN | 待指定模型最终独审 |
| R03-09 | NOT_RUN | 待return/最终包 |
| R04-01 | PASS | 原资产SHA无变化；新增demo_v2属授权内增量，另记SHA |
| R04-02 | PASS | 数学等价和120稀疏稠密边界反例exit0 |
| R04-03 | PASS | 9session2605帧真实新跑，全阶段/成员/状态精确parity |
| R04-04 | PASS | 9会话p95全部<50ms，纯算法串行；p99 far50.294ms保留；板端NOT_RUN |
| R04-05 | NOT_RUN | v1初始化覆盖实证，v2修复，待完整真实操作记录 |
| R04-06 | NOT_RUN | 待指定最终只读审核，旧wrapper失败不抹掉 |
| R04-07 | NOT_RUN | 待最后回传与增量源SHA |

整体工程实跑完整，待最终Demo/独审/return；算法目标仍FAIL（far/occl/turn/FURNITURE/ghost），GT资格BLOCKED，生产BLOCKED且NOT_RUN。既有人工资格下R03 near五帧回退不需要新GT才认FAIL。
