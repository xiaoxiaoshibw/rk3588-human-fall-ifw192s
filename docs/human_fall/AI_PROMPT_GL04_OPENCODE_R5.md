# OpenCode GL04 R5：固定nullable绑定、预测与source-only消费者

你仍是唯一生产代码writer，指定`opencode-go/deepseek-v4.1-flash`、default DB；Codex独审。用户允许同model/default DB紧凑新会话。只改preview四文件和本轮新证据/returns末尾。正式页已有外部Q/E/帮助变化不可覆盖；core/config/driver/其它webui/旧数据/旧证据/原44断言不动，无GL05/板端联网/部署/采集/commit/reset。GL04_ACCEPTANCE v1判据不变，V10生产缺R/t/support仍BLOCKED、D01 NOT_RUN。

先读r5/PLAN_REVIEW、R4 CODEX_REVIEW、90和92 FAIL尾以及R3 C01–C15矩阵和必要源码函数。不要复制全部历史/大manifest/export。实现前r5/00_diag必须把C01/C05/C07/C08/C11的每个组合写清输入来源、函数与赋值顺序、选择/当前source测量/GT跌倒观测/预测诊断各消费者资格、失效/恢复与具体反例；其余C行引用已过入口并核保留。不要把这几处做成孤立if补丁。

1. **绑定**：snapshot cal_id/schema/GDID与state相应字段完整nullable比较。两侧null/缺失合法legacy source-only；任一侧known对侧null/undefined拒绝（R4 90的state GDID缺失、schema null都导致旧upright）。显式schema2仍拒。保留旧纯函数断言的合法partial输入，真实kind=target_state/schema1完整消息必须严格；必要时在调用者使用窄资格，不把首选context和已选目标观测混成单一门。
2. **当前目标**：R4唯一候选匹配保留。candidate只有other但state仍留旧source/ground字段→unknown/position空；predicted=true仍是预测诊断，不把旧source值放入“当前位置”行（R4 90/92），事件/track预测语义和灰色警示保留。legacy no-cal/no-ground无R/t、source当前实际目标与候选已匹配时，原始模式能显示locked与实际source XYZ，fall_status unknown/未地面核验；其首次选人仍能发原snapshot/candidate id。选择需要fresh当前候选与context，不要求已有目标或有效ground；显式坏schema/frame/版本不能绕过。
3. **旧入口坐标变化**：render token覆盖coordinate.source_frame以及显式变换units（连同已有R/t、schema/GDID、candidate签名）；caller原地修改或同ID同帧不同coordinate后旧按钮/drag不可用。新当前按钮仍用原ID，合法source/ground同内容切换/旋转缩放后仍可选。源frame与已声明coordinate.source_frame矛盾时不可当当前已知坐标。必要payload可用无几何计算的字段比较，不建新跟踪/拟合。
4. R3已过的source/ground R/t、ground实际AABB、grid/support≤3000/3D有限、DPR同步逻辑、静默/断连GPU重绘、`state.performance.queue_dropped`以及原告警色/ack/history保持。新增r5离线fixture只预生成/复制已知几何字段（Node或Python离线，不放browser计算），注明synthetic/offline、固定sample/frame版本、物理flags false；不要覆写r1–r4证据。可复用r4 Codex脚本作你自验，但stdout/JSON落r5新名，不冒称Codex独立复审。

自验先复现R4 90的5FAIL与92的2FAIL，再查各C行及原44 JS断言。相关源码没碰core/正式，不跑326/7/12+2；真实browser你没有就NOT_RUN交Codex，实际DPR未切换也必须NOT_RUN。按RETURN_TEMPLATE在returns/GL-04.md末尾追加 **OpenCode GL-04 R5**，只SUBMITTED/BLOCKED，逐ID、矩阵、实际命令/exit、源码SHA、未跑项，停止写入并给会话/模型/证据路径。控制上下文，读源码一次，测试只返失败摘要；若>120k未结束停写交接，不强行继续到200k。
