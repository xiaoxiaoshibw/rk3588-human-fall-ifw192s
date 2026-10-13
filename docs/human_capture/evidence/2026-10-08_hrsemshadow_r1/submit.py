"""Create this round's report and append the HR return. Never edits older records."""
import csv
import hashlib
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
REL = OUT.relative_to(ROOT).as_posix()

def read(p):
    return json.loads(p.read_text(encoding='utf8'))

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, obj):
    with (OUT / name).open('x', encoding='utf8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')

def textfile(name, text):
    with (OUT / name).open('x', encoding='utf8', newline='\n') as f:
        f.write(text)

binding = read(OUT / 'pass3/binding.json')
summary = read(OUT / 'pass3/summary.json')
audit = read(OUT / 'audit_checks.json')
negative = read(OUT / 'negative4/summary.json')
baseline = read(OUT / '00_baseline.json')
for n in ['full_pass2', 'full_pass3', 'old_negative3', 'old_negative4', 'prepare', 'review_check', 'vote_repro', 'plot', 'plot_zoom']:
    assert read(OUT / (n + '.run.json'))['exit_code'] == 0
assert read(OUT / 'determinism.json')['pass']
rows = json.loads((OUT / 'regression_registration_r3.stdout.log').read_text(encoding='utf8'))
assert len(rows) == 23 and all(r['result'] == 'PASS' for r in rows)
today = datetime.now(timezone(timedelta(hours=8))).isoformat()
matrix = [
    ('SEM-01', 'PASS', '00_baseline.json + pass3/binding.json + integrity.json；5908 起始文件、五段原始源/固定TLS/诊断代码绑定；最终完整性检查后生效。'),
    ('SEM-02', 'PASS', '原函数/阈值精确片段 SHA；24 ROI 特征与12空场抽样逐值一致；semantic_selfcheck exit0。'),
    ('SEM-03', 'PASS', '1276 原始帧，1561 帧分支行，4311 实际候选簇；同原cleanup簇全部有效成员；全零/无效源row独立记账，原输出同时保存。'),
    ('SEM-04', 'PASS', '三值/标志/数值原因齐全；小簇分档、空点与无效点自检；NECK未显式分类=null，不补骨架；valid_member_size_bins见audit_checks。'),
    ('SEM-05', 'BLOCKED', '114205 REF影子：HUMAN证据13/244（5.33%诊断上界）；人工簇身份/全帧连续映射0覆盖，不可报95%通过。'),
    ('SEM-06', 'BLOCKED', '114254 REF影子：269/271（99.26%代理）；非ROI成员与家具混入身份待GT，gate仍WARN。'),
    ('SEM-07', 'BLOCKED', '114340离线V2：281/281代理；185点与5 cleanup点身份UNKNOWN，不能把区域保留率当人体保留率。'),
    ('SEM-08', 'BLOCKED', '114422离线V2：1/195（0.51%诊断上界）；HEAD全0、ARM45/195，腿证据1帧；GT未闭合，目标不宣布通过。'),
    ('SEM-09', 'PASS', '空场285帧：V2残留0簇/0 HUMAN；工作空间1582簇=0 HUMAN/1097 OBJECT/485 UNKNOWN；全部小簇与虚点影响公开。'),
    ('SEM-10', 'BLOCKED', '旧空场54帧283簇0 HUMAN；WD01区域出现4(P)/12(WS) HUMAN待身份审阅；WD02固定job代码绑定不符BLOCKED；格栅NOT_RUN，低横条cleanup后0点不计有效负例。'),
    ('SEM-11', 'PASS', '按最近5个实际储存帧、含缺失帧、每机器身份每帧<=1票、原min_age；歧义UNKNOWN，真人身份BLOCKED；43碰撞帧、88过期确认帧及合成repro完整披露。'),
    ('SEM-12', 'PASS', '52228边缘线索、原185点+原5 cleanup点精确对账；34关键帧、全帧本地载入/sidecar校验工具完成；点身份BLOCKED_GT，实际浏览器UI子检查BLOCKED。'),
    ('SEM-13', 'PASS', '逐段分母、全簇三值/上游/粗候选/瞬时joint/原track/参照票分开；ROI全部PROVISIONAL，旧负例未冒充GT准确率。'),
    ('SEM-14', 'PASS', 'pass2==pass3与negative3==negative4所有数据digest；30语义检查、票repro、GT负例检查、34页内案例headless检查；PL38/replay45/registration23实际全过；早期失败保留。'),
    ('SEM-15', 'PASS', '本轮只新增evidence与追加return；全旧资产/SHA与return原前缀复验，见integrity.json；生产、captures、阈值、artifact与旗标未变。'),
    ('SEM-16', 'PASS', 'SUBMITTED / REWORK_REQUIRED分项；ponytail实读路径已记录；接入与最小修订设计已提交，停在证据可复审，不自封ACCEPTED。'),
]
write('acceptance_status.json', {'ticket': 'HR-SEM-SHADOW', 'acceptance_version': 'v1',
    'acceptance_sha256': binding['acceptance'], 'ticket_sha256': binding['ticket'],
    'status': 'SUBMITTED / REWORK_REQUIRED; human GT and some negative coverage BLOCKED; not ACCEPTED',
    'rows': [{'id': i, 'status': s, 'reason': r} for i, s, r in matrix],
    'outside_scope': {'independent_review': 'NOT_RUN', 'production_switch': 'NOT_RUN', 'deploy_capture_board_network_driver_ML': 'NOT_RUN'}})
