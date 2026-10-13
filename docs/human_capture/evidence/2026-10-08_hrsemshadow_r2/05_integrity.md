# R2 旧资产与新交付完整性

最终 `integrity_final.run.json` exit0；`integrity.json` pass=true，head_unchanged=true。

- 起始6140路径、43,283,465,274字节；其中return独立验证旧字节前缀，其余6139路径逐项检查SHA/大小、原符号链接或缺失状态。
- changed=[]；unexpected_new_git_files=[]。R1执行 evidence 147条路径和R1独立复审 evidence 84条路径均保持起始内容；冻结验收表、ticket、原始captures、生产源码/config/阈值、console包无漂移。
- return原18732字节前缀SHA `3b00db9f0c28b50291ec9a6f9093a679e236ff16118348d8e01578e54781002f`不变，只在末尾追加R2回传和完整性收尾。允许追加的return与禁止修改的冻结evidence分别核对。
- 基线范围：全git tracked/untracked加ignored captures、既有HC文档/evidence和console dist；当前R2目录排除于旧资产集，.git内部不属于业务资产检查。不将旧deleted tracked路径或src/CMakeLists符号链接改成新普通文件。
- 实际仓库新增仅R2目录；生产算法修改0、冻结门/原数据修改0、旧evidence改写0。HEAD/branch未改变，无commit/push/deploy/capture/生产接入。
- R2新产物的SHA见delivery_manifest.json，包含最终页面、源码、报告、合成夹具、截图和真实日志；manifest不自包含。先前页面草稿/有警告与失败日志保留，不计最终通过。
- 临时HTTP helper仅绑定127.0.0.1:8879供本地只读浏览器测试，已确认进程命令后停止，见browser_server_shutdown.json。浏览器UNKNOWN下载是明确SYNTHETIC夹具，复制到本目录用于验证，不作为真实GT。

完整性检查不代表GT真值或算法目标通过。最终分项为11 PASS、5 BLOCKED；WD02仍BLOCKED，离线交付BLOCKED，生产未授权。
