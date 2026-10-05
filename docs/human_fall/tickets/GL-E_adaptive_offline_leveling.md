# GL-E：Adaptive Leveling只读离线应用 / 计划工单 v1

状态：PLANNED / IMPLEMENTATION_NOT_RUN；前置D软件验收。来源：[最终计划§4/8/14](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§7](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。唯一验收表v1在本文件。

## 目标与范围

新增transform模块/离线runner，应用accepted source→adaptive-display R/t，保留raw XYZ/source_rows/source/time/frame/accepted version、same-source前后与FINAL诊断。candidate不直接应用；HOLD应用最近已接受数值但有效性分开。physical1.14不被observed d覆盖。先离线，不ROS/正式配置/SDK/driver/生产WebUI。

操作矩阵：source vs已Ry26+tz1.34显示域、normal正负/已知GT、无accepted/reference明确fallback、candidate-only/accepted/HOLD/expired、每种epoch变化、raw output/caller修改、已有输出目录、坏模型kind/R/t/unit、当前P02 joint/leave-out FAIL。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-E-01 | source-plane→Rx@Ry/tz=d，yaw/tx/ty gauge；Rn=up/properR/Z=signedres/inverse误差≤1e−12；已知GT sign正确；显示修正不能冒名安装角 | GT plus independent scalar/metamorphic tests | NOT_RUN |
| AGL-E-02 | 同source行/frame/时间/units/accepted model绑定；异常点计数保留，显示抽样不参与fit/验收；输出新ID独占不改原输入 | full source-row lineage/output hashes | NOT_RUN |
| AGL-E-03 | raw/filter/accepted/reference分开；无accepted不补identity；HOLD numeric保持但fresh/geometry expiry正确；坏model/reload不半应用 | state × producer/consumer combinations | NOT_RUN |
| AGL-E-04 | physical_height1.14只读，observed tz独立；kind与physical/runtime资格不能升级；d/nz/refitRMS optimizer不存在；参与fit/独立验证区分 | schema + existing consumer rejection/source audit | NOT_RUN |
| AGL-E-05 | per-frame raw/filtered/accepted角/offset及RMS/P95/pose spread完整；P02四区/留一区历史FAIL不追改；参数/selector变更新epoch | real exposed fixture / per-region reports | NOT_RUN |
| AGL-E-S01 | one writer，pony_tail/diag/有效回归/SHA/原始命令/停写/指定独审；无设备或实时接入 | scope + return | NOT_RUN |

## 交付

offline CLI、transform/diagnostic artifacts、frame/transform IDs及numeric/source索引检查；`evidence/<date>_agl_e_rN/`、`returns/GL-E.md`。软件通过不替代物理精度/全场范围，不自动放行H。
