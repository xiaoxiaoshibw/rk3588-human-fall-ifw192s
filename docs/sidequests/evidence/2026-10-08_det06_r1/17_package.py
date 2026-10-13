"""DET-06 17 packaging: code snapshot, run manifest, evidence/artifact index. No inference. Read-only on inputs."""
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[3]
CODE = WORK / 'sidequests/human_detectors'
ART = CODE / 'artifacts/det06_r1'
SNAP = HERE / 'code_final'
CODE_FILES = ['det06_prepare.py', 'det06_foreground.js', 'det06_annotate.py', 'det06_record.py',
              'det06_freeze.py', 'det06_eval.py', 'det06_metrics.py', 'det06_hardneg_check.py', 'test_det06.py']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def main():
    assert not SNAP.exists(), 'code_final already exists; not overwriting'
    SNAP.mkdir()
    code = []
    for name in CODE_FILES:
        src = CODE / name
        shutil.copy2(src, SNAP / name)
        code.append(dict(path=f'sidequests/human_detectors/{name}', sha256=sha(src)))
    readme = CODE / 'README.md'
    frozen = ART / 'frozen/gt_eval_v1.json'
    protocol = HERE / '02_protocol_freeze.json'
    run = dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        writer='OpenCode only (opencode-go/deepseek-v4.1-flash)',
        skill_loader='opencode skill tool (id=ponytail, intensity=full)',
        skill_base_dir='C:/Users/30680/.config/opencode/skills/ponytail',
        branch='codex/human-detector-models', HEAD='cfbb80c57508be1a0435fdb92260f698dc763934',
        acceptance_sha256=sha(WORK / 'docs/sidequests/DET06_ACCEPTANCE.md'),
        plan_sha256=sha(WORK / 'docs/sidequests/DET06_PLAN.md'),
        return_sha256=sha(WORK / 'docs/sidequests/returns/DET-06.md'),
        report_sha256=sha(HERE / 'README.md'),
        readme_top_sync_sha256=sha(readme),
        gt_eval_v1_sha256=sha(frozen),
        protocol_sha256=sha(protocol),
        eval_config_sha256=sha(ART / 'eval/config.json'),
        metrics_sha256=sha(ART / 'eval/metrics.json'),
        checkpoint_sha256=sha(CODE / 'artifacts/upstream/epoch_160.pth'),
        code=code,
        code_note='all DET-06 code is new this round; no existing sidequest code modified except README top sync',
        forwards=dict(declared=74, used=74),
        status='SUBMITTED (author self-check); not ACCEPTED')
    (HERE / '17_run_manifest.json').write_text(json.dumps(run, ensure_ascii=False, indent=2), encoding='utf-8')
    evidence = sorted(p for p in HERE.rglob('*') if p.is_file() and p.name != '17_artifact_index.json')
    index = dict(evidence=[dict(path=str(p.relative_to(WORK)).replace('\\', '/'), sha256=sha(p)) for p in evidence],
                 artifacts={})
    for sub in sorted(p for p in ART.iterdir() if p.is_dir()) + sorted(p for p in CODE.joinpath('artifacts').iterdir()
                                                                        if p.is_dir() and p.name.startswith('det06_')):
        files = [p for p in sub.rglob('*') if p.is_file()]
        index['artifacts'][str(sub.relative_to(WORK)).replace('\\', '/')] = dict(
            files=len(files), bytes=sum(p.stat().st_size for p in files),
            manifests={p.name: sha(p) for p in files if p.suffix == '.json' and p.parent == sub})
    (HERE / '17_artifact_index.json').write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
    print('17 PASS: code snapshot %d files; evidence indexed %d; artifact dirs %d'
          % (len(code), len(evidence), len(index['artifacts'])))


if __name__ == '__main__':
    main()
