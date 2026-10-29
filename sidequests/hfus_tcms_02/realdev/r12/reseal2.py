"""Second sealing round: rebind manifest/seal, excluding the sealing round's own outputs.

R1 (FINAL_SEAL.json) is retained as history: its manifest embedded the sealing
run's own then-empty DELIVER_R2.log and omitted its RUN file. R2 records the
frozen final bytes of every artifact except the exclusion set below.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

from common2 import EV, read
from register2 import HERE as R12, sha, put

EXCLUDED = ('MANIFEST_R2.json', 'FINAL_SEAL_R2.json', 'FINAL_SEAL_R2.sha256', 'RESEAL_R2.log', 'RESEAL_R2_RUN.json')


def main():
    r1 = read(EV / 'MANIFEST.json')
    assert r1['files']['DELIVER_R2.log']['sha256'] != sha(EV / 'DELIVER_R2.log'), 'expected R1 self-reference staleness not observed'
    seal1 = read(EV / 'FINAL_SEAL.json')
    files = {p.relative_to(EV).as_posix(): dict(bytes=p.stat().st_size, sha256=sha(p)) for p in EV.rglob('*') if p.is_file() and p.name not in EXCLUDED}
    put(EV / 'MANIFEST_R2.json', dict(
        files=files,
        excluded=dict(self_round=list(EXCLUDED), note='Sealing-round outputs and the R2 seal trio are the only exclusions; the R1 seal trio and all prior DELIVER run files are included with frozen bytes.'),
        supersedes='MANIFEST.json (R1) whose DELIVER_R2.log entry captured the then-empty log of the sealing run itself',
    ))
    put(EV / 'FINAL_SEAL_R2.json', dict(
        item=seal1['item'],
        manifest_sha=sha(EV / 'MANIFEST_R2.json'),
        source={p.name: sha(p) for p in R12.glob('*.py')},
        status='SUBMITTED',
        supersedes='FINAL_SEAL.json (R1): its bound manifest included the sealing run\'s own then-empty DELIVER_R2.log (self-reference) and omitted DELIVER_R2_RUN.json; R1 and its sha256 are retained for history.',
        excluded_self=list(EXCLUDED),
        note='Every other evidence file is bound with frozen final bytes, including the R1 seal trio and all run logs of failed and successful attempts. Verify by recomputing MANIFEST_R2 entries; the five excluded files are this sealing round\'s own outputs.',
    ))
    put(EV / 'FINAL_SEAL_R2.sha256', sha(EV / 'FINAL_SEAL_R2.json') + '  FINAL_SEAL_R2.json\n')
    print('resealed; entries', len(files), flush=True)


if __name__ == '__main__':
    main()
