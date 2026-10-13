import shutil
from prepare import E,I,sha,save
src=I/'pc_apps/human_replay/validation.py';digest=sha(src)
for folder in ['frozen','candidate']:
    dest=E/folder/'validation.py';assert not dest.exists();shutil.copyfile(src,dest);assert sha(dest)==digest
assert sha(src)==digest
save('validation_fixture_binding.json',dict(origin=str(src),sha256=digest,reason='Fourth full suite reached actual HTTP leveled_latest then missing frozen validation import; fixtures completed without changing any module.'))
