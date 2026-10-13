# HR-RET-V2 increment 1：融合删除能力函数 + 单测（自验）

- **授权/工单**：[tickets/HR-RET-V2.md](../../tickets/HR-RET-V2.md)；唯一验收表 v1：[HRRETV2_ACCEPTANCE.md](../../HRRETV2_ACCEPTANCE.md)。
- **范围（increment 1）**：`pc_apps/human_replay/human_pipe_lib.js` 新增：
  - `_bg_match_rec`（返回命中体素记录；`_bg_match` 改为其布尔包装，语义不变）；
  - `extract_foreground_fused(xyzi, refkeys, online)`（v2 融合删除：参考命中删；在线命中且其体素邻接参考<0.12m 删；在线-only 保留；`refkeys=null` 保守不删；工作空间裁剪与原函数一致；返回诊断计数）。**默认不被任何现有路径调用；P 路径无调用点、逐位不变。**
  - 导出 `extract_foreground_fused`。
- **测试**：`human_pipe_lib.test.js` 新增 2 组用例（融合语义 + 退化语义）。
- **自验结果**（`lib_tests.log`）：
  - `human_pipe_lib.test.js`：**37 passed / 0 failed**（首跑 1 项误报 = float32 与双精度字面量比较写法问题，仅改测试断言后复跑；日志保留两跑）；
  - `human_replay_lib.test.js`：45/45；`panel.test.js`：PASS。
- **验收表逐条（increment 1 范围）**：V2-01 / V2-10 / V2-13 **PASS（自验）**；其余见 [表](../../HRRETV2_ACCEPTANCE.md)。
- **未做（increment 2）**：消费侧能力旗标（默认关；仅 VALID artifact 走 v2）、加载路径、浏览器/节点行为验证、V2-07/11/12/14（含独立复审）。
- **ponytail**：实读（opencode skill，base `C:\Users\30680\.config\opencode\skills\ponytail`，full）；复用既有 `_bg_match` 循环（单处改写为返回记录版、布尔语义保持）、不新增参数、测试沿用既有 harness，无新依赖。
- 未 commit / 未 push；本增量是用户 2026-10-08「授权」项下的生产代码变更（仅此一处），其余边界（W03 状态、驱动/网络/部署）不变。
