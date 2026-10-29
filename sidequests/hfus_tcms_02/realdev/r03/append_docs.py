"""Append S2 work-order entry to WORKFLOW top and REVIEW_LOG end (UTF-8, original bytes preserved)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
WF = ROOT / 'docs/human_fall/WORKFLOW.md'
RL = ROOT / 'docs/human_fall/REVIEW_LOG.md'

WF_ENTRY = '''## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S02 地面审核与求解（SUBMITTED / 源码停写）

用户本聊天说“继续开发”并在范围选择中选 A：开 S2 新工单。本会话为唯一实现 writer，RESEARCH（距离图/地面审核）+ ENGINEERING（源/回放/浏览器）。唯一[G01–G04,G10–G12验收v1](evidence/2026-10-17_hfus_tcms_02_s02_r1/ACCEPTANCE_V1.md)、[协议v4](evidence/2026-10-17_hfus_tcms_02_s02_r1/PROTOCOL_V4.json)、[报告](evidence/2026-10-17_hfus_tcms_02_s02_r1/REPORT.md)、[回传](returns/HFUS-TCMS-02-REALDEV-02-S02.md)；实际技能路径见回传。

源 cap_20261017_113516 双SHA重核；FIT[0,20)s/VAL[20,28)s/前缀[28,30)s 运行前冻结；7个薄层审核片（先验条件选择，非独立真值，v1–v4失败保留）。距离图1024×512与512×256；C（体素）/D（距离图）提案、FIT-only排名、预登记3cm/5cm/80%门。C3D_03 4/4 FIT+3/3 VAL，DIMG_01 3/4+3/3，VAL RMS 0.8–2.6cm；跨族0.84°/2.8cm；旧TLS 2/4+1/3，VAL_F/G 3.9cm 超门。78/78 VAL帧、19/19前缀帧稳定。真实Edge 6帧点选28B/双XYZ、距离图bin反查、相机不变。

状态 CANDIDATE_PLANE_PREVIEW/OFFLINE_REVIEW；地面身份/本段几何验证/物理高度/独立D BLOCKED，S3/S4/人体 NOT_RUN，设备/部署/采集 NOT_RUN；正式独审 NOT_RUN。审核片先验条件选择、VAL非独立，不把候选相容当S3通过。旧r01/r02/证据/门/配置/模型/GT只读，data零写，无Git写。作者停写SUBMITTED，交独审，不自动下一阶段。以下原文保留。

'''

RL_ENTRY = '''
## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S02 作者自验
本会话为唯一实现 writer，尚无正式独立复审（NOT_RUN）。S2 只做地面审核与求解：FIT/VAL 冻结、距离图、C/D 提案、预登记门。作者自验 G01–G04、G10–G12 PASS（G03/G04 附“审核片先验条件选择、VAL 非独立真值”限制）；r03 9/9 合成契约、r02 14 项坐标与 handler 契约 exit 0；真实 Edge 6 帧点选/反查/相机不变。C3D_03 4/4 FIT+3/3 VAL，DIMG_01 3/4+3/3，旧TLS 2/4+1/3；78/78 VAL 帧、19/19 前缀帧稳定。S3/S4、人体、独立D、设备/未跑项保留 BLOCKED/NOT_RUN；正式独审由 fresh 会话只读进行。见[报告](evidence/2026-10-17_hfus_tcms_02_s02_r1/REPORT.md)、[交接](evidence/2026-10-17_hfus_tcms_02_s02_r1/HANDOFF.md)。
'''

if __name__ == '__main__':
    wf = WF.read_text(encoding='utf8')
    if 'HFUS-TCMS-02-REALDEV-02-S02' in wf:
        raise SystemExit('WORKFLOW already has S02 entry')
    WF.write_text(WF_ENTRY + wf, encoding='utf8')
    rl = RL.read_text(encoding='utf8')
    if 'HFUS-TCMS-02-REALDEV-02-S02' in rl:
        raise SystemExit('REVIEW_LOG already has S02 entry')
    RL.write_text(rl + RL_ENTRY, encoding='utf8')
    print('appended', len(WF_ENTRY), len(RL_ENTRY))
