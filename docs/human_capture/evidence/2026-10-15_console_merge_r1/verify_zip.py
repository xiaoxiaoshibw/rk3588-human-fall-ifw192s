# -*- coding: utf-8 -*-
"""打包复验：make_release.FILES 全量成员 vs 仓库当前文件 sha256 对账（2026-10-15 console merge）。

只读：读 dist/LiDAR_Console.zip 与 FILES 指向的仓库文件，不写任何产物。
"""
import hashlib
import os
import sys
import zipfile

CONSOLE = r'D:\Code\ldiar\pc_apps\console'
sys.path.insert(0, CONSOLE)
import make_release as MR  # noqa: E402

zip_path = os.path.join(MR.HERE, 'dist', 'LiDAR_Console.zip')
with zipfile.ZipFile(zip_path) as z:
    names = z.namelist()
    mismatch = []
    for name, src in sorted(MR.FILES.items()):
        want = open(os.path.join(MR.HERE, src), 'rb').read()
        if hashlib.sha256(z.read(name)).digest() != hashlib.sha256(want).digest():
            mismatch.append(name)
    pointset = [n for n in names if 'pointset' in n.lower()]
    size = os.path.getsize(zip_path)
    sha = hashlib.sha256(open(zip_path, 'rb').read()).hexdigest()

print('zip:', zip_path)
print('members:', len(names), 'files_checked:', len(MR.FILES))
print('mismatch:', mismatch)
print('pointset_entries:', pointset)
print('bytes:', size)
print('sha256:', sha)
print('VERDICT:', 'PASS' if not mismatch and not pointset else 'FAIL')
