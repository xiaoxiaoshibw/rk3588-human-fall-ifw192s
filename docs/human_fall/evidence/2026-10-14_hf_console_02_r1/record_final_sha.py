import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
relative_files = [
    "pc_apps/console/console_gui.py",
    "pc_apps/console/console.html",
    "pc_apps/console/Console.spec",
    "pc_apps/console/ConsolePointset.spec",
    "pc_apps/console/make_release.py",
    "pc_apps/console/README.txt",
    "pc_apps/console/dist/Console.exe",
    "pc_apps/console/dist/Console_Pointset.exe",
    "pc_apps/console/dist/LiDAR_Console.zip",
    "docs/human_fall/WORKFLOW.md",
    "docs/human_fall/REVIEW_LOG.md",
    "docs/human_fall/returns/HF-CONSOLE-02.md",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/ACCEPTANCE_V1.md",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/FINAL_REPORT.md",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/SOURCE_STARTUP.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/POINTSET_FROZEN_STARTUP.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/BROWSER_CHECK_FINAL.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/PACKAGED_VERIFICATION_FINAL.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/SHORTCUT_FINAL.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/PRE_EDIT_STATE.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/POINTSET_PREBUILD_STATE.json",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/CONSOLE_HOME_FINAL.png",
    "docs/human_fall/evidence/2026-10-14_hf_console_02_r1/CONSOLE_REAL_FALL_FINAL.png",
]
files = {}
for rel in relative_files:
    path = ROOT / rel
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    files[rel] = {"size": path.stat().st_size, "sha256": digest}
for path in sorted((OUT / "originals").iterdir()):
    if path.is_file():
        rel = path.relative_to(ROOT).as_posix()
        files[rel] = {"size": path.stat().st_size,
                      "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
shortcut = Path(r"C:\Users\30680\Desktop\总控制台.lnk")
files["C:/Users/30680/Desktop/总控制台.lnk"] = {
    "size": shortcut.stat().st_size,
    "sha256": hashlib.sha256(shortcut.read_bytes()).hexdigest(),
}
payload = {
    "branch": subprocess.check_output(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=ROOT, text=True).strip(),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "git_writes": "none",
    "shortcut_target": "D:/Code/ldiar/pc_apps/console/dist/Console_Pointset.exe (properties unchanged)",
    "files": files,
}
with (OUT / "FINAL_SHA.json").open("x", encoding="utf-8") as stream:
    json.dump(payload, stream, ensure_ascii=False, indent=2)
print(json.dumps({"branch": payload["branch"], "head": payload["head"],
                  "recorded_files": len(files),
                  "pointset_exe_sha256": files["pc_apps/console/dist/Console_Pointset.exe"]["sha256"],
                  "zip_sha256": files["pc_apps/console/dist/LiDAR_Console.zip"]["sha256"]},
                 ensure_ascii=False))
