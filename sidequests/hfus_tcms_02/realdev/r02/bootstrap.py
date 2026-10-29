"""Freeze scope before real-source processing. No data writes or algorithm runs."""
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s01_r1'
ITEM = 'HFUS-TCMS-02-REALDEV-02-S01'


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(b)
    return h.hexdigest()


def write(path, value):
    p = Path(path).absolute()
    if not p.resolve().is_relative_to(OUT.resolve()):
        raise ValueError('Output outside item')
    if any(x.is_symlink() or x.is_junction() for x in [p, *p.parents] if x.exists()):
        raise ValueError('Output reparse path')
    with p.open('x', encoding='utf8') as f:
        if isinstance(value, str):
            f.write(value)
        else:
            json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT)


if __name__ == '__main__':
    started = time.time()
    files = sorted(set(git('ls-files', '-c', '-o', '--exclude-standard', '-z').decode('utf8').split('\0')) - {''})
    OUT.mkdir(exist_ok=False)
    write(OUT/'ENVIRONMENT.json', dict(item=ITEM, writer='Codex sole implementation writer',
        model='GPT-6 as identified by system; exact runtime model ID not exposed; no model switch',
        platform=platform.platform(), python=sys.version, executable=sys.executable,
        strategy=dict(measurement='RESEARCH', coordinate='ENGINEERING'),
        ponytail='C:/Users/30680/.codex/skills/ponytail/SKILL.md',
        scientific_toolkit='C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md'))
    write(OUT/'BASELINE_GIT.json', dict(branch=git('branch','--show-current').decode().strip(),
        head=git('rev-parse','HEAD').decode().strip(), status=git('status','--porcelain=v1','-uall').decode('utf8'),
        scope='all tracked and nonignored untracked files; ignored data is input, separately hashed'))
    with (OUT/'BASELINE_FILES.jsonl').open('x', encoding='utf8') as f:
        for name in files:
            p = ROOT/name
            # Never traverse a junction, symlink, or the ignored data root.
            if name.startswith(('data/', 'captures/remote/', 'captures/leveled/', 'captures/registration/')):
                raise ValueError('Data unexpectedly appears in workspace baseline')
            record = dict(path=name)
            if p.is_symlink():
                record.update(kind='symlink', target=os.readlink(p))
            elif not p.is_file():
                record.update(kind='missing_or_nonfile')
            else:
                record.update(kind='file', bytes=p.stat().st_size, sha256=sha(p))
            f.write(json.dumps(record, ensure_ascii=False)+'\n')
    protocol = dict(item=ITEM, version=1, status='PRE_RUN_FROZEN',
        source=dict(path='D:/Code/ldiar/data/sessions/cap_20261017_113516', sid='cap_20261017_113516',
            meta='eeb336b895e2a147a09f23f9d69cdecb9490e020c2d91467e2ab5a84bd082ad4',
            points='254c481fb4faad01f6d30d4630b471dcbc74a25985caba0949ea6d40705f84f1',
            rows=38298918, frames=780, stride=28, decode='XYZ <f4 bytes 0..11 only; tail 12..27 opaque',
            validity='finite AND any XYZ != 0; preserve invalid values/order/source_row',
            purpose='REAL_DEVELOPMENT/B', taint='development_seen/dev-tainted', independent_test=False),
        historical=dict(path='data/leveled/61cb6976b0f8479394641850d9a7c6ca/tls/transform.json',
            sha256='01662ac7df061b42353c465ad74ab5a0d1d8452ede014c09d4a3b310f26b447a',
            report='data/leveled/61cb6976b0f8479394641850d9a7c6ca/report.json',
            report_sha256='09fda8013758666fb66609f33f49cba2eefd666975e836de9ae404e71a3226a0',
            policy='reuse complete historical R/t byte-bound artifact, no refit, no nominal_R mixing',
            direction='innolidar -> ground_offline_display', units='m',
            reference_axis='historical R first row; project for PLAN basis numeric crosscheck only; no alternate axis'),
        frozen_run='docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_r1/ai_continuation_r2',
        math=dict(column='p_local=R@p_raw+t', row='p_raw@R.T+t', plane='n.p+d=0; normalize n and d together',
            float64='max(1e-8,1e-12*norm(p)) m', float32='max(1e-5,1e-6*norm(p)) m',
            rotation_atol=1e-10, reference_projection_min=1e-8, boxes='all 8 corners -> OBB',
            vectors='R only', covariance='R Sigma R.T'),
        objects='all source rows + frozen M0 centers/OBB/support CSR + candidate members/centers/boxes + track centers/predictions; no segmentation or association rerun',
        missing_fields='frozen run has no velocity/covariance fields; transform adapters tested synthetic; never fabricate measured values',
        state='CANDIDATE_PLANE_PREVIEW', mode='OFFLINE_REVIEW',
        qualification='identity/geometry/physical/runtime all false; historical identity evidence only; no height/cut',
        causal='keep original map availability per frame and build maximum; no early map',
        residual='full valid scene residual all 780 frames + legacy band flags descriptive only; no ground identity/validation',
        measurement_review='OB01..OB10 code/formula/report/result audit; no new ground solver; no reinterpretation as NN',
        probe_frames=[0,192,193,270,271,430,431,779],
        browser_frames=[0,192,193,270,271,385,430,431,432,439,520,750,760,770,779],
        display=dict(current=9000, surfaces=3000, support_sample=600),
        budget=dict(probe_s=180, full_s=2400, peak_rss=2147483648, output_bytes=3221225472),
        forbidden=['data writes','old artifacts edits','production/config/model/GT edits','refit','local voxel rebuild','algorithm rerun','S2/S3/S4/E2/E3/E4','train/HR09','git writes','device/network/driver/deploy/capture'])
    write(OUT/'PROTOCOL_V1.json', protocol)
    clauses = ['来源SHA、tracked/untracked基线、零数据写入', 'E0/E1逐OB复核与勘误边界',
        '完整候选R/t来源、方向、版本', '数学、逆变换、退化与错误方向拒绝', '780帧全源行守恒与双XYZ',
        '全对象坐标/成员/关联保持', 'API与真实浏览器同帧/点选/相机', '资格、因果、版本更新边界',
        '受影响契约、性能、RSS、输出预算', '命令/失败/SHA/回传/独审交接']
    write(OUT/'ACCEPTANCE_V1.md', '# '+ITEM+' 唯一验收 v1\n\n运行前登记，结果见 REPORT.md；本表不修改旧 OB/G 验收。\n\n| ID | 条款 | 运行前状态 |\n|---|---|---|\n'+''.join('| C%02d | %s | NOT_RUN |\n'%(i+1,c) for i,c in enumerate(clauses))+'\n作者自验、只读助手检查、正式独立复审分别记录。工程C通过不提升PLAN G05/G06或地面资格。\n')
    write(OUT/'BOOTSTRAP_RESULT.json', dict(seconds=time.time()-started, workspace_files=len(files),
        source_read=False, protocol_sha256=sha(OUT/'PROTOCOL_V1.json')))
    print(str(OUT))
