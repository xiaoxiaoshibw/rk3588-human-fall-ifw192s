"""CL2-13 seal: list every file in this evidence dir, sha256 each, write 07_EVIDENCE_MANIFEST.json.
Same shape as CL2-12's cl2_12_seal.py so the next round's reviewer sees identical structure."""
import json, hashlib, os
E = os.path.dirname(os.path.abspath(__file__))
files = {}
for f in sorted(os.listdir(E)):
    p = os.path.join(E, f)
    if os.path.isfile(p) and f != '07_EVIDENCE_MANIFEST.json':
        files[f] = hashlib.sha256(open(p, 'rb').read()).hexdigest()
out = {
  'round': 'CL2-13_r1', 'date': '2026-10-10 Asia/Shanghai',
  'evidence_dir': E, 'n_files': len(files), 'files': files,
  'external_readonly_inputs': {
    'bin': 'D:/Code/cl208audit/audit_inputs/cap_20261009_121647/points.bin',
    'bin_sha256': '97def5d21c28d695c686bb79b255fddd4f666ea856c39593f5dff567506017fc',
    'domain_npz_sha256': '1cf1ea9c4856f2ddc36f58e23d3747bb9ecb391ac582e8dd3ebc3febd03b5c26',
    'report_json_sha256': '9101d28a50c30e0210eb7eaca2b697b486517da000c660a89b34e82177b96214',
  },
  'sealed_history_readonly': {
    'cl2_10_dir': 'docs/sidequests/evidence/2026-10-09_cl2_10_r1 (05_evidence_manifest.json 195 files, untouched)',
    'cl2_11_dir': 'docs/sidequests/evidence/2026-10-10_cl2_11_r1 (07_EVIDENCE_MANIFEST.json 22 files, untouched)',
    'cl2_12_dir': 'docs/sidequests/evidence/2026-10-10_cl2_12_r1 (07_EVIDENCE_MANIFEST.json 28 files, '
                  'recomputed by 02_independent_recompute.py this round: 28/28 SHA match, 0 writes)',
  },
  'carried_findings': {
    'F-AUTHOR-1': 'CL2-12 corrected design_m3 has baseline-cell -> last-ring dummy collision. CL2-12 seal UNTOUCHED; '
                  'corrected numbers live in 02_RECOMPUTE_RESULTS.json.',
    'F-AUTHOR-2': 'CL2-12 02 uses morton-ordered c_levels while 03 CV uses plain-sorted -> baseline cells differ; '
                  '02 and 03 M3 numbers are NOT the same parametrization and must not be cross-cited as one model.',
  },
}
json.dump(out, open(os.path.join(E, '07_EVIDENCE_MANIFEST.json'), 'w'), indent=2)
print('manifest files:', len(files))