table = '| ID | 自验 | 证据与限制 |\n|---|---|---|\n' + ''.join('| %s | %s | %s |\n' % row for row in matrix)
data_table = '| 会话/分支 | 总帧 | 整簇HUMAN证据帧 | ROI关联HUMAN帧（代理） | 旧粗候选帧 | 旧瞬时联合确认帧 | 原当帧簇track-confirmed | 原active轨道确认 | 参照旧票确认 | 参照语义票确认 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|\n'
for s in summary:
    data_table += '| %s / %s | %d | %d | %d | %d | %d | %d | %d | %d | %d |\n' % (s['sid'][-6:], s['mode'], s['frames'], s['any_human_frames'],
        s['proxy']['roi_human_frames'], s['old_geometry_frames'], s['old_instant_joint_frames'], s['old_cluster_confirmed_frames'],
        s['old_active_track_confirmed_frames'], s['reference_old_frames'], s['reference_semantic_frames'])
cluster_table = '| 会话/分支 | 全候选簇帧 | HUMAN | OBJECT | UNKNOWN | 60–199 | 200–399 | ≥400 | 无簇帧 |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|\n'
for s in summary:
    cluster_table += '| %s/%s | %d | %d | %d | %d | %d | %d | %d | %d |\n' % (s['sid'][-6:], s['mode'], s['clusters'],
        s['semantic'].get('HUMAN_EVIDENCE', 0), s['semantic'].get('OBJECT_EVIDENCE', 0), s['semantic'].get('UNKNOWN', 0),
        s['size_bins'].get('60-199', 0), s['size_bins'].get('200-399', 0), s['size_bins'].get('>=400', 0), s['no_cluster_frames'])
limits_table = '| 会话 | 原始无效XYZ | 变换后通过denoise/workspace | 主前景候选无效成员 | 碰撞帧 | 旧确认不满足实际帧票的帧 |\n|---|---:|---:|---:|---:|---:|\n'
for s in summary:
    if s['mode'] == 'WORKSPACE':
        continue
    limits_table += '| %s | %d | %d | %d | %d | %d |\n' % (s['sid'][-6:], s['invalid']['raw'], s['invalid']['workspace'],
        s['invalid']['candidate_members'], s['collision_frames'], s['stale_window_confirmed_frames'])
