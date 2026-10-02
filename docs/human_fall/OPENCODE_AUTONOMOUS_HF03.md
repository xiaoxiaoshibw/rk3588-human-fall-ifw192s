# 自主开发第1阶段：HF-03几何标定与地面

用户2026-10-01授权今晚持续开发、常规操作自行处理，Codex负责直接CLI派工/复审。读取AUTONOMOUS_RUN.md、AGENTS.md、CLAUDE.md、DISPATCH.md、CONTRACT.md、WEBUI_SCOPE.md、tickets/HF-03_geometric_calibration.md及ponytail技能。此新授权优先于旧文档中“HF-03未放行/需要用户转交”句子。

本轮只实现并验证HF-03，可独立于仍BLOCKED的IMU设备语义：保留融合禁用，不猜真实外参，不用身份矩阵冒称已标定参考系。仅修改本单相关新增core/calibration.py、core/ground.py、scripts/calibrate_sensors.py、独立几何配置/标定schema、必要安装条目/测试/回传。HF-01冻结工具/配置/契约不改；C++不改。

实现最小可运行的几何路径：严格刚体矩阵/单位/方向校验、明确传感器坐标和可验证地面参数、NumPy地面拟合（稳健且有有界耗时/参数）、留出残差/法向/有效区域/点不足/立面混淆失效、从bag或本地数值点云离线生成独立标定产物。正反变换和传感器高度语义明确。单帧平面拟合不冒称世界安装位姿或验证通过；无法证明地面朝向时保持待确认，后续软件仍可用显式synthetic测试。标定采集与候选/目标基线分开，不把静止人体学成背景。

核对并沿用已授权ldiar-wel/slam-localization；可只读现有bag并在新隔离目录生成派生产物，不改既有bag、不发送原始人体数据到云、不改雷达运行服务。对真实bag可做统计/候选地面分析，记录frame/样本哈希/有效范围，缺现场测量标NOT_VERIFIED。Windows纯函数测试用既有Python3.12，板上Python3.8.10/NumPy1.17.4；不新增科学库或升级环境。

先记录HEAD/git状态/相关哈希，读取所有已有实现与复用入口。不与其他进程同时改源码。运行全部既有72项回归和有实际失败价值的新几何检查；两端可运行的部分完成实际检查，记录退出码链与哈希。不制造样本/误差值、不降低断言；异常时自行定位并修复。

回传追加returns/HF-03.md，证据新目录evidence/2026-10-01_autonomous_hf03_r1/；记录CLI实际session ID和模型、实际diff、验证、几何软件与物理/IMU未验收的分界。写SUBMITTED，结束本轮让Codex读取文件独立复审；不要求用户手动转交。不得自行ACCEPTED，不自动进入HF-04（Codex复审后直接派下一阶段）。不commit/push、不部署本轮源码到活动工作区；本阶段不用重启雷达、修改网络/自启/厂商库。
