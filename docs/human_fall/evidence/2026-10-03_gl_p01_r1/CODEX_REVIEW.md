# GL-P01 R1 Codex独立复审 / 2026-10-03

结论 **REWORK**。源SHA946b998d1ba7854906278e1ea39e49b38f74d55b3add26169fc4c9819afd5f78首尾一致。OpenCode10同session压缩后exit0/SUBMITTED/停写；实际ponytail仓库内完整副本读取可核，原SHA相同。03外部skill拒绝exit0无提交、05主动暂停、07辅助服务断连与09实际压缩分别保留；不是算法失败轮次。

## 实际缺陷与责任

P01/P02/P03：_coordinate_ground_projection对R/t要求list（539），但既有validate_geometry_calibration允许tuple，并保留容器；tuple JSON与GDID同list。合法tuple R、tuple t或二者tuple，pure及实际FallNodeCore都生成actual_points ground AABB，ground_status valid，但新增coordinate.ground为null，JS unavailable/no_ground_block。预期为同list ready/原R/t。只读审查助手独立四格复现；root97正式检查确认同一缺陷。这是既有输入契约，不增需求/不改验收v1。

Codex派前未把strict validator接受的容器交集列为正例；实现者在已经validated结果上再做list-only门，且新增管线测试仅helper producer，没有FallNodeCore。两者遗漏集中补齐，不归因模型能力。R2按全部M矩阵复核，容器list/tuple R/tuple t/双tuple×pure/Node/ROS/JS；坏输入仍由共享严格入口拒绝，不新增局部重复schema验证。

## 独立证据与勘误

96_codex_independent.py→97_codex_independent_results.json，20个记录，只有tuple反例FAIL，其余包括actual NodeCore全倾角/非零t→ROS projection→strict JSON→真实preview parser、empty候选、artifact-only unqualified、legacy/none/foreign/different parent、损坏whole parent/child schema/units/ID/R/t/derived physical flag、输出隔离、旧模块逐字段对比PASS。新增wire字节增量存结果记录，小于2KiB；没有物理或板端性能门槛。

94_codex_gl_regression.txt：GL相关123回归exit0；95_codex_node_regression.txt：HF07 25回归exit0。生命周期按这些已有startup/reload/pending/ready/monitor/lost/prediction/invalid/恢复正负例复用，runtime冻结且SHA未变。没有用实现者334/55总数替代独审。实现者自验数字与SHA属实，但回传P03全覆盖声明过宽，未逐M行报告，R2补齐。

root90探索脚本把process参数写成now_s、误把父verification.ground_physical_verified=true一概当非法；92又假设未选目标state.coordinate必须非null。均为审查脚本/过严预期，非产品缺陷：原失败91/93保留，96分别按实际now参数、derived.physical_verified非法旗和既有未选目标null资格修正。正式97只剩真实tuple FAIL。00_diag第30行称projection深拷贝不准确，后续§5已明确保留nested浅拷贝；独审以实际源码与§5为准，不覆写历史。

98_scope_verify.json：原基线文件只改本单producer和Codex添加的验收解释段；无删除。新增文件为本单tests/contract/return/证据；旧源码、网页、数学/runtime/config/driver/原始数据/历史证据保持。无commit/push/reset/checkout/clean、设备/部署/采集。

| ID | 结果 | 证据 |
|---|---|---|
| P01 | FAIL | tuple合法输入新增变换丢失；97 |
| P02 | FAIL | 合法容器被局部门错误拒绝；坏whole artifact负例通过 |
| P03 | FAIL | tuple实际NodeCore→ROS→JS unavailable；list实际链通过 |
| P04 | PASS | 同内容reload、输出隔离、94/95既有生命周期；生产runtime未改 |
| P05 | PASS | auto bounds及trusted ROI不发布轮廓；null+reason，JS unavailable |
| P06 | PASS | 97旧模块逐字段比较、wire增量、原source/reference/ID与实际ground AABB；scope |
| D01 | NOT_RUN | 未设备操作/真实ROS运行/人体/性能/部署 |

M01/M03/M04/M05/M06/M07/M08/M10/M11/M12 PASS；M02/M09 FAIL仅合法tuple交集。GL04 V04仍NOT_RUN，V10完整support/正式实际集成BLOCKED；本单未软件收口，不启动GL-I01写入者、正式不合并、不GL05设备。
