

## GL-B01 R1 / Codex / 2026-10-04T17:52:25.543038+08:00

- 状态SUBMITTED；唯一GLB01_ACCEPTANCE.md v1；Codex唯一writer，源码已停写。
- 起始master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6，01全tree tracked/untracked/ignored；当前26保护GL/math/配置/UI/旧evidence漂移0。
- 外部并发human_replay/annotator.html更新首尾SHA在26单列，root未写、未回滚、不归因GL；21初次全树不变assert失败保留。
- ponytail实际读取C:/Users/30680/.codex/skills/ponytail/SKILL.md。

### 集中诊断与覆盖

source/model/window/旧draft绑定，regionXY全高度、单source frame/互异3验证组，frozen selector/indices gates；全部源行/坐标/场景统计与posthoc legacy PCA标域。manual确认消费时从source/model/plan重算权威观察，避免caller报告篡改改变footprint。00完整矩阵，20逐ID自验。无当前FIT残差筛holdout，不改26/1.1，不标ground.valid。

| 文件 | 与用户差异区分/用途 | SHA |
|---|---|---|
| src/human_fall_detection/core/ground_region_review.py | 本轮新文件：区域复核/CLI/集中tests | 02382a314f7b97d984e0df7f4e7729df3435ec52fa22c2aaca8c9ff297b937c0 |
| src/human_fall_detection/tests/test_ground_region_review.py | 本轮新文件：区域复核/CLI/集中tests | ecdb06570234b04aee411de6f8c62f24aea03d45fc2ac73697750d0791cb58d6 |
| src/human_fall_detection/scripts/review_ground_regions.py | 本轮新文件：区域复核/CLI/集中tests | 47100a095e6986223314f7fc53621f26d884aebad8d93691658e488584d3c800 |

| ID | 层 | 入口/命令 | 自验 | 证据 |
|---|---|---|---|---|
| R01 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| R02 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| R03 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| R04 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| R05 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| R06 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| S01 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| P01 | offline | 08–20原命令/逐条证据 | BLOCKED（剩余行集/精度/SDK） | 22_manifest/26_scope |
| D01 | offline | 08–20原命令/逐条证据 | NOT_RUN | 22_manifest/26_scope |
| Q01 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| Q02 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| Q03 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| Q04 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| Q05 | offline | 08–20原命令/逐条证据 | PASS（自验；独审待完成） | 22_manifest/26_scope |
| Q06 | offline | 08–20原命令/逐条证据 | NOT_RUN | 22_manifest/26_scope |

08集中8/09fall453/05follow2 exit0，10真实CLI exit0、15已有out exit2；11 AST3.8；13全部2959行scalar/成员对拍；14 synthetic完整人工确认分支仍physical/candidate=false。12 PNG实际查看，19原HTML离线mock逻辑通过，真实browser未重试/NOT_RUN（既有协议限制）。source_01/02/03/04新编号完整版本、review_01/02产物均保留，不覆写历史。22完整manifest关闭作者日志，回传与后续probe/review/controller/status按排除项追加。

### 人工证据与限制

用户已明确图中低位连续带为现场木地板、侧上层为工作台（17/18）；随后说明台面距离水平参考面75cm，24记录显式cm→0.75m、测量方法/不确定度未提供。25仅场景层gap诊断，两层median差0.827637m，与参考差0.077637m；含场景杂物/边缘，不是独立台面测量/地板误差，也不输出标签行或更新参数。20提交在24之前形成，后补资料24/25、26新scope保留时间顺序；不能抹掉用户确认或说用户没给物理参数。

当前P01只剩具体源行集合边界/精度/SDK复核；人工语义已完成。源行候选全部高度均保存，精确地面集合未签造，selection=null。下一步行级身份复核/固定变换误差评估，不自动算法候选/IRLS/设备/采集/生产/部署。指定Go Flash/defaultDB只读独审前一次fresh≤1min无工具probe，正文stdout归档新编号；源码持续停写。


## 2026-10-04 GL-B01 R1指定独审收口

2026-10-04 GL-B01 R1 **区域复核/诊断软件独审PASS / SUBMITTED / STOPPED**：[唯一v1](GLB01_ACCEPTANCE.md)/[收口](evidence/2026-10-04_gl_b01_r1/33_CLOSEOUT_01.md)/[独审](evidence/2026-10-04_gl_b01_r1/30_OPENCODE_VERDICT_01.md)。R01–R06/S01/Q01–Q06 PASS，无需返工；用户木地板/工作台语义和75cm参考已记录，P01剩余行集/精度/SDK BLOCKED，D01 NOT_RUN。89帧当前数据2959候选场景行保持全高度、未制造精确ground标签。联合反解下一单按新用户具体授权处理，B代码持续停写。
actual probe26.547s、review994.250s/exit0/stop；31模型导出、32工具及62SHA无漂移；外部annotator及ignored pycache变化单列，source不改。
