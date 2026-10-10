# -*- coding: utf-8 -*-
"""离线核验 Console.exe 内嵌副本的板端 IP（不启动 GUI）。

用法: python probe_embedded.py <Console.exe>
判定: console.html 与内嵌 human_replay/config.py 均含新 IP 且不含旧 IP → PASS(exit 0)
"""
import sys

from PyInstaller.archive.readers import CArchiveReader

NEW_IP = "192.168.31.58"
OLD_IP = "192.168.3.125"
WANTED = (("console.html", "console.html"),
          ("human_replay/config.py", "config.py"))


def find_name(toc, suffix):
    for name in toc:
        if name.replace("\\", "/").endswith(suffix):
            return name
    raise SystemExit("not found in exe toc: " + suffix)


def main():
    exe = sys.argv[1]
    arc = CArchiveReader(exe)
    ok = True
    for label, suffix in WANTED:
        name = find_name(arc.toc, suffix)
        blob = arc.extract(name)
        if isinstance(blob, str):
            blob = blob.encode("utf-8")
        text = blob.decode("utf-8", "replace")
        new, old = NEW_IP in text, OLD_IP in text
        print("%s (%s): len=%d new_ip=%s old_ip=%s" % (label, name, len(blob), new, old))
        ok = ok and new and not old
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
