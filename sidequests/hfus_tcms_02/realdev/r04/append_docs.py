"""T8: append the S3 entry to WORKFLOW (top) and REVIEW_LOG (end) in binary, LF only.

S2 normalised 247/815 historical CRLF line endings by using text mode here. These two files are
now LF-only, and this script never decodes them: it splices bytes and proves the original bytes
are still a suffix (WORKFLOW) / prefix (REVIEW_LOG).
"""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import s3core as C

WORKFLOW = C.ROOT / 'docs/human_fall/WORKFLOW.md'
REVIEW = C.ROOT / 'docs/human_fall/REVIEW_LOG.md'
ITEM_DIR = '2026-10-17_hfus_tcms_02_s03_r1'

WORKFLOW_ENTRY = """## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S03 本段几何配平（SUBMITTED / 源码停写）

用户实际派发 S3 实施提示词 v1；本会话为唯一实现 writer，ENGINEERING（坐标接线、M0 重建、回放、浏览器）+ RESEARCH（新验证域与失败解释）。唯一[G05–G07/G10–G12验收v1](evidence/{d}/ACCEPTANCE_V1.md)、[协议v1](evidence/{d}/PROTOCOL_V1.json)→[v2](evidence/{d}/PROTOCOL_V2.json)（只改域选择约束，验证门未动）、[报告](evidence/{d}/REPORT.md)、[回传](returns/HFUS-TCMS-02-REALDEV-02-S03.md)、[独审交接](evidence/{d}/HANDOFF.md)；实际技能路径见回传。

由 S2 的 C3D_03 构造唯一配平变换 `S3_LOCAL/f0533fd8…ab8d`（RᵀR 偏差 2.2e-16、det=1、z 恒等 3.6e-15 m、float64 往返 6.5e-15 m、float32 1.06e-6 m；错误方向/反射/非正交/错 frame/二次配平/退化参考轴全部拒绝）；在 [20,28) 冻结 3 个与 S2 七片**空间与源行都不重叠**的新薄层片（纯度 0.9196/0.9074/0.8950，先验条件选择已披露、候选残差未参与）；只用 FIT[0,20) 行在新坐标重建 M0（34,681 面 / 23,783 资格 / 7,181,833 支持行 = FIT 有效行，另附 0.13 m 敏感性）；r01 原阈值/邻域/关联/TTL/生长原样重跑 780 帧，空间 3/3、时间 78/78、前缀 19/19 全通过，271 起 `GEOMETRY_VALIDATED_LOCAL`，0 reset、行守恒 38,298,918/29,049,839/9,249,079；真实 Edge 13 帧同帧 RAW/配平、z=0、R/t 版本、点选 56 hex 28B + 双 XYZ + source_row 反查、相机不变、无效行可查。

本轮无独立 D：全段 dev-tainted、S2 VAL 已曝光、S3 新域仍是先验条件选择，**不称独立验证**；地面身份/物理高度/独立 D/人体效果/设备仍 BLOCKED/NOT_RUN，G08/G09 NOT_RUN，S4/S5 未派发。data 只读、旧证据/门/配置/模型/GT 只读、范围外差异 0、无 Git 写。作者停写 SUBMITTED 交正式独审，不自动进入 S4、不自行宣布 ACCEPTED。以下原文完整保留。
""".format(d=ITEM_DIR)

REVIEW_ENTRY = """
## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S03 本段几何配平（作者自验 SUBMITTED）

- 状态：SUBMITTED；作者自验 G05/G06/G07/G10/G11/G12 PASS，G08/G09 NOT_RUN；**正式独立复审 NOT_RUN**，不自行 ACCEPTED，不进入 S4。
- 证据根：`docs/human_fall/evidence/{d}/`，哈希链 `FINAL_SEAL.sha256` → `FINAL_SEAL.json` → `MANIFEST.json` → 各文件；回传 `docs/human_fall/returns/HFUS-TCMS-02-REALDEV-02-S03.md`。
- 关键事实：transform `f0533fd84b9c7e1f0ec22bfcf3f7f433fb071fa73327ca9c9c881cc4aef4ab8d`（R/t 由 C3D_03 唯一确定，未重拟合/未平均）；新域 S3V_H/I/J 与 S2 七片零共享源行；M0 支持行 7,181,833 = FIT 有效行，应用链内重建指纹一致；780 帧 0 reset、行守恒；qualified 首次为真恰在 fi=271。
- 保留失败：`RUN_BUG1/`（时间门按片汇总的错误实现）、`OBJECTS_CHECK_FAIL1.json`（CSR 语义错误）、`BROWSER_RESULTS_ATTEMPT1–4`。
- 复审重点见 `evidence/{d}/HANDOFF.md`：候选未被重拟合；v1→v2 只改域选择约束且发生在域冻结前；第三片纯度 0.8950 的真实原因（S2 占满 >0.9 核心）；前缀降级路径本轮无实例；`geometric_validated_local=true` 但 identity/physical/runtime 仍 false，不得被页面冒充地面身份或物理高度。
- S4/S5、人体返工、独立 D、设备/采集/部署/训练/HR09、Git 写均未授权。
""".format(d=ITEM_DIR)


def sha(b):
    return hashlib.sha256(b).hexdigest()


if __name__ == '__main__':
    wf = WORKFLOW.read_bytes()
    rv = REVIEW.read_bytes()
    if b'\r' in wf or b'\r' in rv:
        raise SystemExit('input files are not LF-only; refusing to splice')
    entry = WORKFLOW_ENTRY.encode('utf8')
    if b'S03 \xe6\x9c\xac\xe6\xae\xb5' in wf[:400]:
        raise SystemExit('WORKFLOW already has an S3 entry at the top')
    if not wf.endswith(b'\n') or not rv.endswith(b'\n'):
        raise SystemExit('unexpected trailing newline state')
    new_wf = entry + wf
    new_rv = rv + REVIEW_ENTRY.encode('utf8')
    with WORKFLOW.open('wb') as f:
        f.write(new_wf)
    with REVIEW.open('wb') as f:
        f.write(new_rv)
    wf2 = WORKFLOW.read_bytes()
    rv2 = REVIEW.read_bytes()
    checks = dict(
        workflow_prefix_is_new_entry=wf2[:len(entry)] == entry,
        workflow_original_bytes_preserved=wf2[len(entry):] == wf,
        review_original_bytes_preserved=rv2[:len(rv)] == rv,
        review_suffix_is_new_entry=rv2[len(rv):] == REVIEW_ENTRY.encode('utf8'),
        crlf_after=dict(workflow=wf2.count(b'\r\n'), review=rv2.count(b'\r\n')),
        bytes_before=dict(workflow=len(wf), review=len(rv)),
        bytes_after=dict(workflow=len(wf2), review=len(rv2)),
        sha_before=dict(workflow=sha(wf), review=sha(rv)),
        sha_after=dict(workflow=sha(wf2), review=sha(rv2)))
    C.write(C.OUT / 'DOCUMENT_APPEND.json', dict(
        item=C.ITEM, method='binary splice, UTF-8, LF only, never decoded/recoded',
        entry_bytes=dict(workflow=len(entry), review=len(REVIEW_ENTRY.encode('utf8'))), checks=checks,
        PASS=bool(checks['workflow_original_bytes_preserved'] and checks['review_original_bytes_preserved']
                  and checks['workflow_prefix_is_new_entry'] and checks['review_suffix_is_new_entry']
                  and not any(checks['crlf_after'].values()))))
    print('appended', checks['bytes_after'], 'PASS', not checks['crlf_after']['workflow'] and not checks['crlf_after']['review'])
