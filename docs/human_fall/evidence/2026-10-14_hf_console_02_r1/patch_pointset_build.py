import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
state = json.loads((OUT / "POINTSET_PREBUILD_STATE.json").read_text(encoding="utf-8-sig"))
spec = ROOT / "pc_apps/console/ConsolePointset.spec"
release_script = ROOT / "pc_apps/console/make_release.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def read(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


build = read(spec)
assert build.count("('console_icon.png', '.')") == 1
build = build.replace("('console_icon.png', '.')", "('console_icon.ico', '.')", 1)
release = read(release_script)
old = '    "LiDAR_Console/Console.exe": "dist/Console.exe",'
new = old + '\n    "LiDAR_Console/Console_Pointset.exe": "dist/Console_Pointset.exe",'
assert release.count(old) == 1
release = release.replace(old, new, 1)

expected = state["sha256"]
assert sha(spec) == expected["pointset_spec"]
assert sha(release_script) == expected["make_release"]
updates = {
    spec: build.encode("utf-8").replace(b"\n", b"\r\n"),
    release_script: release.encode("utf-8").replace(b"\n", b"\r\n"),
}
temps = {}
for path, data in updates.items():
    temp = path.with_name(path.name + ".hf-console-02.tmp")
    if temp.exists():
        raise FileExistsError(str(temp))
    temp.write_bytes(data)
    temps[path] = temp
for path, temp in temps.items():
    os.replace(str(temp), str(path))
print(json.dumps({str(path.relative_to(ROOT)): sha(path) for path in updates}, indent=2))
