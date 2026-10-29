"""S5 finalize: binary-LF doc append, baseline preservation, MANIFEST + FINAL_SEAL."""
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'r05'))
import s4core as C

OUT = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s05_r1'
ITEM = 'HFUS-TCMS-02-REALDEV-02-S05'
WORKFLOW = C.ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = C.ROOT / 'docs/human_fall/REVIEW_LOG.md'
RETURN = C.ROOT / 'docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S05.md'
BASE = C.S3 / 'BASELINE_FILES.jsonl'
EXCLUDE = {'MANIFEST.json', 'FINAL_SEAL.json', 'FINAL_SEAL.sha256'}

WF = """## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S05 全段交付索引与独审交接（仅文档，SUBMITTED）

用户要求“持续开发到人体和骨架的持续标定”。本轮先收口 S1–S4：唯一[交付索引](evidence/2026-10-17_hfus_tcms_02_s05_r1/DELIVERY_INDEX.json)、[正式复审入口](evidence/2026-10-17_hfus_tcms_02_s05_r1/FINAL_HANDOFF.md)、[回传](returns/HFUS-TCMS-02-REALDEV-02-S05.md)。索引把 7 个 item 的 FINAL_SEAL/manifest 与 6 份回传逐项哈希绑定，并分列“已交付 7 条 / 阻塞 8 条（地面身份、物理高度、独立 D、人体效果/GT、身份轨迹、贴地前景保留、骨架持续标定、设备采集部署训练）”。S3 的 OpenCode 只读复审（D1–D4）与其 r2 收尾已在索引中登记，r1 封存未被改写。

S3/S4/S5 均 SUBMITTED，Codex 正式复审 NOT_RUN，作者不宣布 ACCEPTED；本项不跑算法、不改任何结论、data 与旧证据只读、无 Git 写。以下原文完整保留。
"""

RV = """
## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S05 全段交付索引（仅文档，SUBMITTED）

- 交付索引把 REALDEV-01、S01、S02、S03、S03-REVIEW-R1、S03-r2、S04 七项封存与六份回传逐项哈希绑定；已交付 7 条、阻塞 8 条分列。
- S3 独立 AI 只读复审：无改判缺陷，D1–D4 已由 S3 r2 收尾；Codex 正式复审仍 NOT_RUN。
- 未关闭：地面身份、物理安装高度、独立 D、人体效果/GT、身份与轨迹、贴地前景保留、人体+骨架持续标定、设备/采集/部署/训练。
"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


def write_json(path, value):
    p = Path(path).absolute()
    if not p.is_relative_to(OUT.resolve()):
        raise ValueError('Output must be under the S5 evidence root')
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def check(rec):
    p = C.ROOT / rec['path']
    if rec['path'] == 'docs/human_fall/WORKFLOW.md':
        return dict(path=rec['path'], PASS=sha(p.read_bytes()[-rec['bytes']:]) == rec['sha256'], method='suffix bytes')
    if rec['path'] == 'docs/human_fall/REVIEW_LOG.md':
        return dict(path=rec['path'], PASS=sha(p.read_bytes()[:rec['bytes']]) == rec['sha256'], method='prefix bytes')
    if rec['kind'] == 'file':
        return dict(path=rec['path'], PASS=p.is_file() and C.sha(p) == rec['sha256'], method='sha256')
    if rec['kind'] == 'symlink':
        return dict(path=rec['path'], PASS=p.is_symlink() and str(p.readlink()) == rec['target'], method='link')
    return dict(path=rec['path'], PASS=(not p.is_file() and not p.is_symlink()), method='type')


if __name__ == '__main__':
    wf, rv = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    entry = WF.encode('utf8')
    applied = b'HFUS-TCMS-02-REALDEV-02-S05' in wf[:600]
    if not applied:
        if b'\r' in wf or b'\r' in rv:
            raise SystemExit('not LF-only')
        with WORKFLOW.open('wb') as f:
            f.write(entry + wf)
        with REVIEW.open('wb') as f:
            f.write(rv + RV.encode('utf8'))
    wf2, rv2 = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    recs = [json.loads(x) for x in BASE.read_text(encoding='utf8').splitlines()]
    base_wf = next(r for r in recs if r['path'] == 'docs/human_fall/WORKFLOW.md')
    base_rv = next(r for r in recs if r['path'] == 'docs/human_fall/REVIEW_LOG.md')
    checks = dict(workflow_entry_at_top=wf2.startswith(entry),
                  workflow_original_bytes_preserved=sha(wf2[-base_wf['bytes']:]) == base_wf['sha256'],
                  review_original_bytes_preserved=sha(rv2[:base_rv['bytes']]) == base_rv['sha256'],
                  crlf=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n')),
                  already_applied_before_this_run=applied)
    write_json(OUT / 'DOCUMENT_APPEND.json', dict(
        item=ITEM, method='binary splice, UTF-8, LF only', checks=checks,
        PASS=bool(checks['workflow_entry_at_top'] and checks['workflow_original_bytes_preserved']
                  and checks['review_original_bytes_preserved'] and not any(checks['crlf'].values()))))
    with ThreadPoolExecutor(max_workers=12) as ex:
        results = list(ex.map(check, recs))
    changed = [r['path'] for r in results if not r['PASS']]
    write_json(OUT / 'PRESERVATION.json', dict(item=ITEM, records=len(recs), changed=changed,
                                               baseline=str(BASE.relative_to(C.ROOT)),
                                               git_head=subprocess.check_output(['git', 'rev-parse', 'HEAD'],
                                                                                cwd=C.ROOT).decode().strip(),
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
    seal = dict(item=ITEM, status='SUBMITTED', sealed_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
                delivery_index_sha=C.sha(OUT / 'DELIVERY_INDEX.json'),
                handoff_sha=C.sha(OUT / 'FINAL_HANDOFF.md'),
                preservation_sha=C.sha(OUT / 'PRESERVATION.json'),
                document_append_sha=C.sha(OUT / 'DOCUMENT_APPEND.json'),
                source_code_sha=C.digest(code),
                manifest_sha=C.sha(OUT / 'MANIFEST.json'), manifest_files=len(files),
                return_sha=C.sha(RETURN) if RETURN.is_file() else None,
                review_state=dict(codex_formal_review='NOT_RUN', accepted=False,
                                  s3_independent_ai_review='done (opencode-go/deepseek-v4.1-flash)'),
                note='index and handoff only; no algorithm ran in S5')
    write_json(OUT / 'FINAL_SEAL.json', seal)
    with (OUT / 'FINAL_SEAL.sha256').open('xb') as f:
        f.write(('%s  FINAL_SEAL.json\n' % C.sha(OUT / 'FINAL_SEAL.json')).encode('utf8'))
    print(json.dumps(dict(changed=len(changed), files=len(files), seal=C.sha(OUT / 'FINAL_SEAL.json'))))
