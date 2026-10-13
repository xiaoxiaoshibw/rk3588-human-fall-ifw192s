"""Write this round's review records; append return after checking its old prefix."""
import ast
import csv
from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import sys
from record import OUT, ROOT, RETURN, sha, save, git

def read(p):
    return json.loads(Path(p).read_text('utf8'))

def materials():
    manifest = read(OUT/'input_manifest.json')
    pending = []
    per_branch = {}
    for i, entry in enumerate(manifest['entries']):
        frame = read(OUT/entry['file'])
        key = frame['sid']+'/'+frame['branch']
        s = per_branch.setdefault(key, {'frames': 0, 'clusters': 0, 'member_points': 0, 'invalid_member_rows': 0, 'reviewed': 0, 'person': 0, 'no_cluster_frames': 0})
        s['frames'] += 1;s['clusters'] += len(frame['clusters'])
        if not frame['clusters']:
            s['no_cluster_frames'] += 1
        for c in frame['clusters']:
            s['member_points'] += len(c['receipt']['rows']);s['invalid_member_rows'] += len(c['invalid_source_rows'])
            pending.append({'source': 'unreviewed', 'status': 'BLOCKED_GT', 'receipt': c['receipt'],
                'coordinate_id': frame['coordinate_id'], 'frame_file': entry['file'],
                'review_url': 'http://127.0.0.1:8883/review.html?frame='+str(i)+'&ci='+str(c['receipt']['ci']),
                'required': ['actual reviewer','complete cluster label','person_id if PERSON','track_epoch','human continuity','7 node visibility + visible region_rows + reasons']})
    save(OUT/'gt_pending.json', {'real_gt_records': 0, 'user_reply_2026_10_09': '无', 'all_pending_members': pending,
        'no_cluster_branch_ids': [e['id'] for e in manifest['entries'] if not e['clusters']],
        'minimum_tasks': {'development_1': '114205 ordinal112-114; review every complete cluster (2 each), never automatically select ci1',
                          'development_2': '114254 ordinal125-127; review every complete cluster (3 each), never automatically pick ROI',
                          'positive_and_control': 'at least one actual visible torso region and actual invisible/reject control; all other windows stay pending'}})
    save(OUT/'coverage_by_branch.json', per_branch)
    with (OUT/'frame_index.csv').open('x', encoding='utf8', newline='') as f:
        writer = csv.writer(f);writer.writerow(['id','split','seq','stamp_sec','stamp_nanosec','clusters','reviewed','status','review_url'])
        for i,e in enumerate(manifest['entries']):
            frame = read(OUT/e['file']);sf=frame['source_frame']
            writer.writerow([e['id'],e['split'],sf['seq'],sf['stamp_sec'],sf['stamp_nanosec'],len(e['clusters']),0,'NO_CLUSTER' if not e['clusters'] else 'BLOCKED_GT','http://127.0.0.1:8883/review.html?frame='+str(i)])
    compatibility = []
    for p in sorted(OUT.glob('*.py')):
        ast.parse(p.read_text('utf8'), filename=p.name, feature_version=(3,8))
        compatibility.append({'file':p.name,'sha256':sha(p),'python38_syntax':'PASS'})
    save(OUT/'compatibility.json', {'python38_syntax':compatibility,'actual_runtime':read(OUT/'freeze_r3.json')['python'],
         'numpy':read(OUT/'freeze_r3.json')['numpy'],'actual_python38_execution':'NOT_RUN; no dependency installation'})
    text = '''# 实际人工审阅任务（GT仍空）

用户2026-10-09明确回复“无”。本轮没有真实human sidecar，identity_gt/node_review均为空，336候选簇全部未审；骨架试验不得由Codex截图判断升级PERSON。

启动本地只读入口：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/serve_review.py`，打开 http://127.0.0.1:8883/review.html 。仅127.0.0.1；本轮测试服务已停止。Ctrl+C结束。

优先最小任务是两个开发段各3个连续实际帧：114205 ordinal112/113/114（入口frame=0/1/2）、114254 ordinal125/126/127（frame=20/21/22）。需逐帧检查全部完整簇，不预设哪个是人。member ID为sid/branch/ordinal/ci，原row、global、完整成员/原28B/坐标SHA均在帧JSON。确认为人时填写实际reviewer、同一person_id/track_epoch和真实连续性；家具STATIC_OBJECT、混合MIXED、无法确认UNKNOWN，不裁人体子集。

再标每节点VISIBLE/INVISIBLE/UNCERTAIN；VISIBLE须框选或输入可见区域的原row，理由明确。头/手不清楚保留UNCERTAIN，确认真实头区域才用HEAD_CONFIRMED。至少一个真实可见躯干正例和缺失/拒绝对照；不用把100帧全标完才满足最小B门，剩余未审必须保留。

全部336待审成员、完整receipt及定位URL见gt_pending.json；全部120分支行（含20无簇）见frame_index.csv。三个投影完整显示成员，不暗中裁XY柱；红点原始无效XYZ不能作为区域支撑。

导出后在新获授权证据轮复制工具/重新核输入，运行bind_inputs.js validate <实际sidecar路径>。标签校验只核绑定，不能证明人工真的观察或标签正确。工具当前支持逐簇保存/sidecar导出和导入；真实人工输出未执行。不要在本轮已交付evidence内覆盖产物。
'''
    (OUT/'GT_TASKS.md').write_text(text, encoding='utf8')
    print('MATERIALS',len(pending),'members; 120 rows; Python3.8 syntax PASS')

