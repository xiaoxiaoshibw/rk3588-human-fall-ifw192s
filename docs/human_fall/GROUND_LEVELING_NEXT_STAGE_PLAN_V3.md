# GL主线计划 v3：现有安装参数先落地，证据与适应能力继续复用

最终阶段新增（本轮只规划）：[自适应地面配平与可信度仲裁正式计划 v1](ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md) / [接口与状态契约](ADAPTIVE_GROUND_LEVELING_CONTRACT.md)。GL-A～GL-I均PLANNED/实现NOT_RUN；原静态方案不替换。现行物理高度记录1.14m、显示参考Ry(+26°)+Z≈1.340m明确分离；下文1.1m/26°属于当时历史阶段参数，不改旧证据。

当前覆盖：GL-B01区域复核软件独审完成、场景木地板/工作台语义与75cm参考已确认；GL-C01单FIT联合反解小点作者自验完成，数据质量FAIL如实保留，按用户要求STOPPED、未派独审或进一步开发。见[当前收口](evidence/2026-10-04_gl_c01_r1/20_CLOSEOUT_01.md)。下文较早进度仍为历史记录。

当前进度2026-10-04：阶段A/GL-N01已按26°/1.1m真实执行并完成软件独审，SUBMITTED/STOPPED；[前后图](evidence/2026-10-04_gl_n01_r1/07_before_after_frame05_01.png)/[收口](evidence/2026-10-04_gl_n01_r1/22_CLOSEOUT_01.md)。低位点带近水平但仍在z0以下，阶段B优先核地面源行和偏移；C自动修正及D接入/设备未启动。

2026-10-04。用户授权重新设计并继续按约26°下俯、1.1m高度开发。当前首单[GL-N01唯一验收v1](GLN01_ACCEPTANCE.md)，执行范围为本地离线名义配平。GL-E01/E02/I06已经完成的软件成果保留，不重复返工、不追改旧真实失败。

## 1. 当前目标

先交付真实点云的固定安装变换、同帧前后可见对照和可改pitch/height的入口。此阶段无需等完整测量/人工地面源行才动起来；用户给定参数明确可用，标记名义安装而非独立物理精度已验。地板实际仍有斜率/偏移就原样显示和统计，下一阶段据此改进。

先旋正，再沿旋正后的竖直Z平移。采用初始有效source轴X前/Y左/Z上，roll/yaw=0约定：R=R_y(+26°)、t=(0,0,+1.1m)，p_nominal=R*p_source+t。源雷达原点到nominal系z=+1.1；source地面在旋正后z≈-1.1，转换后目标z≈0。“雷达从其位置下降1.1m到地面”和“源点坐标加1.1m得到地面坐标”是逆向关系。from/to、单位、source轴假设写入版本，不能混作camera移动或map-world外参。

## 2. 执行顺序

| 阶段 | 具体工作 | 交付和完成标准 |
|---|---|---|
| A，当前GL-N01 | 以26°/1.1m生成固定R/t；全部89帧只读变换，保留有效mask与源行；输出frame统计和前后视图；pitch/height可配置 | nominal_model.json、nominal_leveled.npz、frame_stats.json、view.html；合成已知地面误差为浮点精度、inverse一致，真实结果可见且不掩盖偏差；软件独审 |
| B，独立地面复核 | 在A旋正结果中依据照片/原始3D地标确认FIT与三个不同frame_group的地面源行；使用E02打包；分别看斜率/偏移/混杂 | 新selection ID/version；每区源行/人工依据/全点残差与实际尺量分列。身份未核可继续观察，不能把观察统计签成物理PASS |
| C，有条件微调/变安装适应 | 参数更换首先重建固定R/t和版本。只有B证据表明名义误差需修正，再复用已有单帧约束RANSAC/K1 TLS与三组验证求修正 | 26/1.1、其他pitch/height测试可复用；新参数/选择/标定使旧结果失效。不能按被验FIT残差挑validation；约束height interval由明确误差记录生成，不拍脑袋扩大 |
| D，接入与设备 | 用获审模型/真实support接GL-P01消息与preview，完成GL04真实DPR；随后具体授权范围内RK3588物理/性能与发布 | 数值、source/版本、选择/框/显示一致；设备精度/性能单独实测；具体release可回退。当前单不执行 |

## 3. 前面工作的用途

E01的源bag→bin→NPZ链保证变换处理正确原点/帧/源行；E02把参数来源、未知、照片和选择绑定分开；GL02/03提供参数版本变化后的失效规则；I05/I06保留复杂场景的竞争/预算/拒绝信息，K2/K3未获采用就保留K1。indices支持不规则地面源点，后续安装改变无需重做选择协议或基本变换。

