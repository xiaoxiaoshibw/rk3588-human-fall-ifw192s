"""Record the cross-session handoff: append WORKFLOW (top) / REVIEW_LOG (end) in binary, LF only."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_plan_r1'
WORKFLOW = ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = ROOT / 'docs/human_fall/REVIEW_LOG.md'

WF = """## 2026-10-18 HFUS-HUMAN-SKELETON-02 计划 A：复用现有骨架模块 + 只新增持续标定层（仅交接，未实施）

上一会话把 S3（封存 `601a7a24…`）、S3 复审 r2（`c82ea013…`）、S4（`69adaf9d…`）、S5（`e78491c0…`）交付完毕；骨架里程碑 HFUS-HUMAN-SKELETON-01 因四条从零自写的纯几何路线均未过合成门，按约定 **BLOCKED** 封存（`d0c4e0c0…`）。

复盘结论：方法选错，不是方向错——节点提取这种昂贵且已有验证的部分应当复用 `sidequests/human_fusion_lab_next/real_fall/r04/skeleton.py`（`estimate()`/13 SLOT/12 EDGES/`stabilize_display`）、`pc_apps/human_limb/limb_lib.py` 的部件、以及 `src/human_fall_detection/core/association.py::associate_tracks` 的带门限显式歧义关联；本工单只新写**持续标定层**（12 条区域边长的在线均值/方差 + COLLECTING/CALIBRATING/CALIBRATED/DRIFT 状态机）与接线、浏览器。

新工单 [HFUS-HUMAN-SKELETON-02 交接](evidence/2026-10-18_hfus_human_skeleton_02_plan_r1/HANDOFF_NEXT_SESSION.md) 自包含：已封存事实、四轮失败与根因、复用资产（已核实接口）、只新写部分、标定口径（区域边长为标定对象，解剖关节/左右身份/物理高度一律 UNKNOWN/BLOCKED）、新工单 A01–A08 验收草案、执行顺序、以及上一会话踩过的坑（UTF-8/PowerShell、二进制 LF 追加、排他写、M0 指纹、CDP 鼠标与关闭、勿 `Stop-Process -Name msedge`）。

状态：**仅交接文档，未实施**；未改 data/旧证据/配置/模型/GT，无 Git 写。新会话按计划 A 从"先登记协议与唯一验收"开始。以下原文完整保留。
"""

RV = """
## 2026-10-18 HFUS-HUMAN-SKELETON-02 计划 A 交接（仅文档）

- 交接：`evidence/2026-10-18_hfus_human_skeleton_02_plan_r1/HANDOFF_NEXT_SESSION.md`；结论为"复用现有骨架/肢体/关联模块，只新写持续标定层"。
- 依据：SKELETON-01 封存 `d0c4e0c0…`（四轮纯几何全失败，根因可辨识性）；已核实 `real_fall/r04/skeleton.py` 的 `estimate()`/`SLOTS`/`EDGES`、`core/association.associate_tracks`、`limb_lib` 部件均存在且可只读 import。
- 口径：标定对象是 12 条**区域边**边长；解剖关节/左右身份/物理高度保持 UNKNOWN/BLOCKED；门 A03=12 边中 ≥70% 在 max(4cm,8%)、≥3/4 场景 60 帧内 ≥60% 边 CALIBRATED。
- 状态：仅交接，未实施、未封存；新会话需先登记协议与唯一验收（先写后跑）。
"""


def sha(b):
    return hashlib.sha256(b).hexdigest()


if __name__ == '__main__':
    wf, rv = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    entry = WF.encode('utf8')
    applied = b'HFUS-HUMAN-SKELETON-02' in wf[:600]
    if not applied:
        if b'\r' in wf or b'\r' in rv:
            raise SystemExit('not LF-only')
        with WORKFLOW.open('wb') as f:
            f.write(entry + wf)
        with REVIEW.open('wb') as f:
            f.write(rv + RV.encode('utf8'))
    wf2, rv2 = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    checks = dict(entry_at_top=wf2.startswith(entry),
                  workflow_bytes_before=len(wf), workflow_bytes_after=len(wf2),
                  review_bytes_before=len(rv), review_bytes_after=len(rv2),
                  crlf=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n')))
    p = OUT / 'DOCUMENT_APPEND.json'
    with p.open('x', encoding='utf8', newline='\n') as f:
        json.dump(dict(item='HFUS-HUMAN-SKELETON-02-HANDOFF', method='binary splice, UTF-8, LF only',
                       checks=checks, PASS=bool(checks['entry_at_top'] and not any(checks['crlf'].values()))),
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(PASS=checks['entry_at_top'] and not any(checks['crlf'].values()),
                          workflow=len(wf2), review=len(rv2))))
