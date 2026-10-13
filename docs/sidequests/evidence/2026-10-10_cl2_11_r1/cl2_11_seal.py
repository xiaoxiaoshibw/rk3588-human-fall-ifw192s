"""CL2-11 manifest: hash all files in this evidence dir."""
import hashlib
import json
from pathlib import Path

E = Path(__file__).resolve().parent


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    files = {}
    for p in sorted(E.rglob('*')):
        if p.is_file() and p.name != '07_EVIDENCE_MANIFEST.json':
            files[p.relative_to(E).as_posix()] = sha(p)
    manifest = {
        'round': 'CL2-11_r1',
        'date': '2026-10-10 Asia/Shanghai',
        'evidence_dir': str(E),
        'n_files': len(files),
        'files': files,
        'external_readonly_inputs': {
            'cl2_10_report': 'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20/report.json',
            'cl2_10_domain': 'D:/Code/cl208audit/sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20/domain.npz',
            'cl2_10_bin_mirror': 'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin',
            'cl2_10_bin_sha256_expected': '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc',
            'cl2_09a_next_experiment': 'C:/Users/30680/.codex/worktrees/traditional-clustering/ldiar/docs/sidequests/evidence/2026-10-09_cl2_09a_r1/08_next_experiment.md',
            'cl2_09a_next_experiment_sha256': '22e75d46ec309f10812e868c99c4e7f4ab7874cc9fae47054d58d9b2eefe87b2',
        },
        'cl2_10_sealed_unchanged': 'CL2-10 FINAL_REPORT/manifest/04_independent_review_* NOT touched by this round',
        'cross_directory_writes': {
            'note': 'CL2-11 produced two probe JSONs that were written into the CL2-10 sealed directory by mistake (audit finding #6). They are NOT part of CL2-10 05_evidence_manifest.json. No bytes were added/removed from that directory after this round\'s audit closed. Their SHA256 are registered here for traceability.',
            'files': {
                'D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/cl2_11_ring_probe.json': None,
                'D:/Code/ldiar/docs/sidequests/evidence/2026-10-09_cl2_10_r1/cl2_11_ring_xy_probe.json': None,
            },
        },
    }
    import hashlib as _h
    for p in list(manifest['cross_directory_writes']['files'].keys()):
        manifest['cross_directory_writes']['files'][p] = _h.sha256(open(p,'rb').read()).hexdigest()
    (E / '07_EVIDENCE_MANIFEST.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf8')
    print('manifest files:', len(files))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
