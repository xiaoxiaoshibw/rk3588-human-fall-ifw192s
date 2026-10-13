"""Final evidence-level adjudication. No production/old evidence writes."""
from prepare import E,load,save,sha
model=load(E/'opencode_actual_model_03.json');assert model['models']==['opencode-go/deepseek-v4.1-flash'] and model['last_finish']=='stop' and model['exit_code']==0
assert load(E/'opencode_completion_03.json')['marker']
assert load(E/'candidate_regression_06_command.json')['exit_code']==0
assert load(E/'benchmark_no_feasible_command.json')['exit_code']==0
assert load(E/'09_integrity.json')['PASS']

def write(n,t):
    with (E/n).open('x',encoding='utf8') as f:f.write(t)

write('08_CODEX_CROSS_REVIEW.md','''# Codex交叉裁决：保留所有OpenCode原报告

第一轮CLI exit0但所有read拒绝，实质审计BLOCKED，06_opencode_review.md保留。第二轮增加Git project-relative精确白名单后实际完成源码/证据阅读，06_opencode_review_02.md保留；第三轮在同一真正独立审计session中读取補证，06_opencode_review_03.md保留。CLI1.18.35、实际opencode-go/deepseek-v4.1-flash、session ses_edfc71127ffelfZe8UBTFTEywA、初审/补审exit0、finish stop；完整export中每个assistant模型身份实际核验。全程工具只read、无执行/写入/子任务。

| 意见 | 处理 | 最终裁定与证据 |
|---|---|---|
| 五格/大候选假拒绝、旧成功原样、严格原门 | 两方读码一致；作者5/25反例+70小集合oracle+真实11格复核 | CONFIRMED；候选逻辑无新FAIL；35项具名回归PASS |
| 非共线无可行项完整拒绝路径未测 | 接受，新增25/60/100场景与精确C(n,4)计数、SVD次数 | 补证通过；100候选3921225四元组/152097 SVD/38.990秒（含mock计数），性能限制保留，不板端准入 |
| 重复/并列/v3新路由缺专门用例 | 接受，新增3项；测试脚本固定candidate/frozen路径 | 补证通过；v3可从原15cm回退改为沿用修复后的25cm，这是明确语义变化，旧成功不变 |
| 原stderr简略因此没有选择器运行/-W error | 不接受“未运行”的推断：05_command.json已包含test_selector和-W error | 开放原argv+新增06 verbose35项及源码SHA；模型补审认定缺口闭合 |
| B07 CLI版本/help/身份/权限文件不存在 | 不接受不存在断言：文件早已保存，只是未入白名单 | 开放准确文件，模型补审B07逻辑PASS；help实际在cli_help.stderr，两流原样留存；真正模型由作者session export核验，不要求模型自证 |
| 输入report/meta外部依赖，BLOCKED标签不足为证 | 接受增强证据自包含，复制原report/meta/manifest并SHA绑定；原raw/domain仍只读外部并实际核验 | 候选原ROI=原旧完整dict；原72 P95 FAIL，report valid=false/recommended=null；实际source sha校验，非只写标签 |
| 全量SHA未由OpenCode执行、最终return未由模型见证 | 保留审阅方UNKNOWN；不伪称两套独立SHA执行 | Codex起止实际复算封闭关键字节，append-only与final manifest由作者完成；不同责任层不能当源码逻辑FAIL |
| O(n4)失败兜底不能实时生产 | 接受并保留 | 离线候选交付；E01 BLOCKED，板端性能D01 NOT_RUN；不扩大测试到150无必要，因为无生产时延承诺 |

OpenCode补审最终真正代码FAIL=无，B01–B08代码/证据结构PASS；作者执行的数值/SHA及最后seal未经模型执行，UNKNOWN保持。Codex仅据实际运行与文件字节闭合这些作者责任项，不投票、不篡改原报告。

共线剪枝适用于内部clean整数格key，有限工作域|key|≤400、int64乘积安全；重复key间距0不可能合格。没有将接口扩展到外部任意浮点/非有限key，没有新成功门、阈值epsilon或点云残差删减。Python3.8仅候选语法确认；板端实际环境仍NOT_RUN。
''')

