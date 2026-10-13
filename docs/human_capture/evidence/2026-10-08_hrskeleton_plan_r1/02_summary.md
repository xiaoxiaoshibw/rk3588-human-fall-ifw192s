# 下一阶段计划制定轮

日期：2026-10-08，Asia/Shanghai。状态DRAFT_READY_FOR_DISPATCH / PLAN_RECORDED，未开工。

制定计划、独立工单HR-SKELETON-OFFLINE及18项唯一验收表；全部SKO-01～18初始NOT_RUN。顺序为可信绑定/固定窗口→真实人工身份/可见性→可逆标准化→5–7粗结构节点→独立时序→固定验证/独立复审。现有五段首批预登记100唯一原始帧、空场双分支时120分支行；工作量条件不等于精度门槛。

原W03/SEM/WD02阻断保留，旧HR-07/08关闭和HR-09/ML封存不变。新计划不放行正式W04/W05；真实节点试验从人工确认完整人体簇开始，节点必须有当帧原row支撑，缺头/举手歧义/左右不明不猜补。精度未被承诺，已有数据不称全盲留出。

## 本轮实际检查

| 命令（均从仓库根） | exit | 范围与结果 |
|---|---:|---|
| python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrskeleton_plan_r1/record_plan.py baseline | 0 | master/cfbb80c…；6263起始路径、43,359,798,841字节；tracked/untracked+ignored captures/HC evidence/console dist |
| python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrskeleton_plan_r1/publish_plan.py（首次） | 1 | record_plan导入误触CLI，IndexError；尚未写三项登记或return。保留publish_initial_error.log |
| 同命令修复导入保护后重跑 | 0 | 18唯一ID、全部NOT_RUN、15个相关链接；没有算法执行。详见01_document_checks.json |
| python -B -W error -X utf8 docs/human_capture/evidence/2026-10-08_hrskeleton_plan_r1/record_plan.py verify | 0 | 6263旧路径核查；三文档原字节前缀不变，范围外变更/新增0，HEAD不变。详见integrity.json |

基线/dirty文件、计划/工单/唯一表SHA、链接/结构检查及最终manifest在本目录。Git关于原LF/CRLF的提示仅是读diff时已有提示，未运行换行转换或checkout。

新增：HUMAN_SKELETON_OFFLINE_PLAN.md、HR_SKELETON_OFFLINE_ACCEPTANCE.md、tickets/HR-SKELETON-OFFLINE.md、returns/HR-SKELETON-OFFLINE.md及本目录。仅末尾追加：HC README、tickets/INDEX、HUMAN_RECOGNITION_NEXT_STAGE_PLAN。所有生产、captures、SEM R1/R2及其return、其他旧evidence与用户已有dirty差异保留。

本轮未执行骨架、人体算法、采集、部署、板端连接、模型、生产接入；没有新增真实source:human标签，没有commit/push。实读ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。现在停止在计划可转发；实施须新用户明确开工授权。
