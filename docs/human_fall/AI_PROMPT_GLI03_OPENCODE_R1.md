# GL-I03 R1：显式独立 constrained config 变体 / 2026-10-03

当前分工与结果：用户已授权Codex主开发、指定OpenCode Go Flash/defaultDB二审。三文件开发完成且独立二审软件PASS，无需返工；K04 REAL/B01 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。[最新收口](evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md)/[正式二审](evidence/2026-10-03_gl_i03_r1/opencode_second_review_01/00_review.md)/[研究修订计划](evidence/2026-10-03_gl_i03_r1/research_01/27_PLAN_REVISION.md)。

状态：SOFTWARE_SECOND_REVIEW_PASS / REAL_BLOCKED。当前无活动writer/审核进程；旧诊断/RESUME/服务失败提示只保留追溯，不再派未完成的旧实施。Codex负责判断、研究、计划与主开发/收口；OpenCode二审及交接返工，每次其派前仍≤1min probe，不并行写源码/不切modelDBauth。后续计划按实际证据修订，不仅按旧表重复动作。

唯一判据：[GLI03_ACCEPTANCE.md](GLI03_ACCEPTANCE.md) v1；不复制表。唯一恢复锚点：[CODEX_HANDOVER.md](CODEX_HANDOVER.md)。未派工旧草稿保留在本轮evidence/00_original_draft.md。

## 目标与事实

为 `evaluate_gli02_candidate.py` 增加可选 `--constrained-config`。未设置时仍 `resolve_constrained_settings(None)`；显式设置复用既有 `load_config` 和 `resolve_constrained_settings`。新增 `config/geometry_constrained_gli03_r1.yaml`，完整复制冻结配置，仅改变 `spatial_cell_m=0.05`、`max_points_per_cell=8`。不改冻结协议/数学、不默认启用变体。

GL-I01 R1软件已审PASS；GL-I02 R1 synthetic PASS/真实candidate路线3 NOT_RUN，历史不追改。capture共4372400点/89帧；当前审定单组FIT ROI1214点，三个validation区2064/119/542点。本轮Codex只读preflight：默认采样80→ground_points_insufficient；两项变体采样1193→ground_degenerate。见本轮00_preflight_results.json。旧2382是pool统计，不作单组门槛；不跨帧池化绕gate。

真实candidate仍是K04目标。阶段一定位退化具体判定，分清配置接线与数据/冻结算法限制。阶段二真实CLI若仍拒绝，则K04真实candidate BLOCKED/目标未闭合，附exit2/无artifact；不得mask为PASS、降低门槛、改第三项参数、改ROI/先验/数学或自动派R2。其它安全软件检查继续完成。

## 必读、白名单与冻结

完整读WORKFLOW.md、GLI03_ACCEPTANCE.md、RETURN_TEMPLATE.md、本工单与实际调用链；Codex开发前完整读取本机ponytail源，OpenCode二审/返工用原生 `skill(name="ponytail")` 完整读取已安装技能，回传记实际路径，不更改权限。当前已完成，后续是否需要新实现以研究证据和用户授权判断。

生产白名单仅三文件：

- 修改 `src/human_fall_detection/scripts/evaluate_gli02_candidate.py`：可选config入口及必要解析拒绝处理。
- 新增 `src/human_fall_detection/config/geometry_constrained_gli03_r1.yaml`：只改变上述两值。
- 新增 `src/human_fall_detection/tests/test_gli03_candidate_override.py`：集中synthetic入口/负例。

本轮证据 `docs/human_fall/evidence/2026-10-03_gl_i03_r1/` 只新增；阶段二结束按模板追加 `returns/GL-I03.md`（仅SUBMITTED/BLOCKED）。状态/工单/验收结果由Codex维护，OpenCode不写WORKFLOW、DISPATCH、README、REVIEW_LOG、本工单或验收表。

禁止改core（含ground/calibration/capture_input）、原geometry_constrained.yaml及其它既有config、calibrate_sensors.py、prepare_capture_input.py、GL-I01/GL-I02旧tests、driver/webui/captures/pc_apps/human_capture/HR/旧证据。保留用户差异与src/CMakeLists.txt表示。不reset/checkout/clean/commit/push，不部署/采集/板端网络/GL05，不换model/DB/认证/全局配置。

## 已完成的阶段一（过程记录，不再执行）

只新增本轮00_diag.md及只读诊断脚本/日志；生产/config/tests/return/状态均不写。按P01–P06全部子情形映射到实际函数/配置读取/异常传播/输出顺序，列覆盖、缺检查、失败、最小位置。复测已有审定NPZ/draft的单组数据与两组参数，定位ground_degenerate具体判定；不修冻结算法。记录SHA未变和默认/显式/emit-draft、负例、source/physical方案。

CLI无常驻状态：startup=每次调用，同内容reload=重复新CLI，同ID异内容/新ID=同config路径内容变化/新路径逐次运行，caller原地修改=解析对象隔离，外来frame/损坏manifest/不支持版本走原strict gate；GL02/ROS lifecycle不涉及，裁剪理由写00_diag。

完成明确 `DIAG_SUBMITTED; STOPPED_WITHOUT_PRODUCTION_WRITES`，退出。Codex核SHA和完整矩阵后另发阶段二；服务异常停止，不换模型/DB/认证或重复probe。

## 已交付并获二审的行为要求

默认None完全保持GL-I02 R1语义；emit-draft保持原模板行为，不新增config消费。显式config需mapping的ground_constrained；坏路径、YAML语法/结构/缺section/unknown key/bool/NaN/负数/floor非法→exit2无candidate，不fallback。配置边界转换解析异常为既有错误类型，不吞编程错误。保留prepared优先/capture只读/人工draft/frame成员/独立validation/独占输出；capture-dir可产生既有adapted中间文件，“无副作用”指无candidate、原capture/已有output不变。

ground.status只有valid才产candidate；orientation_unverified/invalid/ambiguous继续拒绝。产物status.ground=candidate、physical=false、无ground_derived，已有ground.settings记录resolved参数。真实与synthetic分source/目录，用户审定up_axis/height/四区不动。

自验按表：新synthetic/解析负例→原GL-I02→GL-I01及受影响ground/旧24探针→真实offline CLI→全范围/SHA。记命令/真实exit，保留失败并跑完其它安全检查。Python3.8 AST不冒称设备运行。

按RETURN_TEMPLATE追加实际session/model/defaultDB、ponytail路径、验收v1/SHA、各K/P/B/D分层结果、根因/源码config完整SHA/冻结对照/命令exit/日志/真实candidate阻塞。实现完成停写等待Codex独审。
