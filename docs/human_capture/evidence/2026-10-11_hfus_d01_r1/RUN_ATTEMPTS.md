# HFUS-D01 实际运行尝试（保留失败）

1. `node eval/check_contract.js` exit 0，传感器NaN/Inf/全零、重复坐标行身份、一对一、无候选FN、partial UNKNOWN、真实当前支持/coast与负例资格回归通过。
2. `node .../baseline.js .../baseline` exit 0，六次全帧。原资格名称 BOUND_HUMAN_REVIEWED 可误读为独立复核，最终改为 PARTIAL 并在 baseline_final 新轮重跑，原结果保持。
3. `node .../fixed_candidates.js .../FIXED_JS.json` exit 0，859条候选现存raw输入重建256采样，maxdiff=0。
4. 第一轮 `python -B -W error .../pointnet.py` exit 1；PointNet断言已通过，但XGB native路径载入在DLL的 weakly_canonical 报 Access is denied。改从同一文件只读bytes载入Booster，未改模型/权限/数据。
5. 第二轮PointNet命令 exit 1；native XGB/JS断言已通过，SHA报告相对参数路径未resolve导致 relative_to 错误。修为绝对路径并把输入/模型hash冻结放到推理前。

本文件是失败记录，最终成功输出另外保存在 POINTNET_PARITY.json 与 baseline_final。未用旧覆盖runner，未训练。
