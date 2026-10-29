"""Offline demo imports the same geometric observer as the live engine."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src/human_fall_detection'))
from core.range_demo_alert import DemoAlert  # noqa: E402,F401
