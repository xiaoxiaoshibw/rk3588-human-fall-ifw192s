# GL-E R1 实现前集中诊断（摘要）

来源：契约 §7、计划 §4/§8/§14、GL-E 工单（唯一表 v1，SHA 01345d5b…）。范围：`transform.py`（build/validate/apply/inverse/offline runner/frame report）+ 集中检查；不改 A–D 语义。

## 设计边界

- FinalTransform = source→adaptive-display：R=Rx(roll)@Ry(pitch)、t=[0,0,observed_tz]；yaw/tx/ty=0 gauge；`R@n=[0,0,1]`、det=+1、正交 ≤1e-12 正向验证。
- physical_height_m=1.14 只读记录（measurement_reference），不是拟合目标、不被 observed tz 覆盖；kind/qualification 不得升级（physical/extrinsics/runtime=false），旧 geometry_calibration kind 拒收。
- 只读应用：输入不变；无效行（非有限或全零占位符）原样保留并计数；display 抽样独立且确定性（不参与 fit/验收）。
- candidate 不直接应用；无 accepted → `reference_only`（不补 identity）；HOLD 可携带 last_good 数值但 mode=hold_numeric、fresh/eligible 分开。
- 离线 runner 返回内存工件（points/绑定/资格/绑定哈希），不写盘；CLI/WebUI/写盘属后续单。

## 操作矩阵映射（工单）

| 组合 | 行为 | 测试 |
|---|---|---|
| 已知 GT（10/26.62/45°+roll−10°）| 角度/符号/ gauge / Rn / inverse / 残差不变式 ≤1e-12 | E-01 |
| 已有 Ry26+tz1.34 显示域区分 | t_frame/to_frame/measurement_reference 明示；不覆写 old kind | E-01/E-04 |
| 无 accepted/reference fallback | mode=reference_only，transform/mapped=None，不补 identity | E-03 |
| candidate-only/accepted/HOLD/expired | applied/fresh/eligible 字段分层；HOLD 数值保留 | E-03 |
| epoch/参数变更 | transform 绑定 frame/domain/config/epoch；错绑定拒 | E-01（frame 绑定经 run_offline）；生命周期在 D |
| raw output/caller 修改 | 输入字节不变；输出新 result_id/mapped sha；确定性 | E-02 |
| 坏 model kind/R/t/unit | validate 即拒；无半应用（落盘属后续单） | E-03/E-04 |
| P02 四区/留一区 FAIL | 不重算、不追改；报告只携带引用标记 | E-05（数值证据在 GL-B P02 用例） |

## 保留/不做

- 不 ROS/驱动/生产配置；不改旧 calibration.json/1.14 记录；不冒充样本/物理验证；display（总控制台工作台）集成属 GL-G/P 单，仅消费本模块 JSON 安全工件与引用摘要。
