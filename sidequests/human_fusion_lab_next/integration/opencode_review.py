"""Reuse the verified one-line OpenCode dispatch without writing old evidence."""
import argparse
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
HELPER = ROOT / "docs/human_capture/evidence/2026-10-11_human_fusion_unified_plan_r1/audit_plan.py"


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["probe", "review"])
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--brief", type=Path)
    args = parser.parse_args()
    spec = importlib.util.spec_from_file_location("verified_dispatch", HELPER)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    helper.ROOT = ROOT
    helper.EVIDENCE = args.evidence.resolve()
    if args.action == "probe":
        status, output = helper.cli(args.label, "Reply PROBE_OK only. Do not use any tools.", 55)
        ok = status == 0 and "PROBE_OK" in output
    else:
        if args.brief is None:
            parser.error("review requires --brief")
        brief = args.brief.resolve()
        status, output = helper.cli(args.label, brief.read_text(encoding="utf-8"), 900, True, brief)
        ok = status == 0 and "REVIEW_COMPLETE" in output
    raise SystemExit(0 if ok else 1)
