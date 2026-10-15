# HFUS-LEARN-DEV-03 E0

同一pointset应用的版本模块，继承r01 Handler。原server/app/index文件不修改，旧根路由继续提供R1。新路由为`/learn/<run_id>/`，参数sid/fi；只能读取冻结结果。`CURRENT.json`在全量结果验证后登记，供原console可选加载；已运行EXE不会因此更新。

从仓库根执行（每次必须新证据目录，禁止覆写已有输出）：

```
python -B -W error sidequests/human_fusion_lab_next/learn/r01/run.py prepare --evidence <新目录>
python -B -W error sidequests/human_fusion_lab_next/learn/r01/run.py profiles --evidence <新目录>
python -B -W error sidequests/human_fusion_lab_next/learn/r01/run.py replay --evidence <新目录> --target <新目录>/primary
python -B -W error sidequests/human_fusion_lab_next/learn/r01/server.py --evidence <新目录>
python -B -W error -m unittest discover -s sidequests/human_fusion_lab_next/learn/r01 -p test_contracts.py
```

prepare要求事前AUTHORITIES.json，完整正式执行见本轮execute_e0.py与COMMAND_RESULTS。冻结源SHA、输入数据和背景/注册配置必须一致。输出已经存在就失败；不能以复制primary代替reproduction。

标注：先选任务，在左侧全U源点3D投影拖动旋转，Shift矩形批选；右侧像素选择完整CSR（不只K2）；点击源点查询28B和所有坐标。选择语义/实例后“标记所选”，撤销仅更改本地草稿；填写真实人工审核者、覆盖检查、可见性和原因后保存。保存为本轮证据labels/下不可覆盖快照；撤销已保存修改要重新提交修订。SECONDARY使用冻结66帧名单及独立审核人；缺审/分歧UNKNOWN。建议选择按钮只选源行，不自动转换GT。核心未审核点不做负例，192建议不能在此冻结队列自动成为金标。

仅E0，没有训练命令；三族随机初始化图只作资源profile，整个state_dict含buffer不变。真实学习、实例/关节效果、主权重、种子/学习消融均依赖另附E1与可信人工证据。数据/captures只读。板端/物理/采集/部署、默认晋级不在本模块范围内。
