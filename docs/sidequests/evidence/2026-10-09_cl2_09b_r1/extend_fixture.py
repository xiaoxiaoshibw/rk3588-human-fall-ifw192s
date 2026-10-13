"""Complete isolated dependency/HTTP fixture; retain first failed test log."""
import shutil
from prepare import E,I,save,sha
extra=[]
for name in ['human_replay_lib.py','config.py','leveling.html','leveling.js']:
    src=I/'pc_apps/human_replay'/name;dest=E/'frozen'/name
    digest=sha(src);shutil.copyfile(src,dest);assert digest==sha(src)==sha(dest)
    extra.append(dict(origin=str(src),frozen=str(dest),sha256=digest))
for p in (E/'frozen').rglob('*'):
    if not p.is_file():continue
    target=E/'candidate'/p.relative_to(E/'frozen')
    if target.exists():continue
    target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(p,target)
    assert sha(p)==sha(target)
save('extra_fixture_bindings.json',dict(reason='First combined test exit1: missing human_replay_lib HTTP fixture import; selector28 tests passed. Complete sibling runtime avoids code_hashes reading baseline floor_sheet while candidate module runs.',bindings=extra))
print('ISOLATED_FIXTURE_COMPLETED')
