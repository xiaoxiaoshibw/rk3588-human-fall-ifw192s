# HR-SKELETON-DEMO-01 / R1 / 真实点云粗骨架预览交付

2026-10-12，Codex唯一writer，SUBMITTED；当前唯一验收 ACCEPTANCE_V2.md。用户授权“现在能不能实现一下骨架标定给我看看”。

入口：http://127.0.0.1:8927/ ，已在Codex浏览器打开并保留。源 sidequests/human_fusion_lab_next/skeleton_demo/r02/，启动 server_v3.py 或 start_demo_v3.bat。仅本机只读，未接板端。v1/v2代码与失败记录保留，临时8925/8926/8928服务测试后停止；8927保留。未外部派审，不伪称独立审核通过。

## 实际显示与效果边界

默认使用已有真实human/PERSON点集作为明确标明的人工输入，非自动人体分割成果。近距175429/f220有1069个真实有效点，五粗节点支撑146/223/228/197/259点；由真实点集区域中位数计算。五个指定参照样例（近距220、远行5、转身162、遮挡110、静止0）均输出五区域中心；两侧下部未满足分离门，保持UNKNOWN，不画虚构腿；顶部头/手待确认，手臂/肘/腕未估计。缺精确节点人工参照，不能报告真人骨架准确率。

自动候选模式独立保留，估计/默认选择不使用GT；近距a_220_2虽然算法确认且prob=.9935，但793点的XY范围混入旁边物体，五带全CONFLICTING_SPATIAL_SUPPORT、零节点。另有家具候选能产区域中心，说明形状连线不是人体身份真值。没有放宽.8m/6点等支撑门以画完整人，也没有改检测器、split、分类或tracker。

代码复用旧skeleton.py通用normalize/observe，不调用旧人工资格process入口、不构造reviewer/HEAD_CONFIRMED或visibility标签。独立新的几何预览契约，不放行旧SKO或正式W04/W05。输入全部完整成员，原28B原始点用已有R/T配平到参考坐标，Z单位米；只在每高度区域有真实支撑时画点/线。无未来帧、无历史补节点或EMA。已有机器身份和人工ID按模式分开显示。

## 当前逐ID结果

| ID | 结果 | 实际证据与限定 |
|---|---|---|
| SD01 | PASS | SHA核验的原输入/候选/已有人工成员；原provider只读核source/model/input/ledger/GT；机器模式不读GT，人工模式明确消耗人工完整点集；S9参照空 |
| SD02 | PASS（几何数学） | 复用normalize/observe、固定参数、节点support_rows；独立struct+标量f32变换+statistics.median七场指定帧核查最大误差0m；非关节精度 |
| SD03 | PASS（查看工具） | 真3D点云、完整点集框、节点/连线/支撑表、九会话选项、模式/目标/播放暂停/逐帧、旋转缩放；人工正例与机器失败明确分开 |
| SD04 | PASS | 4 unittest exit0，17.895秒，-B -W error；JS语法/3.8语法exit0，独立raw审计exit0；4非法请求真实HTTP400；v1失败不覆盖 |
| SD05 | PASS（作者浏览器验证） | BROWSER_CHECKS/BROWSER_FINAL_SUPPLEMENT：真人近距220/221/222、远行5、家具40空参照、混簇候选零节点、支撑点击、正侧视、开关、播放与加载期间暂停、实际画布旋转/缩放；错误SHA清旧图且禁播放；控制台error/warn空 |
| SD06 | PASS | before15879/end15911全SHA，HEAD/branch不变；无范围外变动/新增/缺失/errors/drift；末尾新增记录另存SOURCE_MANIFEST；新return |
| SD07 | BLOCKED / NOT_RUN | 真人解剖节点标定/误差、自动完整四肢与骨架准确率BLOCKED；真实跌倒、设备、实时板端性能、部署NOT_RUN |

## 保留的真实失败与修正

- V1_REAL_FAILURE/CHECKS_ATTEMPT_01：近距真正目标候选混簇导致零节点，初始默认选择倾向家具；没有因增加人工模式而改写成自动成功。v2验收事前登记允许显式人工参照输入，节点公式和拒绝参数不变。
- UI_V2_TIMELINE_DEFECT：帧220，range默认max100导致滑条显示100。新app_v3先设置当前会话max再写frame；真实220/221/222双值一致；播放加载时仍可暂停。
- v3第一次SHA等待超时：随后新AX观察已加载；仅自动化等待失败，不伪造成功时间。
- NEAR220_REFERENCE_DESKTOP截图被native可见面裁切，不用作完整布局证明；viewport override已reset。FINAL_NEAR220_ROTATED误名实际顶部工具栏，已用SCREENSHOT_ROTATION_CORRECTION排除；从fresh画布真实拖动后保存ORBIT_VERIFIED及ZOOM_VERIFIED。

## 来源/检查/范围

数学节点模块：docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py；参数prototype_params_v1.json；只读provider：sidequests/human_fusion_lab_next/d05/r06/demo_v2/demo_server.py；Three/OrbitControls复用现有vendor。旧载入源与写前基线SHA核对，不覆盖GB账本，offset索引/hash流式处理。

`python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/skeleton_demo/r02 -p test_server.py`

`python -B -W error sidequests/human_fusion_lab_next/skeleton_demo/r02/audit_real.py`

未部署、未采集、未修改生产/原GT/输入/模型/旧证据，没有Git写/代理/新依赖。全树扫描非原子，.git内部排除；最终报告/回传/最后截图在扫描后另计SHA，不宣称全树原子冻结。工程SUBMITTED，几何工具自验PASS；自动检测质量未晋级，真实骨架精度BLOCKED，设备NOT_RUN，不ACCEPTED。

实际ponytail路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。复用已有数学与控件，未另建标注框架或深度模型。
