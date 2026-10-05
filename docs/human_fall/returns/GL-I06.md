

R1 skeleton planned, not yet submitted — 见 evidence/2026-10-04_gl_i06_r1_skeleton/（99_STOP_WRITE.md 记录的 7 文件 SHA 与停写声明为准）。本段不提交、不标 SUBMITTED，不覆盖下方既有 R1 提交/独审记录；是否并入、作废或另开实施单由用户/Codex 裁定。

---

## GL-I06 R1 / 2026-10-04 / SUBMITTED

唯一验收GLI06_ACCEPTANCE.md v1；Codex唯一研究writer。实际pony­tail路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。
branch master / HEAD cbd0be1c86a1051a9a5800dfb7263f842896e1e6；首尾完整tracked/untracked及显式ignored输入SHA见01/16基线，范围外变化0。

采用结论：保留冻结单次TLS，不采用K2/K3。开发62case、额外固定source12case、最终封存种子30case、107项集中契约探针。测试数仅台账，逐ID结果如下。
K2/K3单假设偏差可减少，但分别新增10/6个开发未决；完整W与不同精炼W域明确，误闭合0。最终holdout为合成，不是当前89帧的真实物理留出。

| ID | 自验 | 证据 / 限制 |
|---|---|---|
| A01 | PASS | R0 62cases source/FIT/settings/raw/sample SHA；K1与旧W全等；active05真实WHAT_IF一次转换后W/metrics全等。 |
| A02 | PASS | raw per draw拒绝、旧代表动作、refine/成员/merge/资源detail完整；report counts是旧callback adapter计数，非收敛计数。 |
| A03 | PASS | math scalar独立oracle+合成GT；full W指标和stored subset分域；ties/chain/late/weak与每预算边界。 |
| A04 | PASS | R0已证0.827°截取偏差→K2/K3同sampled域；每轮重查，正常不收敛/注入cycle/later越界/LO gap单列；均不伪closed。 |
| A05 | PASS | full W support最大、全FIT J/覆盖分列；schema/caller/source/units/NaN/zero/line/旧out；IRLS条件实验NOT_RUN，未声称鲁棒收益。 |
| A06 | PASS | 10类×3seed×置换，固定source另3RANSAC seed；三独立validation groups及空间bounds；未筛holdout；freeze后1707/1719/1741首次最终合成holdout30case。 |
| A07 | PASS | 3次active计时每K、12case三重复，分阶段/序列化；另进程Windows memory peak；GT/最差区域/稳定/误闭合/额外未决；不称板端或端到端加速。 |
| S01 | NOT_RUN | pony­tail/先diag/单writer/不可覆盖/首尾SHA完成；指定Go Flash/defaultDB实际独审待执行，故当前NOT_RUN。 |
| B01 | BLOCKED | 真实up、point-origin高度、地面身份未核；physical=false、ground_valid=false。 |
| D01 | NOT_RUN | 不生产接入/设备运行/部署/采集；RK3588性能NOT_RUN。 |
| Q01 | PASS | checks_05身份/输入/不可覆盖/无缓存；schema bool及空序列非法K/LO拒绝。 |
| Q02 | PASS | scalar全相似/链/中best/ties/weak/late×四预算0/边界/不足。 |
| Q03 | PASS | 数值非收敛与资源独立；注入solver-state cycle不是实际TLS振荡证据。 |
| Q04 | PASS | 同支持J仅诊断，小J distinct不吞；鲁棒权重/零尺度权重计算NOT_RUN，条件适用由独审确认。 |
| Q05 | PASS | 硬场景/seed/置换/固定source/真实WHAT_IF/validation独立；真实最终留出NOT_RUN。 |
| Q06 | NOT_RUN | 成本/否定/冻结/停写已完成，实际probe/独审当前NOT_RUN。 |

开发最差单平面GT/独立区域：
K1：法向 0.411852478°，offset 0.011593347m，区域RMS 0.043115929m / P95 0.081146612m。
K2：法向 0.323418439°，offset 0.002930087m，区域RMS 0.043116771m / P95 0.079318112m。
K3：法向 0.280728624°，offset 0.002742756m，区域RMS 0.043092672m / P95 0.079168339m。

独立memory（整进程含imports，不是算法增量）：
K1 PeakWorkingSet 71970816 bytes / PeakPrivateCommit 733319168 bytes。
K2 PeakWorkingSet 78929920 bytes / PeakPrivateCommit 739872768 bytes。
K3 PeakWorkingSet 91549696 bytes / PeakPrivateCommit 753819648 bytes。

