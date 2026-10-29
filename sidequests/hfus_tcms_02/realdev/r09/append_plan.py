"""Record the S06 plan round: append WORKFLOW (top) / REVIEW_LOG (end) in binary, LF only."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-18_hfus_tcms_02_s06_plan_r1'
WORKFLOW = ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = ROOT / 'docs/human_fall/REVIEW_LOG.md'

WF = """## 2026-10-18 HFUS-TCMS-02-REALDEV-02-S06 计划：近地前景保留 + 全段骨架覆盖 + 漂移根因 + 统一复审交接（仅计划，SUBMITTED）

用户在新窗口按计划 A 完成 SKELETON-02（封存 `799c8a06…9cb9`，SUBMITTED，A01–A08 自验 PASS、Codex 复审 NOT_RUN），随后要求制定下一步计划。本会话为唯一文档 writer，未跑数据。当前[计划v1](evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_V1.md)、[P01–P09计划验收](evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_ACCEPTANCE_V1.md)、[自检](evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_CHECK.md)、[输入基线](evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/INPUT_BASELINE.json)、[回传](returns/HFUS-TCMS-02-REALDEV-02-S06-PLAN.md)。

计划针对 SKELETON-02 暴露的三个结构性缺口：①尾段 f759–779 共 21 帧无骨架（已核对 `RUN_R4/frames.jsonl`），根因是 S4 已诊断的"贴地人体被 M0 吸收"，S4 把它列为 NOT_IMPLEMENTED；②107/490 个 ACTION 帧无可测候选，其中尾段 21 帧已定位，其余 ~86 帧当前**不可查询**（`RUN_R4/frames.jsonl` 的 `candidate_summaries` 为空）；③12 条边中 2 条从未 CALIBRATED、163 次 DRIFT_RESET 没有根因分类，且 `REAL_EVALUATION` 0.012365 m 与 `FRAME_SUMMARY` 0.019529 m 两份 max std 不一致。

S06 分五块：A 近地/接触前景保留（预注册 `envelope_foreground` 变体，只有一处语义变化，附空场不劣化 +2pp 与 745–779 ≥60% 帧有候选两道自检）；B 全段骨架覆盖重跑（复用 SK02 标定层，禁预测填充，双分母并列）；C 漂移与未标定边根因（分类合计=163、逐边结论、至多一个预注册修法）；D 107 空帧逐帧重建（先补 `candidate_rows` 字段再结论）；E 统一复审交接（S3/S4/S5/SK01/SK02 五项 NOT_RUN 的单入口）+ 交付索引 v2。

状态 SUBMITTED（仅计划）：S06 实施 NOT_RUN，须用户实际派发并另立唯一验收表；解剖关节/左右/物理高度/身份/效果/独立 D 仍 UNKNOWN/BLOCKED。本轮只写文档：未改源码/数据/旧证据/门/配置/模型/GT，无 Git 写。以下原文完整保留。
"""

RV = """
## 2026-10-18 HFUS-TCMS-02-REALDEV-02-S06 计划（仅计划，SUBMITTED）

- 计划：`evidence/2026-10-18_hfus_tcms_02_s06_plan_r1/PLAN_V1.md`（P01–P09 自验 PASS，S06 未实施）。
- 依据 SKELETON-02（`799c8a06…`）暴露的三处缺口：尾段 21 帧无骨架、107/490 ACTION 帧无候选且其中 ~86 帧当前不可查询、2 条边从未 CALIBRATED + 163 次 DRIFT_RESET 无分类 + 两份 max std（0.012365 / 0.019529）不一致。
- 计划要点：近地前景变体只改一处匹配语义并带两道自检；全段重跑禁预测填充；漂移分类必须合计=163；空帧重建先补字段；统一五项复审入口。
- 状态：仅计划、未实施、未封存；S06 实施须另行派发；不自动进入 S07；五项 Codex 正式复审仍 NOT_RUN。
"""


def main():
    wf, rv = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    entry = WF.encode('utf8')
    applied = b'HFUS-TCMS-02-REALDEV-02-S06' in wf[:700]
    if not applied:
        if b'\r' in wf or b'\r' in rv:
            raise SystemExit('not LF-only')
        with WORKFLOW.open('wb') as f:
            f.write(entry + wf)
        with REVIEW.open('wb') as f:
            f.write(rv + RV.encode('utf8'))
    wf2, rv2 = WORKFLOW.read_bytes(), REVIEW.read_bytes()
    checks = dict(entry_at_top=wf2.startswith(entry),
                  crlf=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n')),
                  workflow_bytes=[len(wf), len(wf2)], review_bytes=[len(rv), len(rv2)])
    OUT.mkdir(parents=True, exist_ok=True)
    with (OUT / 'DOCUMENT_APPEND.json').open('x', encoding='utf8', newline='\n') as f:
        json.dump(dict(item='HFUS-TCMS-02-REALDEV-02-S06-PLAN', method='binary splice, UTF-8, LF only',
                       checks=checks, PASS=bool(checks['entry_at_top'] and not any(checks['crlf'].values()))),
                  f, ensure_ascii=False, indent=2)
    print(json.dumps(dict(PASS=checks['entry_at_top'] and not any(checks['crlf'].values()),
                          workflow=len(wf2), review=len(rv2))))


if __name__ == '__main__':
    main()
