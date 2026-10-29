"""Explicit read-only dependencies; independent of other replay services' sys.path."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np

ROOT=Path(__file__).resolve().parents[4]

def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result)
    return result

GEOMETRY=ROOT/'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1'
SLOTS=['TOP_REGION','UPPER_TORSO','CHEST','PELVIS','LOWER_CENTER','UPPER_A','UPPER_B',
       'OUTER_A','OUTER_B','LOWER_A','LOWER_B','END_A','END_B']
EDGES=[('TOP_REGION','UPPER_TORSO'),('UPPER_TORSO','CHEST'),('CHEST','PELVIS'),
       ('PELVIS','LOWER_CENTER'),('UPPER_TORSO','UPPER_A'),('UPPER_TORSO','UPPER_B'),
       ('UPPER_A','OUTER_A'),('UPPER_B','OUTER_B'),('PELVIS','LOWER_A'),
       ('PELVIS','LOWER_B'),('LOWER_A','END_A'),('LOWER_B','END_B')]
SK=SimpleNamespace(G=module('active_project_geometry',GEOMETRY/'skeleton.py'),
    PARAMS=json.loads((GEOMETRY/'prototype_params_v1.json').read_text(encoding='utf8')),SLOTS=SLOTS,EDGES=EDGES)
CalibrationLayer=module('active_project_calibration',ROOT/'sidequests/hfus_tcms_02/realdev/r08/calibrate.py').CalibrationLayer

def valid_nodes(sk):return sum(bool(n['valid']) for n in sk['nodes'].values())

def measurements(sk):
    return {(a,b):float(np.linalg.norm(np.array(sk['nodes'][a]['xyz'])-sk['nodes'][b]['xyz']))
            for a,b in EDGES if sk['nodes'][a]['valid'] and sk['nodes'][b]['valid']}
