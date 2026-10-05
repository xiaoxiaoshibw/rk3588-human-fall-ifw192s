# GL-E02 R1首轮执行提示（准备状态）

仅在用户明确开始下一阶段后执行；当前DRAFT_READY，不启动代码、CLI probe、现场测量/采集或部署。读WORKFLOW当前入口、GROUND_LEVELING_NEXT_STAGE_PLAN.md、唯一GLE02_ACCEPTANCE.md v1、GLE01收口与实际冻结loader/selector/geometry接口。

Codex唯一实现writer，ponytail实际读取并在回传记路径；提交停写后由Go Flash/defaultDB实际只读二审。只本单最多三个新生产文件(core/ground_evidence.py、scripts/prepare_ground_evidence.py、tests/test_ground_evidence_input.py，可合理减少)与新日期run_root及允许状态文件。旧core数学/配置/原数据/driver/UI/HR/历史证据只读，不commit/push/reset/checkout/clean。

先fresh branch/HEAD/全tracked+untracked SHA，建立范围与完整Q01–Q07映射。在00_diag逐行说明实际函数/输入来源/赋值顺序/输出资格；缺测量时允许合法pending证据包，不制造虚假数据。不新增笼统人工审批系统/账号/缓存/服务/模型/外部依赖。

复用现有load_adapted与selector校验source/frame/rows；三个validation frame_group互异且不同FIT，另列空间分布，不以同帧三个box替代。来源sidecar新增，不回填旧NPZ未核字段。SDK/log与录制需联合绑定，字段齐全只是结构，不能把current config/旧日志/PCA/26°示例/约1.1m光学窗口高度当成物理证据。地面局部配平不要求完整地图/底盘/IMU标定；这些未知字段保持unknown。

先完成证据schema/最小工具/集中负例：坏输入、同路径/ID异内容、caller变化、录制/config/run错绑定、from/to/单位/测量原点混用、ROI alias/重复/跨组、已有out与保护目录。只输出pending evidence packet/draft/缺口表，不fit、不保存runtime calibration/ground_derived、不自动设置physical flags。缺现场证据独立记P01 BLOCKED，不混为软件FAIL。

自验完整E/S/P/D/Q→相关回归与scope→关闭日志/完整manifest→returns/GL-E02.md按模板追加SUBMITTED/BLOCKED→停写。派实际指定独审前新≤1min无工具probe；失败不换model/DB/auth、不伪PASS。审查scripts/outputs修订使用新编号，禁止覆盖历史。不得自动跨到P2/GL05/采集/生产接入/部署。
