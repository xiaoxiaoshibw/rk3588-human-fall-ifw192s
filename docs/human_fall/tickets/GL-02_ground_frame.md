# GL-02 局部地面变换、标定产物与有效期

执行：Codex直接派OpenCode CLI `opencode-go/deepseek-v4.1-flash`；审核：Codex。当前（2026-10-02）：R7软件PASS（A01–A12），设备NOT_RUN、真实物理BLOCKED。GL-03软件前置已满足，本轮未启动。物理未确认只允许明确标注的候选配平预览。

执行按[流程v2](../WORKFLOW.md)与[统一验收v1](../GL02_ACCEPTANCE.md)，先集中诊断所有入口/状态再实现。最新结果：[R7最终复审](../evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md)；[CLI恢复与成本控制](../CLI_RECOVERY.md)。下方历轮附记仅保留追溯，已闭合的软件不再按旧提示词重做。

## 任务

2026-10-01前置：GL00 R4契约/软件PASS、GL01 R4软件PASS，真实地面/来源/物理BLOCKED。仅数学软件/显式候选配平预览授权；读取 ../evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md 与GL00获审契约，不部署。

1. 在现有calibration纯模块中实现PLAN约定的ground_local基底和R/t。严格验证n单位长度、d/frame/轴参考、正交/右手性、米制与逆变换；参考方向近似法向时拒绝。
2. 原点为雷达原点地面垂足；X来自经确认的源参考轴投影，Y=n×X。保存此约定，不能称北向/底盘前向；坡面与重力关系标注明确。
3. 地面派生产物采用GL-00获审兼容策略，不冒用已有measured_mount证据或强置extrinsics_verified。保留底盘、地图和IMU外参unknown。
4. 产物记录source/ground frame、ground_id/版本/hash、R/t、n/d、ROI/有效范围、数据来源、质量、物理核验与创建时间。完整写新版本，不覆盖历史；异常产物不能启用。
5. 分清几何可用、地面身份已确认、物理高度验证通过三个条件。候选变换可以诊断显示，但不能进入已验证离地结论。
6. 实现必要的加载/切换边界；固定场景冻结变换，版本切换使旧快照/位置/站姿基线资格失效。先使用显式节点启动配置加载，不为了未来做通用热更新框架。
7. 监测逻辑只对有可信地面支持的区域作残差检查，支持不足输出unknown/degraded。显著连续变化输出需重标定，不声称检测了全部水平移动/yaw。

## 允许修改

calibration/ground相关纯模块、标定CLI/配置、必要node_runtime加载与基线失效入口、相关测试和兼容契约扩展。保留HF01与原始话题语义，不触driver/IMU融合/confirmed。

## 验收

- 多组非零倾角、高度与方向；地面Z≈0、雷达Z=d、任意点Z=n·p+d；逆变换恢复点。
- 轴投影退化、非刚体、非法单位/frame/version、损坏文件、无标定不能身份矩阵假成功。
- 老v1加载保持原义，新字段未知的客户端不会默认已验证。
- 新标定不继承旧目标基线或混用旧快照；源stamp/seq/epoch不变。
- 输出产物样例、数学检查、生命周期日志、`returns/GL-02.md`；Codex确认数值变换及验证标志分离后放行GL-03。

## 最新用户派工方式与GL02 R1复审 / 2026-10-01

用户要求“接下来任务让我手动给cluadecode”。后续改为用户手动交Claude Code；Codex只准备具体工单/独立复审，不自动调用OpenCode继续返工或派后续。当前GL02 OpenCode R1已结束exit0，Codex262常规回归通过但独立6方法6失败，软件REWORK/真实物理BLOCKED，GL03未放行。手动下一步为AI_PROMPT_GL02_CLAUDE_REWORK.md，详细证据evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md与40_*。GL00/01已审软件不重做。无活动实现写入者，不部署/采集，旧失败保留。

## GL-02 Claude R2 Codex独立复审 / 2026-10-01

软件REWORK，GL03不放行；继续用户手动派Claude Code。Codex独立262回归/原6方法exit0；新增集成5方法5失败，补类型检查后最终7方法7失败exit1（evidence/2026-10-01_gl02_r2/50～54）。R2闭合原反例，但实际加载仍可保留旧ground、裸块版本错配；monitor失效仍发布位置/继续相关观测、散点误报整体变化、重标定被一帧清除；float版本/mixed bool矩阵仍通过。详同目录CODEX_REVIEW.md；下一步手动AI_PROMPT_GL02_CLAUDE_R3.md。板端兼容NOT_RUN，真实物理BLOCKED，未改生产算法/部署/采集。

## GL-02 Claude R3 Codex独立复审 / 2026-10-01

R2原七方法/267全回归/R2静态六方法独立通过（GL02 R3 evidence50～52），已闭合部分保留；新增其他入口四方法四失败，补单侧遮挡后最终五方法五失败exit1（55_*）。软件REWORK，设备兼容NOT_RUN/真实物理BLOCKED，GL03不放行。剩余为配套局部更新calibration版本错配/caller引用、同GDID新calibration版本未清旧资格、monitor不可用仍accepted基线请求、10%单侧遮挡误锁存整片变化。详evidence/2026-10-01_gl02_r3/CODEX_REVIEW.md；用户手动下一步AI_PROMPT_GL02_CLAUDE_R4.md，不自动派工。生产算法未由Codex修改，未部署/采集。

## GL-02 Claude R4 Codex独立复审 / 2026-10-01

R3原五方法5/5、R2七方法7/7、静态6/6、fall 271/271、follow 2/2、两个webui各18/18均由Codex独立实跑通过。新增reload/已有pending三方法3失败exit1：空或相同配套reload沿用旧版本却丢input.sha256/evidence/note等完整产物字段；已accepted基线请求在随后monitor持续不可用超过10秒时仍pending且无终态回执。软件REWORK，GL-03不放行；设备兼容NOT_RUN、真实物理BLOCKED。详[evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md](../evidence/2026-10-01_gl02_r4/CODEX_REVIEW.md)与57_*。手动下一步[AI_PROMPT_GL02_CLAUDE_R5.md](../AI_PROMPT_GL02_CLAUDE_R5.md)；只修这两项，不自动派工。生产源码/原测试/driver差异/Windows软链接表示保留，未部署/采集/commit/push/reset。

## GL02最终Codex验收 / 2026-10-02

R5→R7原缺陷及完整入口/请求矩阵已闭合，A01–A12软件PASS、D01 NOT_RUN/P01 BLOCKED。最终证据与CLI上下文恢复见 ../evidence/2026-10-02_gl02_r7/CODEX_REVIEW.md；原始成功/失败及用户差异保留。GL03软件前置满足，本轮未启动；实际设备/物理启用仍不得用合成结果代替。
