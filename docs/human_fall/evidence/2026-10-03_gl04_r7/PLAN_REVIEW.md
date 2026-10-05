# GL04 R7 设计前置 / 2026-10-03

同工作项、GL04_ACCEPTANCE v1，唯一OpenCode Go Flash/default DB writer，Codex独审。R6原95/97全部闭合，54lib/41+2+3+20独立exit0；R6 CODEX_REVIEW只剩V07/V09/C08 source位置来源消费者FAIL。来源契约由Node _state_payload 1156–1186/1208–1216、INTERACTION165/178确定，不新增要求。

根因：显式负向position_source_from只并入physical门，当前位置和“实测”还只看三元组/position_predicted。需要共享source位置provenance门用于所有当前source位置读数/实测标签消费者；bbox_observed=false是独立的框/physical标志，不应连带清空actual_points合法raw中心。缺字段/nullable legacy保留。仅source中心可用性，不要求新tracking/几何/变换/单位/严格Node组合框架。

Codex纠正98中五条过严“必须隐藏所有灰预测诊断”的探索assert：现有C08保留原非physical灰诊断，实际五例current '--'/physical unknown；非合法Node组合的容忍局限记录，不当阻断，不要求实现改变它。原98失败历史不覆盖，后续新检查按契约只断言非测量/非physical。真正的两source来源FAIL保持，不降原44/48/54。

| C行 | 组合/消费者 | ID/预期与覆盖 |
|---|---|---|
| C01 | legacy cal/GDID/source_from缺失/null × locked source读数 | V09：first select/原XYZ/track保留，原54/92；physical门不放宽 |
| C02 | raw/state/candidate任一先到 × raw来源变化 | V07：更新当前位置/实测标签同用当前版本字段，不迟用旧值；R6入口保留 |
| C03 | 同内容reload/仅相机变动 | V05：token/原ID不变，source读数资格不受camera影响；原90 |
| C04 | cal版本交错→双侧当前恢复 | V06：混配unknown/拒旧、恢复仅当前；原90 |
| C05 | known/null/undefined cal/schema/GDID、同ID异内容 | V05/06：R6绑定/token全部保留；原90/97/54 |
| C06 | schema2/frame/epoch/verifier非法 | V06：已有source/physical失效不放宽；原90/97 |
| C07 | 当前目标→空/other/重复→唯一恢复+ready基线 | V07：原无详情/0/多匹配未知、历史不背书；原90/97 |
| C08 | locked×source_from{missing,null,actual_points,unavailable,predicted,other}×bbox_observed{missing,true,false}×position_predicted | V07/09：明确non-actual来源不显示当前sourceXYZ/“实测”；actual_points/legacy缺来源保留raw，bbox false仅physical未知；合法预测灰诊断/年龄/当前空原义保留；98两真FAIL+新字段交叉正例 |
| C09 | pending/ready silent/disconnect→reconnect | V06/09：当前未知、旧select拒、历史/ACK/当前终态保留；R6真实browser16–21与90复用未改入口 |
| C10 | ground valid/unknown/none/verifier与source合法实际读数 | V06：R6raw与physical分门保留，来源恢复后只恢复合法raw；95/97 |
| C11 | caller变candidate/RT/units/coordinate token×list/drag | V05：旧拒/当前原ID保留；R6原90/97/54，选择本身不要求已有目标实测 |
| C12 | rotate/zoom/resize/DPR/clip/退化×两mode | V04：数学/真实已验部分复用；隔离DPR-only/完整camera clip仍NOT_RUN，不冒实测 |
| C13 | support0/3/3000/3001/9000/显式坏units | V02：预算/索引及单位门保持，原90/97/54 |
| C14 | source/support units正确/缺失/mm/其它×当前/旧选择 | V03/05：R6全部守门保留，不因位置来源修改降低units资格 |
| C15 | normal/tilted/no_extrinsics固定frame、完整绑定、offset=t[2] | V08：R6生成器/六图已过且不改，物理false/生产缺R/t/support分层；source_from只如实消费 |

实施前00_diag必须把C08所有读数/位置来源、hasMeasuredPos/hfPred与physical/source几何消费者逐格映射函数/赋值顺序；其余行引用R6已验检查并说明不改。不要把actualObservationQualified（含bbox负旗）粗套raw来源，否则损坏合法raw正例。

范围最多四preview+新r7证据+returns末尾。R6/旧证据、正式Q/E/帮助、core/config/driver/其它webui/数据冻结。先读ponytail实际路径并准确回传；R6日志确实read了.claude路径、回传误称.config/skill，R7勿沿用虚构。按原model/default DB≤1分钟probe，复用同session需先真压缩当前长上下文，无同时writer。无部署/采集/板端网络/GL05/commit/push/reset/checkout/clean。
