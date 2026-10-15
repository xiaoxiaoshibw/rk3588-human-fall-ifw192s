# 当前唯一交付 · HF-MAINLINE-LEVELING-01

状态 SUBMITTED，未ACCEPTED；软件自验与leveling FAIL/registration BLOCKED分开。

- [报告](FINAL_REPORT.md)、[当前验收v2](ACCEPTANCE_V2.md)、[逐项状态](ACCEPTANCE_FINAL.json)、[回传](../../returns/HF-MAINLINE-LEVELING-01.md)。
- 可运行源：D:/Code/ldiar/tools/hf_mainline_leveling/run.py、select_planar.py、test_run.py。
- 原三臂：[冻结配置](run_02/FROZEN_CONFIG.json)、[完整结果](run_02/RESULTS.json)、[真实gate/loader](run_02/original_patches/registration/EXPERIMENT_SUMMARY.json)。
- 返工：[公共清洁域](run_03/FIT_DISCOVERY.json)、[失败结果](run_03/RESULTS.json)、[FIT-only组合选择](fit_planar_selection_02/FIT_SELECTION.json)。
- [完整实跑日志02](RUN_02.log)、[实跑日志03](RUN_03.log)、[测试实录](TEST_RUNS_FINAL.json)、[新契约日志](TEST_LOCAL.log)。旧run_01失败保留。
- 原source/旧证据/生产源码首尾hash见run_02与run_03的BASELINE/IMMUTABILITY；最终保护检查见FINAL_INTEGRITY。代码及小型证据hash见DELIVERY_MANIFEST。

两套新UUID原基线派生保存在run_02/workspace，仅本实验消费；未注册到原latest选择、未修改8944/R3，未产生新的合格共享leveling或VALID registration。
