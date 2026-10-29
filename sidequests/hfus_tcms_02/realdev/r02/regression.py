"""Unchanged legacy assertions; fixture IO relocated in memory to this item's sandbox."""
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from bootstrap import ROOT,OUT,write


def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(spec)
    sys.modules[name]=m;spec.loader.exec_module(m);return m


if __name__=='__main__':
    target=sys.argv[1]
    pre=ROOT/'sidequests/hfus_tcms_02/predev/r01'
    old=ROOT/'sidequests/hfus_tcms_02/realdev/r01'
    sandbox=OUT/('regression_'+target);sandbox.mkdir(exist_ok=False)
    if target=='predev':
        c=module('contracts',pre/'contracts.py')
        c.EVIDENCE_ROOT=sandbox
        # Same synthetic input contract, relocated expected evidence root only.
        # Source checks retain the original suffix and kind/role restrictions.
        original_new=c.new_output
        os.environ['PREDEV_TEST_OUTPUT']=str(sandbox/'2026-10-17_hfus_tcms_02_predev_r1/tests')
        for name in ['fixtures','pipeline','evaluate','run']:module(name,pre/(name+'.py'))
        tests=module('unchanged_assertions',pre/'test_predev.py')
    elif target=='realdev':
        sys.path.insert(0,str(old))
        c=module('contracts',old/'contracts.py');c.ITEM=sandbox
        for name in ['PROTOCOL_V1.json','PROTOCOL_V3.json','USER_UPDATE_V1.json']:
            source=c.ROOT/'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_realdev_r1'/name
            (sandbox/name).write_bytes(source.read_bytes())
        module('pipeline',old/'pipeline.py')
        tests=module('unchanged_assertions',old/'tests/test_realdev.py')
    else:raise ValueError('Unknown regression suite')
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    write(sandbox/'RELOCATION.json',dict(assertion_file=str(tests.__file__),assertions_changed=False,
        fixture_root=str(sandbox),binding='module globals / environment paths only; old source not edited',
        ran=result.testsRun,failures=len(result.failures),errors=len(result.errors)))
    raise SystemExit(0 if result.wasSuccessful() else 1)
