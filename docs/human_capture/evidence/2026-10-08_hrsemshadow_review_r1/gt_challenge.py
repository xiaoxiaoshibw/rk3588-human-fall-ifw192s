"""Schema adversarial fixture only; never publish a human GT sidecar."""
import importlib.util
import json
from audit import OUT, R1, save

spec = importlib.util.spec_from_file_location('r1finish', R1 / 'finish.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
template = json.loads((R1 / 'gt_review_template.json').read_text('utf8'))
attack = json.loads((OUT / 'review_index_challenge.json').read_text('utf8'))
record = attack['exported_record_in_memory']
fixture = {'kind': 'hr_sem_shadow_gt', 'schema': 1, 'source': 'human',
    'reviewer': 'SYNTHETIC INTEGRITY FIXTURE, NOT REAL GT', 'created_iso': 'synthetic-fixture',
    'binding': template['binding'], 'clusters': [record], 'points': []}
c = {r['id']: r for r in template['clusters']}
p = {r['id']: r for r in template['points']}
result = module.check_gt(fixture, template['binding'], c, p)
save('gt_challenge.json', {'synthetic_only': True, 'real_human_labels_written': 0,
    'tampered_display_record_passes_format_check': result,
    'conclusion': 'validator cannot prove reviewer saw the bound member set; frontend index binding must reject the tampered index'})
print('REPRODUCED: record from altered displayed members passes existing schema validator; zero real labels written')
