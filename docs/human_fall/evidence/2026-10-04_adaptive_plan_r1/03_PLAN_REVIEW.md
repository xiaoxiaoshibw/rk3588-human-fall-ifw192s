# 自适应最终计划编制收口 / PLAN_READY

任务起点2026-10-04；本轮仅计划/设计/接口/验收文档。主计划15章节、接口契约、GL-A到GL-I九工单（各唯一v1表）、57唯一验收ID与45文件链接完整。模块分文件，TLS/SVD家族保护、quality硬门、六状态/median+EMA/rate/last_good age、false update与相关帧统计、三列+FINAL、日志/故障、shadow/人工接管/回退门均落实。

v3末尾已新增最终阶段§6，旧1.1m与历史结果不重写；主线/设计/INDEX/README/DISPATCH/WORKFLOW链接同步。1.14测距仪物理记录与Ry26+Z1.340显示参考分开；当前四区392196点/作者自验/leave-one-out3/4 FAIL/P1 NO保持；经典三算法不宣称原创。

## 文档编制检查（不是未来软件验收）

| ID | 检查 | 结果 |
|---|---|---|
| PLAN-01 | 当前事实/引用与物理-观测参数分离，旧证据不改 | PASS（文档检查） |
| PLAN-02 | 15要求章节、架构/模块/接口/状态/score/共识/滤波/UI/日志完整 | PASS（文档检查） |
| PLAN-03 | 9工单、57唯一ID、每单1份v1表、依赖/negative matrix/交付/停止点 | PASS（文档检查） |
| PLAN-04 | 参数仅候选、场景/量化指标/失败/独立holdout/相关性/risk/rollback | PASS（文档检查） |
| PLAN-05 | 45新链接存在、Markdown fence配对、模块分文件、现行计划最终阶段链接 | PASS（文件检查） |
| PLAN-06 | 281个protected source/UI/capture条目普通文件SHA无漂移，既有HTML SHA与前轮最终manifest一致 | PASS（范围检查） |

初次QA因main缺literal rollback命令名停止，尚未写QA产物；补明确enable/disable/freeze/unfreeze/rollback语义与失败行为后复验。原失败01_QA_FIRST_FAILURE保留，01早轮QA与04最终manifest各有版本，不覆盖旧结果。

当前GL-A～GL-I实现、CLI、设备/性能/真实browser测试全部NOT_RUN；没有修改运行配置、PCAP、1.14物理值、SDK/driver、外参或生产WebUI，没有commit/push。后续新启动首单GL-A；F真实动态/独立数据/物理范围门、H硬件性能与实时授权、I消费者/激活授权仍需证据，不因PLAN_READY绕过。

PLAN_READY仅表示工程实施计划可逐工单执行，不是PRODUCTION_READY或独立软件验收。Code writer并未启动；规划role按后续WORKFLOW当前授权。基线HEAD与终HEAD记录，既有用户dirty tree保持。Memory只辅助height datum区分，旧1.1记忆未用于当前参数。
