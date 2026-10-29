"""Finalize the skeleton milestone as BLOCKED: doc append (binary LF), preservation, MANIFEST + seal."""
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s5core as C

OUT = C.OUT
ITEM = C.ITEM
WORKFLOW = C.ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = C.ROOT / 'docs/human_fall/REVIEW_LOG.md'
RETURN = C.ROOT / 'docs/human_fall/returns/HFUS-HUMAN-SKELETON-01.md'
BASE = C.S3 / 'BASELINE_FILES.jsonl'
EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}

WF = """## 2026-10-17 HFUS-HUMAN-SKELETON-01 人体 + 骨架持续标定（BLOCKED）

用户要求持续开发到“人体和骨架的持续标定”。本项先冻结[协议v1](evidence/2026-10-17_hfus_human_skeleton_r1/PROTOCOL_V1.json)→[v2](evidence/2026-10-17_hfus_human_skeleton_r1/PROTOCOL_V2.json)（只改可辨识量，严格度不变）与[K01–K08验收](evidence/2026-10-17_hfus_human_skeleton_r1/ACCEPTANCE_V1.md)，随后实现并**全部保留**四条纯几何路线：v1 参数化 16 段 + 关节位置交替最小二乘、v2 可辨识 9 段 + 2 宽（全局躯干带/肢体两段折线）、v3 0.03 m 栅格 + Zhang-Suen 细化 + DT 脊线并映射人体拓扑、v4 时序跟踪（上一帧姿态作初值）+ 数据侧段长/宽度测量 + 在线标定状态机。

结果：**K03 合成门未通过**（门槛 9/11 容差内 + 3/4 场景 60 帧收敛；v4 最好 5/11，从未进入 CALIBRATED）。根因是**可辨识性**：单视角、每帧 0.5–1.2k 点、无关节 GT、禁止训练/外部模型时，同肢两段的关节位置不可辨识，段长测量有系统偏差；v4 恰好只在可辨识量上准确（躯干 6 mm、上臂 9–13 mm、宽度 16 mm）。项目自身 HR-07 结论（`pc_apps/human_limb/README.md`：纯几何需参数化人形 + ICP，且“外标签必须有”）与此一致。

状态 **BLOCKED**（不是通过、不是 ACCEPTED）：不降低验收门、不宣称任何骨架/关节/物理结论、未进入真实数据与浏览器阶段。解除条件（任一，均需用户/物理输入）：①一帧人工或用户委托的 AI 种子；②少量关节标注/GT；③多视角或更高密度采集授权；④外部参数化人体模型或训练授权（当前禁止）。证据与回传见[STATUS](evidence/2026-10-17_hfus_human_skeleton_r1/STATUS.md)与[回传](returns/HFUS-HUMAN-SKELETON-01.md)。以下原文完整保留。
"""

