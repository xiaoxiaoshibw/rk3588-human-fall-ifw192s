import hashlib
import json
from pathlib import Path
import zipfile

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CONSOLE = ROOT / "pc_apps/console"
EXE = CONSOLE / "dist/Console.exe"
RELEASE = CONSOLE / "dist/LiDAR_Console.zip"


def sha_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


archive = CArchiveReader(str(EXE))
embedded_html = archive.extract("console.html")
embedded_ico = archive.extract("console_icon.ico")
source_html = (CONSOLE / "console.html").read_bytes()
with zipfile.ZipFile(RELEASE, "r") as package:
    bad_member = package.testzip()
    members = set(package.namelist())
    exe_member = sha_stream(package.open("LiDAR_Console/Console.exe"))
    html_member = package.read("LiDAR_Console/源码/console.html")
    spec_member = package.read("LiDAR_Console/源码/Console.spec")

result = {
    "exe_sha256": hashlib.sha256(EXE.read_bytes()).hexdigest(),
    "zip_sha256": hashlib.sha256(RELEASE.read_bytes()).hexdigest(),
    "embedded_console_html_matches_source": embedded_html == source_html,
    "embedded_icon_present": bool(embedded_ico),
    "zip_integrity_error": bad_member,
    "zip_contains_current_exe": exe_member == hashlib.sha256(EXE.read_bytes()).hexdigest(),
    "zip_contains_current_console_html": html_member == source_html,
    "zip_contains_current_spec": spec_member == (CONSOLE / "Console.spec").read_bytes(),
    "zip_contains_console_icon": "LiDAR_Console/console_icon.ico" in members,
    "zip_member_count": len(members),
}
result["ok"] = all((
    result["embedded_console_html_matches_source"],
    result["embedded_icon_present"],
    result["zip_integrity_error"] is None,
    result["zip_contains_current_exe"],
    result["zip_contains_current_console_html"],
    result["zip_contains_current_spec"],
    result["zip_contains_console_icon"],
))
with (OUT / "PACKAGED_VERIFICATION.json").open("x", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
assert result["ok"], result
print(json.dumps(result, ensure_ascii=False, indent=2))