def report():
    integrity = read(OUT/'integrity_final.json')
    assert integrity['pass']
    manifest = read(OUT/'input_manifest.json');branches = read(OUT/'coverage_by_branch.json')
    metrics = read(OUT/'pass5/metrics.json')
    blocked = {4,9,10,11,14,15}
    reasons = {
      1:'6299旧路径/44,460,273,500字节基线；branch/HEAD不变；用户本轮明确离线授权',
      2:'R2全部交付SHA/传递导入、固定TLS与诊断矩阵核对；独立raw复算336簇/871476坐标/票据',
      3:'100唯一raw帧/120分支行；336未审簇/20无簇行全部保留；固定按会话划分，不称盲测',
      4:'真实reviewer/PERSON/连续person_id=0；两个开发sid各3连续实际帧门未满足，用户回复无',
      5:'CONTRACT/params-v1在首算法前冻结；参数SHA三次源码冻结间未变；无验证调参；真人参数标定BLOCKED',
      6:'纯XY平移、全有效成员/原Z/row保存；synthetic独立逆变换0m≤1e-5；真实PERSON标准化BLOCKED',
      7:'完整raw/member/global映射独立核验；20绑定/节点区域挑战；synthetic合法节点support独立重算；真人支撑BLOCKED',
      8:'空、非有限/原零XYZ、低支撑、家具/MIXED/UNKNOWN拒绝测试；184125无效源成员已定位，无上游重聚类',
      9:'synthetic真实形状数学正例产7节点，真人可见躯干正例没有GT；不得用全拒绝算阳性通过',
      10:'synthetic头/手和缺头拒绝PASS；实际举手窗口HEAD可见性未标，不验证真实头能力',
      11:'PCA退化/符号UNKNOWN、单下部/双A-B synthetic PASS；真实分离/朝向GT未闭合',
      12:'独立SkeletonTracker；实际整数stamp/dt；重复/倒退/seek/缺帧/换5类键/恢复/跳变实测；原Tracker/Fall无变化',
      13:'实际浏览器12检查+人工声明门；完整簇/row拾取/切帧/空场/篡改清状态；headless 6合成导出绑定检查另列；真人导出未发生',
      14:'逐节点336未审/valid0/UNKNOWN336；1680槽观测；区域误差、真人跳变/恢复和精度均BLOCKED，无伪造正确率',
      15:'固定验证/举手/空场拒绝流程运行；40空场分支行0有效PERSON节点；隔板/举手真人效果因GT缺失BLOCKED',
      16:'独立struct+标量变换复算raw/票据，synthetic显式胸中心[10,20,1.05]/support/逆变换；最终pass5/6三个数据SHA相等',
      17:'Python -B -W error；15 Python+20绑定+6审阅工具检查；replay45/pipe38/registration23回归exit0；旧资产SHA无变化，最终return前缀另核',
      18:'本轮工具/GT/效果/资产/失败/停止报告齐全；ponytail实读路径；SUBMITTED/BLOCKED，未ACCEPTED，无代理或下一阶段'}
    table = '| ID | 状态 | 实测证据与限定 |\n|---|---|---|\n'+'\n'.join('| SKO-%02d | %s | %s |'%(i,'BLOCKED' if i in blocked else 'PASS',reasons[i]) for i in range(1,19))+'\n'
    save(OUT/'acceptance_status.json', {'acceptance':'HR_SKELETON_OFFLINE_ACCEPTANCE.md v1','sha256':sha(ROOT/'docs/human_capture/HR_SKELETON_OFFLINE_ACCEPTANCE.md'),
         'delivery_status':'SUBMITTED / BLOCKED','accepted':False,'rows':[{'id':'SKO-%02d'%i,'status':'BLOCKED' if i in blocked else 'PASS','evidence':reasons[i]} for i in range(1,19)],
         'counts':{'PASS':12,'BLOCKED':6},'outside_scope':'NOT_RUN/BLOCKED; no W04/W05 qualification, WD02 remains BLOCKED'})
    (OUT/'ACCEPTANCE.md').write_text('# SKO逐项自验 v1\n\n唯一原表未修改；PASS仅限行内工具检查，不授予真人或生产资格。\n\n'+table,encoding='utf8')
    branch_table='| sid / branch | 计划帧 | 簇 | 全成员 | 原无效成员 | 已审PERSON | 无簇行 |\n|---|---:|---:|---:|---:|---:|---:|\n'
    for key,s in branches.items():
        branch_table+='| %s | %d | %d | %d | %d | 0 | %d |\n'%(key,s['frames'],s['clusters'],s['member_points'],s['invalid_member_rows'],s['no_cluster_frames'])
    runs={p.stem.replace('.run',''):read(p) for p in sorted(OUT.glob('*.run.json'))}
    cmds='| 记录 | 命令 | exit | runtime s |\n|---|---|---:|---:|\n'
    for name,r in runs.items():
        cmds+='| %s | `%s` | %s | %.3f |\n'%(name,' '.join(r['command']),r['exit_code'],r.get('runtime_s',0))
    (OUT/'COMMANDS.md').write_text('# 实际命令与日志\n\n所有*.run.json含命令/cwd/runtime/exit/源码和日志SHA，stdout/stderr同名。首次失败保留。报告/追加/manifest后产生的命令元数据见对应run文件。\n\n'+cmds,encoding='utf8')
    report_text='''# HR-SKELETON-OFFLINE 交付复审

**SUBMITTED / BLOCKED，未ACCEPTED。** 单writer本聊天Codex；没有外部审阅者/代理签署。用户2026-10-09明确授权A–F PC离线实施，后又确认真实sidecar“无”。本轮完成可独立执行的工具、审阅与证据工作；真人粗节点阳性及效果验收尚未闭合。

## 1. 实际工具与节点能力

bind_inputs.js只读核R2交付及传递导入，再调用authority/source/receipt；从指定R1完整成员和raw28B建立120帧审阅数据，不运行历史main/prepare/run。CONTRACT/params-v1在首算法前冻结，绑定错误修复后只更新源码冻结记录freeze_r2/r3，参数与节点规则SHA始终不变。最终freeze_r3和pass5/pass6为交付口径，早期失败/冻结/运行均保留。

skeleton.py实现全部有效成员纯XY标准化、原Z和一一row/global映射、无符号PCA描述、5固定槽和有分离支撑的A/B。合成合法形状有7个有效区域代表，胸中心[10,20,1.05]及rows32–47可独立手算；逆变换误差0m。HEAD仅在人工独立标明HEAD_CONFIRMED区域时取支撑中心，是条件化区域代表，未实现自主头部检测。固定Z带仅直立片段工具默认值，真人开发标定因GT阻断，不声称从真实开发数据优化过。

独立SkeletonTracker使用参考坐标滤波、实际整数stamp差值，EMA/跳变/当前缺失/重新获得及键/seek清理；不改原human Tracker、3/5、EMA、lost或Fall。缺支撑时raw和当前filtered为null，历史单列。真实输出120行/文件、336成员的1680基础槽全部无效；真实normalized=null且BLOCKED_GT，不拿空输出当阳性能力通过。

## 2. 修改范围及原因

仅本轮新evidence内新增工具/契约/派生帧/测试/页面/报告，另追加returns/HR-SKELETON-OFFLINE.md。record.py负责新轮基线、实际运行日志与旧资产；bind_inputs.js负责可信入口与GT校验；skeleton.py/run_offline.py负责独立几何和受控运行；test_skeleton.py/binding_tests.js/review_tests.js/independent_audit.py负责明确正负预期与独立复算；review.html/review.js/review_config_final.js/serve_review.py负责只读本地审阅和sidecar；closeout.py负责清单与记录。完整文件SHA见delivery_manifest.json，范围与源摘要见changes.json。

没有src/pc_apps/webui/captures/ML/旧limb/旧evidence/冻结门变更，没有生产接入或安装artifact，未连接板端、部署、采集、commit/push/reset/checkout/clean。WD02未消费，额外历史代码相等检查未删除或绕过；原SEM/W03/HR-RET-V2表与状态不变。

## 3. 测试、实际失败与复审方法

最终15 Python数学/生命周期测试、20绑定/区域正负检查、6 headless审阅契约检查全部exit0；相关replay45、pipe38、registration23回归exit0。实际浏览器12项显示/切帧/空场/非法row/摘要/保存门检查，并额外验证人工声明门；headless与真实浏览器分列，不伪称标签为人工GT。Python3.8语法检查通过；实际运行Python3.12.10/NumPy1.26.4，Python3.8实际执行NOT_RUN。

首次binding exit1：误用R2未导出的R辅助函数；修复新包装。binding_r2 exit1：空场实际分支名V2_IDENTITY曾误写V2；保留split_attempt_r2和binding_r2_partial_frames后按原计划正确分支重建，没有改变窗口或样本。首次binding_tests exit1揭示新输入摘要比较多做了一次字符串哈希；直接比原文件SHA后重验通过。其余冻结是增加区域负向检查/重复person-frame防护，参数未变。浏览器隔离环境拒绝访问纯导出函数，不绕过；导出数学/绑定用明确合成headless入口检查，真人合法导出未执行。一次编辑命令的PowerShell解析失败无文件写入，随后用单引号here-string完成新页面清理修复。

独立复审不导入算法或R2校验器：struct原始字节、标量矩阵逐步骤f32复算全部871476坐标、336完整簇global/票据；独立原点判断184125无效成员；独立重算合成support中位数/逆变换，显式胸中心及rows预期。pass5/pass6 normalized/raw/filtered三个实际文件摘要逐项一致。没有第三方签署，真实节点正确性不由工具PASS证明。

## 4. GT、分母、节点效果与成本

''' + branch_table + '''
100唯一原始帧、120分支行不能报成120独立样本；全部已观察过，不称盲测。336簇真实身份/节点reviewer=0，各基础节点可见/不可见/不确定标注均0、未审336、valid0、UNKNOWN336；合计1680槽观测不是1680独立帧。20 V2_IDENTITY无簇行无节点槽，依然保留行分母。空场两分支40行当前0有效PERSON节点是无人工输入下的拒绝纪律，不是自动人体零误报率证明。

真人躯干阳性、头/手判断、区域参考误差、已标可见漏检、真实跳变/延迟/缺失恢复全部BLOCKED_GT。不存在精确关节GT，不报告关节精度；躯干工具合成成功不代表头或四肢成功。详见pass5/metrics.json、coverage_by_branch.json与GT_TASKS.md。

'''+'拒绝/状态路径的PC每分支行中位耗时 %.6fs、最大%.6fs（不含绑定SHA与raw IO），只是拒绝路径成本；真实人体几何代价、板端性能NOT_RUN。实际整次命令runtime见COMMANDS.md和*.run.json。\n\n'%(metrics['runtime_per_branch_row_s']['median'],metrics['runtime_per_branch_row_s']['max'])+'''## 5. 完整性与逐项状态

旧6299路径逐SHA/大小/符号链接/既有缺失状态复算无变化，branch/HEAD不变，范围外新增0。return原字节前缀在追加时与最终prefix_check再次核验。原冻结输入、旧证据和验收表未漂移。完整性见integrity_final.json、05_integrity.md、prefix_check.json；新交付SHA见delivery_manifest.json。

''' + table + '''
## 6. 后续建议及停止点

下一项数据工作是实际人工审阅：114205 ordinal112–114、114254 ordinal125–127优先逐完整簇确认reviewer/连续person_id/epoch，并标至少一个躯干可见区域和真实缺失/拒绝对照；其余全部未审继续保留。完整336待审receipt、每帧来源/成员SHA与URL在gt_pending.json；frame_index.csv含全部120行。导出实际sidecar后在另获授权新轮先复核绑定，再做真人节点阳性与固定验证；旧轮禁止覆盖。

正式W03未冻结/W04/W05未放行、WD02 BLOCKED不因本单改变。弯腰、坐蹲、躺卧、多人、真实跌倒、完整四肢、精确关节、W06/W07/生产/ML/设备/物理均NOT_RUN/BLOCKED。测试只在127.0.0.1:8883，服务已核进程身份并停止。现在交付后停止，不自动进入后续阶段。

ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）；没有自动派代理/OpenCode或更换模型。
'''
    (OUT/'REVIEW.md').write_text(report_text,encoding='utf8')
    (OUT/'05_integrity.md').write_text('# 旧资产完整性\n\n'+json.dumps(integrity,ensure_ascii=False,indent=2)+'\n\n全旧资产核对完成后仅继续写新证据和追加本return；最后prefix_check核旧前缀并登记范围，manifest覆盖最终交付。旧captures/源码/配置/验收/旧evidence无变化；.git内部不列业务资产。\n',encoding='utf8')
    readme='''# HR-SKELETON-OFFLINE r1 交付入口

SUBMITTED / BLOCKED；12项工具自验PASS，6项真人效果/GT项BLOCKED，未ACCEPTED。真实GT=0（用户回复无）。本轮不是再次规划：已提供可运行可信绑定、完整簇审阅、5–7区域节点数学原型、独立时序和完整120行运行证据。

- [完整复审/六类结果](REVIEW.md)、[SKO-01～18](ACCEPTANCE.md)、[实际命令](COMMANDS.md)。
- [人工任务](GT_TASKS.md)、[全部待审成员](gt_pending.json)、[120行索引](frame_index.csv)。
- [契约](CONTRACT.md)、[输入](input_manifest.json)、[划分](split_manifest.json)、[参数v1](prototype_params_v1.json)、[最终源码冻结](freeze_r3.json)。
- [最终normalized](pass5/normalized_frames.jsonl)、[raw](pass5/nodes_raw.jsonl)、[filtered](pass5/nodes_filtered.jsonl)、[真实指标/缺口](pass5/metrics.json)。真实normalized为null/BLOCKED_GT；合成正例见synthetic_fixture.json/synthetic_output.json，不计真人。
- [独立复算](independent_audit_final.json)、[完整性](05_integrity.md)、[交付SHA](delivery_manifest.json)。

从仓库根启动审阅：

```powershell
python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/serve_review.py
```

打开 http://127.0.0.1:8883/review.html ；当前测试服务已停止，Ctrl+C关闭。参数frame为固定分支行索引，ci为完整簇编号；例frame=0&ci=1是开发112的一个待审簇，不预设PERSON。页面显示完整点、原row/摘要、raw/filtered与UNKNOWN；矩形选择节点参考区域，填实际reviewer/标签/连续身份后导出sidecar。

测试命令（已运行，复跑必须使用新输出日志名/目录，不能覆盖旧产物）：

```powershell
python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/test_skeleton.py -v
node docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/bind_inputs.js validate <实际人工sidecar路径>
```

后续运行真实数据必须有最小B门及新证据轮授权，复制工具到新rN后重新核输入/冻结；绝不把合成或ROI改为human。不启动HR-07/08/09、W06/W07/ML或生产。

![已核验的完整簇审阅](browser_review_final.jpg)
'''
    (OUT/'README.md').write_text(readme,encoding='utf8')
    prefix = read(OUT/'00_baseline.json')['files'][RETURN.relative_to(ROOT).as_posix()]
    assert RETURN.stat().st_size == prefix['bytes'] and sha(RETURN) == prefix['sha256']
    append='\n\n## '+datetime.now(timezone(timedelta(hours=8))).isoformat()+' HR-SKELETON-OFFLINE r1 实施回传（Codex）\n\n'
    append+='本轮用户明确授权A–F PC离线实施；单writer、本聊天Codex，无代理/OpenCode/模型切换。唯一表HR_SKELETON_OFFLINE_ACCEPTANCE.md v1 SHA `'+sha(ROOT/'docs/human_capture/HR_SKELETON_OFFLINE_ACCEPTANCE.md')+'`。\n\n'
    append+='起始master / cfbb80c57508be1a0435fdb92260f698dc763934；6299旧路径/44,460,273,500字节基线。ponytail实读 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。\n\n'
    append+='状态 **SUBMITTED / BLOCKED，未ACCEPTED**；用户确认真实sidecar无，336簇未审、100唯一帧/120分支行保留。工具已实现/测试/交付，真人阳性/效果阻断；设备/物理/生产NOT_RUN。\n\n'
    append+='实际工具、原因、集中根因、失败、GT/节点/代价、六类最终结果及停止点见 [REVIEW.md](../evidence/'+OUT.name+'/REVIEW.md)，实际命令/exit/runtime/SHA见COMMANDS.md与同名run/log；完整变更SHA见changes/delivery_manifest。绑定首次2失败及摘要挑战1失败保留，修复新工具后20绑定检查通过；参数始终冻结不变。\n\n'
    append+='15 Python + 20绑定 + 6 headless审阅检查exit0；replay45/pipe38/registration23回归exit0；实际浏览器显示/拾取/切帧/篡改12检查与声明门通过，真人导出未发生。独立raw 336簇/871476坐标/184125无效源成员复算通过，synthetic支撑及逆变换0m核验，最终pass5/6三文件SHA相等。\n\n'+table+'\n'
    append+='旧资产integrity_final PASS：changed=[]、unexpected_new=[]，HEAD/branch不变；return原前缀在本次追加前已核SHA，追加后prefix_check再核。只新增本r1证据并追加本return，未改上游或旧证据。\n\n'
    append+='后续仅建议人工review两个开发会话各3连续PERSON帧及可见躯干/拒绝对照；GT_TASKS/gt_pending/frame_index提供全部成员与URL。WD02继续BLOCKED；正式W03/W04/W05门不变。无外部独立签署；没有部署/采集/板端连接/重签/commit/push/reset/checkout/clean。临时127.0.0.1服务已停。停止于本轮可复审交付，不自动进入W06/W07或生产。\n'
    (OUT/'return_append.md').write_text(append,encoding='utf8')
    with RETURN.open('ab') as f:
        f.write(append.encode('utf8'))
    save(OUT/'prefix_check.json', {'original_bytes':prefix['bytes'],'original_sha256':prefix['sha256'],
        'prefix_sha256':hashlib.sha256(RETURN.read_bytes()[:prefix['bytes']]).hexdigest(),
        'prefix_unchanged':hashlib.sha256(RETURN.read_bytes()[:prefix['bytes']]).hexdigest()==prefix['sha256'],
        'new_bytes':RETURN.stat().st_size,'final_sha256':sha(RETURN),'append_sha256':sha(OUT/'return_append.md'),
        'head_unchanged':git('rev-parse','HEAD').decode().strip()==read(OUT/'00_baseline.json')['head']})
    save(OUT/'changes.json', {'new_scope':OUT.relative_to(ROOT).as_posix(),'only_existing_write':RETURN.relative_to(ROOT).as_posix(),
        'purpose':'new PC offline tools, data, tests, review and evidence; existing return append only',
        'production_changes':0,'old_evidence_changes':0,'parameters_changed_after_first_algorithm':False,
        'source_files':{p.name:sha(p) for p in sorted(OUT.iterdir()) if p.suffix in ['.py','.js','.html']}})
    print('REPORT_AND_RETURN_APPENDED; 12 PASS, 6 BLOCKED; no ACCEPTED')

def manifest():
    files={p.relative_to(OUT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json' and not p.name.startswith('delivery_manifest.')}
    save(OUT/'delivery_manifest.json', {'files':files,'return_final_sha256':sha(RETURN),
        'authority':'compare with trusted delivery copy; SHA is not proof of human label truth',
        'excludes':'this manifest and delivery_manifest command stdout/stderr/run record completed after snapshot',
        'status':'SUBMITTED / BLOCKED','accepted':False})
    print('DELIVERY_MANIFEST',len(files),'files')

if __name__ == '__main__':
    {'materials':materials,'report':report,'manifest':manifest}[sys.argv[1]]()
