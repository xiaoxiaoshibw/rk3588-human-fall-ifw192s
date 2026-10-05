# GL-I04 R1任务：离线几何诊断与保守候选搜索研究

2026-10-03当前入口：[GL-I04 v1](GLI04_ACCEPTANCE.md)/[收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[指定OpenCode二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)。Codex三新文件停写后独立二审：L01–L06/R01–R06/S01/Q01–Q10 PASS，无源码返工；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。离线诊断可用，搜索原型保留研究、不接运行时；无活动writer，冻结算法/批准输入保持，GL04DPR/正式及GL05设备边界不变。下方准备/GL-I03入口均为历史。

状态：DRAFT_READY / 未执行。2026-10-03用户本轮只要求下一区间任务与AI开发提示词；本文件不代表已经启动开发、派工或设备操作。唯一判据为[GLI04_ACCEPTANCE.md](GLI04_ACCEPTANCE.md) v1；主开发提示为[AI_PROMPT_GLI04_CODEX_R1.md](AI_PROMPT_GLI04_CODEX_R1.md)。

## 本区间要解决的问题

GL-I03配置入口已实现且OpenCode独立二审软件PASS，真实candidate仍BLOCKED。当前三个障碍必须分别研究：source-frame里的up符号/录制extrinsic、四个固定区域的几何一致性、RANSAC候选截断导致的搜索证据不足。下一区间交付可重复使用的诊断代码与独立算法研究原型，不把“必须产真实标定”作为其软件成功条件。

## 任务与交付

| 工作 | 交付 | 判断标准 |
|---|---|---|
| 离线诊断工具 | 新纯core模块、新CLI、新集中tests；JSON+Markdown+带source-index的诊断数据，至少一份可核查局部空间图/报告 | 完整保留输入身份和固定选择，计算可手算核查，明确actual fit/replay/WHAT_IF区别 |
| 坐标与区域研究 | 旋转表达条件推导、录制配置证据表、四box逐帧残差/固定空间分箱、高低尾部与时序稳定性 | 不把缺失物理证据伪造为零值，不按FIT残差筛validation来通过 |
| 候选搜索原型 | 仅本单evidence内的prototype、同输入/seed/设置的冻结baseline、合成反例/成本对照 | 每个已见合格假设的处理可追溯；真实竞争、非传递相似链和预算不足不能误接受 |
| 二审与决策 | Codex自验提交、OpenCode独立二审、原型采用/不采用/需补实验的决策记录 | 软件与physics、缺证据与代码缺陷分层，按固定ID报告，不以测试数量或原型“看起来更好”收口 |

## 执行方式

Codex负责研究判断、实现和计划修订，是当前唯一生产writer；停写后交OpenCode CLI `opencode-go/deepseek-v4.1-flash` / default DB二审。二审发现实现缺陷时集中返工，明确交接后才能让OpenCode成为返工writer，不并行写入。服务probe只在OpenCode派发前执行一次≤1min，不再阻断Codex本地开发。

第一步用GL-I03已有证据和实际源码做简短设计映射，确认本单观测能区分三道障碍，然后直接开发；不要重复整个历史诊断或为例行设计新增用户确认。先交付可用诊断，再做搜索原型。发现预设方案不成立时，用反例修订计划；若新语义改变验收要求，留下版本/来源/影响记录，不悄悄降低判据。

## 新代码范围

- 新 `src/human_fall_detection/core/ground_diagnostics.py`：纯std+NumPy，无ROS/UI导入。
- 新 `src/human_fall_detection/scripts/diagnose_gli04_geometry.py`：薄CLI，复用GL-I01适配/selector及既有config解析能力。
- 新 `src/human_fall_detection/tests/test_gli04_geometry.py`：集中语义/边界回归，尽量复用既有synthetic exporter。
- 本单 `docs/human_fall/evidence/2026-10-03_gl_i04_r1/` 新脚本/报告；搜索原型只在 `research_01/search_prototype.py`，不接入core/runtime/候选标定入口。
- 本单文档与 `returns/GL-I04.md` 追加；流程/结果入口由Codex维护。

如果更少文件能清晰实现可测纯逻辑，可在00_diag中说明并收敛；若新增生产路径/接入点，先给出具体理由与范围变更记录。禁止修改现有ground.py/calibration.py、GL-I03三文件、原config/原tests、批准draft、capture、driver、webui、pc_apps/HR与历史证据；不reset/checkout/clean/commit/push/部署/采集/板端网络/GL05。新增纯core模块是本任务计划范围，不能借此改冻结旧core。

## 阶段决策门

1. 诊断能复现既有现象后，输入证据缺口只阻physics结论，不阻工具/synthetic原型。
2. 真实四区差异仍存在时，搜索原型不承担让真实holdout通过的目标；不清truncated、放宽15°/残差门或自动挑新ROI。
3. 原型发生任何竞争/预算场景误接受，属于研究代码安全语义FAIL，先集中修复。无性能收益或未胜过baseline可以成为诚实研究结果；永远unresolved、未跑负例不能冒充可用原型。
4. 二审后只推荐后续采用方案。没有本单之外的接入/物理资格/部署许可，不自动合并原型或启用真实calibration。

## 承接证据与事实

- [GL-I03收口](evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md)、[独立二审](evidence/2026-10-03_gl_i03_r1/opencode_second_review_01/00_review.md)。
- [三先验对照](evidence/2026-10-03_gl_i03_r1/research_01/25_prior_hypotheses_results.json)、[区域空间统计](evidence/2026-10-03_gl_i03_r1/research_01/26_region_consistency_results.json)、[89帧时序](evidence/2026-10-03_gl_i03_r1/research_01/30_temporal_regions_results.json)、[来源与下一步](evidence/2026-10-03_gl_i03_r1/research_01/31_EVIDENCE_AND_NEXT_STEPS.md)。
- 已批准输入仍up=[0.438371,0,0.898794]、height=[1.2,1.7]与原四区。负X或数据法向只能是明确WHAT_IF，不覆盖批准值。
- 真实FIT1214点；默认采样80不足；0.05/8采样1193，但正X角差52.28°。负XWHAT_IF角度合格却competition_unresolved，三holdout直接残差诊断均不达门。89帧偏差稳定，不支持靠延长录制解决。
- 9月30实际SDK零extrinsic记录不能证明10月2日16:36录制配置；source XYZ本地链透传，但SDK侧可变换。缺真实录制参数应保持BLOCKED。

本区间结束应得到“可复现工具 + 经反例审核的研究原型 + 有根据的下一步选择”，而非保证真实candidate或提前宣布物理通过。
