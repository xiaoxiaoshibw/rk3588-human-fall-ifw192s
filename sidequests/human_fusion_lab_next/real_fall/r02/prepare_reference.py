"""Reuse the first version's existing auto-floor pipeline without changing it."""
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parents[4]
OUT=ROOT/'docs/human_fall/evidence/2026-10-13_hf_real_02_r1'
spec=importlib.util.spec_from_file_location('real_fall_existing_prepare',Path(__file__).parent.parent/'r01/prepare.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
module.OUT=OUT
module.prepare('cap_20261013_131958')
