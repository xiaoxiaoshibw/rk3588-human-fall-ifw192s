# GL04 R3 设计 / 责任审查（实施前）

触发：WORKFLOW WF-CODEX-R1/R4。同一验收ID在R1/R2连续两轮暴露资格/版本/生命周期族缺陷：V06（R1 unknown/schema/verifier/未来snapshot，R2 snapshot↔state标定交错/schema2/quiet GPU）；V07（R1无/空候选，R2其他候选存在却本目标详情缺失）。V03同坐标读数也未完整闭合。判据v1不变，未新增功能/物理门槛。

两轮证据：r1/CODEX_REVIEW + 10 runtime；r2/CODEX_REVIEW + 20 runtime + 44 browser matrix + 45/46/48真实图。R2已过immutable token/source/ground/current presented math保留，不推倒重写。

| 责任 / 根因 | 证据 | R3设计修正 |
|---|---|---|
| Codex事前覆盖缺粒度 | R1/R2矩阵列了版本不匹但未逐到达顺序；V07仅无/空list未列target缺而other在；只查DOM未查GPU重绘 | 先把STATE旧/CAND新、STATE新/CAND旧、当前目标详情匹配/不匹配、无新消息四种消费者路径逐行列出 |
| 实现未执行明确绑定要求 | R2提示词要求snapshot/state比较cal/schema/GDID，observationQualified只检查snapshot ground/非空list/monitor | 一个纯qualification结果同时供目标读数、框颜色、位置/ground中心及选择上下文；不能任一候选代本目标 |
| 界面生命周期遗漏 | quiet DOM unknown但cached GPU/ground入口仍有效 | 失效转换需一次性dirty3d重绘，清框/支持/有效panel；静态raw可留但明确过期，历史保留 |
| 真实字段核查不足 | queue_dropped实际state.performance，R2只猜顶层/quality | 先读human_fall_node.py:285及performance_block，再按真实schema消费；缺/disabled显示unknown |
| 服务与上下文分流 | R1 summarize240秒timeout；R2本身exit0约203k，不属算法失败原因 | 不重试同一挂起helper；用户允许同model/default DB紧凑新会话，无第二writer。只读必要源码一次，测试输出tail失败/exit，120k前停止写入交接 |

不是模型能力不足的证据；无同条件对照。此审查不改旧断言、不触core/正式/设备，不把GL03 R8或GL05混入。

完整实施前操作矩阵：`02_operation_matrix.md`；实现者必须00_diag逐行映射实际函数、更新顺序、资格、UI/GPU失效与检查入口后再写代码。所有R2通过项继续回归，旧证据不覆写。
