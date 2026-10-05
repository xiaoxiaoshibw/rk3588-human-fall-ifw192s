# GL-I05 R2 写前集中诊断与操作组合 / 2026-10-04

Codex唯一研究writer，OpenCode R1二审已stop/exit0。按用户持续开发授权只修同单既有v1缺陷；新研究目录，R1五脚本原字节复制后在本目录修复，所有生产/旧研究/输入/UI/driver冻结。ponytail实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。全tracked+untracked基线../00_before_baseline.json，master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6。

集中根因与责任：R1 oracle无向对按best索引方向漏报；非法oracle参数未查；比较漏旧包络原型；未决缺竞争归因；成本仅总时间且不可证46s；空间数据消费链错误来源/残差/seq和无点读/输出独占。不是新需求，不改变ALL/NEAR三终态或冻结参数。R1已正确终态/预算/计数保留，原有失败证据不覆盖。

| Q | ID | 实际函数、顺序和检查；预期 |
|---|---|---|
| Q01 | C02/E01/S01 | oracle先resolve_constrained_settings和_validate_witness再dot；settings对象/NaN/bool/法向单位、非法event拒；source build_payload先schema/frame/units/boxes/groups/row检查，再计数，再write_payload独占，非法out先拒绝 |
| Q02 | C02/C05/S01 | 无跨call状态或refine cache；search每call转float64一次，再replay/refine；points/settings/report改后重算，事件trace复制；同路径异内容与新路径由SHA检测，已有out拒绝 |
| Q03 | C01/C03/C04/C05 | oracle先所有i<j distinct，再用双方是否top筛BEST_ONLY；保留tie、.8边界、ALL/NEAR独立；processing gaps先锁unresolved，actual-near reason只归因不改gate |
| Q04 | C01/C03/C04 | 独立scalar参考手算0/4/8和0/6/12全部排列、middle-best、best首末；旧I04固定anchor状态/reasons同序列保存，证书不足与near实际竞争分桶 |
| Q05 | C02/C04/C06 | compare同points/rows/up/height/settings/seed，对冻结fit/replay/旧I04/new原型；sampling及event digest对拍；clean/noise/high_noise/weak/dual/close×3seed×原与置换，正例不硬规定高噪闭合 |
| Q06 | C03/C04/C05 | search_events candidate/refine/trace/iteration0/边界/耗尽；late best和第二平面、refine reject、raw reject、事件ceiling；计数恒等/已有gap不得恢复；所有closed与scalar/全W一致 |
| Q07 | C02/C05/C06 | 不实现refine-reuse cache，hit/miss=0明确；同/异sample-inlier成员实测、完整依赖表(source/full-fit/sample/up/height/settings/code)，无持久或跨runcache，因此碰撞/cache-full命中不适用。dtype单call转换不是结果缓存 |
| Q08 | E01/E02/S01 | build_payload独立每frame×4box，依据source manifest row range/ordinal/seq查索引与重复/alias/跨组；全统计与sidecar数量逐项含empty校核。display预算只改变绘制数量；payload保留XYZ供索引/点击读取；plane按真正posthoc origin/physical=false，残差消费者用所选normal/offset重算 |
| Q09 | C02/E01/E02/S01/B01/B02 | 复用R1独立bounded recording audit并补metadata SHA/原录制窗口/提取时间/config/from-to/SDK unknown表；不全历史扫描或远程操作。批准up和posthoc plane分开，1.1m光学窗口不替代已审height输入，不改FIT/validation |
| Q10 | S01 | 自验/关闭raw日志/完整manifest/全树首尾SHA/停写→新<=1minGo Flash/defaultDB probe→只读二审；失败不切model/DB/auth，不伪PASS；收口仅Codex，R2无其他writer |

成本实现仅perf_counter分sampling/raw/refine/decision/serialization，至少3次固定case重复，单独tracemalloc测量且不混入计时基准。数学与已见序列保持，报告阶段不等同冻结fit端到端，不增加速度门。真实大输入一次float64物化复用，明确内存代价并核source/sequence/输出不变。

裁剪：纯离线函数无ROS热reload/GL02锁定生命周期；无cache实现不测缓存碰撞/满命中（有完整依赖审计/未缓存对照）。文件身份、caller变化、预算pending→terminal、source frame与oracle负例均不裁剪。B01/B02 BLOCKED，D01/D02 NOT_RUN。诊断完成，现可最小修复。
