# GL-E01 R1 主线收口 / 2026-10-04

**主线原始录制来源链已独立核验PASS。** GLE01_ACCEPTANCE.md v1：A01–A05、S01、Q01–Q06 PASS；B01 **仅原bag→canonical bin→NPZ来源链PASS**；B02 BLOCKED，D01 NOT_RUN，D02 BLOCKED。不是安装/地面/人体/时间单位标定PASS，整单不标ACCEPTED。

用户本轮“继续与推进主线”后，Codex用已有SSH别名只读取既有文件，未部署、采集、启停服务或修改driver/网络/板端config。本次设备只读文件取证与GL-05性能/真人阶段明确分开；GL-I05 R2软件PASS及其当时未做设备阶段的历史保持。唯一证据writer Codex，已停写；ponytail路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。

## 已补齐的链路

1. 指定原bag `/root/catkin_ws/captures_remote/cap_20261002_163621.bag` 仍在RK3588现有容器，114550423bytes，实际首尾SHA `bbbc0c00122c68c9c71cd6a799e4ee977f839cc4904d733f9660998df0ebd378` 与既有metadata声明一致。
2. Codex独立结构化dtype解码原26B PointCloud2并重建28B canonical；OpenCode用不同字节拼接方法独立读原bag复核。89frames、4372400points、zero drop；逐frame header/源row/bytes/XYZ均一致。原字段x/y/z/intensity f32@0/4/8/12、ring u16@16、timestamp f64@18；canonical timestamp f32@20，18/24 padding为零。
3. 两种独立方法的全量canonical SHA `b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff` 等于本地points.bin；XYZ SHA `a4ad287ea14edd1ba584dd24dce866d7c4eacdc7ce2594edb2ddb1eef1b51c27` 等于bin与既有NPZ，全89帧逐项核验。原NPZ/meta/bin与旧manifest不修改，`source_bag_hash_verified=false`保留其历史值，新sidecar独立补证。

## 指定独审

fresh无工具probe11.468s/exit0/PROBE_OK；Go Flash/defaultDB正式复核1099.531s/exit0/stop。session `ses_efcf6b467ffewHbmcPqpeFNz16`，15_review_session.json确认实际provider/model；报告 `opencode_review_01/00_review.md`。独立原bag读取、独立本地frame/NPZ解析、手工byte-layout/header/hash反例、单独timestamp loss复测、SDK上下文、38文件首尾SHA及3.8 AST均完成，无验收FAIL。

作者04首版错用raw bag time位级相等，exit1日志保留；按照冻结extractor的`round(to_sec,6)`精确策略修正后04b exit0，不增加任意容差，header secs/nsecs始终整数精确。审查者02脚本自身ROOT深度错误后以新02b编号纠正，保留原02文件，无覆盖作者数据。作者04审计源文件在自验实现期间修订（未形成原JSON）记录在07说明；以后审计脚本版本也优先新编号。

## 新确认的精度限制

原timestamp float64→canonical float32的最大**数值**误差实测0.00781099998857826，独立复测一致，半ULP约0.0078125（原值量级183460）。旧extractor注释“1s内<0.1µs”不受数据支持。未独立验单位/硬件同步，不把逐点量化损失说成header时间丢失，也不改变原格式/解码器。原bag保留原逐点精度，可供将来独立format升级；当前主线几何XYZ与frame header已确认无该精度损失。

## 仍未闭合

- **B02**：当前config/保留SDK日志显示enabled六零，但无10月2日录制run/config联合绑定；现有日志mtime晚于bag窗口。安装source→world/up表达、原点高度、四box地面身份仍unknown。不能拿当前状态、文件mtime、PCA或光学窗口高度代替记录与测量。
- **D01**：本轮没有运行跌倒算法设备性能/真人验证、测安装或新采集/部署。
- **D02 / GL04 V04/C12/M03**：当前CUA browser只有viewport(w,h)与visibility，真实DPR-only不能控制；旧Ctrl+plus/visibility失败记录不盲重试。GL04相关实际项保留NOT_RUN，正式页不因本单放行。
- 完整support/真实calibration与正式实际端到端仍不能以这条来源链PASS替代；GL-P01软件R/t能力既有PASS保持。

下一主线证据按14_NEXT_PHYSICAL_EVIDENCE.md优先补录制绑定/独立安装表达/原点高度与原ROI身份，再决定是否需要明确范围的新记录。原bag来源不足这一步已通过新实证解除，不继续围绕它循环做synthetic研究。

## 冻结与状态

master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6保持；原生产/driver/UI/HR、captures/NPZ/draft、旧证据与Windows catkin软链接不变。主线新入口/本表/return与REVIEW_LOG允许追加/更新结果；不改旧GL-I05验收或回传当时B01状态，不回填旧未核字段。最终19_final_verify.json记录首尾scope/行政变化。无活动writer，无源码返工/部署/采集。
