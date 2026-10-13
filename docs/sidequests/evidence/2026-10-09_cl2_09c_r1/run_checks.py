import difflib
import os
import sys
from prepare import E,run,save,sha

label=sys.argv[1]
if label=='tests':
    temporary=E/'test_tmp';temporary.mkdir(exist_ok=True)
    env=os.environ.copy()
    env['PYTHONPATH']=os.pathsep.join([str(E/'candidate'),str(E/'frozen'),str(E)])
    env['TEMP']=str(temporary);env['TMP']=str(temporary)
    code=run(sys.argv[2] if len(sys.argv)>2 else '05_regression',['-m','unittest','-v','test_selector','floor_detector_test',
             'floor_sheet_test','floor_roi_test','leveling_test','test_equivalence'],env)
elif label=='profile':code=run(sys.argv[2] if len(sys.argv)>2 else '03_profile',['benchmark.py','profile',sys.argv[3] if len(sys.argv)>3 else '03_profile.json'])
elif label=='benchmark':code=run('04_benchmark',['benchmark.py'])
else:raise SystemExit('unknown check')
raise SystemExit(code)
