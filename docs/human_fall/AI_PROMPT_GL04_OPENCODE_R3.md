# OpenCode GL-04 R3（设计前置集中返工）

唯一生产写入者仍你，指定`opencode-go/deepseek-v4.1-flash`、default DB；Codex唯一编排/独立复审。用户允许同model/default DB紧凑新会话；R2已exit0停止写入，约203k上下文，不继续塞长历史。只四preview文件；正式页有外部Q/E/帮助改动及根目录重组，保留不写不回滚。core/config/driver/其它webui/旧数据/旧证据/原38断言冻结。无GL05/设备/部署/采集/板端网络/commit/reset。

只读本提示词、R3 PLAN_REVIEW/02_operation_matrix、R2 CODEX_REVIEW和20_codex_runtime的失败尾段、GL04_ACCEPTANCE v1结果表以及必要实际函数/消费者。不要重复读所有旧报告、巨型manifest/export、整份stdout。需读文件按调用链一次读完，之后只读必要片段。测试日志落r3，只把失败摘要/exit送回上下文。120k前若未结束停止写入记录锚点交Codex，不无限读同文件。

## 必须先设计

连续V06/V07资格族失败已触发WORKFLOW设计前置。先在r3/00_diag逐C01–C15映射：输入来源/STATE与CAND到达顺序、实际函数、更新先后、共享资格结果、目标详情匹配、DOM/overlay/GPU失效及source/ground/predicted/ready等消费者、检查。检查本轮已有明确反例和兄弟入口，不只修8个方法。

## 修三个根因，保留R2已过部分

1. **同一当前绑定/对应目标资格**。snapshot/state的session/epoch/source seq-stamp/frame、snapshot_id（提供时）、calibration_id/schema/GDID（实际state的GDID在顶层）必须一致；坏schema不能因双方同值就支持；错/旧/缺匹配的当前观测unknown。合法legacy source-only缺新ground渲染字段不能当坏源坐标。无/空candidate、本目标详情缺但other还在都不能显示旧位置/正常色，ready基线不能代替观测。删除`hfAnyGroundCandidate`任取第一人补ground位置的语义；只能消费明确对应当前目标的现有几何字段（依据已有标识或精确已发布几何字段做一致性检查，不最近邻、不跟踪、不算候选/拟合）。无法证明对应就position空/fall unknown。预测/锁状态和旧事件/ack/按钮语义保留，预测不能成为当前actual_points。

共享结果用于目标读数、source/ground框/颜色、有效position、geometry入口及选择上下文，不能只限制配平按钮而source仍upright。旧token及caller mutation拒绝保持；fresh same-content/原candidate ID、当前source/ground选择保持；frame/单位/版本不匹配选择拒绝。原始模式保持已有source-only候选浏览/请求能力，不能因缺新增R/t变成不可选；物理状态仍unknown，ground模式明确禁用。

2. **失效必须真的重绘**。quiet>TTL、断连、错误版本/校准/monitor及无目标详情的转换，DOM、overlay、GPU同步清正常色/框/有效支持层/读数；至少一次`dirty3d`使实际cached canvas消失。ground旧snapshot过期不能仍可用/绿字，raw可留但明确过期与真实帧龄；历史不清。避免每RAF重建3000点layer，按当前绑定或资格转换更新；合法到齐恢复时首次消息组立即同步，不靠下一轮feed凑正确panel。

3. **字段/维度/读数只按真实来源**。`_parseGroundBlock`未知/错units（如mm）不当m；2D ground_local支持可按声明平面显示，显式3D支持必须三分量有限，null/NaN Z不能丢掉再置0；渲染保留已知3D分量。支持预算/indices/LineLoop/两模式/图例已过不退化。ground模式position值的行名、候选label读数必须当前系（或source读数明确另列，不让ground值叫source）；snapshot schema/geometry schema/标定版本分别明确显示。R/t与backend ground_local高度符号原义保持，俯瞰相机从+Z向地面看，不浏览器翻坐标或拟合。

性能读取真实`state.performance`：只读human_fall_node.py的performance_block及_publish_state（约31–48、285、387），kind/schema/enabled/queue_dropped符合则显示，缺/disabled/非法unknown；保留旧兼容字段时不得覆盖真实字段。render-fps计数已正确保留，原pcSkip/Hz不冒充队列。静态JSON fixture流程保留（R3需要当前新evidence fixtures，不能覆写r2旧JSON），正常/tilted/no_extrinsics同帧截图由Codex实跑；可为本轮扩展static fixture脚本，几何仅离线Node执行。V10生产R/t/support缺口继续BLOCKED，不改core/topics。D01 NOT_RUN。

## 验证/回传

R2旧21反例通过保留；新增8FAIL在R2/20与真实44/45/46/48（根因见CODEX_REVIEW）。R3自身检查覆盖C01–C15，每行记录PASS/FAIL/NOT_RUN/BLOCKED。原38断言文本不改，只追加有效检查；辅助代码/fixtures/日志只写r3，不覆写旧 evidence 或作者/审查旧日志。Codex脚本运行可作你的自验，禁止把输出标作Codex独立结果/overwrite其已有结果文件；新stdout/JSON名放r3。

不跑326/7/12+2，core/正式未由preview改动。真实browser没有就NOT_RUN；实际DPR当前browser能力没改变，不能把VM的DPR模拟称真实browser PASS。源码SHA/范围（tracked+untracked包括现有外部差异），按RETURN_TEMPLATE末尾追加`returns/GL-04.md`标题“OpenCode GL-04 R3”，状态仅SUBMITTED/BLOCKED。结束停写，给回传/evidence/未闭合ID/session/model。GL04 v1判据不变。
