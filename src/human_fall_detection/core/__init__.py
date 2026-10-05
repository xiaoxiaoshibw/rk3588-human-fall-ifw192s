"""Core helpers for the human-fall work (HF-02 and later tickets).

Pure, ROS-free modules. The frozen HF-01 checks live in ``scripts/sensor_health.py``
and are reused (never copied) through the path bootstrap below.

catkin's devel-space ``core/__init__.py`` is a namespace relay: it extends
``__path__`` with the real source ``core`` directory and then execs this file,
but ``__file__`` still points at ``devel/lib/python3/dist-packages/core``. So the
bootstrap scans ``__path__`` for the real source ``core`` dir and adds its
sibling ``scripts`` directory (which holds the real ``sensor_health.py``, not the
devel relay), rather than trusting ``__file__``.

Only when no source scripts directory is found (a true installed layout) does it
fall back to ``<prefix>/lib/human_fall_detection``: ``dist-packages/core`` up
three levels is ``<prefix>/lib``. Adding that directory in the devel case would
wrongly put the relay-laden ``devel/lib/human_fall_detection`` ahead of the real
source scripts, so it is deliberately skipped whenever source scripts exist.
"""

import os
import sys


def _add(path):
    path = os.path.abspath(path)
    if os.path.isdir(path) and path not in sys.path:
        sys.path.insert(0, path)


_source_scripts = False
for _entry in globals().get("__path__", ()) or (os.path.dirname(os.path.abspath(__file__)),):
    _parent = os.path.dirname(os.path.abspath(_entry))
    _scripts = os.path.join(_parent, "scripts")
    if os.path.isdir(_scripts):
        _add(_scripts)
        _source_scripts = True

if not _source_scripts:
    _here = os.path.dirname(os.path.abspath(__file__))
    _add(os.path.join(_here, os.pardir, os.pardir, os.pardir,
                      "human_fall_detection"))
