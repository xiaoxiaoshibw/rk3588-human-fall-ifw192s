# GL-I01 R1 派工前计划 / 2026-10-03

来源为下一阶段计划C与只读数据/现代码审查，用户开始开发且后续继续。先只读诊断stop、Codex实际审核后另发实施消息，确保不重演GL-P01 R2先写后diag。生产writer只有指定Go Flash/default DB，本单新紧凑session；每派前<=1分钟probe。唯一GLI01_ACCEPTANCE v1，I01-I08/M01-M13软件要求，B01原bag布局证据BLOCKED、D01设备物理未跑。

28B meta/bin为现有capture export，不是原bag。4份原始数值数据完整连续/drop0/XYZfinite，但有约15%零点；全部原行保留后fitter仍使用原pooled index。meta.sensor.frame_id是extractor硬编码、单位缺原记录，要求显式声明并标metadata_declared。integer headerstamp为frame时间，point timestamp float32在该批ULP .015625s，不能恢复ns。source_bag_sha只declared，未本地读bag，无width/height/original_count证据，不将capture行等同已核bag原点索引。

最小方案单NPZ(points+UnicodeJSONmanifest)与pure loader，manifest绑定实际source meta/bin/hash、canonical成员及points字节；加载重核source并验证group，不接受任意标签假独立。fit/validation由外部选区/先验，bounds先group限制，再复用现数学入口；不按平面残差预滤。旧points路径保持，含manifest损坏不得fallback为legacy。原子exclusive输出及校验在副作用前完成，原captures/旧证据冻结。

真实163621可作完整解析与map证明，不自动生成真实标定。原点/安装/up/source轴/地面身份/空间ROI和现场门槛留待现场授权，不阻挡本单adapter软件。只准新core/capture_input.py、新scripts/prepare_capture_input.py、calibrate_sensors.py opt-in loader/group gate、新test_gli01_capture_input.py及本单contract/evidence/追加return；ground/math/runtime/config/driver/webui/采集跨包全部不改。