当前参数可配置意味着换安装无需改代码；已有拟合/证据工具为后续基于地面观测修正提供能力。两者区别明确：本单完成的是给定参数适应，不能宣称未知姿态已经自动估计。

## 4. 本单实现边界

新三源码core/nominal_leveling.py、scripts/level_capture_nominal.py、tests/test_nominal_leveling.py。复用load_adapted、strict_numeric_array、calibration数值变换与校验，不改冻结ground/calibration/default/geometry/perception/driver/webui。旧draft正X up和[1.2,1.7]只读历史；新参数模型不继承这些值，不生成旧fitter可直接消费的伪valid结果。

输出kind=nominal_installation_leveling，frame=ground_nominal，status=nominal，physical/extrinsics/runtime=false。这是能够变换/显示的数值结果，不是空pending，也不是已测世界外参；冻结运行时资格消费者必须拒绝它。新output独占，原数据不改。保存全部有效点与原pooled rows，invalid零点/非finite单独计数；显示均匀采样仅影响画面，不影响数值输出。

## 5. 检查与分工

按GLN01 N01–N06/S01/P01/D01/Q01–Q06集中检查：地面/雷达原点/正反号/先后顺序、多pitch/height、单位/frame/NaN/类型、同ID异内容/caller/新ID、保护目录、同源每帧源行、不晋级资格。独立测试不能只抄当前矩阵，使用标量公式与已知GT。真实图不作为ground身份或物理误差证明。

Codex唯一writer，OpenCode Go Flash/defaultDB承担只读独审和可委派的重复核查/整理，避免重复全量研究；每次新派工先≤1min无工具probe。完成自验、SHA/manifest/回传后停写；独审只读stdout、新编号保存结果。当前不板端、不部署/采集、不IRLS、不给旧检查器同名覆盖。未来物理精度验收保持独立，不再次把它变成A的前置阻塞。

## 6. 最终阶段：Adaptive Ground Leveling Framework（新规划）

在既有固定配平、来源/资格/坐标/预览基础上新增模块化质量、相关性保护的三估计器仲裁和六状态时间控制。经典TLS/SVD/RANSAC保持其方法归属，自研范围是适用于本项目的框架与集成。参考模型继续可用，observed compensation不覆写physical1.14m。

| 新工单 | 最终阶段内容 | 放行边界 |
|---|---|---|
| [GL-A](tickets/GL-A_adaptive_estimator_interface.md) | 同域三估计器/统一接口与来源 | 后续明确启动、软件验收 |
| [GL-B](tickets/GL-B_adaptive_quality.md) | full/逐区残差、support、coverage/退化、quality scores | 不用低RMS或score替代ground身份 |
| [GL-C](tickets/GL-C_adaptive_consensus.md) | GOOD/DEGRADED/BAD与TLS/SVD相关性保护 | LS-only不能靠2/3更新 |
| [GL-D](tickets/GL-D_adaptive_temporal.md) | median+EMA+rate、INIT/ACQUIRING/STABLE/DEGRADED/HOLD/RECOVERING | 低可信保持，age过期几何失效，不自动清旧latch |
| [GL-E](tickets/GL-E_adaptive_offline_leveling.md) | source finalR/t、只读离线应用 | 不接生产实时链 |
| [GL-F](tickets/GL-F_adaptive_replay_validation.md) | 八场景、真实数据/独立holdout、false updates与profile冻结 | 已曝光ABC非最终holdout，缺证据保持BLOCKED |
| [GL-G](tickets/GL-G_adaptive_diagnostics_webui.md) | 三列、confidence/consensus/state/FINAL与事件 | 独立preview先行，不替换正式WebUI |
| [GL-H](tickets/GL-H_adaptive_shadow_mode.md) | 目标机实时只读shadow和性能对照 | F/G证据、环境核验及后续具体授权 |
| [GL-I](tickets/GL-I_adaptive_controlled_activation.md) | 人工enable/disable/freeze与版本化回退/消费者适配 | H、物理/作用范围/性能/consumer门与启用授权 |

这里GL-A～GL-I是最终阶段新工单，不混用本v3早期A/B/C/D简称或旧GL-B01/I01。每单只有其ticket内一张唯一v1验收表。所有模块实现均NOT_RUN；本轮只把路线、契约和可直接派工的标准编齐。详细参数候选/指标/风险/最终数据流以新增[正式计划](ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)为准。

PLAN_READY不等于REAL/PRODUCTION_READY。现有P02四区作者自验和leave-one-out3/4失败保持；自适应不能用temporal/共识将这些物理外推缺口签PASS。既有GL02/03/04/05资格、独审、设备和release流程继续有效。