table='''| ID | 最终自验结果 | 证据/边界 |
|---|---|---|
| B01 | PASS | 01 baseline、原源/输入/旧证据SHA、09 guard及最终seal；main只作上下文 |
| B02 | PASS | 5格反例、原门不降、完整oracle |
| B03 | PASS | 旧成功完整dict、真实121647、真拒绝/重复/并列/稳定排序/caller ownership |
| B04 | PASS（离线） | 小/大失败路径完整；非共线无可行项C(n,4)精确计数；O(n4)限制公开，不是性能准入PASS |
| B05 | PASS（本地） | 35项-W error；身份/purity/15cm源码SHA未变、v3路线联动有检查；3.8语法，板端运行NOT_RUN |
| B06 | PASS / 有效TLS BLOCKED | 原11 clean格/四ROI保持，72 P95=0.050291869m FAIL；无新TLS估计或真实输入导出 |
| B07 | PASS（实际只读复审） | CLI1.18.35/指定模型/原始IO/argv/权限/export；首轮不可读不计完成；模型未运行数值/SHA |
| B08 | PASS（最终seal绑定） | 历史不变、原失败保留、append-only return、manifest逐项复算；不宣布ACCEPTED |
| E01 | BLOCKED | 未接生产、未发布/部署 |
| D01 | NOT_RUN | 无设备/物理/采集/B2/B3，板端性能未跑 |
'''
write('FINAL_REPORT.md','''# CL2-09B 离线修复提交

2026-10-09（Asia/Shanghai）。**SUBMITTED / STOPPED；规定B01–B08检查通过，尚未ACCEPTED；121647有效TLS仍BLOCKED，生产接入BLOCKED，设备/物理NOT_RUN。** 最终字节完整性绑定final_integrity.json与10_evidence_manifest.json。没有自动进入新阶段。

## 修复结果

已交付完整可运行的隔离候选[candidate/floor_sheet.py](candidate/floor_sheet.py)和单文件[02_fix.patch](02_fix.patch)，variant `cl209b_feasible_roi_v1`，源码SHA见candidate_version.json。候选副本其他runtime文件与frozen逐SHA相同；原生产树、CL2-08隔离树和CL2-07/08/09A冻结证据未由本轮修改。新文件全部在本目录；唯一外部写入为已授权旧CLUSTER-01 return追加。

原问题是先选最大间距或唯一贪心组合，再只检查其条件数。该组合共线失败，不代表无其他满足原约束的四区。修复先计算完整旧结果，旧成功直接原样返回；只有旧失败才在全部满足原间距≥0.5m、独立4、条件数≥0.1的组合中最大化最小间距，稳定并列取排序最早项。无可行四区仍返回原失败诊断。真共线集/组合快速排除，无门控降低、误差epsilon、Z过滤或异常点删除。

这同时处理≤24枚举的错误排序与>24单次贪心失败。原先成功的>24贪心结果不重排名，保留既有ROI。原v2假拒绝的部分场景现在可提供合格25cm四区，v3按原控制流采用它们而不走15cm回退；v3/15cm自身源码与门控未改，但这项触达变化已明确记录并测试。

## 验证

35项本地回归全部PASS，实际命令 `python -X utf8 -B -W error -m unittest -v test_selector floor_detector_test floor_sheet_test floor_roi_test leveling_test`，PYTHONPATH明确指向本轮candidate/frozen；完整argv/退出码/具名stderr和test/candidate源码SHA在candidate_regression_06_command.json及.stderr。

覆盖5格4种合格替代、25格旧贪心失败、70个小候选随机集合的全枚举oracle、旧成功dict、拒绝/并列/重复/输入反序/不修改caller、原间距边界、Python3.8语法、身份/purity、v1 verbatim、15cm既有回退、v3新25cm路线、配平数值和真正127.0.0.1 HTTP集成。没有联网到板端；HTTP测试显式禁止板端调用。板端Python3.8/NumPy1.17实际运行NOT_RUN。

真实121647只读原bin：原拟合帧及冻结auto候选平面重建11个clean cells，旧/新selector完整dict精确相同，四区与原report精确相同。原ordinal72/ROI2为300点，P95=0.05029186936019117m，仍FAIL；原TLS valid=false/recommended=null和有效TLS BLOCKED保持。没有重新拟合TLS、替代验收或导出有效真实数据。report/meta/manifest只读复制在input_snapshot，raw/domain绑定原路径及SHA。

## 性能限制

完整失败搜索最坏O(n4)，只适用于本轮离线候选交付，不承诺运行中的程序或板端时延。实测存在可行项：25/60/100候选约0.119/4.271/34.209秒；完全共线可快速拒绝。补测非共线无任何可行项：

| 候选数 | 完整四元组数 | SVD次数 | 秒（含计数mock开销） |
|---:|---:|---:|---:|
| 25 | 12650 | 1772 | 0.1473 |
| 60 | 487635 | 30857 | 4.4303 |
| 100 | 3921225 | 152097 | 38.9902 |

未提供绝对最坏时间上界，更大规模未跑。未来若另行授权生产接入，需要单独性能设计与验收；本轮不为降低耗时加数量cap重新制造假拒绝，不擅自部署或改运行程序。

## 实际独立复审及裁决

OpenCode CLI1.18.35，实际`opencode-go/deepseek-v4.1-flash`，有效独立session `ses_edfc71127ffelfZe8UBTFTEywA`；源码初审及补审exit0、最终finish=stop，actual model从完整session export重算元信息核验。进程agent工具仅read、精确Git-project-relative及absolute白名单，shell/write/task/network工具deny；CLI模型请求及自身日志/DB属于已批准运行环境。原argv/stdout/stderr/version/help/model/permissions/export都保留，没有模拟输出。

首轮exit0但read全拒绝，实质BLOCKED，不计独审完成；补齐按Git project root匹配的白名单后重新真实审阅。独立初审发现非共线无解性能与专门路由/并列检查缺口，本轮补齐35具名测试、SVD/完整枚举实测及自包含input副本，候选源码补丁不再变。其“文件不存在/未跑选择器/-W error未证”由实际已存argv及进一步开放准确路径澄清，原报告不修改。补审真正代码FAIL=无，结构及证据一致性PASS；OpenCode没有运行数值/SHA，作者执行层UNKNOWN原样保留。Codex负责实际起止SHA、最终return和seal，不假称双份全量执行。详细逐项在08_CODEX_CROSS_REVIEW.md；原报告06_*保留。

## 执行失败、来源与并发

所有执行尝试留存：初次缺human_replay_lib隔离fixture，第二次sandbox默认temp子目录权限，第三次回环socket权限，第四次HTTP已到leveled_latest但缺validation fixture。仅补齐原只读依赖副本，把临时目录放本轮evidence并批准本机HTTP；未降低测试断言。第五轮32项PASS，第六轮补证35项PASS。

执行输入来自CL2-08 `D:/Code/cl208audit` 固定源副本及已绑定原输入，原HEAD语境cfbb80c…加SHA overlay，不冒称新代码已提交。当前main起点master/347a5bf…，全文件库存含untracked/ignored只作上下文；其中detect_overlay.js及.test.js范围外并发变化在09_integrity.json记录，未回滚、不推断操作者。它们未作为运行输入；main原floor_sheet.py、隔离全树、历史证据和原raw/domain/report/meta起止SHA实际核验。

ponytail实际路径Codex C:/Users/30680/.codex/skills/ponytail/SKILL.md；OpenCode读本目录PONYTAIL_SKILL.md的原副本。没有新依赖安装，Python3.12.10/NumPy1.26.4本地测试；不改原物理参数边界。

## 唯一验收表v1逐ID

'''+table+'''

表为00_SCOPE_AND_ACCEPTANCE.md v1，SHA在verdict.json。旧CLUSTER01 v1及CL2-07整体BLOCKED/09A诊断PASS不回填。最终作者字节完整性在final_integrity.json、完整证据10_evidence_manifest.json（不自哈希），return只追加原传统聚类分支的CLUSTER-01.md，返回中使用本轮主工作区证据绝对路径，避免误指分支下不存在的新目录。

复现须授权的新revision，不覆盖本轮或旧evidence；步骤见README与run_*脚本。交付已停止，不自动接入生产、发布Console、commit/push、部署、采集、B2/B3或继续下一阶段。
''')

