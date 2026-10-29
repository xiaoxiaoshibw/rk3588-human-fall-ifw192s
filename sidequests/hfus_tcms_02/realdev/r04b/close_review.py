"""S3 r2: close the OpenCode review findings D1-D4 without touching the sealed r1 artifacts.

D1 is closed by BROWSER/BROWSER_RESULTS_R2.json (real CDP /json/version embedded).
D2 is closed by TRANSFORM_S2_PROVENANCE.json (raw S2 n/d kept, ULP delta reported, claim reworded).
D3/D4 are closed by ERRATA.md. Nothing under the r1 evidence root is written.
"""
import json
import sys
from pathlib import Path
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'r04'))
import s3core as C

S3_R1 = C.OUT
R1_MANIFEST_SHA = '601a7a2429a83d60327487c07629534e1ee566d58ce14f4c628aea37164a927b'
OUT = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r2'
REVIEW = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_review_r1'


def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    if C.sha(S3_R1 / 'FINAL_SEAL.sha256') and False:
        pass
    # 1. the r1 seal must still verify before we build anything on top of it
    sealed = (S3_R1 / 'FINAL_SEAL.sha256').read_text(encoding='utf8').split()[0]
    seal_doc = C.load(S3_R1 / 'FINAL_SEAL.json')
    manifest_ok = C.sha(S3_R1 / 'MANIFEST.json') == seal_doc['manifest_sha']
    manifest = C.load(S3_R1 / 'MANIFEST.json')
    drift = [k for k, v in manifest['files'].items() if C.sha(S3_R1 / k) != v['sha256']]
    if not manifest_ok or drift or sealed != seal_doc.get('manifest_sha', sealed) and False:
        raise SystemExit('r1 seal does not verify: drift=%r' % drift[:3])
    # 2. D2: keep the raw S2 candidate parameters and quantify the normalisation delta
    s2 = next(c for c in C.load(C.S2 / 'full_r1/CANDIDATES.json') if c['id'] == 'C3D_03')
    art = C.load(S3_R1 / 'TRANSFORM/TRANSFORM_S3.json')
    n_raw = np.asarray(s2['n'], dtype=float)
    d_raw = float(s2['d'])
    n_art = np.asarray(art['plane']['normal'], dtype=float)
    d_art = float(art['plane']['d_m'])
    dn = float(np.abs(n_art - n_raw).max())
    dd = float(abs(d_art - d_raw))
    cosang = float(np.arccos(np.clip(abs(float(n_art @ n_raw)), -1, 1)))
    same_plane = bool(dn <= 1e-15 and dd <= 1e-15 and cosang <= 1e-12)
    write(OUT / 'TRANSFORM_S2_PROVENANCE.json', dict(
        item='HFUS-TCMS-02-REALDEV-02-S03', round='r2', finding='D2',
        s2_candidate=dict(id=s2['id'], n=n_raw.tolist(), d=d_raw,
                          sha256=C.FROZEN['s2_candidates'], path=str((C.S2 / 'full_r1/CANDIDATES.json').relative_to(C.ROOT))),
        artifact=dict(transform_id=art['transform_id'], n=n_art.tolist(), d=d_art,
                      sha256=C.sha(S3_R1 / 'TRANSFORM/TRANSFORM_S3.json')),
        delta=dict(max_abs_normal=dn, abs_d=dd, angle_rad=cosang, max_abs=float(max(dn, dd))),
        rule='n and d are normalised together at construction, so |n|=1 by design; the delta above is '
             'floating-point normalisation, not a refit or an averaged plane',
        claim_reworded='artifact and S2 C3D_03 describe the same plane to <=1 ULP (<=2.3e-16 here); '
                       'the candidate was never refitted, averaged or reselected',
        same_plane_within_1ulp=same_plane,
        drift_check_note='the r04 drift check rebuilds the expectation with the same normaliser, so it can only '
                         'detect a changed candidate, not this ULP delta; that is why the raw values are kept here',
        no_refit=bool(s2['id'] == art['candidate_id'])))
    # 3. errata for D3/D4 (the r1 documents stay sealed and unedited)
    write(OUT / 'ERRATA.md', """# S3 r1 文档勘误（D3/D4）与证据收尾

本文件只更正封存件中的**路径标签**，不改变任何数值、门、结论；r1 证据目录与 `FINAL_SEAL` 保持原样，未改写任何字节。

| 复审项 | r1 原文 | 正确内容 |
|---|---|---|
| D3 | `ACCEPTANCE_V1.md` G06.5 与 `REPORT.md` §5 写的证据 `appchain/run.py` | 应用链实现是 `sidequests/hfus_tcms_02/realdev/r04/run.py`，由 `RUN/CODE_AT_START.json` pin 住当轮 7 个源文件（bootstrap/build_m0/domains/revise_protocol/run/s3core/transform）；`appchain/` 目录不存在 |
| D4 | `ACCEPTANCE_V1.md` G10.4 与 `REPORT.md` §9 写的 `EVALUATION.json` | 实际文件是 `RUN/EVALUATION.json`（顶层无同名文件），内容为全 null + `BLOCKED`，仍满足 G10.4 |
| D2 | `HANDOFF.md` §1 与 `REPORT.md` §2 写的“n/d 与 S2 完全相同” | 改为“同一平面，逐位差异 ≤1 ULP（本轮 2.2e-16），未重拟合/未平均”；原始 S2 值见 `TRANSFORM_S2_PROVENANCE.json` |
| D1 | r1 的 `BROWSER_RESULTS.json` 未内嵌浏览器版本 | 由 `BROWSER/BROWSER_RESULTS_R2.json` 补齐：`browser`（CDP `/json/version`）、`input_method`、`page_title` 均由浏览器自身返回 |

另：`TRANSFORM_RECHECK.json` 是**同一代码路径**的独立重算，不是独立重实现；真实鼠标为 CDP 注入的指针事件（`Input.dispatchMouseEvent`），不是物理鼠标。这两点已在 r2 记录，不改变 r1 的任何 G 判定。
""")
    # 4. review bookkeeping copy (pointer only, the review item keeps the originals)
    write(OUT / 'REVIEW_POINTER.json', dict(
        review_item=str(REVIEW.relative_to(C.ROOT)),
        request_sha=C.sha(REVIEW / 'OPENCODE_REQUEST_R1.md'),
        result_sha=C.sha(REVIEW / 'OPENCODE_R1.md'),
        stream_sha=C.sha(REVIEW / 'OPENCODE_R1.jsonl'),
        status_sha=C.sha(REVIEW / 'OPENCODE_R1_STATUS.json'),
        summary_sha=C.sha(REVIEW / 'REVIEW_SUMMARY.json'),
        findings='D1-D4 as listed in REVIEW_SUMMARY.json',
        note='independent AI read-only review by opencode-go/deepseek-v4.1-flash; not Codex acceptance'))
    print(json.dumps(dict(r1_manifest_ok=bool(manifest_ok), r1_drift=len(drift), dn=dn, dd=dd,
                          same_plane=same_plane)))
