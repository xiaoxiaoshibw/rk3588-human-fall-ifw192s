# GL-E02 R1 有效source / 测量 / 地面身份证据分层

本单纯离线，未fit，未连接板端。唯一验收GLE02 v1。原89帧为已曝光开发/工程诊断数据，不能成为未见最终物理holdout。

## 已完成证据子项

- 照片实际查看、SHA与PHOTO_EVIDENCE_01一致：b080a67e2fb63d8c2688230f3aa7dd0ce48e0e2e049bc82cb149c74ece7394d0。真实现场及参考视向正确=user_confirmed，不重复询问。
- 用户本轮确认“刚刚拍摄”，精确时间未提供；07_user_reply_01为新记录。其recorded_at和measurement.observed_at仅为本轮归档时间，不能当照片拍摄时间。安装是否自旧录制后改变未答，保持unknown。
- 木地板连续可见，左右桌/桌脚、右桌下箱板、植物/设备为障碍/遮挡线索；条带/接缝区域独立列出，未断言有无高度差。
- 复用E01已审sidecar，当前实际NPZ/meta/bin/SHA与bag声明、全部89frame ordinal/seq/stamp/offset/count/drop及既定round6窗口对应。source为innolidar，单位m只是metadata_declared；未回填旧NPZ来源标志。source_chain在新包中记GL-E01_cited_and_correlated，而非重新宣称现场测量已验证。

## SDK→publisher→bag→adapter

source_driver.cpp读extrinsic.valid、XYZ、roll/pitch/yaw进入SDK decoder_param.transform_param。本地SDK data_types.hpp描述XYZ单位m、欧拉角rad，但没有给出原生轴向、原点位置或内部施加R/t的实现和顺序。SDK .so、headers、driver wrapper/publisher和当前config均绑定实际SHA，作为本地上下文，不填作旧录制run版本。

publisher.toRosMsg逐点复制point.x/y/z，不再施加可见旋转；header.frame_id来自ros_frame_id字符串，不是轴约定的证明。E01已有完整bytes/XYZ证据支持bag→canonical bin→NPZ保持XYZ。现有厂商资料目录没有能绑定此次SDK有效轴/光学窗口到点原点偏移的IFW192S安装图；不能用AISC-3830手册或他种设备假定。

当前PCAP config与保留SDK日志enabled六零只能说明所见上下文。9月30日志/较晚日志、当前文件mtime和当前配置均缺10月2日run+config+SDK/code联合绑定。有效source轴向、SDK是否/如何已变换、world-up表达仍unknown。未知不会自动翻X或重加R。

## 物理缺口与解除条件（P01 BLOCKED）

| 项 | 已有证据 / known观察 | 缺口 / 所需独立证据 |
|---|---|---|
| 照片 | user_confirmed真实/视向；刚刚拍摄 | 精确拍摄时间、照片与录制同场景/同安装绑定未知；不能以mtime补 |
| source/SDK | publisher复制SDK XYZ、header innolidar、E01来源链 | 录制run/config/SDK及代码归档、有效原生轴/R/t方向与启用状态 |
| up/安装 | 用户已确认下视 | source系独立up、角度及测量误差；26度粗估和PCA均不能补值 |
| 原点 | 高度必须相对于point_origin | 厂商原点定义、窗口偏移、独立高度和误差；约1.1m是窗口位置，拟合d≈1.33m不是尺量 |
| 地面源行 | 照片地板语义及前/中/侧空间计划 | 人工地标到原始3D源行对应、确认人/时间/依据、source SHA与新selection ID/version |
| FIT/validation | 现有indices全链可复用 | FIT单source frame；至少3个互异且不同于FIT的validation frame_group，空间分布另记；目前selection=null |
| 物理门 | 软件门与物理资格分开 | 独立审查测量/身份/不确定度与预登记容限，最终物理holdout不能称当前89帧未见 |

不把“区域混杂”“地面不平”“模型偏差/外推”“跨帧变化”归并为单个确定解释。不重做I06、不做K2/K3/IRLS/比较阈值研究，不删失败点，不从FIT残差带造验证源行。

## 已准备的未来受控记录清单（未执行，需另具体授权）

旧录制无法绑定时：先固定安装；记录设备/SDK/driver/code/config SHA、启动run和明确from/to/单位/启用状态；保存原点厂家定义、窗口偏移及独立up/高度测量与方法/仪器误差；用人工现场/3D地标确定FIT及三个不同源frame_group验证集合；采样前预登记允许误差与保留方案，采样后封存SHA、窗口/安装稳定性及未曝光留出数据。只需局部配平，不要求完整地图yaw/相机外参/IMU融合。此清单不启动新采集、板端算法、生产接入或部署。

## schema与版本边界

request_id为整个request除ID外的规范JSON SHA；selection_id为selection除ID外的SHA，修改需新ID。不设缓存。known表示有引证的观察，binding=null或run/config/SDK不齐使recording_eligibility=unknown；binding错误直接拒。完整引用也只能cited_pending_review，不能证实事实为真。

测量uncertainty约定：source_axes/world_up_source/installation_angle_deg为度；height为m；description/statement不定量。SDK rotation是sdk_native→有效source的3×3 proper R，translation_m同方向，enabled=false须identity。world_up_source是直接表达在有效source的单位向量，不能把相反方向矩阵暗中反转。

出包白名单五JSON；只pending、physical/extrinsics/candidate/runtime=false。目录限定本工单RUN_ROOT下新子目录，不能写capture/生产/历史证据或已有out；JSON拒NaN/Inf与未知晋级字段。工具能查结构、文件身份、源成员，不能签造人工事实。照片确认单独保留，不因物理链未闭合抹掉已完成子项。
