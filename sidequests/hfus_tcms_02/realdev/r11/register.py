"""S07 pre-experiment registration; exclusive outputs, no data writes."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import platform
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = Path(__file__).resolve().parents[4]
EV = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s07_r1'
HERE = Path(__file__).resolve().parent

def sha(p):
    with Path(p).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def put(p, x):
    p = Path(p)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(x, str): f.write(x)
        else: json.dump(x, f, ensure_ascii=False, indent=2, allow_nan=False); f.write('\n')

def inventory(hashes=True):
    result = {}
    paths=[]
    for base, dirs, files in os.walk(ROOT, followlinks=False):
        dirs[:] = [n for n in dirs if n not in ('.git', 'data') and not (Path(base)/n).is_junction() and not (Path(base)/n).is_symlink()]
        for n in files:
            p = Path(base)/n
            if p.is_symlink(): continue
            paths.append(p)
    def record(p):
        s=p.stat()
        return p.relative_to(ROOT).as_posix(),dict(bytes=s.st_size,mtime_ns=s.st_mtime_ns,**({'sha256':sha(p)} if hashes else {}))
    with ThreadPoolExecutor(max_workers=8) as pool:
        for i,(key,value) in enumerate(pool.map(record,paths)):
            result[key]=value
            if hashes and i%10000==0:print('baseline files',i,'of',len(paths),flush=True)
    return result

if __name__ == '__main__':
    if EV.exists():
        if (EV/'BASELINE_ALL.json').exists():raise FileExistsError('registered baseline exists')
    else:EV.mkdir()
    t = time.perf_counter()
    baseline = inventory()
    put(EV/'BASELINE_ALL.json', dict(files=baseline, branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(), head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=ROOT,text=True), seconds=time.perf_counter()-t, excludes=['.git','data','junction/symlink traversal']))
    inputs = {}
    for sid in ('cap_20261017_113516','cap_20261018_110029'):
        inputs[sid] = {n:dict(sha256=sha(ROOT/'data/sessions'/sid/n),bytes=(ROOT/'data/sessions'/sid/n).stat().st_size) for n in ('meta.json','points.bin')}
    put(EV/'INPUTS.json', inputs)
    put(EV/'ENVIRONMENT.json',dict(python=sys.version,executable=sys.executable,platform=platform.platform(),skills=['C:/Users/30680/.codex/skills/ponytail/SKILL.md','C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md'],strategy=dict(association='ENGINEERING',foreground_regions_effect='RESEARCH')))
    put(EV/'ACCEPTANCE_V1.md', '''# S07 唯一当前验收 v1（实验前冻结）

|ID|类别|验收|
|---|---|---|
|S07-01|交付|输入、范围、基线、协议和SHA冻结；两段均REUSED_DEVELOPMENT|
|S07-02|工程|旧缺陷最小失败复现；新契约歧义测量/创建0；争用/近等价/顺序/空输入/失配/过期和分类生命周期检查|
|S07-03|工程+观测|780帧仅关联语义修复，逐帧披露覆盖/歧义/轨迹/标定变化；非法旧基线不保数|
|S07-04|研究证据|386帧源行账本、无人负对照、站立/展开/保持/轻晃/离开；纯度/召回UNKNOWN|
|S07-05|研究证据|四组消融、全部固定窗口、机制及合成边界验证齐备|
|S07-06|研究效果|候选必须同时满足下列冻结数值门；任一失败=FAIL并停止推广；关节精度/人体效果BLOCKED无GT|
|S07-07|交付+独审|可复现命令/环境/源码SHA/失败/范围核验/完整OpenCode只读审查；独立执行另记|

S07-06 依据：旧保持段胸0/151、>=6仅14/151、OUTER_A最大1069mm；要求实质改善且不以缺测换稳定。
改善前景+新提取器在[183,334)须>=6节点至少90%（136/151），CHEST及OUTER_A各>=90%；节点有效总数不得低于原ROI+旧；共同可测节点最大连续跳变不得恶化，OUTER_A最大<=100mm（相对旧约10倍改善、仍为区域稳定性非精度）；所有节点保持段最大跳变<=200mm；原始3D std完整报告不作单独成功门。
持续标定至少6/12条边在保持段有当前测量且CALIBRATED的帧>=75/151（避免只报曾标定）。无人后半[50,100)前景中位点数<=原ROI的10%；无背景在线更新；离开末[376,386)中位数<=原ROI的20%仅作明确末段清退效果门，失败不得因用户离开边界近似而改窗。该末段不是已验证无人GT。
所有窗口均报告全帧与>=30输入点候选分母，不能只选轨迹。数据复用非独立测试；设备/关节精度/人体语义BLOCKED。
''')
    protocol = dict(item='HFUS-TCMS-02-REALDEV-02-S07',version=1,coordinate='new session RAW/innolidar meters; old session original S3 transform',data_role='REUSED_DEVELOPMENT_NOT_INDEPENDENT_TEST',windows=dict(full=[0,386],empty=[0,100],standing=[100,160],opening=[160,183],hold=[183,334],small_motion=[334,348],exit=[348,386]),roi=[[.75,2.4],[.9,1.65],[-.4,1.85]],foreground=dict(hypothesis='frozen empty reference removes furniture without absorbing stationary pose',fit=[0,50],negative_control=[50,100],initialization='first 50 empty frames only; no human seed',nearest_distance_m=.06,justification='6cm conservative spatial background tolerance, comparable historical ~5.5cm; not tuned on candidate outputs',updates='NONE; frame<50 emits no foreground MAP_BUILDING, frame>=50 query fixed prior reference',ledger='all finite nonzero ROI raw rows partition kept/background; non-ROI source rows identified by ROI complement; no future queries',old_S3_M0_claim=False),association=dict(reuse='frozen association via isolated corrected implementation; no new tracker framework',fix='reject tentative matches whose candidate is ambiguous; classify affected track ambiguous; all near-equivalent candidates in margin ambiguous',lifecycle='expire before association with explicit LOST event; do not refresh ambiguous/unmatched last measurement'),region=dict(stage='first foreground+unchanged old extractor; only if failure persists register one variant before candidate experiments',prohibited=['relax .8m gate','EMA','prediction','display fill','future filtering']),statistics=dict(std='population sqrt(sum(axis variances))*1000 mm',steps='only consecutive source indices, distribution and max; no missing bridge',relative='current measured CHEST only, else null; paired denominator',edges='reuse r08 CalibrationLayer; current measurement separate from persisted state'),stop='one region variant only; frozen gate failure retained, no promotion',unknown=dict(purity='UNKNOWN',recall='UNKNOWN',joint_accuracy='BLOCKED',human_effect='BLOCKED'))
    put(EV/'PROTOCOL_V1.json',protocol)
    workflow=ROOT/'docs/human_fall/WORKFLOW.md'
    old=workflow.read_bytes()
    entry='''## 2026-10-18 HFUS-TCMS-02-REALDEV-02-S07 实施授权（进行中）

用户明确启动S07：现有780/386帧复用开发数据，Codex唯一writer；关联ENGINEERING，前景/区域/效果RESEARCH；OpenCode opencode-go/deepseek-v4.1-flash只读审核。当前唯一[验收v1](evidence/2026-10-18_hfus_tcms_02_s07_r1/ACCEPTANCE_V1.md)、[预注册协议v1](evidence/2026-10-18_hfus_tcms_02_s07_r1/PROTOCOL_V1.json)。后继隔离r11；先修关联重建合法基线，再前景旧提取，必要时唯一新区域变体及四组消融。data/旧源码/配置/证据/模型只读，无Git写/部署/采集/驱动网络/训练/模型下载/HR09；区域骨架非解剖关节。以下历史原字节保留。

'''
    workflow.write_bytes(entry.encode('utf8')+old)
    put(EV/'REGISTRATION.json',dict(epoch=time.time(),acceptance_sha=sha(EV/'ACCEPTANCE_V1.md'),protocol_sha=sha(EV/'PROTOCOL_V1.json'),inputs_sha=sha(EV/'INPUTS.json'),workflow_old_sha=hashlib.sha256(old).hexdigest()))
    print('registered',EV)