save('verdict.json',dict(status='SUBMITTED / STOPPED',acceptance_file='00_SCOPE_AND_ACCEPTANCE.md',acceptance_version=1,acceptance_sha256=sha(E/'00_SCOPE_AND_ACCEPTANCE.md'),
    acceptance={**{f'B0{k}':'PASS' for k in range(1,9)},'E01':'BLOCKED','D01':'NOT_RUN'},
    effective_TLS_121647='BLOCKED',physical_root_cause='UNKNOWN',production_integrated=False,board_runtime='NOT_RUN',
    candidate_source_sha256=sha(E/'candidate/floor_sheet.py'),tests=35,independent_model=model['models'][0],session=model['session'],
    independent_numerical_execution=False,known_limit='Offline complete fallback worst O(n4); n100 measured38.99s including mock counters; no production latency approval.',
    final_integrity='Bound by subsequent final_integrity.json and10 manifest; no ACCEPTED claim'))

text='''\n\n## CLUSTER-01 R8 — 2026-10-09 / CL2-09B ROI选择器假拒绝离线修复 / SUBMITTED · STOPPED

- 用户在“CL2-09B离线修复、保留门控、不部署”范围后明确“好的继续”。Codex唯一writer，ponytail实际C:/Users/30680/.codex/skills/ponytail/SKILL.md；OpenCode实际读本轮PONYTAIL_SKILL.md。新证据位于D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_09b_r1/（本轮在主工作区evidence；旧支线return只追加，不误用../evidence相对链接）。完整FINAL_REPORT.md、candidate源码、02_fix.patch、source/input SHA、35项具名原始回归、性能、真实CLI、裁决与manifest均保存。
- 唯一CL2-09B验收表00_SCOPE_AND_ACCEPTANCE.md v1，SHA见verdict.json；CLUSTER01原v1及CL2-07/08/09A历史不改。来源固定CL2-08 isolation源码复制；当前main起点master/347a5bf…仅上下文，执行用SHA frozen/candidate。仅candidate/floor_sheet.py改变，原main和冻结生产源码未动，未接运行程序、commit/push/发布/部署/采集/B2/B3。
- 根因量词错误：最大间距或唯一贪心组合不合格，不等于不存在合格四区。新候选旧成功原样返回，只有旧失败在完整可行集最大化间距；原间距0.5m/独立4/condition0.1、A层/purity/15cm全不变。v2原假拒绝修复后v3可直接承接25cm四区、不再进入15cm；此联动明确声明及测试。
- 35项本地-W error全部PASS，具名日志及argv/PYTHONPATH/test+candidate SHA齐全；原环境/fixture失败保留。5格及25格反例、70小随机oracle、旧成功/重复/并列/拒绝/边界/ownership/调用者、实际回环HTTP均覆盖。板端3.8/NumPy1.17运行NOT_RUN，3.8仅语法。
- 完整失败兜底最坏O(n4)。非共线无可行项100候选实际遍历3921225四元组，152097 SVD，38.990秒含counter开销；仅离线候选，不作板端/生产时延承诺、不加cap假拒绝。
- 121647原bin与冻结auto平面重建11 clean格；旧/新完整selector及四ROI精确一致，ordinal72 ROI2 P95=0.05029186936019117m仍FAIL，原TLS valid=false/recommended=null；有效TLS BLOCKED、物理根因UNKNOWN。无重新估计TLS、删点或真实有效导出。
- OpenCode真实CLI1.18.35/opencode-go/deepseek-v4.1-flash；有效session ses_edfc71127ffelfZe8UBTFTEywA，源码审+补审exit0/finish stop，工具仅read、完整raw IO/argv/权限/model export。首轮所有read拒绝的BLOCKED保留、不计完成。补审代码FAIL=无、结构证据PASS；数值/SHA未由模型执行仍UNKNOWN，由Codex实际起止复算与最终seal闭合，不伪报双份执行。
- 本轮B01/B02/B03/B04/B05/B06/B07/B08=PASS（离线检查及最终seal绑定）；E01=BLOCKED，D01=NOT_RUN；121647有效TLS BLOCKED。不是ACCEPTED/生产接入许可。main无关overlay两项并发变更仅记录，不回滚；关键原源/输入/历史SHA不变，return前缀保持，最终final_integrity.json及10_evidence_manifest.json逐项封存。
- 到此停止；未自动进入生产、板端、后续性能改造或任何新阶段。
'''
write('return_append.md',text)
print('FINAL_REPORTS_READY_FOR_APPEND_AND_SEAL')
