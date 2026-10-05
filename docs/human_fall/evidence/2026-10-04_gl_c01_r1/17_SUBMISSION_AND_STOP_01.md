# GL-C01 当前小点完成 / SUBMITTED / STOPPED（作者自验，未独审）

按用户“在他的基础上继续开发”，完成单source FIT冻结源行→TLS平面→闭式联合反解pitch/roll/tz→同一个FIT平面对三个独立验证frame全部选定点检查。随后用户明确“这一个小点做完先停下来”；本轮自验/产物/manifest/回传落档后停止，不派新的probe/Go独审，不继续调参/筛点/生产/部署。独审S01/Q06阶段NOT_RUN，不宣称整单软件独审PASS或ACCEPTED。

## 当前数据估计（不是安装测量）

99帧cap233210与此前89帧分开；原meta/bin只读、实际bin SHA d946b80b…，新adapter保留原bag hash未独立verified。初始26°/roll0/tz1.340来自用户所贴方案/slider归档，仅显示系；此前1.1m口头物理记录未覆盖。

单FIT=pick03/frame0/528行；VAL pick01/frame33/890、pick02/frame66/276、pick04/frame98/624；角色/帧在00前置固定。只取初始XY、全部有效高度，原行号冻结；没有Z-median/.12或optimized |Z|<.15裁剪。

- pitch=26.3143101922°，roll=-0.6120612045°，tz=1.3231366999m。
- 方法R=Rx(roll)@Ry(pitch)，第三行=n_source；pitch=atan2(-nx,nz)、roll=asin(ny)、tz=平面d，无小角迭代/IRLS。
- 相比贴文26.234/-1.322/1.322，不同点域（单FIT帧 vs pool四框99帧+修剪）产生不同估计，不能直接视作复现其数值或传感器真侧倾。roll仍含地面坡度，tz仍是数据平面距离。
- 全2318行独立标量点变换差4.44e-16m；before/after正交FIT-plane残差变化≤6.67e-16m。刚体变换不消掉固定点集之间的偏差。

## 同一个FIT平面、全部冻结验证点（原质量指标子集）

| 域 | 点数 | 全点RMS(m) | |res|P95(m) | 支持率 | 数值质量 |
|---|---:|---:|---:|---:|---|
| FIT pick03 | 528 | 0.009201 | 0.018324 | 1.000000 | PASS |
| VAL pick01 | 890 | 0.024627 | 0.050762 | 0.942697 | FAIL（P95） |
| VAL pick02 | 276 | 0.028318 | 0.057539 | 0.916667 | FAIL（P95） |
| VAL pick04 | 624 | 0.020218 | 0.037627 | 0.991987 | PASS |

阈值复用冻结resolve_constrained_settings：20点、RMS≤.03、P95≤.05、支持≥.8。两区P95分别超0.7625mm/7.5386mm，完整失败保留。每区self-fit仅诊断，不替换同FIT验证；无删点转绿。未运行原constrained fitter的RANSAC/竞争完整性/资格/稳定等全套，不能把此子集说成GL-P2正式PASS。

11前后图实际查看，12是全点scalar/行号/不变性oracle及指标；joint_02含模型、quality report、冻结selection、source binding及全部selected source/estimated points。新kind=joint_ground_level_estimate、status=data_estimate、candidate/physical/extrinsics/runtime=false，冻结资格消费者拒它。

## 所贴基础的审计结论

optimize_transform原来pool四框99帧且|Z-median|<.12初筛；per_box_stats每次重新按新rectangle分组并残差修剪，前后n不同。p2_frozen_validation仍删|res|>.12的验证尾，software_gate_check用各区self-fit、待验证Z先筛后声称untruncated。ground.py实际验证是同一个FIT n/d对每组全部选定域。这些“全绿”不沿用，旧脚本/报告保留不改，不无测量断言地板真实起伏或噪声物理下限。

原user_picks_accumulator.json第13行相邻字符串拼接不是合法JSON，首次准备选择失败后07真实CLI exit2（缺selection）保留。03记录改为AST.literal_eval只读提取已读optimize_transform.py的PICKS常量，不执行脚本、不修旧JSON、不导入其ALL_GATES_PASS旗；新04选择严格JSON并绑定实际source/初始化参数。09新编号重跑exit0。

## 逐ID作者自验（非指定独审）

| ID | 结果 | 证据 |
|---|---|---|
| C01 | PASS（自验） | known GT多pitch/roll/height、8mm noisy/line反例；闭式姿态与properR，14 tests |
| C02 | PASS（自验） | FIT仅frame0，val33/66/98；源行不随pose重选，04/12 |
| C03 | PASS（自验） | source、schema/type/bool/NaN/unit/aliases/caller/hash/newoutput；13已有out exit2 |
| C04 | PASS（软件自验；真实质量FAIL） | parallel-offset本区self-fit很好但共同FIT失败反例；09/12真实P95失败完整 |
| C05 | PASS（自验） | frozen domain正交不变性，12；不解释为已核物理原因 |
| C06 | PASS（自验） | 模型false、旧消费者拒，失败不晋级；14 tests |
| C07 | PASS（本地来源/选择自验） | actual99 adapter/03/04及noZ全高度，原99bag独立来源链NOT_RUN |
| S01 | NOT_RUN（指定独审未派）；作者范围/回归完成 | 用户要求当前小点完成后停；三源码、18scope、19manifest |
| P01 | BLOCKED | 精确地面行/独立仪器/SDK/99bag原链未核，模型不能代测量 |
| D01 | NOT_RUN | 不设备/采集/部署/网络/生产/IRLS |
| Q01 | PASS（自验） | input/types/finite/schema/frame/noise/line/min/consumer |
| Q02 | PASS（自验） | 内容ID/caller/source变/out/保护path |
| Q03 | PASS（自验） | frame/alias/noZ/行域从source重算 |
| Q04 | PASS（自验） | GT/noisy/offset各域、全point真实quality失败 |
| Q05 | PASS（自验） | 任意quality状态model资格不晋级 |
| Q06 | NOT_RUN（独审/probe未执行）；作者冻结阶段完成 | 最新用户停写范围覆盖自动二审调度 |

命令/真实exit：14新增5方法exit0，15完整fall458 exit0；此前B 2follow回归在无对应源码变动时仍适用，未为形式重复。09真实exit0输出质量FAIL、13已有out exit2。10/16 3.8AST，不冒充板端环境实测。core_source01/02、CLI_source02、tests02/03各版本txt保留，未同名改检查器/旧产物。user latest stop is authoritative。此小点落档后无活动writer/下一步自动任务。
