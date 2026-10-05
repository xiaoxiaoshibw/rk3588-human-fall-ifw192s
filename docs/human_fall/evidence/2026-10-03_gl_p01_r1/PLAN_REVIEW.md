# GL-P01 派工前计划审查 / 2026-10-03

用户引用01a0fe21-e8c8-7272-877f-b69136ed43aa并要求开始开发；已读其最终计划审查及现场文件。授权按本地软件开发理解：先执行计划B生产R/t能力，不含设备/采集/部署。GL04 DPR-only依旧NOT_RUN；本轮Computer Use因无法可靠确认Edge URL停止，未继续UI输入，正式合并前置未闭合。没有GL04代码FAIL，不派形式R8。

唯一表GLP01_ACCEPTANCE v1含P01-P06/D01与M01-M12组合。已有校验/producer→NodeCore→ROS projection→strict JSON→preview parser链已读；只改一个producer、集中interop回归，NodeCore/ROS无需先改。正式旧JS暂不支持新块，故本单验证当前已审preview consumer软件能力；不能称正式实际端到端ready。

不变量裁决：validated canonical child唯一投影源；源frame/显式parent绑定由既有共享校验守门；white-list避免把artifact evidence大块发到UI。fullartifact only ground=None旧unknown资格保留。支持区当下无真实轮廓，null+wire reason；auto AABB或trusted ROI包络不变polygon，不提升物理flag。软件序列化/透传能通过不等于设备当前配置有真实标定。

M01-M12完整设计前置；GL02/03已有生命周期检查可复用本轮源码相关回归，非变更数学/HF模块不无由全量重跑。服务先<=1分钟新probe，default DB与指定Go Flash，新紧凑实现session；失败保留日志不换模型不启动第二writer。

范围/SHA：00_before_manifest.json记录branch/HEAD/dirty tree、所有git tracked及未忽略untracked文件（含未跟踪production source），冻结用户及旧证据。单writer提交停写后Codex独审。C离线适配另做只读审查，不与本单并行写源码，不以新工单绕过设备判据/ROI缺口。
