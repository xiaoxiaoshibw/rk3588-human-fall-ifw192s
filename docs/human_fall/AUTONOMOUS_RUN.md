# HF自主开发：当前状态与恢复入口

## 最新优先状态：GL阶段用户暂停 / 2026-10-01

更新优先：用户已提供机器人总高1.4m、雷达眼球垂直离地约1.1m，明确恢复开发并纠正雷达向下看（旧向前上倾作废，角度未知）。GL-00 R4经Codex软件方案/参数/契约复审PASS，仅允许GL-01合成原型；真实地面/物理BLOCKED，未部署。复审见evidence/2026-10-01_gl00_r4/CODEX_REVIEW.md，后续以此覆盖下方暂停历史。

用户要求“等我先测数据你再动工”。当前PAUSED_USER，停在GL-00；OpenCode本轮已结束，无GL续接/后续派工，GL-00未PASS。指定DeepSeek探针通过，当前场景47帧有界采集已保存并独立校验；等待雷达中心/机器人尺量与地面区域确认。完整session、路径/哈希、真实失败/退出码、待审事项见 [CODEX_PAUSE](evidence/2026-10-01_gl00_r1/CODEX_PAUSE.md)。下方HF首版历史保持，不能按旧持续授权自动恢复GL。

更新：2026-10-01。用户授权持续软件开发、直接OpenCode CLI派工/复审/返工和必要可回退部署，无需逐轮搬运或常规确认。保留失败、旧版本与用户改动；不默认commit/push。

## 当前状态

软件首版PASS并已部署，整体真人/物理验收未通过。最终结论见returns/HF-10.md、REVIEW_LOG.md；启动/停机/回滚见deployment.md。

- 仓库D:\Code\ldiar，master HEAD c96489e40037aca810b23b98d71ba34632d18bd0，用户修改/未跟踪目录保留。
- 板SSH ldiar-wel，容器slam-localization，RK3588/Noetic/Python3.8.10/NumPy1.17.4。
- 活动版本/root/catkin_ws/human_fall_deploy/releases/20261001T051310Z，节点PID26591（下次操作先实时核对，不盲用旧PID）。
- 正式URL http://192.168.3.125:8090/human_fall/index.html 。算法全量/innolidar_points；网页只读/human_fall/display_points，约12000/49144点。有完整source header↔真实ROS1wire_seq映射。
- current和webui/human_fall链接指向版本bundle；原首页和driver未变，不改系统/网络/自启/厂商库。
- driver二进制0286545f…f3c4，C++修复源未部署、ROS2全包NOT_RUN。
- 本地/板211回归，根端44独立Python边界、网页18纯检查+独立display-key PASS；活动12源/资源哈希匹配、manifest0、外层SSH0。
- 原R1真实30min统计为输入9.647/处理8.718Hz，处理p95约146ms；未冻结性能门槛，不能标性能ACCEPTED。记录不冒称新版本浏览器FPS/端到端时延。
- 真实地面/外参/可信空场背景/IMU单位轴向偏置同步/人体标签仍缺证据；ground未配置时unknown/degraded正常，confirmed和IMU融合禁用。

## CLI与证据

HF09最后同session ses_f0b628b84ffefnOtctWabVpJsw，DeepSeek；R3 resume已exit0，无正在执行的OpenCode任务。HF08 Luna session ses_f0b78f0f6ffez18d7PSN69mbE3已结束。不要重复派工或复跑已闭合轮次。

主要最终证据：evidence/2026-10-01_autonomous_hf09_r1/；codex_final_regression.txt、codex_final_boundaries.txt、codex_final_js.txt、codex_active_deployment_final_checked.json.txt、codex_final_wire_join.txt、codex_finalize_geometry_deploy.txt、codex_board_geometry_check.txt、codex_final_live.jpg。原始失败/CLI日志和每轮回传均保留。

