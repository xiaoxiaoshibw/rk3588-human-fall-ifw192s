"""GL-I03 R1 phase-1 read-only config-load/exception mapping.

Exercises the exact building blocks the phase-2 ``--constrained-config`` route
would reuse: ``sensor_health.load_config`` + ``core.ground.resolve_constrained_settings``.
No production file is written; YAML fixtures live in a temp dir.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path[:0] = [str(ROOT / "src/human_fall_detection/scripts"),
                str(ROOT / "src/human_fall_detection")]

from core.ground import (CONSTRAINED_DEFAULT_SETTINGS,
                         resolve_constrained_settings)
from sensor_health import load_config

report = {}
frozen = ROOT / "src/human_fall_detection/config/geometry_constrained.yaml"
report["frozen_config"] = {
    "load_type": type(load_config(str(frozen))).__name__,
    "top_keys": sorted(load_config(str(frozen)).keys()),
    "resolved_equals_default": resolve_constrained_settings(
        load_config(str(frozen))["ground_constrained"])
    == CONSTRAINED_DEFAULT_SETTINGS,
}

tmp = Path(tempfile.mkdtemp(prefix="gli03-cfg-"))


def probe(name, text):
    path = tmp / (name + ".yaml")
    if text is not None:
        path.write_text(text, encoding="utf-8")
    entry = {}
    try:
        config = load_config(str(path)) if text is not None else load_config(
            str(tmp / "missing.yaml"))
        entry["load"] = "ok"
        entry["load_type"] = type(config).__name__
        section = config.get("ground_constrained") if isinstance(config, dict) \
            else "NON_MAPPING_NO_GET"
        entry["section_present"] = None
        if isinstance(config, dict) and "ground_constrained" in config:
            entry["section_present"] = True
            entry["resolved_via"] = "resolve_constrained_settings"
            entry["resolved_equal_default"] = resolve_constrained_settings(
                config["ground_constrained"]) == CONSTRAINED_DEFAULT_SETTINGS
        else:
            entry["section_present"] = False
            entry["note"] = "missing section would need an explicit refuse"
    except Exception as exc:  # noqa: BLE001 - we are mapping exception classes
        entry["load"] = "raised"
        entry["exc_type"] = type(exc).__name__
        entry["exc_module"] = type(exc).__module__
        entry["is_valueerror"] = isinstance(exc, ValueError)
        entry["is_oserror"] = isinstance(exc, OSError)
        entry["is_yamlerror"] = type(exc).__name__ == "YAMLError"
        entry["caught_by_current_wrapper"] = isinstance(
            exc, (ValueError, OSError))
        entry["message"] = str(exc)[:160]
    report[name] = entry


probe("missing_path", None)
probe("yaml_syntax_error", "ground_constrained: [1, 2\n")
probe("empty_file", "")
probe("top_level_list", "- a\n- b\n")
probe("missing_section", "other: {}\n")
probe("section_not_mapping", "ground_constrained: 5\n")
probe("unknown_key", "ground_constrained:\n  bogus_key: 1\n")
probe("bool_value", "ground_constrained:\n  min_inliers: true\n")
probe("nan_value", "ground_constrained:\n  spatial_cell_m: .nan\n")
probe("negative_value", "ground_constrained:\n  max_points_per_cell: -1\n")
probe("floor_violation", "ground_constrained:\n  min_inliers: 99\n")
probe("two_value_variant_ok",
      "ground_constrained:\n  spatial_cell_m: 0.05\n  max_points_per_cell: 8\n")

with (Path(__file__).resolve().parent / "00_diag_config.json").open(
        "x", encoding="utf-8") as handle:
    json.dump(report, handle, indent=2, allow_nan=False)
print(json.dumps(report, indent=2, allow_nan=False))
