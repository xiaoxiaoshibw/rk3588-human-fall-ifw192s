# GL-E02 R1 自验提交 / SUBMITTED（待指定独审）

Codex唯一writer。唯一GLE02_ACCEPTANCE.md v1；ponytail实际C:/Users/30680/.codex/skills/ponytail/SKILL.md。只新增三固定代码路径，未fit、不I06/IRLS、不设备/采集/部署/生产接入。物理P01 BLOCKED，照片真实/视向确认、刚刚拍摄陈述为已完成子项。

## 逐条自验（不是独立验收）

| ID | 自验结果 | 本轮证据 / 入口 |
|---|---|---|
| E01 | PASS | prepare_packet/read_bound_json/load_adapted；18集中tests；21/22真实来源chain/audit/NPZ当前SHA对应；旧NPZ未改 |
| E02 | PASS | strict keys/type/finite/units、实际派生binding与expected_source；Q01/Q03/Q04测试；当前/旧日志不晋级 |
| E03 | PASS（软件） | check_measurement，独立方法/误差/from-to/原点引用；unknown合法；照片known观察与recording_eligibility分开；17缺口 |
| E04 | PASS（软件） | check_selection复用gate_selection；源行/group/重复/alias/独立frames反例；合成合法members；真实selection=null，不签造确认 |
| E05 | PASS | 五输出白名单与固定pending/false；齐全未审合成正例、unknown真实正例、禁止runtime字段 |
| E06 | PASS | content-address request/selection ID；输入首尾SHA与parse快照SHA；同内容packet_03/04逐byte相等；已有out exit2；保护目录测试 |
| S01 | PASS（自验阶段，指定独审待完成） | 00写前diag、01全树基线；19完整fall回归438；05 follow2仍适用；24 Python3.8 AST；范围核查/manifest见26/27/28 |
| P01 | BLOCKED | 用户不知道SDK/up/原点/源行；安装连续性未知。17分层表，packet_03 measurement及selection=null |
| D01 | NOT_RUN | 无设备算法/新采集/部署/网络/driver修改 |
| Q01 | PASS | 18 tests：pending、缺/坏/schema/NaN/单位、错误数值类型 |
| Q02 | PASS | 身份/caller/新ID/同selection ID异内容/parsed snapshot/已有out/保护路径；23真实out拒覆写 |
| Q03 | PASS | source/window/run/config/code绑定错拒；无旧录制binding的观察只unknown |
| Q04 | PASS | 独立方法、PCA/fit_offset拒、窗口不等于原点、from/to逆向、单位与误差反例 |
| Q05 | PASS | fit/三个互异validation成员正例；跨组/同FIT/duplicate/alias/越界/残差方法/缺人工依据反例 |
| Q06 | PASS | 全字段齐全也不晋级；真实无source映射仍pending，照片确认保留 |
| Q07 | NOT_RUN（待独审） | 当前代码封存后一次fresh≤1min无工具probe，指定Go Flash/defaultDB只读独审，最终CLI流保存 |

## 原始命令、版本与失败保留

18_checks_04：python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_ground_evidence_input.py -v，15 methods exit0；19_fall_regression_03同suite全量438 exit0；05_follow_regression_01为2 exit0。数量仅日志摘要，逐ID以表为准。24三文件AST按3.8语法检查，不冒充板端Python3.8.10/NumPy1.17.4实际运行。

21/22：python -B -W error src/human_fall_detection/scripts/prepare_ground_evidence.py --request 本目录/20_real_request_03.json --output 本目录/packet_03（或packet_04），各exit0；23重用packet_03 exit2。所有原命令与真实exit见对应_meta.json，输出/log均新编号。

02首版集中test exit1保留：合成bag SHA本来为ab重复，负例仍改成同值ab，未真正改内容。这是检查fixture错误；改为ef，原断言不降低。test source_01/02保留完整字节。随后作者阶段新增selection内容ID、SDK严格数值、parsed JSON快照身份 checks，ground/tests source_03/04保留各版本；production三个固定文件路径在提交前修订，未同名改历史检查器/报告/输出。当前最后版本为source_04；CLI源码source_01未改。独审后不修改三源码。

08/packet_01/02对应首版源码；16为中间请求版本；20/packet_03/04绑定当前最终版本。历史全保留，不把旧包当当前版本。旧批准draft/四box/数学/冻结配置/原输入/driver/UI/HR/I06及历史证据保持。

已知局限：工具核身份/结构/成员而非签造物理真值；说明文字不能验证测量事实。current/日志上下文可归档但无录制联合绑定时仍unknown。没有人工源行不会阻合法pending正例，不生成fitter可直接消费的候选标定。

本报告日志已关闭；完成范围对照和manifest、按RETURN_TEMPLATE回传后停写源码。独审/最终状态另新编号记录，不覆盖本报告。
