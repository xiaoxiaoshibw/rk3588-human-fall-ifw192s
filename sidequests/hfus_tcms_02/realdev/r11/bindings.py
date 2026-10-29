"""Bind reused implementation/configuration bytes before any experiment."""
import platform
import sys
import numpy
import scipy
import matplotlib
from common import W, ROOT, EV, HERE, SK, save, sha

paths=[W.ASSOCIATION,ROOT/'src/human_fall_detection/core/tracking.py',W.R01/'contracts.py',W.R04S/'skeleton.py',W.R04S/'paths.py',W.R04/'transform.py',W.R01/'pipeline.py',HERE.parent/'r08/wire.py',HERE.parent/'r08/calibrate.py',ROOT/'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py',ROOT/'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/prototype_params_v1.json',W.S3/'TRANSFORM/TRANSFORM_S3.json',ROOT/'docs/human_fall/evidence/2026-10-18_hfus_human_skeleton_02_r1/PROTOCOL_V3.json']
save('EXECUTION_BINDINGS.json',dict(files={p.relative_to(ROOT).as_posix():sha(p) for p in paths},environment=dict(python=sys.version,numpy=numpy.__version__,scipy=scipy.__version__,matplotlib=matplotlib.__version__,platform=platform.platform()),caller_audit=dict(actual=['src/human_fall_detection/core/tracking.py:258 single locked track; applies matches then ambiguous requires reselection; frozen unchanged','sidequests/hfus_tcms_02/realdev/r08/wire.py:305 multi-track; trusts matches; prefilter silently drops expired tracks; new replay adapter corrects LOST transition'],test_callers=['src/human_fall_detection/tests/test_hf05_tracking.py'],search='rg -n associate_tracks\\( src sidequests pc_apps tools -g *.py',scope='r11 isolated adapter only; production core and old wire remain byte-identical'),skeleton_params=SK.PARAMS))
