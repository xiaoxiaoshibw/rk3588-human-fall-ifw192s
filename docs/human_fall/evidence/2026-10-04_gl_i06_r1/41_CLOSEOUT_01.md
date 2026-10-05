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
