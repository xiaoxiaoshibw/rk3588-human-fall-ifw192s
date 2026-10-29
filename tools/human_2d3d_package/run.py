"""包入口：把包目录放到 sys.path 后转交 cli，不依赖仓库其余部分。"""
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parent
if str(PACKAGE) not in sys.path:
    sys.path.insert(0, str(PACKAGE))

from cli import main

if __name__ == '__main__':
    sys.exit(main())