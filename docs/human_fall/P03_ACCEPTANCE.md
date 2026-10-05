# P03 回放自动配平 / 唯一验收 v1

2026-10-05 用户授权：回放页选择会话时**算法自动配平**（不手输参数、不手画 ROI），算法放 8901 服务侧。前置证据：P02 v2 四区联合（[结果](evidence/2026-10-04_p02_four_roi_r1/08_REPORT.md)）、P02 R3 分区/逐帧（类型 C、6 对互预测 FAIL、[结果](evidence/2026-10-04_p02_r3_region_frame/09_REPORT.md)）、GL-W01 工作台（[GLW01 v1](GLW01_ACCEPTANCE.md)，其**人工确认哲学不因本单取消**：auto 只是把"画 ROI"变算法，结果页仍显区分、确认后才消费）。范围：仅 `pc_apps/human_replay/` 内 —— `leveling.py`、`leveling.js` 允许微调、`leveling_lib.py`（新建）、`replay.js`、`human_replay_lib.test.js`（如纯函数进 lib）、`leveling_auto_test.py`（新建）；console exe 不重打包、annotation/driver/webui/数据源/生产外参不动。单 writer：Claude Code。

| ID | v1 要求 / 检查 | 当前结果 |
|---|---|---|
| P03-A | 自动域检测：纯函数 `detect_ground_domain(points)`（stdlib+NumPy，无新库）；候选门 n_z≥.85、d∈[.8,1.8]m、支持率报告公开；输出 K∈[3,8] 互不重叠 ROI（凸包栅格近似，区域每边≥5cm、与 leveling 现契约一致）；三既有 session（cap_20261004_202456/_203349 + 二选一）候选平面 pitch 与 R2 联合值 26.623° 差 <1.5°；**全场 RANSAC 拐墙/家具的失败如实保留不裁数据** | 未实施 |
| P03-B | 负路径显式：候选门未达/网格空/ROI<3 → `ground_auto_candidate_invalid` 等显式 reason，前端显示失败并可回手动；不为 PASS 调门/降阈/裁尾 | 未实施 |
| P03-C | 回放消费：`__load_session_sid` 获取 or 复用 transform（source-frame schema：R=Rx(roll)@Ry(pitch)、t=[0,0,d]、yaw=0），变换在 CPU 上一次性作用于 points buffer 后渲染；旧对话（无 transform）显示名义或原样不破坏；**旧的 leveling 手动工作流行为不变**（level，不改 regions 必填的 DEFAULT 路径语义，只加 auto 分支） | 未实施 |
| P03-D | 一致性锚点：auto 模式全程公开 RANSAC/TLS/SVD 三法 861/seed20261001/.05（同 R2 全点等权）；auto 输出 transform 与 R2 冻结域联合 TLS 在 cap_20261004_* 上比较（pitch/roll/d 差值如实报告，不设新物理门） | 未实施 |
| P03-E | 既有回归不破：`leveling_test.py`、`human_replay_lib.test.js` 通过（或仅 wasm 端增量）；GL-W01 手动工作流逐行为对照不变 | 未实施 |
| S01 | ponytail SKILL 路径声明；范围/页面/请求校验 Node+Python 检查器；非法请求显式拒绝（schema/字段/SID/自填域）；指定独审与真实 browser 单列 NOT_RUN 不冒称 | 未实施 |
| D01 | 不设备/采集/部署/网络/driver/commit/push/reset/生产外参写入；console exe 不重打包 | 未实施 |

数据门沿用 RMS≤.03m／|P95|≤.05m／support(.05m)≥.8／每区≥20 点／λ2/λ3≥.01／二维展开≥.10m；三法两两一致性 ≤2°/3cm 仍为**工程参考**不作物理精度。auto 输出 `status: research_display`、`physical_verified/extrinsics_verified/runtime_eligible` 全 false，1.14m 实测继续另存不绑定。
