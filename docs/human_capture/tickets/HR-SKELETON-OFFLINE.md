# HR-SKELETON-OFFLINE：人工确认人体簇上的离线粗骨架

- 版本v1；2026-10-08（Asia/Shanghai）。状态 **DRAFT_READY_FOR_DISPATCH**；用户本轮仅授权制定计划，未开工。
- 阶段计划：[HUMAN_SKELETON_OFFLINE_PLAN.md](../HUMAN_SKELETON_OFFLINE_PLAN.md)。
- 本单唯一验收表：[HR_SKELETON_OFFLINE_ACCEPTANCE.md v1](../HR_SKELETON_OFFLINE_ACCEPTANCE.md)，SKO-01～18；与SEM/T37/T38/V2各表独立，不能互相放行。
- 性质：正式W04/W05前的受控PC离线可行性；不声明主线进入W04/W05，不重开关闭的HR-07/08，不激活HR-09/ML。
- writer：用户开工后由本聊天Codex单writer执行；无自动子代理/OpenCode或模型切换。先实读 `C:/Users/30680/.codex/skills/ponytail/SKILL.md` 并在return记录。

## 开工前必读

AGENTS.md、HC README、本计划/工单/唯一表；W01_W09_FINAL_ALGORITHM_PLAN.md和HUMAN_RECOGNITION_NEXT_STAGE_PLAN.md；SEM R2 REVIEW_R2/01_sem12_fix/03_blocked_revalidation/05_integrity/delivery_manifest、R1 pass3/binding/clusters/frames/votes；现有pc_apps/human_replay坐标/切片/PCA/Tracker消费者；关闭的human_limb README只读了解反模式，不能运行其服务或把旧pin/密度评分当人体真值。

重新记录branch/HEAD、tracked+untracked及ignored冻结输入/旧evidence的SHA，核当前树与本轮授权。原数据28B布局、job目录、固定SHA按计划复核；不直接运行会写旧evidence的历史main/prepare/run。

## 执行与最小范围

1. A：固定五段/原分支、预登记100唯一帧/120分支行、输入与数据划分；源或成员不一致阻断该输入。
2. B：真实人工identity/person_id/连续性与节点可见性；开发会话最小可信GT满足计划条件才做真实人体节点。无GT完成独立工具部分，对应真实项保持BLOCKED。
3. C：纯XY平移标准化，保留Z/逆变换/row；排无效源row、拒绝MIXED/UNKNOWN资格；不重新背景/cleanup/聚类、不裁干净圆柱。
4. D：五基础节点+可支撑的A/B下肢，最多七；头/手歧义、缺头、稀疏、家具拒绝；每有效观测有可重建support_rows，零支撑不猜补。
5. E：独立SkeletonTracker，实际timestamp、缺失/重获/seek/身份/坐标版本切换reset；raw与filtered分列，不修改human Tracker/Fall。
6. F：开发集参数冻结后跑固定验证/难例/空场；逐ID、真实分母/节点GT/UNKNOWN/失败、独立raw核查、必要相关回归、完整性和return；停在SUBMITTED可复审。

参数v1、节点支撑定义、评分含义和输出schema在首次算法运行前写清；参数只在开发资料上确定，验证失败保留，不改样本划分凑通过。已观察资料不称盲测；没有精确关节GT不报关节精度。

## 写入与禁止项

只新增新轮 `docs/human_capture/evidence/<日期>_hrskeleton_offline_r<N>/`，以及本return末尾追加。所有现有src/pc_apps/webui/captures/旧evidence/冻结配置和算法只读；新原型Python3.8兼容、stdlib+已安装NumPy，无新模型/重依赖。改计划/契约须保留旧版本并经对应范围授权。

不部署/采集/连接板端/重签安装artifact/启生产旗标/commit/push/reset/checkout/clean。WD02额外历史代码检查不删除、不绕过、不换job；本单不消费WD02，其BLOCKED保持。人体分类、背景、跟踪、Registration、Fall算法均不改。

## 交付与停止

按计划§8交付；return追加 `returns/HR-SKELETON-OFFLINE.md`，字段参照HF RETURN_TEMPLATE但不进入HF/GL流程。逐SKO ID PASS/FAIL/NOT_RUN/BLOCKED；GT缺口和节点效果分开，synthetic/工具通过不替代真人验收。

发现绑定不可核验、需要改生产冻结项、需要伪造GT或改变正式前置才继续时，停止对应依赖、保留证据，继续独立可完成部分。提交后不自动实施W06/W07/W08/W09或生产接入。计划登记轮不执行上述算法，也不填写预期PASS。
