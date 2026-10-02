# GL-02 派工 / 2026-10-01

前置GL00 R4/GL01 R4软件PASS，物理/真实来源仍BLOCKED。按GL02工单、GL00 R4获审25_contract_extension_draft.json及GL01 CODEX_REVIEW.md实现，仅本单，不自行GL03。使用本目录ponytail_SKILL.md哈希验证副本，DeepSeek V4.1 Flash，短工具输出。

范围calibration/ground、CLI/独立配置、必要node_runtime加载及基线失效入口、相关测试与兼容契约扩展。冻结default.yaml/geometry.yaml/旧契约原义/driver/UI/candidate算法不变；不部署、不采集。新字段ground_derived为optional嵌套schema_version=1、units=m、from/to/frame/ground_derived_id/R/t/n/d/ROI/hash/source/创建时间/质量/physical_verified及assumed/confirmed区分。旧frames.reference、T_reference_lidar、IMU、extrinsics_verified不冒用。

数学按PLAN：o=-d*n；源参考轴a投影单位u，v=n×u，R rows[u;v;n]，t=-R*o。严格拒绝非法frame/units/bool/nonnumeric/NaN/Inf、非单位n、非刚体/反射、近法向参考轴、未知nested version、变换与n/d不一致、damaged hash或版本等。默认source+X只作显式记录的朝向约定，不标世界/底盘前向。复用现成transform validator但不得用make_transform(measured_mount)给derived伪外参。

geometry_calibration读取时，有constrained_ground或ground.constrained须走GL01严格validator，不能仅旧validate_ground_plane。源数组和标识保留。几何可用/地面身份/物理高度核验分开；只有preview不能升级physical/extrinsics/IMU flags或开启confirmed，旧v1无新字段ground模式禁用。

CLI显式导出派生变换至新产物，不覆盖已有输出/历史标定；记录规范化hash/ID绑定实际内容与来源。换标定/加载损坏使旧快照/目标位置/站姿基线资格失效，明确未知；复用现有绑定/reset入口，不引入通用热更新框架。生产节点只显式启动配置加载，不发布服务/原始话题改变。

监测只使用可信已知地面区域支持，固定变换不逐帧漂移。稀疏/断流/不可信ROI输出unknown/degraded；连续实质变化要求重标定，不能声称全设备运动检测。复用GL00软件残差/支持门槛，不自设放宽阈值；若持续时间需新门槛，给清楚有限合成设计值、来源及未实测限制，经复审才能放行。

验收多倾角/方向/高度；groundZ0、sensorZ=d、任意Z=n·p+d、逆变换、参考方向退化、老v1语义、新参数损坏/未知版、标定切换绑定与support不足/变化失效。Windows纯回归，板端隔离3.8.10/1.17.4兼容，两端SHA及inner/outer exit。真实地面/窗口1.1m偏移/机器人1.4m高度误差保持BLOCKED。近期hardware_inventory.md有外来截图粗估约26度，仅参考不是实测。

回传returns/GL-02.md，本目录证据，原失败/旧产物不覆写。执行者只SUBMITTED/BLOCKED。Codex独立审查后方可GL03。