活动源码：refinement_05.py；入口checks_05/publish_04/fixed_source_02/holdout_03/cost_memory_03。01–04历史修订均保留；只有_01/02首次数值源码运行及_04/_05完整发布/最终入口实际使用，未执行修订不是试验结果。
活动R1台账r1_case_*_02.json来自不可变_01数值记录；_02追加full-W vector/scalar复核、J/覆盖和额外决策计时。active05真实K1及合成完整入口复核相同W。
所有最终holdout数值源码SHA与method_freeze_01.json相同；无曝光后调参。冻结源码与生产423/2旧回归仍匹配，不重跑代替独审。
日志已关闭；19_manifest_01.json为全部作者本轮文件+冻结依赖SHA（排除manifest自身），接着追加return后停止代码写入。独审新检查只在opencode_review_01，独审失败不自动返工/切模型。

Manifest SHA256: 57b226671258e13526a81618baa5ac2b7f7afdb0ac03b274c4876aea5e0c1f05
验收表SHA256: 58983b71733056c19ccea7da62a6e59440bb8ca3420d99a1a5402784086ac847
实际执行者Codex；指定OpenCode独审尚未执行，未填会话/模型成功。全部原始命令退出码见17_evidence_audit_01.json；本次所有记录退出0。

---

## GL-I06 R1 / 2026-10-04 / 指定只读独立二审（OpenCode Go Flash / default DB）

- 执行者：OpenCode CLI，实际模型 `opencode-go/deepseek-v4.1-flash`，default DB；只读独审，不写算法/生产/配置/输入/旧证据，不改源码或自批标定。
- 证据目录：`docs/human_fall/evidence/2026-10-04_gl_i06_r1/opencode_review_01/`（新编号 00_review、01–09 脚本与 JSON，未覆盖任何旧文件）。
- 控制器 probe：`21_service_probe_01_meta.json`/`23_probe_session_01.json`，session `ses_efa9b0eddffeCDGAhIWtGA8fpk`，`PROBE_OK` exit 0；本次二审流 `22_second_review_01.jsonl`。
- ponytail 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`。
- 起始 branch/HEAD：master / `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（与 before/submission/manifest 一致，范围内源码/输入未变，changed_sha=0）。

| 验收ID | 独立二审 | 依据 / 限制 |
|---|---|---|
| A01 | PASS | 清单 646/646、冻结依赖 2917/2922（5 项 before 即缺/坏符号链接，前后一致）；62 R0 SHA 与 K 台账一致、K1≡R0 W、fresh 重算复现、W 域明示。 |
| A02 | PASS | 186 台账计数恒等式、逐 draw 分阶段拒绝、资源与收敛分列；reason 汇总不替代计数。 |
| A03 | PASS | 自写纯标量 oracle 与 62R0+186K+90final 的 full-W/stored 域全等；tie/链/late/弱边界/预算/多重性/BEST_ONLY 非门全对；candidate_budget=0 时 full best=max(W)、stored None。 |
| A04 | PASS | 复现 0.827°/108 成员截断偏差；K2/K3 同域；真实不收敛（high_noise K2 682/683）强制 unresolved；注入 cycle/越界保留末有效见证、无静默回退；LO 缺口单列。 |
| A05 | PASS | full-W 最大支持；J/覆盖重算 0 差；17 项非法输入全拒。鲁棒权重 NOT_RUN：仅对称噪声截断偏差，wall/table/dual 为竞争曲面、无混合尾部证据，条件不适用经确认。 |
| A06 | PASS（附限制） | 10 类×3seed×置换 + 固定 source 3 RANSAC seed；非退化案例 3 独立验证组、含 bounds、全行无残差过滤；freeze 早于首个 final 0.87s、90 final 台账独立 oracle 无误闭合；最终合成。限制：collinear/narrow_band/real_approved 无平面故无区域打分；“竞争 closed”不认证区域质量（wall K1 0.412°/0.043m，已披露）。 |
| A07 | PASS | 每 K 3 次 active 计时、12 组三重复+真实 3 次、阶段/序列化/decision 单列、独立子进程内存峰值（数值与提交一致）、一次 dtype 转换、无 RK3588/端到端声明。 |
| S01 | PASS（软件） | ponytail 路径、先 diag、单 writer、不可覆盖（写探针独立验证）、首尾含 untracked；指定 Go Flash/default DB probe 由控制器提供；本次指定二审即本报告会话。 |
| B01 | BLOCKED | physical=false、ground_valid=false；真实 up/高度/身份未核；真实 approved 合格 draw=0。 |
| D01 | NOT_RUN | 无采集/部署/设备/production 接入；桌面离线。 |
| Q01 / Q02 / Q03 | PASS | 输入与身份、三类×tie/链/late×预算 zero/one-short/exact/+1、K1-3 收敛/资源分列均独立复验。 |
| Q04 | PASS（鲁棒 NOT_RUN） | 同支持 J 仅诊断、小 J distinct 不吞；鲁棒条件未触发。 |
| Q05 | PASS（真实最终留出 NOT_RUN） | 硬场景/seed/置换/固定 source/真实 WHAT_IF/验证独立均已核；物理留出因 B01 未跑。 |
| Q06 | PASS | 成本/否定/冻结/停写完成；probe 与指定二审在场；未自动下一单。 |

