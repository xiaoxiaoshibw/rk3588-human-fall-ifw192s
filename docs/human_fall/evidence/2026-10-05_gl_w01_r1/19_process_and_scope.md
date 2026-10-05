# 补充故障/范围记录

指定OpenCode Go/defaultDB无工具probe55.477s timeout、真实exit1，stdout/stderr均空；没有生成session/指定模型推理事件，不编造已做独审，也不将旧403当作当前根因。仅本单独审服务BLOCKED；功能作者自验继续。

写前基线4176左右路径（实际4167），最终复核既有files零读取错误。除本单声明的docs和pc_apps改动外，P02_ACCEPTANCE.md及returns/P02.md在期间由外部工作追加了R3分区/逐帧研究（未由本单写入）；保留，不回滚，不归因。其旧四区质量门、ROI和P02历史FAIL未被本单修改。GL-W01静态配平不消费新增PPCF模型，不宣称该研究已集成。

包装过程首两版因同时写源/冻结datas时点有旧leveling.py和检查文件，12_archive_check如实FAIL保留；13重新打包后15_archive_final逐字节核24文件PASS。最终补console启动端口冲突后另17包装，需新的archive检查，不使用15代替最终二进制证据。

原本本地8901服务PID27512（python human_replay_lib.py，无子进程）被本单为包装验证正常停止；随后外部进程41552从parent18404重新占用8901。未停止它。首包装测试Console父PID38076及其子47460为本单创建，服务地址冲突导致不可启动，已仅关闭这两个本单进程。根因补在_start_replay_server与console URL：新实例占用默认端口失败时bind localhost端口0，返回真实端口，卡片URL和回到首页保留query，旧服务不受影响。18真实HTTP新实例启动检查PASS。

使用说明明确静态离线范围、地面身份人工依据、全高度同域、TLS/SVD同家族、3独立留帧、物理false与参考height≠observed tz。原始captured SHA始终检查，不修改旧录制。Windows软链接src/CMakeLists.txt既有表示保留。无设备/采集/driver/板端网络/部署/commit/push/reset/clean。

补正：写前基线实际4167路径。最终窗口版的sys.stderr=None场景新增共享日志入口guard；20真实HTTP检查PASS，21是最终包装日志，前版17不替代最终二进制。
