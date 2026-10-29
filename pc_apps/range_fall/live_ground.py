"""PC compatibility entry for the shared site-ground implementation."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'src/human_fall_detection'))
from core.range_site_ground import *