RV = """
## 2026-10-17 HFUS-HUMAN-SKELETON-01 人体 + 骨架持续标定（作者自验 BLOCKED）

- 四条纯几何路线（v1 交替最小二乘 / v2 可辨识测量 / v3 像素骨架化+DT 脊线 / v4 时序跟踪+在线标定）在理想合成胶囊数据上均未达到预登记门 K03；v4 最好 5/11（门槛 9/11），未收敛。
- 根因：可辨识性限制（同肢两段关节位置在单视角稀疏点云下不可辨识），不是调参问题；v4 只在可测的量上准确。
- 保留：PILOT_R1/PILOT_V2/PILOT_V4、协议 v1/v2、STATUS 的可辨识性分析；未进真实数据与浏览器；未降低任何门。
- 解除条件：用户/物理输入（一帧种子 / 关节标注 / 多视角或高密度采集 / 外部模型或训练授权）。
- 复审重点：四条路线是否公平实现；门是否被降；若复审认为仍有未试的可行纯几何路线，应指出并重新派发。
"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write_json(path, value):
    p = Path(path).absolute()
    if not p.is_relative_to(OUT.resolve()):
        raise ValueError('outside item')
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def check(rec):
    p = C.ROOT / rec['path']
    if rec['path'] == 'docs/human_fall/WORKFLOW.md':
        return dict(path=rec['path'], PASS=sha(p.read_bytes()[-rec['bytes']:]) == rec['sha256'], method='suffix')
    if rec['path'] == 'docs/human_fall/REVIEW_LOG.md':
        return dict(path=rec['path'], PASS=sha(p.read_bytes()[:rec['bytes']]) == rec['sha256'], method='prefix')
    if rec['kind'] == 'file':
        return dict(path=rec['path'], PASS=p.is_file() and C.sha(p) == rec['sha256'], method='sha256')
    if rec['kind'] == 'symlink':
        return dict(path=rec['path'], PASS=p.is_symlink() and str(p.readlink()) == rec['target'], method='link')
    return dict(path=rec['path'], PASS=(not p.is_file() and not p.is_symlink()), method='type')


if __name__ == '__main__':
    wf, rv = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    entry = WF.encode('utf8')
    applied = b'HFUS-HUMAN-SKELETON-01' in wf[:600]
    if not applied:
        if b'\r' in wf or b'\r' in rv:
            raise SystemExit('not LF-only')
        with WORKFLOW.open('wb') as f:
            f.write(entry + wf)
        with REVIEW.open('wb') as f:
            f.write(rv + RV.encode('utf8'))
    wf2, rv2 = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    recs = [json.loads(x) for x in BASE.read_text(encoding='utf8').splitlines()]
    b_wf = next(r for r in recs if r['path'] == 'docs/human_fall/WORKFLOW.md')
    b_rv = next(r for r in recs if r['path'] == 'docs/human_fall/REVIEW_LOG.md')
    write_json(OUT / 'DOCUMENT_APPEND.json', dict(
        item=ITEM, method='binary splice, UTF-8, LF only', already_applied=applied,
        checks=dict(entry_at_top=wf2.startswith(entry),
                    workflow_original_preserved=sha(wf2[-b_wf['bytes']:]) == b_wf['sha256'],
                    review_original_preserved=sha(rv2[:b_rv['bytes']]) == b_rv['sha256'],
                    crlf=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n'))),
        PASS=bool(wf2.startswith(entry) and sha(wf2[-b_wf['bytes']:]) == b_wf['sha256']
                  and sha(rv2[:b_rv['bytes']]) == b_rv['sha256']
                  and not wf2.count(b'\r\n') and not rv2.count(b'\r\n'))))
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, recs))
    changed = [r['path'] for r in results if not r['PASS']]
    write_json(OUT / 'PRESERVATION.json', dict(
        item=ITEM, records=len(recs), changed=changed, baseline=str(BASE.relative_to(C.ROOT)),
        git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=C.ROOT).decode().strip(),
        PASS=bool(not changed)))
    files = {}
    for p in sorted(OUT.rglob('*')):
        rel = str(p.relative_to(OUT)).replace('\\', '/')
        if p.is_file() and rel not in EXCLUDE:
            files[rel] = dict(sha256=C.sha(p), bytes=p.stat().st_size)
    src = Path(__file__).resolve().parent
    code = {p.name: C.sha(p) for p in sorted(src.iterdir()) if p.is_file()}
    write_json(OUT / 'MANIFEST.json', dict(item=ITEM, files=files, count=len(files),
                                           output_bytes=sum(v['bytes'] for v in files.values()),
                                           source_code=code, source_code_sha=C.digest(code)))
    seal = dict(item=ITEM, status='BLOCKED', sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                acceptance_sha=C.sha(OUT / 'ACCEPTANCE_V1.md'),
                protocol_v1_sha=C.sha(OUT / 'PROTOCOL_V1.json'),
                protocol_v2_sha=C.sha(OUT / 'PROTOCOL_V2.json'),
                status_sha=C.sha(OUT / 'STATUS.md'),
                pilots=dict(v1=C.sha(OUT / 'PILOT_R1.json'), v2=C.sha(OUT / 'PILOT_V2.json'),
                            v4=C.sha(OUT / 'PILOT_V4.json')),
                preservation_sha=C.sha(OUT / 'PRESERVATION.json'),
                document_append_sha=C.sha(OUT / 'DOCUMENT_APPEND.json'),
                source_code_sha=C.digest(code),
                manifest_sha=C.sha(OUT / 'MANIFEST.json'), manifest_files=len(files),
                return_sha=C.sha(RETURN) if RETURN.is_file() else None,
                blocked_reason='K03 synthetic calibration gate not met after four independent geometry-only '
                               'implementations; the same-limb joint positions are not identifiable from a '
                               'single-view sparse cloud without joint GT or a one-frame seed, so segment '
                               'lengths carry a systematic bias (best 5/11 vs gate 9/11)',
                unblock=['one-frame human or user-delegated AI seed',
                         'small joint annotation / GT',
                         'multi-view or denser capture authorisation',
                         'external parametric body model or training authorisation (currently forbidden)'],
                review_state=dict(codex_formal_review='NOT_RUN', accepted=False),
                note='blocked milestone: no skeleton/joint/physical claim; gate never relaxed')
    write_json(OUT / 'FINAL_SEAL.json', seal)
    with (OUT / 'FINAL_SEAL.sha256').open('xb') as f:
        f.write(('%s  FINAL_SEAL.json\n' % C.sha(OUT / 'FINAL_SEAL.json')).encode('utf8'))
    print(json.dumps(dict(changed=len(changed), files=len(files), seal=C.sha(OUT / 'FINAL_SEAL.json'))))