report = f'''# HR-SEM-SHADOW r1：全帧整簇冻结语义旁路

状态 **SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**。工具和离线证据已交付；四段人体目标的全帧身份GT缺失，SEM-05～08 BLOCKED；旧对抗覆盖SEM-10 BLOCKED。设备/物理/部署/采集/独立复审/生产切换 NOT_RUN。本轮在接入设计后停止。

冻结 S-A+ v1 在真实整簇上并未普遍复现区域抽样表现：中央普通静立仅13/244帧、举左手仅1/195帧输出HUMAN证据；两段的“任意候选HUMAN帧”诊断上界也低于95%。右桌前269/271、隔板旁281/281是候选结构/ROI代理结果，不能称准确率或正式95%通过。新空场两种口径均0 HUMAN，允许UNKNOWN并公开全部分母。

## 输入、冻结与复现

- 执行者：本聊天 Codex，单writer，无子代理/OpenCode/改模型；实际模型标识未通过运行接口核实，不编造worker身份。用户本轮直接授权A–D；README/工单初始DRAFT字样不被改写。
- 起始 {baseline['branch']} / `{baseline['head']}`；完整基线5908文件、35,826,341,519字节（tracked+untracked及ignored captures/既有HC证据/console dist），脏树原样保留。详情00_baseline.json、00_dirty.patch；当前轮排除于旧资产保护集。
- 唯一表 [HR_SEM_SHADOW_ACCEPTANCE.md v1](../../HR_SEM_SHADOW_ACCEPTANCE.md)，SHA `{binding['acceptance']}`；工单SHA `{binding['ticket']}`。不替换W03或HR-RET-V2验收表。
- 五段固定源帧244/271/281/195/285=1276，源点62,680,017。固定job与TLS/manifest/report/代码/源meta-bin全部绑定在pass3/binding.json。没有ICP重估、按mtime换job或loader放行。114205/114254只REF_SHADOW；114340/114422只离线V2函数试验；空场identity-reference不证明跨会话PASS/VALID。
- Frozen bodies SHA `{binding['semantic']['frozen_bodies_sha256']}`，原文件SHA `{binding['semantic']['original_sha256']}`；适配器源片段、数学和参数精确保留（含w_min=.06）。semantic_selfcheck 30检查、24 ROI结果；全管线991帧与历史retention逐值一致，24 ROI点数组/特征与12空场抽样逐值一致。历史S-A+生成时PL SHA早于inc2，不执行历史main；本轮新数据诊断的PL/registration代码绑定与当前逐文件相同。
- 实际原始布局是28B/点（meta与RL.STRIDE_BYTES对账），不是README示例16B。source row为帧内原始row，global row=offset_points+row；逐级顺序子序列映射有断言，重复坐标依序保留，不靠坐标Set折叠源row。

## 每段结果，分母不可偷换

{data_table}

“原当帧簇track-confirmed”是候选处理时快照；“原active轨道确认”包括lost轨道保留的状态，因此114205为25与98，而人体ROI关联旧确认是0。原pipeline里的`confirmed`不是有效字段，实际记录`human_confirmed`及每簇`track_confirmed`。上表原窗口与严格实际帧参照必须区分；参照身份仅PROVISIONAL机器空间身份，真人确认仍BLOCKED。所有无簇帧留在总帧分母。

{cluster_table}

分档按原聚类候选总n；无效源row过滤后的有效n另在audit_checks.valid_member_size_bins和CSV中计数。小于400的冻结v1一律UNKNOWN/POINTS_LOW；本轮工作空间空场485/1582（30.66%）UNKNOWN，1097 OBJECT。V2空场虽0候选，仍有10375前景点、6974 cleanup删除、2880未成分量点、146个小分量，不能把0候选说成点已完全清空。所有低于候选门的小分量/散点在frames.jsonl记账。

## 整簇边界与最小诊断

114205中帧f122/c1：全簇2416点、ROI重叠2337点；冻结区域诊断HEAD/LEGS/TORSO正证据，完整簇HEAD=false、LEGS=false、TORSO=true、FLAT_TOP=true → OBJECT。全簇cv=.104、w_torso=.190，而ROI cv=.235、w=.173。只多79个ROI之外成员就使组合证据改变，不能把手工ROI的结果推广到整簇，更不能偷偷先裁干净人体。

114422中帧f97/c1：全簇2443点、ROI重叠2361，w=.185、cv=.115、HEAD/LEGS/ARM=false → UNKNOWN。全部195主大簇TORSO=true，但HEAD=0、LEGS=1、ARM=45，导致HUMAN仅1；72帧FLAT_TOP，122帧INSUFFICIENT_OR_CONFLICT。此为真实完整候选与原区域结构的差异；哪些外缘成员属于家具、人体或混合仍需GT。

114254中帧c1含32个ROI外成员，114340含11个；不能因此自动写MIXED或STATIC_OBJECT。NECK参数/标志在冻结实现中没有显式分类，本轮保持null；min_bands虽在TH中，实际cv要求至少5个15点带，不能把TH.min_bands=3当已实施的可见性判据。没有新增头/关节坐标、骨架拟合或缺点补全。

![四段中帧全簇点云，局部坐标显示](full_cluster_cases_zoom.png)

图中的绿/灰/紫是算法证据，不是人工身份；红色为删除线索。缩放只改变显示坐标范围，分类始终使用全成员。未缩放视图见full_cluster_cases.png；所有点可按row定位。

## 无效XYZ与上游保留

{limits_table}

五段原始无效XYZ总11,744,951，均与既有report.invalid_xyz_count一致。当前变换把零XYZ平移到有效高度，继续进入冻结背景/工作空间；本轮没有修生产I01或重建替代图。四段主前景及V2空场候选无invalid成员，参考匹配把这些点移出前景。

未删背景空场285个候选含2,623,664个虚点。最终两遍把同一原cleanup簇的全部有效源成员交给旧结构规则与语义规则，另存未经改变的原pipeline/Tracker输出；不重聚类、不让placeholder提供正证据。虚点可能已影响原图和簇拓扑，本轮有效成员对照不构成生产I01补丁已落地或物理坐标已核验。初始pass1曾把含虚点的整簇保守UNKNOWN；其证据保留，当前仅pass2/pass3有效成员对照支持结论。

上游逐帧workspace、reference删除、online-supported删除、cleanup删除与未成簇都有完整row账。隔板区域“91.9%保留”仍是原固定区域口径，不作真实人体损失8%结论。52228条区域删除线索中，f140原185个reference删除点与原数组精确匹配；5个cleanup区域点分别列在edge_review.json，全部身份UNKNOWN。

## 旧负例与覆盖缺口

- 旧空场233658：54帧、283整簇=217 OBJECT/66 UNKNOWN/0 HUMAN；有效原成员口径，两遍一致。
- WD01源223757：P165帧884簇、workspace165帧810簇；场景有真人，不能把整个场景的89/38个HUMAN簇当静态误报。历史WD01半径.55区域P在f65/66/147/148输出4次HUMAN，workspace12次；静态区域标签不是逐点身份，可能有遮挡/真人进入，优先审阅这些源row，不发布假阳性率。正式金标代表f2/42/150同位置全候选分别948/957/949点，均UNKNOWN，未凭机器补STATIC_OBJECT标签。
- 箱子历史区域64帧均有点，但逐帧支撑不足/结构不足全部UNKNOWN；只有合并校准集曾过400门，不能声称逐帧已排除家具误报。
- low_bar历史区域在本轮cleanup后64/64帧为0点，NOT_RUN有效结构覆盖；不能用空输入0 HUMAN做强负例。格栅没有独立来源/row身份，在现有资产中未找到可绑定样本，NOT_RUN，不把low_bar改名格栅。
- WD02固定旧job c9712acad48c4fb7a78cb119c08d4cdb 的leveling生成源码SHA与当前不符：历史leveling.py `4b8d7ae...` vs当前`3c3a881...`。本轮保持BLOCKED_INPUT_BINDING，保留失败日志，不改SHA、不换job、不重签或重新配平。新空场远场候选不能替代WD02金标。

## 原Tracker与独立3/5票

最近5个**实际储存原始帧ordinal**开窗；每候选机器身份每帧至多1票，缺失记0，关联歧义记null/UNKNOWN；至少3正票且原min_age=3。源seq缺口原样记录，不虚构未录制帧。仅唯一双向0.75m门关联才接续机器身份，仍用EMA.35与lost_max8；一对多/多对一拒绝强行近邻认人。不会把参照写回Tracker/Fall。

真实同帧track复用：114254共8帧、空场workspace35帧；空场有35帧参照关联UNKNOWN。114205原active确认98帧中88帧不满足按实际帧去重的原票参照，这包括缺失时不老化的状态；不把这些全部归因为真人误确认。逐簇处理快照、最终track状态、原5观测票、最近5实际帧票、missing/关联边和ID分歧均在votes.jsonl / vote_examples.json。

合成机械repro还复现原Tracker年龄3时，同一实际帧3个正簇可给一track3票；f0/f1正、f2–8空、f9正仍旧确认，但参照最近5帧仅1票。合成只是逻辑证据；两段真实输入的同帧碰撞/轨道拆合不是人工真人身份，依赖GT。冻结门与Fall从未修改。

## 人工审阅工具与GT纪律

[review.html](review.html)自包含34关键帧，可逐簇/点查看、投影切换、拾取原row；全帧入口选择pass3/clusters.jsonl与目标原始meta/bin，核SHA后固定变换重建全部成员。默认UNKNOWN/PENDING；簇PERSON需要人工person_id，点级标签只接受已绑定删除线索，导出需实际reviewer。机器未导出任何source:human真实标签。

gt_review_template.json与pass3/review.jsonl均source:diagnostic。手工导出后运行 `python -X utf8 -B -W error {REL}/finish.py validate <人工sidecar路径>`，校源/变换/代码、ID/seq、成员SHA、重复项、标签枚举与PERSON身份。校格式不验证标签真实性/覆盖；全帧每簇PERSON/STATIC_OBJECT/MIXED/UNKNOWN以及连续person_id必须由人工确认或批准的映射闭合，才评95%目标。

查看页34案例的headless渲染/表单拒绝逻辑exit0，GT校验器1个合成有效格式+8个拒绝例、真实标签创建0；实际浏览器UI烟测被环回连接超时和file协议策略阻止，单列BLOCKED（browser_ui_status.json），不声称截图/浏览器实操通过。两幅真实点云PNG已视觉检查。临时127.0.0.1只读helper已停止，未连接板端。

## 当前交付与日志

最终输入和结果：pass3（与pass2完全一致）/negative4（与negative3一致）。每个JSONL在CSV中有byte offset，可按sid/mode/ordinal/ci定位；完整row成员在clusters.jsonl，阶段删除在frames.jsonl，票在votes.jsonl。determinism.json保存全部数据文件的两对digest。

Node v24.14.0，Python3.12.10；Python统一-B -W error -X utf8，无新依赖。PL38/replay45/registration23实际PASS（T37-20不在该套自动运行内，不以这组回归改变历史验收）。registration首轮T37-09为临时目录rename EPERM/exit1，日志保留；r2仅require模块没有执行suite，不计测试；r3将夹具限定到本轮test_tmp并实际run，23ID全PASS。old_negative1遇到WD02绑定assert/exit1，继续独立输入的negative2/3/4保存BLOCKED，未绕过绑定。

初始pass1及negative1/2保留；shadow_initial.js保存发现时工具，当前工具版本见各run.json/本轮source_hashes.json。所有正式数据重放均exit0，确定性一致；初始失败/限制不是被覆盖或算通过。

## SEM逐项自验

{table}

SEM-01/15以最后完整旧资产检查integrity.json的实际结果为准；仅允许本轮输出与return追加，发现范围外漂移须追加修订，不能把PASS预期替代检查。当前状态不等于独立验收。

## 下一步设计与停止

见[integration_design.md](integration_design.md)。冻结v1的整簇鲁棒性不足，当前不建议直接切换票源。优先补身份/成员GT、端部与腿带污染诊断；后续校准必须按人物/场景分组，不能把本轮已经多次观察的五段称为全盲留出。接入、修订实现、配准治理、artifact、ML、多姿态/采集各需另行明确工单。本轮完成证据与设计后停止。
'''
textfile('README.md', report)
design = '''# HR-SEM-SHADOW 接入与最小修订设计（仅设计，未实施）

冻结v1暂不具备直接生产切换依据。中央静立13/244、举手1/195的全簇结构上界低于95%；即便右桌/隔板代理接近100%，真人GT与负例对抗覆盖也未闭合。

## 最小离线修订方向

不改背景/cleanup/聚类/Tracker/配准。先给同一真实完整簇生成结构支持分布：头端/上肢团与躯干的关系、腿带双柱和柱内离群成员；把STRUCT_OK或否决使用了哪些源row写成可审阅支持集合。整簇包含额外成员时，先判断正负证据是否由不同空间部分贡献，冲突/粘连返回UNKNOWN。不能从手工人体圆柱取样代替整簇，也不能把少量外缘点自动叫家具。

最小候选v1.1设计是保留TH原数值，先增加可见支持计数、结构团成员定位与冲突解释接口；若人工GT证明少量非人体端部/腿带成员支配判定，再在独立校准资料上设计鲁棒带统计或局部分量一致性。具体算法、带样本下限、异常点策略只能后续单独冻结新版本。本轮未扫描阈值、未运行v1.1或改参数。HEAD/ARM缺失继续invalid/UNKNOWN，不按身高比例补骨架。

校准资料：r1的7个手选/合并区域和WD01已用于开发；r2的竖条失误曾促成w_min修订，不称全盲集。本轮四段同一人的新会话已被ROI抽样和全帧观察，是诊断/开发数据，不能复用为独立最终测试。后续按“人物×场景×采集日”分组拆训练/校准/锁定留出，禁止相邻帧随机拆分；校准组包含静止、举手、贴家具和真正独立格栅/箱子/远场样本。多人物/姿态数据现缺，必须有后续采集授权和人工身份标签后再建盲留出；先记录方案，当前不采集/不开ML。

## 接口与三值票源

未来PC源触点：pc_apps/human_replay/human_pipe_lib.js 的pipeline_frame cleanup后/evidence_postpass附近提供相同簇所有有效成员；不能先classify_human硬门过滤。建议纯函数`semantic_cluster(valid_xyz, provenance)`返回version、semantic、flags、numeric_evidence、reason、support_rows和成员SHA。原joint/evidence作为旁路字段保留方便比较。无原始有效性/坐标/成员绑定则UNKNOWN并退回旧路径。

未来票源必须区分“身份关联”和“结构资格”：HUMAN_EVIDENCE投1，OBJECT/UNKNOWN不提供正票，但不主动取消身份；歧义关联UNKNOWN不强行链接真人。票窗按实际储存帧而非每次簇观测，最近5帧包括缺失，3票+原min_age；对象静态标签不能直接改身份生命周期/Fall。T01/T02修复必须另行授权和验证，本轮FrameVotes是审计器，不可直接复制为生产Tracker。

## 默认关、回退与消费端

future semantic_shadow和semantic_vote_source是设计名，当前没有新增配置/旗标/调用点。将来默认关时必须逐位保持现有P/旧票/Fall；shadow只保存诊断，切换票源需显式版本、GT闭合和独立复审。开关切换与seek/重复/倒退帧必须明确reset生命周期，避免把两种票源历史混用；回退时清理实验历史并重放旧路径，不能共享实验轨道状态。

浏览器human_detect.js/replay.js的载入、run_detect/_run_pipe_frame与UI面板是未来消费者触点，优先核全部调用者，包括seek与同帧去重。源码本轮只读。语义无删除权，不改变融合门、不允许WARN pair按正式V2运行；registration质量PASS仍不能替代新artifact loader VALID。当前不签发、重签、安装或启用任何artifact/生产旗标。无效XYZ生产保留I01单独工单，不顺带替换保留/聚类。

## 进入实施前的依赖与验收

人工：四段所有实际帧的各簇/非成簇人体状态及连续person_id；外缘/删除/合拆分成员归属；隔板185+5点；WD01区域HUMAN帧的静态/真人/混合标签；可绑定的格栅、箱子和WD02资产。格式校验通过不能当GT语义正确。对每会话按全部原始帧分母判95%，空场与已确认静态样本必须0 HUMAN，失败不调分母。

工程：修复/协议确认T01/T02/I01另授权；冻结新版源码/参数/校准来源；旧默认路径逐位回归、真实完整整簇两遍digest、跨坐标/无效点/缺失帧/同帧多簇/seek reset；独立reviewer读取本轮与新版实际证据。硬件/部署/采集/ML依赖不由本单授权。任一身份/输入/安全门未闭合就保持旧路径，停止切换。当前仅交付此设计，不自动进入下一单。
'''
textfile('integration_design.md', design)
source_files = sorted(p for p in OUT.iterdir() if p.suffix in ['.py', '.js', '.html'] and p.name != 'review.html')
source_hashes = {p.name: sha(p) for p in source_files}
write('source_hashes.json', source_hashes)
change_table = '| 文件 | 用途 / 用户原差异区分 | 源SHA |\n|---|---|---|\n'
for name in ['record.py', 'semantic.js', 'shadow.js', 'negatives.js', 'finish.py', 'review_template.html', 'review_check.js', 'vote_repro.js', 'plot_cases.py', 'submit.py']:
    change_table += '| `%s/%s` | 本轮新增离线工具；原生产脏树不动 | `%s` |\n' % (REL, name, source_hashes[name])
