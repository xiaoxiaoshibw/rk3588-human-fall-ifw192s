# 给Claude Code：GL-02 R5，保留完整reload产物与结束已有pending

现行执行流程：[WORKFLOW.md](WORKFLOW.md)；统一验收基线：[GL02_ACCEPTANCE.md](GL02_ACCEPTANCE.md) v1。先对全表集中诊断/检查缺口，再修已知根因；提交按[RETURN_TEMPLATE.md](RETURN_TEMPLATE.md)逐条回传。此更新替代只补上一轮反例的方式，已有失败/范围/手动派工不变。

工作目录 `D:\Code\ldiar`。用户手动派发；仅本轮，不调用OpenCode、不启动GL-03、不部署/采集、不commit/push/reset。只回传SUBMITTED/BLOCKED，由Codex独立复审。

先读根AGENTS.md、CLAUDE.md、ponytail真实SKILL.md、GL02工单/GROUND_LEVELING_PLAN、冻结契约、最新REVIEW_LOG和returns/GL-02.md；本轮权威：

- `docs/human_fall/evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md`。
- 同目录 `codex_r4_reload_checks.py`、`60_codex_reload_final.txt`：3方法3失败，原样复现，不改弱；57首次记录仍保留。
- 前轮R4要求和已通过边界继续有效。R3五方法、R2七方法、静态六方法和271回归已独立通过，保留数学/严格类型/CLI独占创建/遮挡不锁存/整体平移/latch实现。

## 集中检查后，修两项已知根因

1. `ground_context_calibration` 不应仅沿用旧ID却丢掉父产物。空reload、完全相同ground+derived应完整validate/deepcopy现有canonical，保留input.sha256/evidence/note及其他原合法字段、monitor连续性/旧资格，不造新版本。真正局部更新仍须绑定完整一致的新上下文，保留适用的来源证据；对不再一致的constrained_ground/关联记录明确校验或拒绝、或用明确理由失效，不能静默删来源后冒用原版本。不要自动复制不再有效的verified标志，不取消配套更新入口。完整artifact路径已正确，不大重写。
2. `capture_baseline`已accepted后monitor变unknown/degraded/锁存时，collector必须有明确终态及request_id回执，不能无限pending。本轮选择A10的首个失效处理帧取消/失败并回执、ready退休策略，恢复后重新请求，不继承失效样本；这是授权内本轮选择，原R4允许的有界超时/暂停不能被追认成新缺陷。无新云帧时用既有接收单调钟watchdog判断失效并收口，不推进源时间采样时长、不用接收秒补源秒；同时检查ROS终态回执发布路径。先复现未覆盖路径，不凭风险宣称新缺陷。保留原消息schema/辅助IMU/云显示/release，复用collector/回执；确需baseline或ROS wrapper的最小生命周期连接时记录范围理由，不改driver/网络/活动节点或采样时钟语义。

## 验证与回传

- 实现前对A01–A12及两个矩阵一次检查完，缺检查如实记录并补最小有效检查，同根因的全部入口一起处理。既有条目的新失败集中修复，新增功能另列后续。诊断/新检查与条目结果写R5新证据，不改旧独立脚本；无帧、恢复、ready及重复request_id路径不得被连续坏帧检查替代。
- 原样跑R4新3方法全过；R3五方法、R2七方法、静态六方法全过，完整fall/follow/webui回归。至少补同版本空/配套reload元数据保留、真实accepted后monitor坏时终态回执、恢复后不继承失效样本，以及ready基线处理；不要只手动赋pending绕过请求入口。
- 新证据 `docs/human_fall/evidence/2026-10-01_gl02_r5/`，实际命令/退出码/源码与冻结SHA、branch/HEAD/status、对应限制。旧成功/失败/样本/用户driver差异/Windows软链接表示保留；default.yaml/geometry.yaml与候选算法/UI/driver/时间语义不改。
- 板端只有可达且原授权允许时做隔离兼容，不动活动节点/网络/依赖；不可达如实NOT_RUN，不换主机/保存凭据。雷达向下看、具体角度未知；机器人总高1.4m、眼球离地约1.1m不等于点云原点高度；真实物理/外参/IMU/confirmed仍BLOCKED。合成阈值不标实测。
- 向 `returns/GL-02.md` 文件末尾追加“Claude Code GL02 R5”，不要插在历史R3/R4中间；未跑项如实报告。完成后用户回Codex“复审GL02 R5”。
