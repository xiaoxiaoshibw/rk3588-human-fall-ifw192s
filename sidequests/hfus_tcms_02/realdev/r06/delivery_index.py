"""S5 delivery index: hash-binds every HFUS-TCMS-02 item up to S4 and states what is delivered vs blocked.

Documentation-only item: it runs no algorithm and writes only into its own evidence root.
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'r05'))
import s4core as C

OUT = C.ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s05_r1'
ITEM = 'HFUS-TCMS-02-REALDEV-02-S05'

ITEMS = [
    ('HFUS-TCMS-02-REALDEV-01', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_r1',
     'r01 首轮真实开发交付（780 帧、M0、候选/轨迹、双方案、浏览器）'),
    ('HFUS-TCMS-02-REALDEV-02-S01', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s01_r1',
     '测量复核 + 旧完整 R/t 冻结诊断'),
    ('HFUS-TCMS-02-REALDEV-02-S02', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1',
     '地面审核与求解（C3D_03/DIMG_01、距离图、薄层域）'),
    ('HFUS-TCMS-02-REALDEV-02-S03', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1',
     '本段几何配平（transform、FIT-only M0、新域验证、271 因果、浏览器）'),
    ('HFUS-TCMS-02-REALDEV-02-S03-REVIEW-R1', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_review_r1',
     'OpenCode 独立只读复审（D1-D4，无改判缺陷）'),
    ('HFUS-TCMS-02-REALDEV-02-S03-r2', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r2',
     'S3 复审收尾（D1-D4，未重跑应用链）'),
    ('HFUS-TCMS-02-REALDEV-02-S04', 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s04_r1',
     '尾段/近地诊断（M0 吸收根因、接触带标签、A/B/C/D）'),
]


def write(path, value):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def seal_of(rel):
    d = C.ROOT / rel
    s = d / 'FINAL_SEAL.sha256'
    j = d / 'FINAL_SEAL.json'
    doc = C.load(j) if j.is_file() else {}
    return dict(path=rel, seal_sha256=(s.read_text(encoding='utf8').split()[0] if s.is_file() else None),
                seal_json_sha=(C.sha(j) if j.is_file() else None),
                manifest_sha=doc.get('manifest_sha'), manifest_files=doc.get('manifest_files'),
                status=doc.get('status'))


if __name__ == '__main__':
    OUT.mkdir(exist_ok=True)
    rows = []
    for item, rel, role in ITEMS:
        s = seal_of(rel)
        s.update(item=item, role=role)
        rows.append(s)
    returns = {}
    for p in sorted((C.ROOT / 'docs/human_fall/returns').glob('HFUS-TCMS-02-REALDEV-02-S0*.md')):
        returns[p.name] = C.sha(p)
    write(OUT / 'DELIVERY_INDEX.json', dict(
        item=ITEM, generated_utc=time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        source=dict(sid='cap_20261017_113516', meta=C.FROZEN['meta'], points=C.FROZEN['points'],
                    frames=780, rows=38298918, taint='development_seen/dev-tainted; no independent D'),
        items=rows, returns=returns,
        delivered=[
            'S3_LOCAL 配平变换 f0533fd8…ab8d（R/t 来自 C3D_03，未重拟合）',
            'FIT-only M0 34,681 面 / 23,783 资格 / 7,181,833 支持行',
            '新验证域 3/3 空间、78/78 时间、19/19 前缀 → 271 起 GEOMETRY_VALIDATED_LOCAL',
            'r01 应用链原样重跑 780 帧，0 reset，行守恒 38,298,918 / 29,049,839 / 9,249,079',
            '真实 Edge 同帧 RAW/配平、28B/双 XYZ/source_row 反查',
            '尾段根因：贴地人体点被 M0 背景吸收（12/35 零候选帧，contact 行 99.8% 判背景）',
            '接触带仅标签与计数（不删行、不改匹配、不做物理高度）',
        ],
        blocked_or_not_run=[
            dict(item='ground identity', state='BLOCKED', needs='独立人工/AI 地面域审核并绑定源行'),
            dict(item='physical height/extrinsics', state='BLOCKED', needs='独立物理测量'),
            dict(item='independent D / generalisation', state='BLOCKED', needs='未曝光数据'),
            dict(item='human effect / GT metrics', state='NOT_RUN', needs='逐帧标签；当前全部指标为 null'),
            dict(item='identity / track', state='BLOCKED', needs='用户或用户委托的 AI 视觉复核作为身份种子'),
            dict(item='near-floor foreground retention', state='NOT_IMPLEMENTED', needs='预注册新变体，用 M0 观测包络判定'),
            dict(item='human + skeleton continuous calibration', state='NEXT_STAGE', needs='另立工单'),
            dict(item='device / capture / deploy / training / HR09', state='NOT_RUN', needs='单独授权'),
        ],
        review_state=dict(s3_independent_ai_review='done (opencode-go/deepseek-v4.1-flash, read-only)',
                          codex_formal_review='NOT_RUN', accepted=False),
        note='本项只是索引与交接，不跑任何算法、不改任何结果'))
    write(OUT / 'ENVIRONMENT.json', dict(
        item=ITEM, executor='DSH agent (this session)',
        model='deepseek-flash as declared by the harness; exact ID not exposed',
        python=sys.version, numpy=__import__('numpy').__version__,
        strategy=dict(delivery_index='ENGINEERING'),
        ponytail='C:/Users/30680/.codex/skills/ponytail/SKILL.md'))
    print(json.dumps(dict(items=len(rows), returns=len(returns))))
