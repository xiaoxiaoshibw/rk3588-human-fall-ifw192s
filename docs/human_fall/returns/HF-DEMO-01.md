# HF-DEMO-01 追加回传

## 2026-10-12 / R1 / Codex唯一writer / SUBMITTED

用户明确要求优先提供简化跌倒识别Demo。当前入口：http://127.0.0.1:8920/index_v2.html；隔离代码：sidequests/human_fusion_lab_next/fall_demo/r01。

唯一验收：[ACCEPTANCE_V1](../evidence/2026-10-12_hf_demo_01_r1/ACCEPTANCE_V1.md)。完整逐项结果、失败、边界和下一步：[FINAL_REPORT](../evidence/2026-10-12_hf_demo_01_r1/FINAL_REPORT.md)。源码SHA见隔离目录manifest_v2.json，起始全树SHA见BASELINE_BEFORE.json。

FD01–FD05作者自验PASS；FD06独审及处置记录PASS（v1独审，v2作者复核）；FD07真实/设备NOT_RUN。工程SUBMITTED，真实算法NOT_RUN，GT与生产BLOCKED，不自行ACCEPTED。

复用原特征和状态机，只对合成已知目标启用演示确认。六段1086帧、7.5秒跌倒告警、四段零告警、一个同几何主动躺下误报反例；真实浏览器操作/截图/数据SHA负例验证，原HF06回归20项exit0。初版两次生成失败、审核export超时、文档操作策略拒绝均保留，不改写成功。

指定OpenCode只读审查child31512 exit0；导出超时后，以SQLite mode=ro核实实际模型opencode-go/deepseek-v4.1-flash及完成标记。缺陷处置见REVIEW_DEFECT_HANDLING.md，不宣称独审者已复审v2。

起始master / 026e06303f60ed1bbe4ddc4d037836db68da6d27；15824文件全SHA含tracked/untracked/ignored，非原子。原加载规则与基线一致，生产、原模型、采集与GT未由本轮修改。结束核查为元数据辅助，不宣称全树冻结。

ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

下一步：接入真实跌倒离线素材前，先核对人工资格和目标几何；当前合成Demo不代表真实检测跟踪精度。D05-R06保留未收口状态。
