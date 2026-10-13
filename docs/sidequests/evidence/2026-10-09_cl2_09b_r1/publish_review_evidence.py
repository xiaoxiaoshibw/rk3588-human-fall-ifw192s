import shutil
from prepare import E,I,load,save,sha
folder=E/'input_snapshot';folder.mkdir()
job=I/'sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
sources=[job/'report.json',job/'manifest.json',I/'audit_inputs/cap_20261009_121647/meta.json']
bindings=[]
for p in sources:
    dest=folder/p.name;digest=sha(p);shutil.copyfile(p,dest);assert sha(dest)==sha(p)==digest
    bindings.append(dict(origin=str(p),copy=str(dest),sha256=digest))
save('snapshot_bindings.json',bindings)
baseline=load(E/'01_baseline.json');guard=load(E/'09_integrity.json')
save('source_summary.json',dict(main_HEAD=baseline['main_HEAD'],main_branch=baseline['main_branch'],
    main_inventory_count=len(baseline['main_all_files']),isolated_inventory_count=len(baseline['isolated_all_files']),
    source_bindings=baseline['source_bindings'],input_files=baseline['input_files'],
    actual_guard_pass=guard['PASS'],candidate_file_sha=guard['candidate_files'],frozen_file_sha=guard['frozen_files'],
    main_scope='All-file context; two unrelated overlay edits recorded, immutable isolated source governs execution.'))
save('submission_manifest.json',dict(files={p.relative_to(E).as_posix():sha(p) for p in sorted(E.rglob('*')) if p.is_file()},
    scope='Pre-supplement file closure. Final CLI/return/full seal are later records; this manifest never overwritten.'))