return_text = f'''

## {today} HR-SEM-SHADOW 执行 r1（Codex）

### 本轮信息

- 工单HR-SEM-SHADOW / r1 / 本聊天Codex单writer；用户直接授权A–D的PC离线范围。无子代理/OpenCode/改模型；模型运行标识未核实不填。
- 唯一表docs/human_capture/HR_SEM_SHADOW_ACCEPTANCE.md v1，SHA `{binding['acceptance']}`；工单SHA `{binding['ticket']}`。
- 状态 **SUBMITTED / REWORK_REQUIRED，未 ACCEPTED**；SEM-05～08与SEM-10 BLOCKED。设备/物理/板端/部署/采集/网络驱动/ML/生产切换/独立复审均NOT_RUN；实际浏览器UI检查单列BLOCKED。
- 起始branch/HEAD：{baseline['branch']} / `{baseline['head']}`；dirty/完整tracked+untracked+ignored资产SHA见 `{REL}/00_baseline.json`、00_dirty.patch；用户原差异保留。生产、捕获与旧证据最终逐文件完整性见 `{REL}/integrity.json`，return只追加、原前缀不动。
- ponytail实读路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）；复用冻结原函数、PL/registration/RL、stdlib与既有matplotlib，无新依赖。matplotlib技能实读完整路径 `C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md`。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 / 证据 | 入口与消费者 | 本轮处理位置 | 保留行为 |
|---|---|---|---|---|
| SEM-05/08整簇退化 | ROI外79/82成员改变顶团/腿柱/剖面；HUMAN帧13/244、1/195 | cleanup完整成员→冻结S-A+；旧联合判定/Tracker | 全帧harness与报告；不修冻结原型 | 不裁干净ROI、不试阈值；GT缺口保留 |
| SEM-11原票缺陷 | 同帧复用、缺失不老化；真实碰撞43帧、114205过期确认88帧 | PL.Tracker.tick；pipeline_frame；browser重复/seek消费者已读 | votes.jsonl、FrameVotes审计、vote_repro | 原Tracker/Fall零修改；歧义UNKNOWN，身份BLOCKED |
| SEM-04输入虚点 | 零XYZ无条件TLS/registration后通过高度/距窗 | registration.loadFrames/transformBuffer、浏览器载入、pipeline输入 | 原row账与同簇有效成员对照 | 不落地I01、不改变原图/聚类/产物绑定 |
| SEM-10负例不闭合 | WD02生成源码绑定不符；WD01区域不是全成员GT；格栅缺绑定样本 | 固定job、旧静态区域与全簇扫描 | negative4 + coverage.json | 不换job、不重签、不编家具标签/误报率 |

### 实际变更

{change_table}

全部产物位于 `{REL}/`，另仅本return追加。主输出为pass3（pass2同digest），旧负例negative4（negative3同digest）；CSV含JSONL byte offset、逐簇/帧row索引；源码和固定参数绑定见pass3/binding.json/source_hashes.json。历史发现pass1/negative1/2、失败日志和工具快照保留，不改旧evidence。

### 逐条验收（self-check，非独立验收）

{table}

逐ID详细证据见 `{REL}/acceptance_status.json` / [本轮报告](../evidence/2026-10-08_hrsemshadow_r1/README.md)。实际全帧/prepare/selfcheck日志exit0；SEM-05～08、10的BLOCKED不因exit0变PASS。SEM-01/15由最后实际integrity.json闭合；若漂移将追加修订。

回归：PL38、replay45、registration实际23ID通过，日志`regression_*.stdout/stderr/run.json`。registration首轮exit1(T37-09临时目录EPERM)、r2仅模块加载无执行不计回归、r3本轮隔离夹具实际run全过。old_negative1 exit1是WD02绑定不符，后续保留该输入BLOCKED而继续独立范围。两对数据digest逐文件一致；semantic 24原抽样+6边界检查、12空场抽样、991历史retention帧逐值对账；机械票repro/GT格式拒绝/headless34案例exit0。测试数字不替代本表项。

### 未闭合与限制

- 每会话正式95%目标仍缺所有实际帧的人工簇/成员身份或人工批准连续person_id映射。13/244与1/195只是当前任何候选HUMAN的诊断上界，明显未达到目标；269/271、281/281是代理证据，不发布准确率。
- 原185点与5 cleanup点精确定位、扩展52228区域删除线索均UNKNOWN；MIXED/人家具合簇不能由ROI重叠自动命名。WD01区域P4/WS12个HUMAN帧须人工排查；旧代表f2/42/150完整目标均UNKNOWN。格栅/有效low_bar未覆盖；WD02代码绑定阻断。
- reference票只作PROVISIONAL机器身份参照，关联不明UNKNOWN；不假装真人稳定确认。无效XYZ upstream图/拓扑影响仍在，有效成员对照不是生产补丁。
- 浏览器真实UI工具访问BLOCKED，单列browser_ui_status.json；页面逻辑34case/headless、人工标签拒绝检查及两幅真实PNG已验证，不能冒充浏览器截图。
- 弯腰/坐蹲/卧、多人物、物理地面、安装外参、真实跌倒、关节精度、板端与采集等NOT_RUN/BLOCKED，当前数据不提供这些结论。

### 交给独立复审 / 当前停止点

- 现行唯一表及本轮逐ID状态、完整命令exit/SHA/digest、原Tracker轨迹、无效row账、成功与失败均在本轮目录。
- 人工入口 [review.html](../evidence/2026-10-08_hrsemshadow_r1/review.html)，未预填source:human；gt_review_template.json为diagnostic，`finish.py validate`只校格式/绑定、不校人工标签真值或95%覆盖。优先审阅边缘/合粘/未知簇、43碰撞帧、88过期确认帧及WD01区域HUMAN案例。
- [接入与最小修订设计](../evidence/2026-10-08_hrsemshadow_r1/integration_design.md)：目前不建议生产切换；接口/三值票、默认关/回退、seek/reset、源码触点、GT和独立review依赖已列；校准按人物/场景/采集日分组，本轮数据不称全盲集。
- 停止在“证据和设计可复审”；未修改生产/冻结参数、未签artifact、未开生产旗标、未部署采集或进入下一工单。未自动启动独立复审。
'''
textfile('return_append.md', return_text)
target = ROOT / 'docs/human_capture/returns/HR-SEM-SHADOW.md'
before = target.read_bytes()
assert hashlib.sha256(before).hexdigest() == baseline['files']['docs/human_capture/returns/HR-SEM-SHADOW.md']['sha256']
with target.open('ab') as f:
    f.write(return_text.encode('utf8'))
assert target.read_bytes()[:len(before)] == before
write('submission.json', {'time_asia_shanghai': today, 'return_original_sha256': hashlib.sha256(before).hexdigest(),
    'return_prefix_preserved': True, 'return_append_sha256': hashlib.sha256(return_text.encode('utf8')).hexdigest(),
    'report_sha256': sha(OUT / 'README.md'), 'design_sha256': sha(OUT / 'integration_design.md'),
    'status': 'SUBMITTED / REWORK_REQUIRED; BLOCKED subitems; not ACCEPTED'})
print('SUBMITTED: 16 SEM rows; original return prefix unchanged; stop at reviewable evidence/design')
