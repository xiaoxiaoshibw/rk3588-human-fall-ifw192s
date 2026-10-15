import hashlib
import json
from pathlib import Path
import zipfile

from PyInstaller.archive.readers import CArchiveReader

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
CONSOLE = ROOT / "pc_apps/console"
DIST = CONSOLE / "dist"
SOURCES = {
    "console_html": CONSOLE / "console.html",
    "readme": CONSOLE / "README.txt",
    "generic_spec": CONSOLE / "Console.spec",
    "pointset_spec": CONSOLE / "ConsolePointset.spec",
    "release_script": CONSOLE / "make_release.py",
}
EXES = {"Console.exe": DIST / "Console.exe", "Console_Pointset.exe": DIST / "Console_Pointset.exe"}


def sha_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha_stream(stream):
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


source_html = SOURCES["console_html"].read_bytes()
embedded = {}
for name, path in EXES.items():
    archive = CArchiveReader(str(path))
    embedded[name] = {
        "html_matches_source": archive.extract("console.html") == source_html,
        "icon_present": bool(archive.extract("console_icon.ico")),
        "sha256": sha_file(path),
    }

release = DIST / "LiDAR_Console.zip"
with zipfile.ZipFile(release, "r") as package:
    bad_member = package.testzip()
    names = set(package.namelist())
    member_checks = {
        "exe_console": sha_stream(package.open("LiDAR_Console/Console.exe")) == sha_file(EXES["Console.exe"]),
        "exe_pointset": sha_stream(package.open("LiDAR_Console/Console_Pointset.exe")) == sha_file(EXES["Console_Pointset.exe"]),
        "console_html": package.read("LiDAR_Console/源码/console.html") == source_html,
        "readme": package.read("LiDAR_Console/README.txt") == SOURCES["readme"].read_bytes(),
        "generic_spec": package.read("LiDAR_Console/源码/Console.spec") == SOURCES["generic_spec"].read_bytes(),
        "pointset_spec": package.read("LiDAR_Console/源码/ConsolePointset.spec") == SOURCES["pointset_spec"].read_bytes(),
        "release_script": package.read("LiDAR_Console/源码/make_release.py") == SOURCES["release_script"].read_bytes(),
    }

result = {
    "generic_exe": embedded["Console.exe"],
    "shortcut_target_exe": embedded["Console_Pointset.exe"],
    "zip_sha256": sha_file(release),
    "zip_integrity_error": bad_member,
    "zip_member_checks": member_checks,
    "zip_contains_icon": "LiDAR_Console/console_icon.ico" in names,
    "zip_member_count": len(names),
}
result["ok"] = (
    all(entry["html_matches_source"] and entry["icon_present"] for entry in embedded.values())
    and bad_member is None and all(member_checks.values())
    and result["zip_contains_icon"]
)
with (OUT / "PACKAGED_VERIFICATION_FINAL.json").open("x", encoding="utf-8") as stream:
    json.dump(result, stream, ensure_ascii=False, indent=2)
assert result["ok"], result
print(json.dumps(result, ensure_ascii=False, indent=2))
