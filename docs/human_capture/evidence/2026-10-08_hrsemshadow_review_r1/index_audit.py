"""Check actual byte offsets and the embedded viewer's existing bound members."""
import csv
import json
from audit import R1, save

counts = {}
for csv_name, data_name in [('cluster_index.csv', 'clusters'), ('frame_index.csv', 'frames')]:
    count = 0
    with (R1 / csv_name).open(encoding='utf-8-sig', newline='') as f, (R1 / 'pass3' / (data_name + '.jsonl')).open('rb') as data:
        for row in csv.DictReader(f):
            data.seek(int(row['jsonl_byte_offset']))
            record = json.loads(data.readline())
            for name in ['sid', 'mode', 'ordinal', 'seq']:
                assert str(record[name]) == row[name]
            if data_name == 'clusters':
                for name in ['ci', 'n', 'valid_n', 'roi_overlap', 'member_sha256']:
                    assert str(record[name]) == row[name]
                assert record['semantic']['semantic'] == row['semantic']
            count += 1
    counts[csv_name] = count
assert counts == {'cluster_index.csv': 4311, 'frame_index.csv': 1561}
bundle = json.loads((R1 / 'review_bundle.json').read_text('utf8'))
template = json.loads((R1 / 'gt_review_template.json').read_text('utf8'))
assert template['source'] == 'diagnostic'
expected = {r['id']: r for r in template['clusters']}
cases = 0
for case in bundle['cases']:
    for c in case['clusters']:
        rid = '/'.join([case['sid'], case['mode'], str(case['ordinal']), str(c['ci'])])
        assert c['member_sha256'] == expected[rid]['member_sha256']
        point_rows = [p['row'] for p in c['points']]
        assert len(point_rows) == len(set(point_rows))
    cases += 1
assert cases == 34
save('index_audit.json', {'checked_offsets': counts, 'existing_embedded_cases': cases,
    'diagnostic_template_clusters': len(template['clusters']), 'diagnostic_template_points': len(template['points']),
    'scope': 'Existing delivered indices/cases are intact; this does not repair the unbound external-index load path'})
print('INDEX_PASS', counts, '34 existing cases intact')
