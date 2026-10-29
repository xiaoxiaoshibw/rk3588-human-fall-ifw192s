"""Compatibility import; canonical implementation is shared with ROS."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"src/human_fall_detection"))
import core.ground_fit.floor_roi as _shared
globals().update({k:v for k,v in vars(_shared).items() if not k.startswith("__")})
