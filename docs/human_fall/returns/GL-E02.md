

## GL-E02 / R1 / Codex / 2026-10-04T15:55:36.799028+08:00

- 唯一验收：GLE02_ACCEPTANCE.md v1，SHA 331fe411789d88eb79a3554fc837103bab961c8d9047e2a2d9ab387817944792
- 状态：SUBMITTED；软件逐ID仅自验；P01 BLOCKED；D01 NOT_RUN；指定Go Flash/defaultDB独审待执行，不宣称ACCEPTED。
- 起始master / cbd0be1c86a1051a9a5800dfb7263f842896e1e6；全树tracked/untracked/ignored首尾及原脏树见01/27，原3896文件变化0；三外部照片注释新增保留，见26/30。
- ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。

### 集中诊断与根因覆盖

| ID | 根因 | 入口/消费者 | 最小位置 | 保留行为 |
|---|---|---|---|---|
| E01/E02/E06 | 离线证据缺内容/窗口/版本绑定与独占输出门 | prepare_packet/read_bound_json/load_adapted | 三新文件 | 旧NPZ/来源链/原数据冻结，unknown合法 |
| E03/E05 | 已知观察不能自动晋级录制资格 | check_measurement→pending包 | ground_evidence.py | 下视≠测角，窗口≠原点，full fields仍false |
| E04/Q05 | 源行须独立人工身份及帧组关系 | check_selection→gate_selection | 复用indices/gate | 不按FIT残差筛验证；缺资料selection=null |

### 实际变更

| 文件 | 用途 | 用户差异区分 | 最终SHA |
|---|---|---|---|
| src/human_fall_detection/core/ground_evidence.py | 新离线校验/薄CLI/集中tests | 本轮新文件，原脏树保留 | 61149e65d085c64497517670f39a2a241d6b662ccd43f0a40e8a39c5e6f5cbd9 |
| src/human_fall_detection/scripts/prepare_ground_evidence.py | 新离线校验/薄CLI/集中tests | 本轮新文件，原脏树保留 | b42f5797e2facb00417989f7efec7c1d3c86dfbe6887e15bd9dc099412cd1c46 |
| src/human_fall_detection/tests/test_ground_evidence_input.py | 新离线校验/薄CLI/集中tests | 本轮新文件，原脏树保留 | 3691a3d8bcbb3adea56d88ba2bc5189397d32f06f20ca0ceb959b8390b962e9b |

### 逐条自验

| 验收ID | 层 | 命令/证据入口 | 结果 | SHA证据 |
|---|---|---|---|---|
| E01 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| E02 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| E03 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| E04 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| E05 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| E06 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| S01 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（自验；S01独审阶段待闭合） | 28_manifest / 26源码SHA |
| P01 | offline | 18/19/21/22/23/24及25逐行证据 | BLOCKED | 28_manifest / 26源码SHA |
| D01 | offline | 18/19/21/22/23/24及25逐行证据 | NOT_RUN | 28_manifest / 26源码SHA |
| Q01 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q02 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q03 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q04 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q05 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q06 | offline | 18/19/21/22/23/24及25逐行证据 | PASS（软件自验） | 28_manifest / 26源码SHA |
| Q07 | offline | 18/19/21/22/23/24及25逐行证据 | NOT_RUN | 28_manifest / 26源码SHA |

原命令/真实exit见*_meta.json与*.log：18集中15、19全fall438 exit0，05 follow2 exit0，21/22真实CLI exit0、23已存在out exit2；24 Python3.8 AST，非板端实测。02失败fixture改同值ab未构成变更，保留原日志与source_01/02；后来新增边界检查完整版本source_03/04归档。25提交解释版本，不覆盖旧输出。

### 未闭合与限制

照片真实/视向已确认，用户说刚刚拍摄已新记录；精确时间/安装连续性未知。SDK旧run/config、有效source/up、原点定义/尺量及源行不知道。照片木地板/障碍观察和三空间候选区已列，不能冒充三个validation。P01 BLOCKED，需要17独立证据与预登记误差/审查；89帧已曝光，不称未见物理holdout。不fit/I06/IRLS/设备/采集/生产/部署。

### 交指定只读独审

诊断00、物理分层17、自验25、scope26/27、manifest28、派工29、停写30。28包含所有已关闭提交产物SHA及三源码，回传在manifest后追加按排除项记录。当前代码/测试已停写；派前一次新≤1min无工具probe，指定opencode-go/deepseek-v4.1-flash/defaultDB独审全表，检查只读stdout，原最终文字由root保存新编号CLI流；失败不换model/DB/auth/权限，不自动进入下一单。


### R1 指定只读独审附记 / STOPPED

状态仍SUBMITTED。实际Go Flash/defaultDB独审E01–E06/S01/Q01–Q07 PASS，P01独立物理复核BLOCKED，D01 NOT_RUN，无需返工。独审原文36（原文首段“33流”实际应为35流）、收口41、模型会话39、工具/首尾SHA审计40。首次32外部技能目录自动拒绝后tool-calls结束，不算完成；相同会话续审35以stop完成，原始证据不覆盖。无权限/model/DB/auth切换；三源码自提交后停写、SHA不变。用户最新1.1m/约26°下俯按38作为给定的名义安装参数记录，历史提交包unknown不追改；P01不是阻认知或使用初始几何。后续未启动fit/采集/生产/部署。