最后Codex补修：失锁/遮挡时复用candidate_id不能接替目标位置；成功关联才算实测，短预测用原轨迹，lost/ambiguous无位置/距离/框。显示is_dense继承输入；应用bundle使用本地已审f60cb48f…e773解码脚本。板原旧2ef4…解码脚本少静止目标surface_distance两行，但xyz函数AST相同，原板文件保留；应用隔离副本固定版本。

## 恢复与后续边界

先读本文件/最终回传/REVIEW_LOG，实时核对当前链接/PID/源码hash，再继续用户新指令。后续真实验收需可信地面/背景采集与匿名人工动作标签，不能自动假设旧health bag无人或含跌倒。可继续软件和合成测试，不编造物理证据，不开confirmed。需要优化算法时用同冻结输入比对再部署，保留不利样例。

Cua浏览器ID2，正式tab ID3；工具默认30s不够，timeout_ms60000，拆分动作/DOM，避免超过60s导致kernel reset。Native disabled。截图为JPEG，可用screenshot+node:fs/promises保存并在交付内嵌。最终页面保留为deliverable；为避免重复客户端带宽，结束前断开测试WS。JS重置后先选择既有browser/tab，不能重复新开同URL。

此前过程状态完整保存在evidence/2026-10-01_autonomous_hf09_r1/AUTONOMOUS_RUN_history_20261001.md。

## GL-01 R4独立软件复审PASS / 2026-10-01

显式约束RANSAC、数值CLI与加载器经Codex244回归/12独立方法exit0及同SHA板端244验证，软件PASS；真实bag源索引/帧组适配、ROI与物理BLOCKED，未部署。原9/10独立失败已闭合，两次API400在同DeepSeek session压缩后恢复，日志保留。hardware_inventory.md外来人工截图约26度粗估保留，不据此标实测。详evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md。允许串行GL02数学软件/未核验候选预览，不升级真实外参/IMU/confirmed。

## 最新用户派工方式与GL02 R1复审 / 2026-10-01

用户要求“接下来任务让我手动给cluadecode”。后续改为用户手动交Claude Code；Codex只准备具体工单/独立复审，不自动调用OpenCode继续返工或派后续。当前GL02 OpenCode R1已结束exit0，Codex262常规回归通过但独立6方法6失败，软件REWORK/真实物理BLOCKED，GL03未放行。手动下一步为AI_PROMPT_GL02_CLAUDE_REWORK.md，详细证据evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md与40_*。GL00/01已审软件不重做。无活动实现写入者，不部署/采集，旧失败保留。

## GL-02 Claude R2 Codex独立复审 / 2026-10-01

软件REWORK，GL03不放行；继续用户手动派Claude Code。Codex独立262回归/原6方法exit0；新增集成5方法5失败，补类型检查后最终7方法7失败exit1（evidence/2026-10-01_gl02_r2/50～54）。R2闭合原反例，但实际加载仍可保留旧ground、裸块版本错配；monitor失效仍发布位置/继续相关观测、散点误报整体变化、重标定被一帧清除；float版本/mixed bool矩阵仍通过。详同目录CODEX_REVIEW.md；下一步手动AI_PROMPT_GL02_CLAUDE_R3.md。板端兼容NOT_RUN，真实物理BLOCKED，未改生产算法/部署/采集。

## GL-02 Claude R3 Codex独立复审 / 2026-10-01

R2原七方法/267全回归/R2静态六方法独立通过（GL02 R3 evidence50～52），已闭合部分保留；新增其他入口四方法四失败，补单侧遮挡后最终五方法五失败exit1（55_*）。软件REWORK，设备兼容NOT_RUN/真实物理BLOCKED，GL03不放行。剩余为配套局部更新calibration版本错配/caller引用、同GDID新calibration版本未清旧资格、monitor不可用仍accepted基线请求、10%单侧遮挡误锁存整片变化。详evidence/2026-10-01_gl02_r3/CODEX_REVIEW.md；用户手动下一步AI_PROMPT_GL02_CLAUDE_R4.md，不自动派工。生产算法未由Codex修改，未部署/采集。
