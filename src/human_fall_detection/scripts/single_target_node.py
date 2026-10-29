#!/usr/bin/env python3
"""Repository/bundle entry for automatic radar tracking plus measured regions.

This script starts ROS only when explicitly executed. Bundle preparation is a
separate, local-only command.

Layout contract
---------------
Both the repository tree and an unpacked release keep the *repo-relative*
layout, because the region dependency closure resolves its own root by walking
four directories up from ``sidequests/.../current/project_dependencies.py``.
``find_root`` therefore looks for the layout markers instead of counting
``parents[N]`` from this file.

Configuration precedence (highest first)
----------------------------------------
1. explicit command line (``--config`` / ``--perception`` plus anything else
   forwarded to ``human_fall_node``);
2. ROS remaps/params (``_config:=...``, ``~perception:=...``) -- when one is
   present the default is *not* injected, otherwise the CLI default would
   silently win over the operator's ROS parameter;
3. the bundled scene example (``config/single_target_scene_v1.yaml`` +
   ``config/perception_single_target_v1.yaml``).

The bundled scene is an unverified named example, not a site profile: a field
deployment passes an effective config generated from a site profile.
"""
import sys
import json
from pathlib import Path

DEFAULT_NODE_NAME = "single_target_live"

_MARKERS = (
    "src/human_fall_detection/scripts/human_fall_node.py",
    "sidequests/hfus_tcms_02/realdev/current/region_runtime.py",
)


def find_root(start):
    """Return the tree root that actually contains the runtime dependencies."""
    start = Path(start).resolve()
    for candidate in (start,) + tuple(start.parents):
        if all((candidate / marker).is_file() for marker in _MARKERS):
            return candidate
    # Fall back to the historical layout so an error message still points
    # somewhere meaningful (imports will fail loudly afterwards).
    return start.parents[2] if len(start.parents) > 2 else start


def configure_paths(root):
    for path in ('ML/src', 'src/human_fall_detection', 'src/human_fall_detection/scripts',
                 'src/human_follow_calibration/scripts',
                 'sidequests/hfus_tcms_02/realdev/current'):
        sys.path.insert(0, str(root / path))


def _has_option(args, name):
    return any(token == name or token.startswith(name + "=") for token in args)


def _ros_override(args, name):
    """True when a ROS remap/param already supplies ``name`` (``_x:=``/``~x:=``)."""
    prefixes = ("_" + name + ":=", "~" + name + ":=", "/" + name + ":=")
    return any(token.startswith(prefixes) for token in args)


def _ros_node_name(args):
    for token in args:
        if token.startswith("__name:="):
            return token.split(":=", 1)[1] or None
    return None


def build_arguments(args, config_dir):
    """Fill in scene defaults only where the operator did not specify anything."""
    args = list(args)
    if not _has_option(args, "--config") and not _ros_override(args, "config"):
        args += ["--config", str(config_dir / "single_target_scene_v1.yaml")]
    if not _has_option(args, "--perception") and not _ros_override(args, "perception"):
        args += ["--perception", str(config_dir / "perception_single_target_v1.yaml")]
    if _ros_node_name(args) is None:
        args.append("__name:=" + DEFAULT_NODE_NAME)
    return args


def main(argv=None):
    root = find_root(Path(__file__).resolve().parent)
    configure_paths(root)
    from human_fall_node import main as node_main
    from region_runtime import LiveRegions
    args = build_arguments(list(sys.argv[1:] if argv is None else argv),
                           root / 'src/human_fall_detection/config')
    release_path=root/'RELEASE.json'
    release=json.loads(release_path.read_text(encoding='utf-8')) if release_path.is_file() else {}
    shadow=(release.get('features') or {}).get('event_geometry_shadow') is True
    if '--event-geometry-shadow' in args:
        shadow=True;args.remove('--event-geometry-shadow')
    processor=LiveRegions()
    if shadow:
        from event_geometry_shadow import LiveGeometryShadow
        processor=LiveGeometryShadow(processor)
    # rospy reads sys.argv for remaps, not the explicit argv passed to main.
    sys.argv[1:] = args
    return node_main(args, frame_postprocessor=processor)


if __name__ == "__main__":
    sys.exit(main())
