# R4 设计前置：仍是同一资格族

沿GL04 v1与R3 C01–C15，不改判据。R3独立90日志29旧反例通过、30 PASS/4 FAIL；42 lib通过。V07仍FAIL：`hfTargetGeometryPresent`仅查state字段存在，未核当前snapshot的对应目标；source或ground里旧字段仍存在时照样upright。V06仍FAIL：单侧missing GDID不比；V09 FAIL：cal.schema=null的合法legacy source-only首次选择被observationQualified挡掉。

实施责任：R3明确要求“对应本目标/比较已有字段、不取first/nearest”，实现成presence检查，违反明确C07。Codex原R2负例只将ground字段清空、遗漏source和ground字段仍保留的组合；R3独立已补同一要求，不算新增功能。C01明确保留legacy源选择，R3仍将物理观测资格用于所有选择，属于消费者拆分失败。单侧missing/nonnull属于C05版本不匹，需比完整nullable绑定，不能只比双方非空。模型能力不足无对照证据。

R4必须保留R3已过的单位/3D支持/性能/GPU失效/token；最小改共享context校验与目标详情验证。先00_diag逐C01–C15映射，重点补：旧target fields存在×只有other；source/ground两mode；unselected与legacy/source-only首次选择；nullable两边都缺失与单侧缺失。选择context与目标物理观测是不同消费者：首次选择不要求已有target，缺新增ground字段不得死锁source选择；但schema/frame/session/epoch/calibration/GDID错配不能放过。

R3旧会话153k已停止；本轮按用户允许同model/default DB新紧凑会话，不切模型/DB/认证、不并行写源。四preview范围，core/正式/旧断言/旧证据冻结。