结论：未发现违反 GLI06_ACCEPTANCE v1 的软件缺陷（REWORK=0）；无 false closure；生产/配置/driver/UI/HR/旧证据前后 SHA 未变；B01 物理 BLOCKED、D01 设备 NOT_RUN。采用结论“保留 K1、不采用 K2/K3”有据。

**SECOND_REVIEW_SUBMITTED / STOPPED**


## R1指定独审与最终收口附记 / SUBMITTED

# GL-I06 R1 / SUBMITTED / STOPPED

当前研究软件条目已完成指定Go Flash/defaultDB独审；整单未ACCEPTED。Codex代码自作者提交后停写，研究不接入生产。
结论：保留冻结单次TLS，不采用K2/K3。K2/K3虽降低部分GT误差，但开发分别新增10/6个未决；无误闭合，单次最佳误差下降不满足采用门。真实approved先验861 draws中angle828/height2/抽样退化31，合格0，不能用加轮数或猜up解决。

| ID | 现行独审结果 |
|---|---|
| A01 | PASS |
| A02 | PASS |
| A03 | PASS |
| A04 | PASS |
| A05 | PASS |
| A06 | PASS |
| A07 | PASS |
| S01 | PASS |
| Q01 | PASS |
| Q02 | PASS |
| Q03 | PASS |
| Q04 | PASS |
| Q05 | PASS |
| Q06 | PASS |
| B01 | BLOCKED |
| D01 | NOT_RUN |

条件实验：鲁棒权重NOT_RUN（本单未激活，不主张混杂影响为零、不宣称鲁棒收益）；真实最终物理holdout NOT_RUN。当前89帧均为开发/WHAT_IF；最终30case为冻结后独立种子合成holdout，不能冒充物理标定。
物理B01 BLOCKED：实际up/点云原点高度/地面身份未核；physical=false、ground_valid=false。设备D01 NOT_RUN：无板端执行/采集/部署/生产接入。

关键误差须分场景：开发最差法向wall_19_False K1=0.4118524776°，offset=0.0115933474m，其区域最大RMS=0.0260081429m；最差区域RMS高噪high_noise_19_True K2=0.0431167707m，K1=0.0431159289m。不是同一wall案例的两项误差。
成本：每K至少3次active计时；独立进程PeakWorkingSet K1/K2/K3=71970816/78929920/91549696 bytes，整进程含imports。stage/LO/序列化、GT/稳定/额外未决详见17_evidence_audit_01.json与research_01台账；不称RK3588性能。

独审原始过程：第一阶段1114.922s/exit0；第二阶段554.484s/exit0。分别8/2次同名检查源码编辑，以及不准确的不可变/场景/多重性表述，均作为历史流程FAIL保留。25/31恢复27个精确源码版本及64次命令记录，最新版本SHA与实际文件一致；原报告不改。34计划责任审查后最终阶段改为不写检查源码，仅执行已冻结代码并在内存重定向输出到新目录；159.813s/exit0，write/edit/patch调用0，源SHA不变。现行S01/Q06基于此次真实复核闭合，不宣称历史未违规。
实际会话ses_efa9a4743ffeSwZQpegWTbN8DH；39_final_verdict_session_01.json核Go Flash模型且最终stop。派前probe分别14.344/11.812/12.218s，均PROBE_OK/exit0/无工具；无model/DB/auth/permission切换。

最终范围核对：master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6；作者manifest646文件均未改变，全部protected首尾漂移0、范围外新增0；Windows catkin表示保留、driver/UI/HR/原数据/批准draft/旧证据均未改。42_FINAL_VERIFY_01.json为最终核验；19_manifest_01.json为作者完整manifest，后续独审/controller记录按其排除项分列。

最终独审：[39_FINAL_OPENCODE_VERDICT_01.md](39_FINAL_OPENCODE_VERDICT_01.md)（原模型文字原样保存）；不可变输出opencode_review_01/readonly_final_01/。第一/二阶段报告为保留历史，不作为未纠错的最终入口。
本工单只离线研究、状态SUBMITTED，停止代码写入；不自动跨入下一单、候选生产接入、新采集或部署。
