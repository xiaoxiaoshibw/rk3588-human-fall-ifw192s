

## GL-N01 R1 / Codex / 2026-10-04T16:42:04.440822+08:00

- 状态SUBMITTED；唯一GLN01_ACCEPTANCE.md v1；Codex唯一writer已停写，Go Flash/defaultDB只读独审待执行。
- 起始master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6；01全tree tracked/untracked/ignored SHA，13范围核查保护漂移0/范围外新增0。
- ponytail实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。
- 诊断/根因：旧参数仅存证据而未数值应用；复用load_adapted/numeric/calibration arithmetic，新nominal身份和版本独立，不伪造已测extrinsics/ground。00覆盖入口/操作矩阵，原draft/math/config/UI/driver/evidence冻结。

| 变更路径 | 与用户原差异区分/用途 | SHA |
|---|---|---|
| src/human_fall_detection/core/nominal_leveling.py | 本轮新路径；固定参数变换/CLI/集中tests | bb86855e279a9fa082301dcdeaa175872a7512b5a0c245531f383f02c8f72a99 |
| src/human_fall_detection/tests/test_nominal_leveling.py | 本轮新路径；固定参数变换/CLI/集中tests | 4fd3ec5cc2e8dccb284dbdc257ed7acd94d2feb5ec9e795ee0e1e35eff6b0a52 |
| src/human_fall_detection/scripts/level_capture_nominal.py | 本轮新路径；固定参数变换/CLI/集中tests | 5c16dc0481109960259608a9d106d7f4ff9c90fee5ef85c74272098b370e2f9c |

| ID | 层 | 入口/命令 | 结果 | 证据 |
|---|---|---|---|---|
| N01 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| N02 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| N03 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| N04 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| N05 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| N06 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| S01 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| P01 | offline | 02–11原命令/日志、12逐ID自验 | BLOCKED | 13源码SHA / 14manifest |
| D01 | offline | 02–11原命令/日志、12逐ID自验 | NOT_RUN | 13源码SHA / 14manifest |
| Q01 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| Q02 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| Q03 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| Q04 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| Q05 | offline | 02–11原命令/日志、12逐ID自验 | PASS（自验；独审待完成） | 13源码SHA / 14manifest |
| Q06 | offline | 02–11原命令/日志、12逐ID自验 | NOT_RUN | 13源码SHA / 14manifest |

原命令见02–05/10_meta：7集中/445fall/2follow exit0；真实89frames/4372400points→3699085有效+673315零return（nonfinite0），全部source_rows与逐帧对应；独立scalar全点差3.55e-15m。nominal_model/NPZ/frame_stats/input_manifest/view.HTML已输出，07静态PNG实际查看、09Node离线页面逻辑检查通过。IAB拒file:协议，真实browserNOT_RUN/BLOCKED，不绕过、不伪报mock为browser。软件来源/source/代码manifest清楚；独立物理P01仍BLOCKED，低位点带旋后近水平但z<0，不自动用拟合height替换1.1m。

计划v3新增；旧v2/v1全文已在本轮before.txt保存，只加现行入口覆盖，E01/E02/I06成果不白做。source_01/02版本新编号，后续只读独审不得编辑源码。14完整manifest关闭作者产物，回传及后续probe/review/status按排除项追加。当前不拟合/IRLS/设备/采集/部署/生产接入。


### R1 指定只读独审附记 / STOPPED

状态SUBMITTED。N01–N06/S01/Q01–Q06 PASS，无需返工；P01独立物理BLOCKED，D01 NOT_RUN；N05只离线/静态/逻辑PASS，真实browser NOT_RUN/BLOCKED。19实际原文、20actual model导出、21工具及40文件首尾SHA audit、22收口。source/meta/bin/旧配置数学与代码SHA保持。当前参数名义变换/图已交付，改变参数生成新modelID/独占输出；未称未来未知姿态已自动估计，不启用runtime/verified。Codex已停写，无拟合/设备/新采集/部署/生产接入。