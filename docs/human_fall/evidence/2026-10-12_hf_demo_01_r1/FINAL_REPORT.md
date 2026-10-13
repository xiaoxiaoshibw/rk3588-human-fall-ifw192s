# HF-DEMO-01 / R1 当前交付

2026-10-12，SUBMITTED，作者自验，不自行 ACCEPTED。

当前入口：http://127.0.0.1:8920/index_v2.html

启动：sidequests/human_fusion_lab_next/fall_demo/r01/start_demo_v2.bat。同目录 README.md 有操作和限制说明。

| 唯一验收 v1 ID | 结果 | 证据 |
|---|---|---|
| FD01 | PASS | BASELINE_BEFORE.json：15824文件，errors/drift空；LOADED_SOURCE_VERIFICATION.json 核实原加载源码与基线一致；manifest_v2.json |
| FD02 | PASS（合成） | BUILD_V3.log/EXIT：完整181帧下降、疑似、确认、恢复；7.5秒一次告警 |
| FD03 | PASS（合成） | 行走、慢坐、初始低姿态、遮挡零告警；遮挡UNKNOWN；快速主动躺下同几何反例一次误报 |
| FD04 | PASS | BROWSER.jsonl：六场景，播放暂停、单步、时间轴、重置、告警确认、恢复；v2时间轴及遮挡另验 |
| FD05 | PASS | DEMO_V2_ALARM.png、CONSOLE_V2.json空；BAD_SHA_BROWSER_V2.json校验失败停止，播放禁用 |
| FD06 | PASS（独审及处置记录） | OPENCODE_01.md；child31512 exit0，实际模型经AUDIT_DB_VERIFICATION核实。v1独审、v2作者处置后浏览器复核，不宣称独审者再次审v2 |
| FD07 | NOT_RUN | 真实跌倒准确率、真实检测关联、设备与部署均未验证 |

6段×181帧=1086帧，逐帧点集、特征、状态、新事件在data.json。全部为合成已知目标，不含真人检测器，不是真实雷达录像。跌倒与快速主动躺下用相同运动几何说明无法辨别意图，不能当独立真实负例。数据SHA：9e5ed82a81053d9f446e84b66d8a69fb00eb1b4c9e45414da2f62857150e0e42。

工程 SUBMITTED；算法合成流程自验PASS、真实能力NOT_RUN；GT资格BLOCKED（无真实跌倒人工参照）；生产接入BLOCKED/未授权，设备NOT_RUN。

## 保留失败与审核处置

BUILD/V2 exit1：合成起始高度与现有速率窗口使descending未覆盖；失败源码与日志保留。仅调整合成输入以覆盖状态路径，未修改原规则，不据此声称算法改善。原HF06回归20项通过，命令：`python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_hf06_fall_state.py`。

独审未发现P0/P1。来源遗漏补实际导入的scripts/sensor_health.py和core/__init__.py；审核指出的core/sensor_health.py不存在，首次补清单失败，核对实际导入路径后纠正。UI v2改合成观测标签、动态设置说明及长度。详见REVIEW_DEFECT_HANDLING.md。

OpenCode run耗时164.207秒，exit0；export超时180秒，原runner exit1/dispatch FAIL保留。随后SQLite mode=ro仅核对本次session：11 messages / 68 parts，实际模型opencode-go/deepseek-v4.1-flash和REVIEW_COMPLETE核验PASS。原FAIL未覆盖。

Start-Process被自动审批拒绝，仅返回blocked by policy；工具托管的前台localhost服务成功。批量收口脚本也被策略拒绝，改用单文件编辑工具保存文档。没有设备网络配置变更。

## 边界

起始master / 026e06303f60ed1bbe4ddc4d037836db68da6d27；BASELINE_BEFORE为非原子全SHA扫描。BOUNDARY_AFTER仅元数据辅助结束核查，不宣称第二次全树SHA冻结；当时已有文件仅WORKFLOW变化，后续回传与审核日志为授权记录。原加载规则五文件另行真实重算SHA与起始基线一致。

ponytail实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

D05-R06仍未收口，本次优先交付Demo不替代其失败回归、独审与return。真实数据接入是本演示的剩余工作，不能用合成结果证明已完成。
