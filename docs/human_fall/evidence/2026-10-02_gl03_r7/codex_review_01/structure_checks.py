"""Independent R6 PLAN_REVIEW structure cells; never writes production files."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[5]
sys.path[:0] = [str(ROOT/'src/human_fall_detection'),
               str(ROOT/'docs/human_fall/evidence/2026-10-02_gl03_r2')]
import codex_reference_checks as ref
from core.calibration import (resolve_reference_transform,
    validate_geometry_calibration, GeometryCalibrationError, make_unknown_transform)

rows = []
def check(name, record, allowed, explicit=True, full=False):
    original = copy.deepcopy(record)
    standalone = ref.transform() if explicit else None
    binding, reason = resolve_reference_transform(record, standalone, 'innolidar')
    assert (binding is not None) == allowed, (name, reason, binding)
    if not allowed:
        assert reason is not None, name
    snap = ref.ReferenceBinding().snapshot(standalone, record)
    assert snap['candidates'], name
    assert all((c['center_reference_m'] is not None) == allowed
               for c in snap['candidates']), name
    json.dumps(snap, allow_nan=False)
    assert record == original, name
    if full and not allowed:
        try:
            validate_geometry_calibration(record)
        except GeometryCalibrationError:
            pass
        else:
            raise AssertionError(('full validator accepted', name))
    rows.append({'cell': name, 'result': 'PASS', 'reason': reason})

def summary():
    return {'calibration_id':'legacy', 'frames':{'lidar':'innolidar',
        'reference':'fixture_reference'}, 'transforms':{'T_reference_lidar':ref.transform()}}

bad = [42, 0, True, False, [], ['innolidar'], {}, '', 'damaged']
for label in ('lidar', 'reference'):
    for value in [42, 0, True, False, [], ['innolidar'], {}, '', None]:
        record = ref.calibration(ref.transform())
        record['frames'][label] = value
        allowed = label == 'reference' and value is None
        check('full frames.%s=%r'%(label,value),record,allowed,full=True)
    record = ref.calibration(ref.transform()); del record['frames'][label]
    check('full missing '+label,record,label=='reference',full=True)

for container in ('frames','transforms','rotations'):
    for value in bad:
        record = ref.calibration(ref.transform()); record[container] = value
        # Empty dictionaries are objects, but a full frames object still needs lidar.
        allowed = value == {} and container != 'frames'
        check('full %s=%r'%(container,value),record,allowed,full=True)

for container, child in [('transforms','T_reference_lidar'),('rotations','R_lidar_imu')]:
    for value in [42,0,True,False,[],['x'],'damaged',None]:
        record = ref.calibration(ref.transform()); record[container][child] = value
        check('full child %s=%r'%(child,value),record,False,full=True)

for container in ('frames','transforms'):
    for value in bad + [None]:
        record = summary(); record[container] = value
        allowed = value is None or isinstance(value,dict)
        check('summary %s=%r'%(container,value),record,allowed)
    record = summary(); del record[container]
    check('summary missing '+container,record,True)

for label in ('lidar','reference'):
    for value in [42,0,True,False,[],['x'],{},'',None]:
        record = summary(); record['frames'][label] = value
        check('summary label %s=%r'%(label,value),record,value is None)
    record = summary(); del record['frames'][label]
    check('summary missing label '+label,record,True)

for value in [42,0,True,False,[],['x'],'damaged']:
    for explicit in (False,True):
        record=summary(); record['transforms']['T_reference_lidar']=value
        check('summary bad child=%r standalone=%s'%(value,explicit),record,False,explicit)
for value in [None,make_unknown_transform('innolidar','fixture_reference')]:
    record=summary(); record['transforms']['T_reference_lidar']=value
    check('summary absent/unknown child=%r'%value,record,True)
record=summary(); del record['transforms']['T_reference_lidar']
check('summary missing canonical',record,True)
for label,value in [('lidar','foreign'),('reference','foreign')]:
    record=summary();record['frames'][label]=value
    check('summary binding mismatch '+label,record,False)
record=summary()
binding,reason=resolve_reference_transform(record,ref.transform(translation=(9,0,0)),'innolidar')
assert binding is None and reason=='reference_transform_conflict'
rows.append({'cell':'known canonical explicit conflict','result':'PASS','reason':reason})
Path(__file__).with_name('11_structure_cells.json').write_text(
    json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
print('ALL',len(rows),'STRUCTURE CELLS PASS')
