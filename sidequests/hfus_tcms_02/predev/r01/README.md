# HFUS-TCMS-02-PREDEV r01

V0–V2 本机隔离研究原型。算法 RESEARCH，读取/回放 ENGINEERING。仅 stdlib + 本机已有 NumPy/SciPy；没有安装依赖。不是板端交付，也不宣称自动人体、骨架或真实地面有效。

从仓库根目录运行，每次使用全新输出目录：

```powershell
python -B -W error sidequests/hfus_tcms_02/predev/r01/run.py --synthetic --out docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_synthetic_r1
$env:PREDEV_TEST_OUTPUT='D:/Code/ldiar/docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_tests_r1'
python -B -W error -m unittest discover -s sidequests/hfus_tcms_02/predev/r01 -p test_predev.py -v
python -B -W error sidequests/hfus_tcms_02/predev/r01/run.py --reused --out docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_reused_r1
python -B -W error sidequests/hfus_tcms_02/predev/r01/server.py --run docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_synthetic_r1 --run docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_reused_r1 --port 0 --process-record docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/my_service_r1.json
```

服务器仅绑定127.0.0.1、独占端口。port=0由系统分配；地址/本项PID/命令记在process-record。GET回放与查询只读；没有任何旧服务/旧目录写入路由。无生产、板端或控制台EXE修改。

输入与输出：`Source`只接受清单给出的sid/路径/源SHA/坐标版本，不枚举会话，D/HOLDOUT入口拒绝。读取器复用`next_contract.validate_meta`；因旧`run_experiment.load`会污染普通模块名，新建最小28B适配，并用旧load等价测试验证。只解XYZ，后16B仅原样返回hex。`source_row`总是帧内行，全局行=offset+source_row，字节偏移=global_row×28。NaN/零回波仍占当前账本行；空帧不造点。重复/逆时间拒绝，同源长空窗重置轨迹但保留不变版本的冻结地图，源/坐标变化清轨并使旧图不可用，需新Engine/显式新图。

真实清单入口：`run.py --manifest <JSON> --confirm-file <JSON数组> --out <全新目录>`。entries每项含sid/path/source_sha256={meta,points}/coordinate_version/kind/role/audit_scope。MAP_ONLY段通过map_authorization.segments逐sid/fi/SHA显式授权；confirmed_empty与layout_consistent必须true。真实A–C还要求real_protocol的pass_lines/matching_rules/annotation_coverage/development_split预登记，标签须绑定sid/fi/source_sha256。当前没有这些输入，不能用示例填猜值。D在本项预开发入口始终拒绝。

人工确认采用显式CLI文件：先在未确认run的REPLAY.json查候选version，再创建本项独立输出下的请求数组，重放同一输入与配置。每条含sid、fi、整数time_ns、source_sha256、coordinate_version、candidate_version、reviewer、provenance="HUMAN_CONFIRMATION"。candidate_version绑定代码/坐标/源/成员/配置；过期当前帧、错源、错版本拒绝。不写GT。合成run中的确认来自FIXTURE_SIMULATOR_NOT_A_HUMAN，不能当真人审核。

五个消融均能用manifest.variant运行：

| 变体 | 唯一显式关闭步骤 | 实际差异与缺能力 |
|---|---|---|
| no_ground | 候选地面范围/高度门 | 原始几何仍诊断，不用RAW z冒充地面；另有低于候选面的反例验证种子变化 |
| no_frozen | M0兼容标签 | 原当前行保留，静态边界不可用，续接/生长相应明确禁用，候选降ambiguous |
| no_continuation | 既有目标当前回波第二路 | 不让背景兼容近地点借历史支持续接；低姿夹具退到0成员预测 |
| no_growth | 一次有界当前点扩展 | 保留发现/续接初始行；记录grown_rows，近表面边缘反例验证扩展确实改变行 |
| no_identity | 人工确认与身份续接 | 仍记录未知候选，目标保持UNCONFIRMED、0实测目标成员 |

同RAW/坐标/审核范围比较；禁用M0带来的安全依赖降级另记effective_growth/static_boundary_available，不是偷偷调别的阈值。某夹具无差异直接记“无差异”，不能推断收益。旧B2/B3仅调用tcms.support/Window/active，输出原阈值、原分数、激活与帧内行；不是新方法的硬门，也不把旧对照当独立数据。

地图动作中冻结；bg标签不预删，bg兼容当前续接点为AMBIGUOUS。小于噪声的表面兼容点不当当前目标支持，宽表面/目标尺度反例保留拒绝行账。近地保留只是构造条件下的契约，薄人体与地板误差不可分时仍有歧义，不能据合成规则宣称真实人体分割。局部冲突仅表示“当前新回波接近未观测非地面表面”的候选，可能是遮挡或家具变化；没有静态锚点审计，整体地图判断UNKNOWN。

强free/强遮挡始终关闭。单独synthetic_visibility给出构造原点/回波/角域支持，演示occlusion_possible层；主夹具缺这些信息，未命中保持unobserved。候选地面自动范围trusted=false，几何与人工身份/物理资格分开；held-out-time接口只报残差，未进行真实跨时间验证。

评价只对显式审核范围，以原始行构造人体分母，包括上游无效/过滤和漏检；点/框/轨迹不能混用。unknown为已审帧有效当前行中的未解释/歧义比例，未标成员污染未知；只框标签不报点纯度。设备时间断档从末次实测算，缺席须显式轨迹GT，无可见点不等于不存在。所有评测effectiveness_pass=false，真实结果BLOCKED；输出不能被总测试数替代为ACCEPTED。

已看过/迭代的旧9会话全部development_seen/dev-tainted；新参数仍是合成假设。将来A–C须预先登记开发协议、校准/确认参数并冻结源码/配置/输入清单，再独立D。不得以旧回归或合成成绩确定D通过线。
