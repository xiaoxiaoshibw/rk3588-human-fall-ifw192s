import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
state = json.loads((OUT / "PRE_EDIT_STATE.json").read_text(encoding="utf-8"))
gui_hashes = state["current_overlay"]
html = ROOT / "pc_apps/console/console.html"
spec = ROOT / "pc_apps/console/Console.spec"
expected_html = "72bfb7d6cf9e7630d74aa9275e152982e13a345821148987a172692379507640"
expected_spec = gui_hashes["pc_apps/console/Console.spec"]["sha256"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


page = read(html)
old = '<link rel="icon" href="console_icon.png" type="image/png">'
new = '<link rel="icon" href="console_icon.ico" type="image/x-icon">'
assert page.count(old) == 1
page = page.replace(old, new, 1)
build = read(spec)
old = "('console_icon.png', '.')"
new = "('console_icon.ico', '.')"
assert build.count(old) == 1
build = build.replace(old, new, 1)

assert sha(html) == expected_html
assert sha(spec) == expected_spec
updates = {html: page.encode("utf-8").replace(b"\n", b"\r\n"),
           spec: build.encode("utf-8").replace(b"\n", b"\r\n")}
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
