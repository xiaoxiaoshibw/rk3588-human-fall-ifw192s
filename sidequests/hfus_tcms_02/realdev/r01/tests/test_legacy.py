"""Re-run the 25 unchanged PREDEV assertions with NEW item-local fixture IO.

Only import bindings/output guards are adapted; legacy files remain read-only.
These assertions check the numerical reference, not equivalence of new maps.
"""
import os
from pathlib import Path
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from contracts import ITEM, PREDEV, module

os.environ['PREDEV_TEST_OUTPUT']=str(ITEM/('legacy_tests_%d'%time.time_ns()))
names=['fixtures','pipeline','run','evaluate']
saved={k:sys.modules.get(k) for k in names}
try:
    for name in ['fixtures','pipeline','evaluate','run']:
        sys.modules[name]=module('legacy_'+name,PREDEV/(name+'.py'))
    tests=module('realdev_legacy_assertions',PREDEV/'test_predev.py')
    PredevContracts=tests.PredevContracts
finally:
    for name,value in saved.items():
        if value is None:sys.modules.pop(name,None)
        else:sys.modules[name]=value
