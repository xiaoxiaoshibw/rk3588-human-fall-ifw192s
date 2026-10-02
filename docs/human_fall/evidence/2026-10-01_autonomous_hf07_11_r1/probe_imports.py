#!/usr/bin/env python3
"""Print the resolved source/devel/install import paths for the HF-07 fix."""

import os
import sys

import core
import core.lidar_candidates  # noqa: F401
import core.node_runtime  # noqa: F401
import sensor_health
from sensor_health import _load_xyz_from_cloud

xyz_from_cloud, calibration_error = _load_xyz_from_cloud()
print("cwd", os.getcwd())
print("core.__file__", getattr(core, "__file__", None))
print("core.__path__", list(getattr(core, "__path__", [])))
print("sensor_health.__file__", getattr(sensor_health, "__file__", None))
print("decoder_available", xyz_from_cloud is not None,
      "calibration_error", calibration_error)
print("PROBE_OK", xyz_from_cloud is not None
      and hasattr(sensor_health, "check_stamp"))
