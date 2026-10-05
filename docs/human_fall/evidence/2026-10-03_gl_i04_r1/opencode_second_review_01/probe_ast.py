"""Independent Python3.8 AST + import-layer probe (read-only)."""
import ast
import json
import sys
from pathlib import Path

ROOT = Path(r"D:/Code/ldiar")
RUN = ROOT / "docs/human_fall/evidence/2026-10-03_gl_i04_r1"
files = {
    "core/ground_diagnostics.py": ROOT / "src/human_fall_detection/core/ground_diagnostics.py",
    "scripts/diagnose_gli04_geometry.py": ROOT / "src/human_fall_detection/scripts/diagnose_gli04_geometry.py",
    "tests/test_gli04_geometry.py": ROOT / "src/human_fall_detection/tests/test_gli04_geometry.py",
    "research/search_prototype.py": RUN / "research_01/search_prototype.py",
    "research/experiment.py": RUN / "research_01/experiment.py",
}
stdlib = set(sys.stdlib_module_names)
out = {"python38_ast": {}, "imports": {}, "core_purity": {}}
for name, path in files.items():
    src = path.read_text(encoding="utf-8")
    try:
        tree = ast.parse(src, feature_version=(3, 8))
        out["python38_ast"][name] = "PASS"
    except SyntaxError as exc:
        out["python38_ast"][name] = "FAIL: " + str(exc)
        continue
    mods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            mods.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            mods.append(("." * node.level) + (node.module or ""))
    out["imports"][name] = sorted(set(mods))

core_imports = out["imports"]["core/ground_diagnostics.py"]
banned = [m for m in core_imports
          if any(t in m.lower() for t in ("ros", "rclpy", "yaml", "browser", "rospy", "std_msgs"))]
out["core_purity"] = {
    "imports": core_imports,
    "banned_hits": banned,
    "external_top_level": [m for m in core_imports
                           if m and not m.startswith(".") and m.split(".")[0] not in stdlib
                           and m not in ("numpy",)],
    "ok": not banned and all(m in ("math", "numpy", "capture_input", ".", ".capture_input")
                             or m.startswith(".") for m in core_imports)}
out["ok"] = all(v == "PASS" for v in out["python38_ast"].values()) and out["core_purity"]["ok"]
print(json.dumps(out, indent=2))
print("\nALL_OK:", out["ok"])
